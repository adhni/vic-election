#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union


DATASETS = {
    "Brexit counting areas": (
        Path("data/uk_2016_eu_referendum_counting_area_fpp.csv"),
        Path("data/uk_2016_eu_referendum_counting_area_boundaries.geojson"),
        382,
        {"Leave": 263, "Remain": 119},
        {"Leave": 17_410_742, "Remain": 16_141_241},
        25_359,
        46_500_001,
    ),
    "Brexit regions": (
        Path("data/uk_2016_eu_referendum_region_fpp.csv"),
        Path("data/uk_2016_eu_referendum_region_boundaries.geojson"),
        12,
        {"Leave": 9, "Remain": 3},
        {"Leave": 17_410_742, "Remain": 16_141_241},
        25_359,
        46_500_001,
    ),
    "Scottish independence councils": (
        Path("data/scotland_2014_independence_council_fpp.csv"),
        Path("data/scotland_2014_independence_council_boundaries.geojson"),
        32,
        {"No": 28, "Yes": 4},
        {"No": 2_001_926, "Yes": 1_617_989},
        3_429,
        4_283_938,
    ),
}


def validate_dataset(label: str, specification: tuple) -> dict[str, dict[str, int]]:
    csv_path, boundary_path, expected_areas, expected_winners, expected_votes, expected_rejected, expected_enrolment = specification
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_area = defaultdict(list)
    for row in rows:
        by_area[row["district"]].append(row)
    if len(by_area) != expected_areas or len(rows) != expected_areas * 2:
        raise SystemExit(f"{label}: expected {expected_areas} two-option areas, found {len(by_area)} areas / {len(rows)} rows")

    winner_counts = Counter()
    national_votes = Counter()
    rejected = enrolment = 0
    codes = set()
    area_votes = {}
    for district, area_rows in by_area.items():
        first = area_rows[0]
        votes = {row["candidate"]: int(row["votes"]) for row in area_rows}
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(first["formal_votes"])
        informal = int(first["informal_votes"])
        total = int(first["total_votes"])
        district_enrolment = int(first["enrolment"])
        if len(votes) != 2 or sum(votes.values()) != formal or formal + informal != total:
            raise SystemExit(f"{label}: {district} vote totals do not reconcile")
        if total > district_enrolment:
            raise SystemExit(f"{label}: {district} turnout exceeds enrolment")
        if first["elected_member"] != ranked[0][0] or first["elected_party"] != ranked[0][0]:
            raise SystemExit(f"{label}: {district} winner is wrong")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{label}: {district} margin is wrong")
        if float(first["turnout_pct"]) != round(total / district_enrolment * 100, 2):
            raise SystemExit(f"{label}: {district} turnout is wrong")
        if first["contest_status"] != "official" or not first["result_note"]:
            raise SystemExit(f"{label}: {district} lacks official provenance metadata")
        code = first["constituency_code"]
        if code in codes:
            raise SystemExit(f"{label}: duplicate area code {code}")
        codes.add(code)
        winner_counts[ranked[0][0]] += 1
        national_votes.update(votes)
        rejected += informal
        enrolment += district_enrolment
        area_votes[district] = votes

    if dict(winner_counts) != expected_winners:
        raise SystemExit(f"{label}: unexpected local winner counts {dict(winner_counts)}")
    if dict(national_votes) != expected_votes or rejected != expected_rejected or enrolment != expected_enrolment:
        raise SystemExit(f"{label}: national totals do not match the official result")

    collection = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    feature_codes = {feature["properties"].get("constituency_code") for feature in features}
    feature_names = {feature["properties"].get("district") for feature in features}
    if len(features) != expected_areas or feature_codes != codes or feature_names != set(by_area):
        raise SystemExit(f"{label}: CSV and boundary areas do not match one-to-one")
    geometries = []
    for item in features:
        geometry = shape(item["geometry"])
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise SystemExit(f"{label}: invalid geometry for {item['properties'].get('district')}")
        geometries.append(geometry)
    summed_area = sum(geometry.area for geometry in geometries)
    overlap_ratio = max(0, (summed_area - unary_union(geometries).area) / summed_area)
    if overlap_ratio > 0.001:
        raise SystemExit(f"{label}: mapped areas overlap materially ({overlap_ratio:.3%})")
    return area_votes


def main() -> None:
    results = {label: validate_dataset(label, specification) for label, specification in DATASETS.items()}
    area_rows = defaultdict(Counter)
    with Path("data/uk_2016_eu_referendum_counting_area_fpp.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            area_rows[row["electorate_type"]][row["candidate"]] += int(row["votes"])
    if {region: dict(votes) for region, votes in area_rows.items()} != results["Brexit regions"]:
        raise SystemExit("Brexit region rows do not exactly aggregate their counting areas")
    print("UK referendum validation passed: Brexit 2016 counting areas/regions and Scotland 2014 councils")


if __name__ == "__main__":
    main()
