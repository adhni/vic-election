#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import warnings
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import geopandas as gpd
import requests
from shapely import make_valid
from shapely.geometry import MultiPolygon, Polygon, mapping


CEC_ROOT = "https://db.cec.gov.tw/static/elections/data"
BOUNDARY_URL = (
    "https://maps.nlsc.gov.tw/download/"
    "%E9%84%89%E9%8E%AE%E5%B8%82%E5%8D%80%E7%95%8C%E7%B7%9A"
    "(TWD97%E7%B6%93%E7%B7%AF%E5%BA%A6).zip"
)
BOUNDARY_PAGE = "https://data.gov.tw/dataset/7441"
BOUNDARY_CHECKSUM = "e028e5a750eee48cf7913330655e5e5c5bb1f176868fbd0afdfc661fca60557c"
BOUNDARY_MEMBER = "TOWN_MOI_1120317"
FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

COUNTY_ENGLISH = {
    "臺北市": "Taipei City", "新北市": "New Taipei City", "桃園市": "Taoyuan City",
    "臺中市": "Taichung City", "臺南市": "Tainan City", "高雄市": "Kaohsiung City",
    "宜蘭縣": "Yilan County", "新竹縣": "Hsinchu County", "苗栗縣": "Miaoli County",
    "彰化縣": "Changhua County", "南投縣": "Nantou County", "雲林縣": "Yunlin County",
    "嘉義縣": "Chiayi County", "屏東縣": "Pingtung County", "臺東縣": "Taitung County",
    "花蓮縣": "Hualien County", "澎湖縣": "Penghu County", "基隆市": "Keelung City",
    "新竹市": "Hsinchu City", "嘉義市": "Chiayi City", "金門縣": "Kinmen County",
    "連江縣": "Lienchiang County",
}

ELECTIONS = {
    2024: {
        "theme": "4d83db17c1707e3defae5dc4d4e9c800",
        "source_checksum": "b0da39166856d48dde2decf2cbdadb11f4fe3473aa20e1c9bc83f3a0a1bf6cbe",
        "tickets": {
            1: ("Ko Wen-je–Cynthia Wu", "Taiwan People's Party"),
            2: ("Lai Ching-te–Hsiao Bi-khim", "Democratic Progressive Party"),
            3: ("Hou Yu-ih–Jaw Shaw-kong", "Kuomintang"),
        },
        "expected": {
            "Ko Wen-je–Cynthia Wu": 3_690_466,
            "Lai Ching-te–Hsiao Bi-khim": 5_586_019,
            "Hou Yu-ih–Jaw Shaw-kong": 4_671_021,
        },
    },
    2020: {
        "theme": "1f7d9f4f6bfe06fdaf4db7df2ed4d60c",
        "source_checksum": "f67899cd999918a64ec0e78ba77a89af67e796ddcebbb1df7ad55616f4fe31c8",
        "tickets": {
            1: ("James Soong–Sandra Yu", "People First Party"),
            2: ("Han Kuo-yu–Chang San-cheng", "Kuomintang"),
            3: ("Tsai Ing-wen–Lai Ching-te", "Democratic Progressive Party"),
        },
        "expected": {
            "James Soong–Sandra Yu": 608_590,
            "Han Kuo-yu–Chang San-cheng": 5_522_119,
            "Tsai Ing-wen–Lai Ching-te": 8_170_231,
        },
    },
    2016: {
        "theme": "61b4dda0ebac3332203ef3729a9a0ada",
        "source_checksum": "93670677157ae812c23d3938e85cba73efd41ad7b796fdd071aecbe1feb00b08",
        "tickets": {
            1: ("Eric Chu–Jennifer Wang", "Kuomintang"),
            2: ("Tsai Ing-wen–Chen Chien-jen", "Democratic Progressive Party"),
            3: ("James Soong–Hsu Hsin-ying", "People First Party"),
        },
        "expected": {
            "Eric Chu–Jennifer Wang": 3_813_365,
            "Tsai Ing-wen–Chen Chien-jen": 6_894_744,
            "James Soong–Hsu Hsin-ying": 1_576_861,
        },
    },
}


