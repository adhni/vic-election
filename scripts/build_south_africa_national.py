#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


RESULT_URLS = {
    2024: "https://results.elections.org.za/home/NPEPublicReports/1334/National%20Ballot/Downloadable%20Results/National.zip",
    2019: "https://www.elections.org.za/content/NPEPublicReports/699/Downloadable%20Results/National.zip",
    2014: "https://www.elections.org.za/content/Elections/Downloadable-results/2014-National-and-Provincial-Elections--Complete-voting-district-level-results-data-(zipped-CSV)/",
}
SOURCE_PAGES = {
    2024: "https://results.elections.org.za/home/NPEPublicReports/1334/National/Results",
    2019: "https://results.elections.org.za/home/NPEPublicReports/699/National/Results",
    2014: "https://results.elections.org.za/home/NPEPublicReports/291/National/Results",
}
RESULT_SHA256 = {
    2024: "da7afa029ee24e2a8cf19c6611922e24f06cfedbb7258956d92eb7deb30fa577",
    2019: "8d3e8a3c408297327b375b0f5d3ae3b5ddb99b8db1d9bb10a0c4058afbb843f0",
    2014: "5a70e4d56646e7521b184457740f7c07e5be0ca22035b6143292052176974bfe",
}
BOUNDARY_URLS = {
    2011: (
        "https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/"
        "MDB_Local_Municipal_Boundary_2011/FeatureServer/0/query?where=1%3D1&"
        "outFields=ProvinceCode%2CProvinceName%2CLocalMunicipalityCode%2C"
        "LocalMunicipalityName&returnGeometry=true&outSR=4326&f=geojson"
    ),
    2016: (
        "https://services7.arcgis.com/oeoyTUJC8HEeYsRB/arcgis/rest/services/"
        "MDB_Local_Municipal_Boundary_2016/FeatureServer/0/query?where=1%3D1&"
        "outFields=ProvinceCode%2CProvinceName%2CLocalMunicipalityCode%2C"
        "LocalMunicipalityName&returnGeometry=true&outSR=4326&f=geojson"
    ),
}
BOUNDARY_SHA256 = {
    2011: "5e0d251f80e186ebddea9ceed76b5dfd2d4b2c2eb01c69e918157f3c3ae905e3",
    2016: "e1758b48d4eb55f555e636b212f8dca57cb7a58a9723bc978655a95e06282dd3",
}
EXPECTED_AREAS = {2024: 213, 2019: 213, 2014: 234}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note", "district_seats",
)

PARTY_NAMES = {
    "AFRICAN NATIONAL CONGRESS": "ANC",
    "DEMOCRATIC ALLIANCE": "DA",
    "ECONOMIC FREEDOM FIGHTERS": "EFF",
    "UMKHONTO WESIZWE": "MK",
    "INKATHA FREEDOM PARTY": "IFP",
    "PATRIOTIC ALLIANCE": "PA",
    "VRYHEIDSFRONT PLUS": "FF+",
    "ACTIONSA": "ActionSA",
    "AFRICAN CHRISTIAN DEMOCRATIC PARTY": "ACDP",
    "UNITED DEMOCRATIC MOVEMENT": "UDM",
    "AFRICAN TRANSFORMATION MOVEMENT": "ATM",
    "AL JAMA-AH": "Al Jama-ah",
    "BUILD ONE SOUTH AFRICA WITH MMUSI MAIMANE": "BOSA",
    "NATIONAL COLOURED CONGRESS": "NCC",
    "PAN AFRICANIST CONGRESS OF AZANIA": "PAC",
    "RISE MZANSI": "RISE Mzansi",
    "AFRICAN INDEPENDENT CONGRESS": "AIC",
    "CONGRESS OF THE PEOPLE": "COPE",
    "NATIONAL FREEDOM PARTY": "NFP",
    "GOOD": "GOOD",
    "AGANG SOUTH AFRICA": "Agang SA",
    "AFRICAN PEOPLE'S CONVENTION": "APC",
}


