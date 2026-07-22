#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


CANVASS_URL = (
    "https://en.wikipedia.org/w/index.php?title="
    "Congressional_canvass_for_the_2022_Philippine_presidential_election&oldid=1353912853"
)
HOUSE_SOURCE_URL = "https://www.congress.gov.ph/index.php/media/photojournal/3000"
BOUNDARY_URL = (
    "https://ulap-nga.georisk.gov.ph/arcgis/rest/services/PSA/Municipal/MapServer/0/query"
)

OFFICES = {
    "president": (
        ("Marcos", "Bongbong Marcos", "Marcos", "Partido Federal ng Pilipinas", 31_629_783),
        ("Robredo", "Leni Robredo", "Robredo", "Independent", 15_035_773),
        ("Pacquiao", "Manny Pacquiao", "Pacquiao", "PROMDI", 3_663_113),
        ("Moreno", "Isko Moreno", "Moreno", "Aksyon Demokratiko", 1_933_909),
        ("Lacson", "Panfilo Lacson", "Lacson", "Independent", 892_375),
        ("Mangondato", "Faisal Mangondato", "Mangondato", "Katipunan ng Kamalayang Kayumanggi", 301_629),
        ("Abella", "Ernesto Abella", "Abella", "Independent", 114_627),
        ("De Guzman", "Leody de Guzman", "De Guzman", "Partido Lakas ng Masa", 93_027),
        ("Gonzales", "Norberto Gonzales", "Gonzales", "Partido Demokratiko Sosyalista ng Pilipinas", 90_656),
        ("Montemayor", "Jose Montemayor Jr.", "Montemayor", "Democratic Party of the Philippines", 60_592),
    ),
    "vice_president": (
        ("Duterte", "Sara Duterte", "Duterte", "Lakas–CMD", 32_208_417),
        ("Pangilinan", "Kiko Pangilinan", "Pangilinan", "Liberal Party", 9_329_207),
        ("Sotto", "Tito Sotto", "Sotto", "Nationalist People's Coalition", 8_251_267),
        ("Ong", "Willie Ong", "Ong", "Aksyon Demokratiko", 1_878_531),
        ("Atienza", "Lito Atienza", "Atienza", "PROMDI", 270_381),
        ("Lopez", "Manny SD Lopez", "Lopez", "Labor Party Philippines", 159_670),
        ("Bello", "Walden Bello", "Bello", "Partido Lakas ng Masa", 100_827),
        ("Serapio", "Carlos Serapio", "Serapio", "Katipunan ng Kamalayang Kayumanggi", 90_989),
        ("David", "Rizalito David", "David", "Democratic Party of the Philippines", 56_711),
    ),
}

# The pinned COC detail transcription does not arithmetically reconcile to the
# adopted Resolution of Both Houses No. 1 for these minor candidates. The map
# preserves the published local COC figures; national percentages use the
# resolution totals above. This exact check prevents the discrepancy growing or
# changing silently if the upstream table is edited.
DETAIL_DELTAS = {
    "president": (0, 0, 0, 0, 0, 1, 1, 1, 1, 1),
    "vice_president": (0, 0, 0, 0, 0, 0, 0, 1, 1_731),
}

CSV_FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

# These cities were separate domestic certificates of canvass. Other highly urbanized
# cities in the PSA layer were included in their surrounding province's COC in the
# congressional table.
CITY_RESULT_UNITS = {
    "Bacolod City": "Bacolod",
    "Baguio City": "Baguio",
    "Cagayan de Oro City": "Cagayan de Oro",
    "Caloocan City": "Caloocan",
    "Cebu City": "Cebu City",
    "Davao City": "Davao City",
    "General Santos City": "General Santos",
    "Iligan City": "Iligan",
    "Iloilo City": "Iloilo City",
    "Lapu-Lapu City": "Lapu-Lapu City",
    "City of Las Piñas": "Las Piñas",
    "City of Makati": "Makati",
    "City of Malabon": "Malabon",
    "City of Mandaluyong": "Mandaluyong",
    "City of Marikina": "Marikina",
    "City of Muntinlupa": "Muntinlupa",
    "City of Navotas": "Navotas",
    "City of Parañaque": "Parañaque",
    "Pasay City": "Pasay",
    "City of Pasig": "Pasig",
    "Quezon City": "Quezon City",
    "City of San Juan": "San Juan",
    "City of Valenzuela": "Valenzuela",
    "Zamboanga City": "Zamboanga City",
}

