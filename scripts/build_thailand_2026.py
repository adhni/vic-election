#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests


DATA_BASE = "https://election69-data.thaipbs.or.th"
ASSET_BASE = "https://election69-assets.thaipbs.or.th/assets"
MASTER_VERSION = "2026-02-08-14-13-57-788"
OFFICIAL_VERSION = "2026-03-18-21-32-25-956"
UNOFFICIAL_VERSION = "2026-02-27-18-35-00-160"
CARTOGRAM_ASSET = "area-view-content-CxLcIqLN.js"
RESULTS_PAGE = "https://www.thaipbs.or.th/election69/result/en/geo/area/{code}?region=all&view=area"

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
]

# The 18 March Thai PBS/ECT snapshot predates the final certification of Suphan Buri 2.
# ECT certified Natthawut Prasoetsuwan on 8 April after the recount. ECT Form 6/1,
# as reproduced by iLaw, gives 45,267 for Prasoetsuwan and 23,277 for Sisangngam;
# the remaining candidate totals come from the final structured results table.
# Post-recount invalid/no-vote totals were not published in the machine feed.
SUPHAN_BURI_2 = {
    "CANDIDATE-MP-720205": 45267,
    "CANDIDATE-MP-720201": 23277,
    "CANDIDATE-MP-720207": 9044,
    "CANDIDATE-MP-720203": 4069,
    "CANDIDATE-MP-720206": 1147,
    "CANDIDATE-MP-720204": 1010,
    "CANDIDATE-MP-720202": 639,
}
SUPHAN_NOTE = (
    "ECT certified this final outstanding seat on 8 April 2026 after a recount. "
    "Candidate totals are final; post-recount turnout and non-candidate ballot metadata were not available in the Thai PBS machine feed."
)


def fetch(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and not refresh:
        return path
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_name(candidate: dict) -> str:
    return " ".join(part for part in (candidate.get("firstName"), candidate.get("lastName")) if part).strip()


def official_detail_url(area_code: str) -> str:
    return f"{DATA_BASE}/result-ect-official-constituency/{OFFICIAL_VERSION}/areas/{area_code}.json"


def download_sources(raw_dir: Path, refresh: bool) -> dict[str, Path]:
    session = requests.Session()
    session.headers["User-Agent"] = "election-preference-explorer/1.0"
    sources = {
        "common": (f"{DATA_BASE}/master-data-en/{MASTER_VERSION}/common-data.json", raw_dir / "common-data.json"),
        "candidates": (f"{DATA_BASE}/master-data-en/{MASTER_VERSION}/candidate-data.json", raw_dir / "candidate-data.json"),
        "parties": (f"{DATA_BASE}/master-data-en/{MASTER_VERSION}/party-data.json", raw_dir / "party-data.json"),
        "official_index": (f"{DATA_BASE}/result-ect-official-constituency/{OFFICIAL_VERSION}/index.json", raw_dir / "official-index.json"),
        "unofficial_index": (f"{DATA_BASE}/result-ect-unofficial-constituency/{UNOFFICIAL_VERSION}/index.json", raw_dir / "unofficial-index.json"),
        "cartogram": (f"{ASSET_BASE}/{CARTOGRAM_ASSET}", raw_dir / CARTOGRAM_ASSET),
    }
    paths = {name: fetch(session, url, path, refresh) for name, (url, path) in sources.items()}
    common = load_json(paths["common"])
    area_codes = [area["code"] for area in common["areas"] if area["code"] != "AREA-7202"]

    def get_detail(code: str) -> Path:
        local_session = requests.Session()
        local_session.headers["User-Agent"] = "election-preference-explorer/1.0"
        return fetch(local_session, official_detail_url(code), raw_dir / "areas" / f"{code}.json", refresh)

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(get_detail, area_codes))
    return paths