def integer(value: object) -> int:
    text = str(value or "").strip().replace(" ", "").replace(",", "")
    return int(float(text)) if text else 0


def party_name(value: str) -> str:
    normalized = " ".join(value.strip().upper().split())
    return PARTY_NAMES.get(normalized, normalized.title())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(path: Path, expected: str) -> None:
    actual = digest(path)
    print(f"{path.name} SHA256: {actual}")
    if actual != expected:
        raise SystemExit(f"{path}: checksum changed; expected {expected}, found {actual}")


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size > 1_000 and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)
    return path


def parse_result_row(year: int, values: list[str], header: list[str]) -> dict[str, object] | None:
    if year == 2019:
        # IEC's file leaves commas in some voting-station names unquoted. Parse the
        # stable columns from both ends instead of silently shifting vote fields.
        if len(values) < 10:
            return None
        province, municipality, vd = values[:3]
        registered, spoilt, formal, party, votes = values[-6:-1]
        return {
            "province": province, "municipality": municipality, "vd": vd,
            "registered": integer(registered), "spoilt": integer(spoilt),
            "formal": integer(formal), "party": party, "votes": integer(votes),
        }
    if len(values) < len(header):
        return None
    row = dict(zip(header, values))
    if year == 2024:
        return {
            "province": row["Province"], "municipality": row["Municipality"],
            "vd": row["VD_Number"], "registered": integer(row["Registered_Population"]),
            "spoilt": integer(row["Spoilt_Votes"]), "formal": integer(row["Total_Valid_Votes"]),
            "party": row["sPartyName"], "votes": integer(row["Party_Votes"]),
        }
    total = integer(row["TOTAL VOTES CAST"])
    spoilt = integer(row["SPOILT VOTES"])
    return {
        "province": row["PROVINCE"], "municipality": row["MUNICIPALITY"],
        "vd": row["VOTING DISTRICT"], "registered": integer(row["REGISTERED VOTERS"]),
        "spoilt": spoilt, "formal": total - spoilt,
        "party": row["PARTY NAME"], "votes": integer(row["VALID VOTES"]),
        "event": row["ELECTORAL EVENT"],
    }


def read_results(path: Path, year: int) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    areas: dict[str, dict[str, object]] = {}
    vd_metadata: dict[str, tuple[str, int, int, int]] = {}
    vd_party_totals: defaultdict[str, int] = defaultdict(int)
    encoding = "utf-8-sig" if year == 2024 else "latin-1"
    with zipfile.ZipFile(path) as bundle:
        member = next(name for name in bundle.namelist() if name.lower().endswith(".csv"))
        with bundle.open(member) as raw, io.TextIOWrapper(raw, encoding=encoding, newline="") as text:
            reader = csv.reader(text)
            header = [column.lstrip("\ufeff").strip() for column in next(reader)]
            for values in reader:
                parsed = parse_result_row(year, values, header)
                if year == 2014 and parsed and "NATIONAL" not in str(parsed.get("event", "")).upper():
                    continue
                if not parsed or str(parsed["province"]).strip().upper().startswith("OUT OF COUNTRY"):
                    continue
                municipality = str(parsed["municipality"]).strip()
                if " - " not in municipality or not str(parsed["party"]).strip():
                    continue
                code, source_name = municipality.split(" - ", 1)
                code = code.strip().upper()
                vd = str(parsed["vd"]).strip()
                metadata = (code, int(parsed["registered"]), int(parsed["formal"]), int(parsed["spoilt"]))
                if vd in vd_metadata and vd_metadata[vd] != metadata:
                    raise SystemExit(f"South Africa {year} VD {vd}: inconsistent repeated metadata")
                vd_metadata[vd] = metadata
                vd_party_totals[vd] += int(parsed["votes"])
                area = areas.setdefault(code, {
                    "source_name": source_name.strip().title(),
                    "province": str(parsed["province"]).strip().title(),
                    "votes": defaultdict(int), "vds": set(),
                })
                area["votes"][party_name(str(parsed["party"]))] += int(parsed["votes"])
                area["vds"].add(vd)

    for vd, (_, _, formal, _) in vd_metadata.items():
        if vd_party_totals[vd] != formal:
            raise SystemExit(
                f"South Africa {year} VD {vd}: party votes {vd_party_totals[vd]} != valid votes {formal}"
            )
    for code, area in areas.items():
        vds = area.pop("vds")
        area["enrolment"] = sum(vd_metadata[vd][1] for vd in vds)
        area["formal"] = sum(vd_metadata[vd][2] for vd in vds)
        area["informal"] = sum(vd_metadata[vd][3] for vd in vds)
        if sum(area["votes"].values()) != area["formal"]:
            raise SystemExit(f"South Africa {year} {code}: municipality votes do not reconcile")
    if len(areas) != EXPECTED_AREAS[year]:
        raise SystemExit(f"South Africa {year}: expected {EXPECTED_AREAS[year]} municipalities, found {len(areas)}")
    return areas, {vd: metadata[0] for vd, metadata in vd_metadata.items()}


