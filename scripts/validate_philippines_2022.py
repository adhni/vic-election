#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union


DATA = Path("data")
FILES = {
    "president": DATA / "philippines_2022_president_fpp.csv",
    "vice_president": DATA / "philippines_2022_vice_president_fpp.csv",
}
BOUNDARIES = DATA / "philippines_2022_coc_boundaries.geojson"

EXPECTED_CANDIDATES = {
    "president": {
        "Marcos", "Robredo", "Pacquiao", "Moreno", "Lacson", "Mangondato",
        "Abella", "De Guzman", "Gonzales", "Montemayor",
    },
    "vice_president": {
        "Duterte", "Pangilinan", "Sotto", "Ong", "Atienza", "Lopez",
        "Bello", "Serapio", "David",
    },
}
EXPECTED_LOCAL_TOTALS = {
    "president": {
        "Marcos": 31_086_532, "Robredo": 14_892_492, "Pacquiao": 3_656_831,
        "Moreno": 1_906_981, "Lacson": 882_779, "Mangondato": 300_189,
        "Abella": 114_207, "De Guzman": 92_638, "Gonzales": 90_116,
        "Montemayor": 60_327,
    },
    "vice_president": {
        "Duterte": 31_647_907, "Pangilinan": 9_215_590, "Sotto": 8_229_631,
        "Ong": 1_846_267, "Atienza": 269_129, "Lopez": 159_480,
        "Bello": 100_151, "Serapio": 90_873, "David": 58_332,
    },
}
EXPECTED_WIN_COUNTS = {
    "president": {"Marcos": 89, "Robredo": 16, "Mangondato": 1, "Pacquiao": 1},
    "vice_president": {"Duterte": 99, "Pangilinan": 7, "Sotto": 1},
}


def validate_csv(office: str, path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = 107 * len(EXPECTED_CANDIDATES[office])
    if len(rows) != expected_rows:
        raise SystemExit(f"{path}: expected {expected_rows} rows, found {len(rows)}")

    by_district = defaultdict(list)
    local_totals = Counter()
    for row in rows:
        by_district[row["district"]].append(row)
        local_totals[row["candidate_party"]] += int(row["votes"])
    if len(by_district) != 107:
        raise SystemExit(f"{path}: expected 107 map areas, found {len(by_district)}")
    if dict(local_totals) != EXPECTED_LOCAL_TOTALS[office]:
        raise SystemExit(f"{path}: mapped candidate totals changed: {dict(local_totals)}")

    codes = {}
    regions = {}
    winners = Counter()
    for district, district_rows in by_district.items():
        labels = {row["candidate_party"] for row in district_rows}
        if labels != EXPECTED_CANDIDATES[office]:
            raise SystemExit(f"{path}: {district} candidate set is incomplete")
        votes = {row["candidate_party"]: int(row["votes"]) for row in district_rows}
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        first = district_rows[0]
        formal = int(first["formal_votes"])
        if formal != sum(votes.values()) or int(first["total_votes"]) != formal:
            raise SystemExit(f"{path}: {district} candidate-vote total does not reconcile")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{path}: {district} majority is wrong")
        if first["elected_party"] != ranked[0][0]:
            raise SystemExit(f"{path}: {district} local winner is wrong")
        if any(row["contest_status"] != "official" for row in district_rows):
            raise SystemExit(f"{path}: {district} is not marked official")
        codes[district] = first["constituency_code"]
        regions[district] = first["electorate_type"]
        winners[first["elected_party"]] += 1
    if dict(winners) != EXPECTED_WIN_COUNTS[office]:
        raise SystemExit(f"{path}: local winner counts changed: {dict(winners)}")
    if len(set(codes.values())) != 107:
        raise SystemExit(f"{path}: map-area codes are not unique")
    return set(by_district), codes, regions


def validate_boundaries(expected_names, expected_codes, expected_regions):
    collection = json.loads(BOUNDARIES.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != 107:
        raise SystemExit(f"{BOUNDARIES}: expected 107 features, found {len(features)}")
    names = {feature["properties"]["district"] for feature in features}
    if names != expected_names:
        raise SystemExit(f"{BOUNDARIES}: boundary names do not match CSV areas")
    geometries = []
    for feature in features:
        properties = feature["properties"]
        district = properties["district"]
        if properties["constituency_code"] != expected_codes[district]:
            raise SystemExit(f"{BOUNDARIES}: {district} code does not match the CSV")
        if properties["electorate_type"] != expected_regions[district]:
            raise SystemExit(f"{BOUNDARIES}: {district} region does not match the CSV")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{BOUNDARIES}: {district} geometry is invalid")
        geometries.append(geometry)
    summed_area = sum(geometry.area for geometry in geometries)
    union_area = unary_union(geometries).area
    overlap_ratio = (summed_area - union_area) / summed_area if summed_area else 0
    if overlap_ratio > 0.001:
        raise SystemExit(f"{BOUNDARIES}: dissolved reporting areas materially overlap ({overlap_ratio:.3%})")


def main() -> None:
    president = validate_csv("president", FILES["president"])
    vice = validate_csv("vice_president", FILES["vice_president"])
    if president != vice:
        raise SystemExit("President and vice-president map-area metadata differ")
    validate_boundaries(*president)
    print(
        "Philippines 2022 validation passed: 107 mapped COC areas, "
        "10 presidential candidates, 9 vice-presidential candidates"
    )


if __name__ == "__main__":
    main()