def download(url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: checksum changed to {actual}; expected {expected}")


def cec_url(kind: str, theme: str, level: str, code: str) -> str:
    return f"{CEC_ROOT}/{kind}/ELC/P0/00/{theme}/{level}/{code}.json"


def json_rows(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if len(payload) != 1:
        raise SystemExit(f"{path}: expected one CEC result group")
    return next(iter(payload.values()))


def source_tree_checksum(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fetch_election_sources(
    year: int, config: dict[str, object], cache_dir: Path, refresh: bool
) -> tuple[list[dict[str, object]], dict[str, Path], dict[str, Path]]:
    theme = str(config["theme"])
    year_dir = cache_dir / str(year)
    areas_path = download(
        cec_url("areas", theme, "C", "00_000_00_000_0000"),
        year_dir / "areas.json",
        refresh,
    )
    counties = json_rows(areas_path)
    ticket_paths: dict[str, Path] = {}
    profile_paths: dict[str, Path] = {}
    requests_to_fetch: list[tuple[str, Path]] = []
    for county in counties:
        code = (
            f"{county['prv_code']}_{county['city_code']}_"
            "00_000_0000"
        )
        ticket_path = year_dir / f"tickets_{code}.json"
        profile_path = year_dir / f"profiles_{code}.json"
        ticket_paths[code] = ticket_path
        profile_paths[code] = profile_path
        requests_to_fetch.extend([
            (cec_url("tickets", theme, "D", code), ticket_path),
            (cec_url("profiles", theme, "D", code), profile_path),
        ])

    def fetch(item: tuple[str, Path]) -> Path:
        return download(item[0], item[1], refresh)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, requests_to_fetch))
    source_paths = [areas_path, *ticket_paths.values(), *profile_paths.values()]
    checksum = source_tree_checksum(source_paths, year_dir)
    expected_checksum = str(config["source_checksum"])
    if expected_checksum and checksum != expected_checksum:
        raise SystemExit(
            f"{year}: CEC source bundle changed to {checksum}; expected {expected_checksum}"
        )
    if not expected_checksum:
        print(f"{year} CEC source checksum: {checksum}")
    return counties, ticket_paths, profile_paths


def polygonal_parts(geometry) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    return []


def build_boundaries(source_path: Path, cache_dir: Path, data_dir: Path) -> dict[str, str]:
    require_sha256(source_path, BOUNDARY_CHECKSUM)
    extract_dir = cache_dir / "boundaries"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_path) as archive:
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            member = f"{BOUNDARY_MEMBER}{suffix}"
            target = extract_dir / member
            if not target.exists():
                target.write_bytes(archive.read(member))
    frame = gpd.read_file(extract_dir / f"{BOUNDARY_MEMBER}.shp", encoding="utf-8")
    features = []
    names: dict[str, str] = {}
    for _, row in frame.iterrows():
        code = str(row["TOWNCODE"])
        county = str(row["COUNTYNAME"])
        town = str(row["TOWNNAME"])
        if county not in COUNTY_ENGLISH:
            raise SystemExit(f"Missing English county name for {county}")
        district = f"{row['TOWNENG']}, {COUNTY_ENGLISH[county]}"
        geometry = make_valid(row.geometry)
        # Remove remote uninhabited claimed-island components that would collapse
        # the interactive map extent. All inhabited Taiwan, Penghu, Kinmen and
        # Matsu polygons fall inside this display frame.
        parts = [
            part for part in polygonal_parts(geometry)
            if part.centroid.x >= 117.5 and part.centroid.x <= 122.3
            and part.centroid.y >= 21.5 and part.centroid.y <= 26.6
        ]
        geometry = parts[0] if len(parts) == 1 else MultiPolygon(parts)
        geometry = make_valid(geometry.simplify(0.0015, preserve_topology=True))
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"Invalid boundary geometry for {code}")
        names[code] = district
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "constituency_code": f"TW-{code}",
                "township_code": code,
                "county": COUNTY_ENGLISH[county],
                "township_name_zh": town,
            },
            "geometry": mapping(geometry),
        })
    if len(names) != 368:
        raise SystemExit(f"Expected 368 township boundaries, got {len(names)}")
    output = {"type": "FeatureCollection", "features": sorted(
        features, key=lambda feature: feature["properties"]["township_code"]
    )}
    (data_dir / "taiwan_township_boundaries.geojson").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return names


