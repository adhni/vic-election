#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union


AREA_COUNTS = {
    (2022, "department"): 106,
    (2022, "region"): 18,
    (2017, "department"): 106,
    (2017, "region"): 18,
    (2012, "department"): 106,
    (2012, "region"): 27,
    (2007, "department"): 105,
    (2007, "region"): 26,
}
CANDIDATE_COUNTS = {2022: 12, 2017: 11, 2012: 10, 2007: 12}


def validate_csv(year: int, round_number: int, level: str) -> tuple[set[str], dict[str, str]]:
    path = Path(f"data/france_{year}_president_round_{round_number}_{level}_fpp.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_area = defaultdict(list)
    for row in rows:
        by_area[row["district"]].append(row)

    expected_areas = AREA_COUNTS[(year, level)]
    expected_candidates = CANDIDATE_COUNTS[year] if round_number == 1 else 2
    if len(by_area) != expected_areas:
        raise SystemExit(f"{path}: expected {expected_areas} areas, found {len(by_area)}")
    if len(rows) != expected_areas * expected_candidates:
        raise SystemExit(f"{path}: unexpected row count {len(rows)}")

    candidate_sets = set()
    codes = {}
    for area, area_rows in by_area.items():
        first = area_rows[0]
        votes = {row["candidate"]: int(row["votes"]) for row in area_rows}
        candidate_sets.add(tuple(sorted(votes)))
        if len(votes) != expected_candidates:
            raise SystemExit(f"{path}: {area} has an incomplete candidate set")
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(first["formal_votes"])
        informal = int(first["informal_votes"])
        total = int(first["total_votes"])
        enrolment = int(first["enrolment"])
        if sum(votes.values()) != formal or formal + informal != total:
            raise SystemExit(f"{path}: {area} vote totals do not reconcile")
        if total > enrolment:
            raise SystemExit(f"{path}: {area} turnout exceeds enrolment")
        if first["elected_member"] != ranked[0][0] or first["elected_party"] != ranked[0][0]:
            raise SystemExit(f"{path}: {area} winner is wrong")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{path}: {area} margin is wrong")
        if float(first["turnout_pct"]) != round(total / enrolment * 100, 2):
            raise SystemExit(f"{path}: {area} turnout is wrong")
        expected_prefix = f"FR{year}-T{round_number}-{'DPT' if level == 'department' else 'REG'}-"
        if not first["constituency_code"].startswith(expected_prefix):
            raise SystemExit(f"{path}: {area} has an invalid code")
        if first["contest_status"] != "official":
            raise SystemExit(f"{path}: {area} is not marked official")
        codes[area] = first["constituency_code"]

    if len(candidate_sets) != 1:
        raise SystemExit(f"{path}: candidate sets differ between areas")
    if len(set(codes.values())) != expected_areas:
        raise SystemExit(f"{path}: area codes are not unique")
    return set(by_area), codes


def validate_boundaries(
    year: int,
    level: str,
    districts: set[str],
    round_one_codes: dict[str, str],
) -> None:
    path = Path(f"data/france_{year}_{level}_boundaries.geojson")
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != AREA_COUNTS[(year, level)]:
        raise SystemExit(f"{path}: unexpected feature count")
    if {feature["properties"]["district"] for feature in features} != districts:
        raise SystemExit(f"{path}: boundary names do not match round-one CSV")

    geometries = []
    for feature in features:
        properties = feature["properties"]
        district = properties["district"]
        if properties["constituency_code"] != round_one_codes[district]:
            raise SystemExit(f"{path}: {district} code does not match round-one CSV")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{path}: {district} geometry is invalid")
        min_x, min_y, max_x, max_y = geometry.bounds
        if min_x < -7 or max_x > 11 or min_y < 36 or max_y > 52:
            raise SystemExit(f"{path}: {district} is outside the compact France layout")
        geometries.append(geometry)

    summed_area = sum(geometry.area for geometry in geometries)
    overlap_ratio = (summed_area - unary_union(geometries).area) / summed_area
    if overlap_ratio > 0.002:
        raise SystemExit(f"{path}: areas materially overlap ({overlap_ratio:.3%})")


def main() -> None:
    for year in (2022, 2017, 2012, 2007):
        for level in ("department", "region"):
            round_one_districts, round_one_codes = validate_csv(year, 1, level)
            round_two_districts, _ = validate_csv(year, 2, level)
            if round_one_districts != round_two_districts:
                raise SystemExit(f"{year} {level}: mapped areas differ between rounds")
            validate_boundaries(year, level, round_one_districts, round_one_codes)
    print("France validation passed: 2007–2022, both rounds, departments/territories and regions")


if __name__ == "__main__":
    main()