PROVINCE_ALIASES = {
    "Compostela Valley": "Davao de Oro",
    "City of Isabela": "Basilan",
    "Cotabato City": "Maguindanao",
}

REGION_ALIASES = {
    "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)": "BARMM",
    "Cordillera Administrative Region (CAR)": "CAR",
    "National Capital Region (NCR)": "NCR",
}

SGA_NOTE = (
    "The Special Geographic Area COC is combined with Cotabato for this map because its "
    "63 constituent barangays cannot be separated from the official municipal geometry."
)


def download(session: requests.Session, url: str, path: Path, *, refresh: bool, params=None) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(url, params=params, timeout=180)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def parse_int(value: str) -> int:
    cleaned = clean_text(value).replace(",", "")
    return 0 if cleaned in {"—", "–", "-", ""} else int(cleaned)


def find_detail_table(soup: BeautifulSoup, office: str):
    expected = [candidate[0] for candidate in OFFICES[office]]
    for table in soup.select("table.wikitable"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headings = [clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
        if headings and headings[0] == "Province / City / Absentee voters" and headings[1:] == expected:
            return table
    raise SystemExit(f"Could not find the {office} COC detail table")


def parse_canvass(path: Path, office: str) -> dict[str, tuple[int, ...]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    table = find_detail_table(soup, office)
    candidate_count = len(OFFICES[office])
    output: dict[str, tuple[int, ...]] = {}
    for row in table.find_all("tr")[3:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        name = clean_text(cells[0].get_text(" ", strip=True))
        if name == "Total":
            break
        if len(cells) != 1 + candidate_count * 2:
            continue
        output[name] = tuple(parse_int(cells[1 + index * 2].get_text(" ", strip=True)) for index in range(candidate_count))
    if "Special Geographic Area" not in output or "Local absentee voters" not in output:
        raise SystemExit(f"{office}: expected domestic and absentee COC rows were not parsed")
    national = tuple(sum(votes[index] for votes in output.values()) for index in range(candidate_count))
    expected = tuple(candidate[4] for candidate in OFFICES[office])
    delta = tuple(actual - certified for actual, certified in zip(national, expected))
    if delta != DETAIL_DELTAS[office]:
        raise SystemExit(
            f"{office}: COC detail/certified-total delta changed to {delta}; "
            f"expected the documented {DETAIL_DELTAS[office]}"
        )
    return output


def feature_result_unit(properties: dict[str, object]) -> str:
    city = clean_text(str(properties.get("city_name") or ""))
    province = clean_text(str(properties.get("prov_name") or ""))
    if city.startswith("City of Manila -"):
        return "Manila"
    if city in CITY_RESULT_UNITS:
        return CITY_RESULT_UNITS[city]
    if city in {"Taguig City", "Pateros"}:
        return "Taguig – Pateros"
    return PROVINCE_ALIASES.get(province, province)


def region_label(raw: object) -> str:
    value = clean_text(str(raw or ""))
    return REGION_ALIASES.get(value, value)


def build_boundaries(
    source_path: Path,
    result_names: set[str],
    output_path: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    geometries: dict[str, list[object]] = defaultdict(list)
    regions: dict[str, list[str]] = defaultdict(list)
    for feature in source.get("features", []):
        properties = feature.get("properties") or {}
        district = feature_result_unit(properties)
        geometry = shape(feature.get("geometry"))
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{district}: invalid municipal source geometry")
        geometries[district].append(geometry)
        regions[district].append(region_label(properties.get("reg_name")))

    actual = set(geometries)
    if actual != result_names:
        raise SystemExit(
            f"Boundary/result mismatch; missing boundaries={sorted(result_names - actual)}, "
            f"unexpected boundary groups={sorted(actual - result_names)}"
        )

    codes = {district: f"PH2022-{index:03d}" for index, district in enumerate(sorted(result_names), 1)}
    area_regions = {district: Counter(regions[district]).most_common(1)[0][0] for district in result_names}
    features = []
    for district in sorted(result_names):
        geometry = unary_union(geometries[district])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        geometry = geometry.simplify(0.003, preserve_topology=True)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{district}: invalid dissolved geometry")
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "constituency_code": codes[district],
                "electorate_type": area_regions[district],
            },
            "geometry": mapping(geometry),
        })
    output_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return codes, area_regions


def mapped_results(raw: dict[str, tuple[int, ...]]) -> dict[str, tuple[int, ...]]:
    names = list(raw)
    domestic_end = names.index("Special Geographic Area")
    output = {name: raw[name] for name in names[:domestic_end]}
    sga = raw["Special Geographic Area"]
    output["Cotabato"] = tuple(a + b for a, b in zip(output["Cotabato"], sga))
    return output


def write_csv(
    office: str,
    results: dict[str, tuple[int, ...]],
    codes: dict[str, str],
    regions: dict[str, str],
    output_path: Path,
) -> None:
    candidates = OFFICES[office]
    rows = []
    for district in sorted(results):
        votes = results[district]
        order = sorted(range(len(votes)), key=lambda index: (-votes[index], candidates[index][1]))
        winner, runner_up = order[:2]
        formal = sum(votes)
        note = SGA_NOTE if district == "Cotabato" else ""
        common = {
            "district": district,
            "district_url": CANVASS_URL,
            "distribution_url": HOUSE_SOURCE_URL,
            "elected_member": candidates[winner][1],
            "elected_party": candidates[winner][2],
            "enrolment": 0,
            "formal_votes": formal,
            "informal_votes": 0,
            "total_votes": formal,
            "turnout_pct": 0,
            "majority": votes[winner] - votes[runner_up],
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": regions[district],
            "constituency_code": codes[district],
            "contest_status": "official",
            "result_note": note,
        }
        for index, (_, candidate, label, _, _) in enumerate(candidates):
            rows.append({**common, "candidate": candidate, "candidate_party": label, "votes": votes[index]})

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Philippines 2022 president and vice-president map data")
    parser.add_argument("--source-dir", type=Path, default=Path("tmp/philippines_2022"))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "vic-election-explorer/1.0"})
    canvass_path = download(session, CANVASS_URL, args.source_dir / "congressional_canvass.html", refresh=args.refresh)
    boundary_path = download(
        session,
        BOUNDARY_URL,
        args.source_dir / "psa_municipal_boundaries.geojson",
        refresh=args.refresh,
        params={
            "where": "1=1",
            "outFields": "reg_name,prov_name,city_name,class,psgc_10d",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "geometryPrecision": "5",
            "maxAllowableOffset": "0.002",
        },
    )

    raw_results = {office: parse_canvass(canvass_path, office) for office in OFFICES}
    results = {office: mapped_results(rows) for office, rows in raw_results.items()}
    if set(results["president"]) != set(results["vice_president"]):
        raise SystemExit("President and vice-president mapped areas do not match")
    if len(results["president"]) != 107:
        raise SystemExit(f"Expected 107 domestic map areas, found {len(results['president'])}")

    args.out.mkdir(parents=True, exist_ok=True)
    codes, regions = build_boundaries(
        boundary_path,
        set(results["president"]),
        args.out / "philippines_2022_coc_boundaries.geojson",
    )
    write_csv("president", results["president"], codes, regions, args.out / "philippines_2022_president_fpp.csv")
    write_csv(
        "vice_president",
        results["vice_president"],
        codes,
        regions,
        args.out / "philippines_2022_vice_president_fpp.csv",
    )
    print("Built Philippines 2022: 107 mapped COC areas, 10 presidential candidates, 9 vice-presidential candidates")


if __name__ == "__main__":
    main()