def build_rows(
    year: int,
    config: dict[str, object],
    counties: list[dict[str, object]],
    ticket_paths: dict[str, Path],
    profile_paths: dict[str, Path],
    boundary_names: dict[str, str],
) -> list[dict[str, object]]:
    tickets = config["tickets"]
    rows: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    seen: set[str] = set()
    source_page = (
        "https://db.cec.gov.tw/ElecTable/Election/ElecTickets"
        f"?dataType=tickets&typeId=ELC&subjectId=P0&legisId=00&themeId={config['theme']}"
        "&dataLevel=C&prvCode=00&cityCode=000&areaCode=00&deptCode=000&liCode=0000"
    )
    for county in counties:
        county_code = (
            f"{county['prv_code']}_{county['city_code']}_"
            "00_000_0000"
        )
        candidate_rows = [
            row for row in json_rows(ticket_paths[county_code])
            if str(row.get("is_vice", "")).strip() != "Y"
        ]
        profile_rows = json_rows(profile_paths[county_code])
        by_code: dict[str, list[dict[str, object]]] = {}
        for row in candidate_rows:
            code = f"{row['prv_code']}{row['city_code']}{row['dept_code']}"
            by_code.setdefault(code, []).append(row)
        for profile in profile_rows:
            code = f"{profile['prv_code']}{profile['city_code']}{profile['dept_code']}"
            if code in seen:
                raise SystemExit(f"{year}: duplicate township {code}")
            seen.add(code)
            if code not in boundary_names:
                raise SystemExit(f"{year}: no boundary for township {code}")
            source_candidates = by_code.get(code, [])
            if len(source_candidates) != len(tickets):
                raise SystemExit(
                    f"{year} {code}: expected {len(tickets)} candidates, "
                    f"got {len(source_candidates)}"
                )
            votes: Counter[tuple[str, str]] = Counter()
            for source in source_candidates:
                number = int(source["cand_no"])
                if number not in tickets:
                    raise SystemExit(f"{year} {code}: unexpected candidate number {number}")
                label, party = tickets[number]
                votes[(label, party)] = int(source["ticket_num"])
            formal = int(profile["valid_ticket"])
            informal = int(profile["invalid_ticket"])
            total = int(profile["vote_ticket"])
            enrolment = int(profile["votable_population"])
            if sum(votes.values()) != formal or formal + informal != total:
                raise SystemExit(f"{year} {code}: CEC ballot arithmetic mismatch")
            ordered = votes.most_common()
            (winner, winner_party), winner_votes = ordered[0]
            runner_up = ordered[1][1]
            base = {
                "district": boundary_names[code],
                "district_url": source_page,
                "distribution_url": BOUNDARY_PAGE,
                "elected_member": winner,
                "elected_party": winner_party,
                "enrolment": enrolment,
                "formal_votes": formal,
                "informal_votes": informal,
                "total_votes": total,
                "turnout_pct": round(total * 100 / enrolment, 2),
                "majority": winner_votes - runner_up,
                "round_number": 0,
                "row_type": "first",
                "excluded_candidate": "",
                "excluded_party": "",
                "electorate_type": "Township / district",
                "constituency_code": f"TW-{code}",
                "contest_status": "official",
                "result_note": (
                    "Official CEC presidential result at township/district level. "
                    "The map shows the local leader; Taiwan elects one president nationally. "
                    "Remote uninhabited claimed-island geometry is omitted from the display."
                ),
            }
            for (candidate, party), candidate_votes in ordered:
                rows.append({
                    **base,
                    "candidate": candidate,
                    "candidate_party": party,
                    "votes": candidate_votes,
                })
                totals[candidate] += candidate_votes
    if seen != set(boundary_names):
        missing = sorted(set(boundary_names) - seen)
        extra = sorted(seen - set(boundary_names))
        raise SystemExit(f"{year}: township mismatch; missing={missing}, extra={extra}")
    if dict(totals) != config["expected"]:
        raise SystemExit(
            f"{year}: national totals changed\nexpected {config['expected']}\n"
            f"actual {dict(totals)}"
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Taiwan 2024, 2020 and 2016 presidential township views."
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/taiwan"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)

    boundary_path = download(
        BOUNDARY_URL, args.cache_dir / "town_boundaries.zip", args.refresh
    )
    boundary_names = build_boundaries(boundary_path, args.cache_dir, args.data_dir)
    for year, config in ELECTIONS.items():
        counties, ticket_paths, profile_paths = fetch_election_sources(
            year, config, args.cache_dir, args.refresh
        )
        rows = build_rows(
            year, config, counties, ticket_paths, profile_paths, boundary_names
        )
        output = args.data_dir / f"taiwan_{year}_president_township_fpp.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"{output.name}: 368 townships/districts, {len(rows)} candidate rows")
    print("Built three Taiwan presidential election views.")


if __name__ == "__main__":
    main()