def round_coordinates(value: object) -> object:
    if isinstance(value, float):
        return round(value, 5)
    if isinstance(value, list):
        return [round_coordinates(item) for item in value]
    if isinstance(value, dict):
        return {key: round_coordinates(item) for key, item in value.items()}
    return value


def load_boundaries(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    geometries: dict[str, dict[str, object]] = {}
    properties: dict[str, dict[str, str]] = {}
    for feature in raw["features"]:
        props = feature["properties"]
        code = str(props["LocalMunicipalityCode"]).upper()
        geom = shape(feature["geometry"])
        geometries[code] = mapping(geom)
        properties[code] = {
            "name": str(props["LocalMunicipalityName"]),
            "province_code": str(props["ProvinceCode"]),
            "province_name": str(props["ProvinceName"]),
        }
    return geometries, properties


def simplified_geometry(geometry: dict[str, object]) -> dict[str, object]:
    geom = shape(geometry).simplify(0.004, preserve_topology=True)
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty or not geom.is_valid:
        raise SystemExit("Boundary simplification produced invalid geometry")
    return round_coordinates(mapping(geom))


def write_geojson(path: Path, features: list[dict[str, object]]) -> None:
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_boundaries(
    year: int,
    geometries: dict[str, dict[str, object]],
    properties: dict[str, dict[str, str]],
    result_codes: set[str],
    output_dir: Path,
) -> None:
    boundary_codes = set(geometries)
    if boundary_codes != result_codes:
        raise SystemExit(
            f"South Africa {year}: result/boundary mismatch; results-only={sorted(result_codes-boundary_codes)}, "
            f"boundaries-only={sorted(boundary_codes-result_codes)}"
        )
    features = []
    name_counts = Counter(properties[code]["name"] for code in result_codes)
    for code in sorted(result_codes):
        props = properties[code]
        district = props["name"]
        if name_counts[district] > 1:
            district = f"{district} ({props['province_name']})"
        features.append({
            "type": "Feature",
            "properties": {
                "constituency_code": code, "district": district,
                "province_code": props["province_code"], "province": props["province_name"],
            },
            "geometry": simplified_geometry(geometries[code]),
        })
    vintage = 2011 if year == 2014 else 2016
    write_geojson(output_dir / f"south_africa_{vintage}_municipality_boundaries.geojson", features)


def province_boundaries(
    geometries: dict[str, dict[str, object]], properties: dict[str, dict[str, str]], output_dir: Path
) -> None:
    grouped: defaultdict[str, list[object]] = defaultdict(list)
    names: dict[str, str] = {}
    for code, geometry in geometries.items():
        province_code = properties[code]["province_code"]
        names[province_code] = properties[code]["province_name"]
        grouped[province_code].append(shape(geometry))
    features = []
    for code in sorted(grouped):
        features.append({
            "type": "Feature",
            "properties": {"constituency_code": f"ZA-{code}", "district": names[code]},
            "geometry": simplified_geometry(mapping(unary_union(grouped[code]))),
        })
    if len(features) != 9:
        raise SystemExit("South Africa: expected nine province boundaries")
    write_geojson(output_dir / "south_africa_province_boundaries.geojson", features)


def compact_rows(
    district: str, code: str, area: dict[str, object], year: int, geography: str
) -> list[dict[str, object]]:
    votes = area["votes"]
    formal = int(area["formal"])
    informal = int(area["informal"])
    enrolment = int(area["enrolment"])
    total = formal + informal
    winner = max(votes, key=votes.get)
    ballot = "national ballot" if year == 2024 else "National Assembly ballot"
    note = f"{geography.title()} {ballot} totals; National Assembly seats are allocated nationally."
    return [{
        "district": district, "district_url": SOURCE_PAGES[year], "distribution_url": "",
        "elected_member": winner, "elected_party": winner, "enrolment": enrolment,
        "formal_votes": formal, "informal_votes": informal, "total_votes": total,
        "turnout_pct": round(total / enrolment * 100, 2) if enrolment else 0,
        "majority": formal // 2 + 1, "round_number": 0, "row_type": "first",
        "excluded_candidate": "", "excluded_party": "", "candidate": party,
        "candidate_party": party, "votes": count, "electorate_type": geography,
        "constituency_code": code, "contest_status": "official", "result_note": note,
        "district_seats": 0,
    } for party, count in sorted(votes.items(), key=lambda item: (-item[1], item[0])) if count]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_results(
    year: int, areas: dict[str, dict[str, object]], boundary_props: dict[str, dict[str, str]], output_dir: Path
) -> None:
    municipality_rows: list[dict[str, object]] = []
    provinces: dict[str, dict[str, object]] = {}
    name_counts = Counter(boundary_props[code]["name"] for code in areas)
    for code, area in sorted(areas.items()):
        props = boundary_props[code]
        district = props["name"]
        if name_counts[district] > 1:
            district = f"{district} ({props['province_name']})"
        municipality_rows.extend(compact_rows(district, code, area, year, "municipality"))
        province_code = props["province_code"]
        province = provinces.setdefault(province_code, {
            "name": props["province_name"], "votes": defaultdict(int),
            "enrolment": 0, "formal": 0, "informal": 0,
        })
        for party, votes in area["votes"].items():
            province["votes"][party] += votes
        for field in ("enrolment", "formal", "informal"):
            province[field] += int(area[field])
    province_rows: list[dict[str, object]] = []
    for code, area in sorted(provinces.items()):
        province_rows.extend(compact_rows(area["name"], f"ZA-{code}", area, year, "province"))
    write_csv(output_dir / f"south_africa_{year}_national_municipality_fpp.csv", municipality_rows)
    write_csv(output_dir / f"south_africa_{year}_national_province_fpp.csv", province_rows)
    print(
        f"South Africa {year}: wrote {len(municipality_rows)} municipality rows and "
        f"{len(province_rows)} province rows; {sum(a['formal'] for a in areas.values()):,} mapped valid votes"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build South Africa National Assembly local-result views")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/south_africa"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"

    result_paths = {}
    for year, url in RESULT_URLS.items():
        path = download(session, url, args.raw_dir / f"{year}_national.zip", args.refresh)
        require_digest(path, RESULT_SHA256[year])
        result_paths[year] = path
    boundary_sets = {}
    for vintage, url in BOUNDARY_URLS.items():
        path = download(session, url, args.raw_dir / f"mdb_{vintage}.geojson", args.refresh)
        require_digest(path, BOUNDARY_SHA256[vintage])
        boundary_sets[vintage] = load_boundaries(path)

    for year in (2024, 2019, 2014):
        areas, _ = read_results(result_paths[year], year)
        vintage = 2011 if year == 2014 else 2016
        geometries, props = boundary_sets[vintage]
        build_boundaries(year, geometries, props, set(areas), args.output_dir)
        build_results(year, areas, props, args.output_dir)
    province_boundaries(*boundary_sets[2016], args.output_dir)


if __name__ == "__main__":
    main()