def build_rows(paths: dict[str, Path], raw_dir: Path) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    common = load_json(paths["common"])
    candidates = {row["code"]: row for row in load_json(paths["candidates"])["candidates"]}
    parties = {row["code"]: row for row in load_json(paths["parties"])["parties"]}
    provinces = {row["code"]: row for row in common["provinces"]}
    areas = {row["code"]: row for row in common["areas"]}
    enrolment = {
        row["areaCode"]: int(row["totalEligibleVoters"])
        for row in load_json(paths["unofficial_index"])["data"]
    }
    if len(areas) != 400 or len(candidates) != 3527 or len(provinces) != 77:
        raise SystemExit("Thai PBS master data no longer has the expected 400 areas, 3,527 candidates, and 77 provinces")

    rows: list[dict[str, object]] = []
    district_info: dict[str, dict[str, object]] = {}
    for area_code, area in sorted(areas.items(), key=lambda item: (provinces[item[1]["provinceCode"]]["name"], item[1]["number"])):
        province = provinces[area["provinceCode"]]["name"]
        district = f"{province} {area['number']}"
        numeric_code = area_code.removeprefix("AREA-")
        result_note = ""
        if area_code == "AREA-7202":
            entries = [
                {"candidateCode": code, "voteTotal": votes}
                for code, votes in SUPHAN_BURI_2.items()
            ]
            formal: int | str = sum(SUPHAN_BURI_2.values())
            informal: int | str = ""
            total: int | str = ""
            district_enrolment: int | str = ""
            turnout: float | str = ""
            result_note = SUPHAN_NOTE
        else:
            detail = load_json(raw_dir / "areas" / f"{area_code}.json")
            entries = detail["entries"]
            formal = int(detail["goodVotes"])
            informal = int(detail["badVotes"]) + int(detail["noVotes"])
            total = int(detail["totalVotes"])
            district_enrolment = enrolment[area_code]
            turnout = round(total / district_enrolment * 100, 2)
            if sum(int(entry["voteTotal"]) for entry in entries) != formal:
                raise SystemExit(f"{district}: candidate totals do not equal valid votes")
            if formal + informal != total or total > district_enrolment:
                raise SystemExit(f"{district}: ballot or enrolment totals do not reconcile")

        result = []
        for entry in entries:
            candidate = candidates[entry["candidateCode"]]
            party = parties[candidate["partyCode"]]
            result.append((candidate_name(candidate), party.get("nameEn") or party["name"], int(entry["voteTotal"])))
        result.sort(key=lambda item: (-item[2], item[0]))
        if len(result) < 2 or result[0][2] <= result[1][2]:
            raise SystemExit(f"{district}: expected an unambiguous contested result")
        winner, winner_party, _ = result[0]
        url = RESULTS_PAGE.format(code=numeric_code)
        base = {
            "district": district,
            "district_url": url,
            "distribution_url": url,
            "elected_member": winner,
            "elected_party": winner_party,
            "enrolment": district_enrolment,
            "formal_votes": formal,
            "informal_votes": informal,
            "total_votes": total,
            "turnout_pct": turnout,
            "majority": int(formal) // 2 + 1,
            "electorate_type": province,
            "constituency_code": numeric_code,
            "contest_status": "official",
            "result_note": result_note,
        }
        rows.extend({
            **base,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": name,
            "candidate_party": party,
            "votes": votes,
        } for name, party, votes in result)
        district_info[numeric_code] = {
            "district": district,
            "province": province,
            "region": provinces[area["provinceCode"]]["regionCode"],
        }

    winners = Counter()
    seen_districts = set()
    for row in rows:
        if row["district"] not in seen_districts:
            seen_districts.add(row["district"])
            winners[row["elected_party"]] += 1
    if sum(winners.values()) != 400 or winners["Bhumjaithai"] != 173:
        raise SystemExit(f"Unexpected final constituency winners: {winners}")
    return rows, district_info


def build_cartogram(path: Path, district_info: dict[str, dict[str, object]]) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    map_start = source.find('const F6=e.jsxs("svg"')
    map_end = source.find("function u6(){return F6}", map_start)
    if map_start < 0 or map_end < 0:
        raise SystemExit("Could not locate the pinned nationwide English cartogram in the Thai PBS asset")
    source = source[map_start:map_end]
    pattern = re.compile(
        r'id:"area-(\d+)".{0,250}?"rect",\{width:"(\d+)",height:"(\d+)",fill:"#CCCACA",'
        r'transform:"translate\(([-\d.]+) ([-\d.]+)\)"'
    )
    coordinates: dict[str, tuple[float, float, float, float]] = {}
    for code, width, height, x, y in pattern.findall(source):
        value = (float(x), float(y), float(width), float(height))
        if code in coordinates and coordinates[code] != value:
            raise SystemExit(f"Thai PBS cartogram contains inconsistent coordinates for {code}")
        coordinates[code] = value
    if set(coordinates) != set(district_info):
        raise SystemExit(f"Cartogram/result code mismatch: {sorted(set(coordinates) ^ set(district_info))[:10]}")

    features = []
    for code, info in sorted(district_info.items()):
        x, y, width, height = coordinates[code]
        # SVG y increases down the screen. Negate y so the app's normal north-up projection
        # preserves the Thai PBS cartogram orientation.
        top, bottom = -y, -(y + height)
        ring = [[x, top], [x + width, top], [x + width, bottom], [x, bottom], [x, top]]
        features.append({
            "type": "Feature",
            "properties": {
                "district": info["district"],
                "constituency_code": code,
                "province": info["province"],
                "region": info["region"],
                "geometry_note": "Equal-area constituency cartogram cell; not a legal boundary",
            },
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })
    return {
        "type": "FeatureCollection",
        "name": "thailand_2026_constituency_cartogram",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Thailand's 2026 constituency election dataset")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/thailand_2026"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    paths = download_sources(args.raw_dir, args.refresh)
    rows, district_info = build_rows(paths, args.raw_dir)
    cartogram = build_cartogram(paths["cartogram"], district_info)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "thailand_2026_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    boundary_path = args.out_dir / "thailand_2026_constituency_cartogram.geojson"
    boundary_path.write_text(json.dumps(cartogram, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(rows):,} candidate rows across 400 constituencies to {csv_path}")
    print(f"Wrote 400 equal-area cartogram cells to {boundary_path}")


if __name__ == "__main__":
    main()
