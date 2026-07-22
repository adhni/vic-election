#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union


CSV_PATH = Path("data/mexico_2024_president_fpp.csv")
BOUNDARY_PATH = Path("data/mexico_2024_federal_district_boundaries.geojson")
EXPECTED_CANDIDATES = {"Sheinbaum", "Gálvez", "Máynez"}
EXPECTED_MAPPED_TOTALS = {
    "Sheinbaum": 35_833_009,
    "Gálvez": 16_416_179,
    "Máynez": 6_200_276,
}
EXPECTED_WINS = {"Sheinbaum": 275, "Gálvez": 25}
EXPECTED_ENROLMENT = 98_245_033
EXPECTED_TOTAL_VOTES = 59_930_858


def validate_csv():
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 900:
        raise SystemExit(f"{CSV_PATH}: expected 900 rows, found {len(rows)}")

    by_district = defaultdict(list)
    candidate_totals = Counter()
    for row in rows:
        by_district[row["district"]].append(row)
        candidate_totals[row["candidate_party"]] += int(row["votes"])
    if len(by_district) != 300:
        raise SystemExit(f"{CSV_PATH}: expected 300 federal districts, found {len(by_district)}")
    if dict(candidate_totals) != EXPECTED_MAPPED_TOTALS:
        raise SystemExit(f"{CSV_PATH}: mapped candidate totals changed: {dict(candidate_totals)}")

    codes = {}
    states = {}
    wins = Counter()
    enrolment = 0
    total_votes = 0
    for district, district_rows in by_district.items():
        if {row["candidate_party"] for row in district_rows} != EXPECTED_CANDIDATES:
            raise SystemExit(f"{CSV_PATH}: {district} candidate set is incomplete")
        first = district_rows[0]
        if any(row["contest_status"] != "official" for row in district_rows):
            raise SystemExit(f"{CSV_PATH}: {district} is not marked official")
        votes = {row["candidate_party"]: int(row["votes"]) for row in district_rows}
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(first["formal_votes"])
        informal = int(first["informal_votes"])
        total = int(first["total_votes"])
        district_enrolment = int(first["enrolment"])
        if formal != sum(votes.values()) or formal + informal != total:
            raise SystemExit(f"{CSV_PATH}: {district} vote totals do not reconcile")
        if first["elected_party"] != ranked[0][0]:
            raise SystemExit(f"{CSV_PATH}: {district} winner is wrong")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{CSV_PATH}: {district} winning margin is wrong")
        expected_turnout = round(total / district_enrolment * 100, 2)
        if float(first["turnout_pct"]) != expected_turnout:
            raise SystemExit(f"{CSV_PATH}: {district} turnout is wrong")
        code = first["constituency_code"]
        if not code.startswith("MX2024-"):
            raise SystemExit(f"{CSV_PATH}: {district} has an invalid district code")
        codes[district] = code
        states[district] = first["electorate_type"]
        wins[first["elected_party"]] += 1
        enrolment += district_enrolment
        total_votes += total
    if len(set(codes.values())) != 300:
        raise SystemExit(f"{CSV_PATH}: federal district codes are not unique")
    if len(set(states.values())) != 32:
        raise SystemExit(f"{CSV_PATH}: expected all 32 states, found {len(set(states.values()))}")
    if dict(wins) != EXPECTED_WINS:
        raise SystemExit(f"{CSV_PATH}: district winner counts changed: {dict(wins)}")
    if enrolment != EXPECTED_ENROLMENT or total_votes != EXPECTED_TOTAL_VOTES:
        raise SystemExit(
            f"{CSV_PATH}: mapped enrolment/total votes changed to {enrolment:,}/{total_votes:,}"
        )
    return set(by_district), codes, states


def validate_boundaries(expected_names, expected_codes, expected_states):
    collection = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != 300:
        raise SystemExit(f"{BOUNDARY_PATH}: expected 300 features, found {len(features)}")
    names = {feature["properties"]["district"] for feature in features}
    if names != expected_names:
        raise SystemExit(f"{BOUNDARY_PATH}: boundary names do not match result districts")
    geometries = []
    for feature in features:
        properties = feature["properties"]
        district = properties["district"]
        if properties["constituency_code"] != expected_codes[district]:
            raise SystemExit(f"{BOUNDARY_PATH}: {district} code does not match the CSV")
        if properties["electorate_type"] != expected_states[district]:
            raise SystemExit(f"{BOUNDARY_PATH}: {district} state does not match the CSV")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{BOUNDARY_PATH}: {district} geometry is invalid")
        min_x, min_y, max_x, max_y = geometry.bounds
        if min_x < -119 or max_x > -86 or min_y < 14 or max_y > 33:
            raise SystemExit(f"{BOUNDARY_PATH}: {district} falls outside plausible Mexico bounds")
        geometries.append(geometry)
    summed_area = sum(geometry.area for geometry in geometries)
    overlap_ratio = (summed_area - unary_union(geometries).area) / summed_area
    if overlap_ratio > 0.001:
        raise SystemExit(f"{BOUNDARY_PATH}: districts materially overlap ({overlap_ratio:.3%})")


def main() -> None:
    validate_boundaries(*validate_csv())
    print(
        "Mexico 2024 validation passed: 300 official federal districts, 900 candidate rows, "
        "275 Sheinbaum wins and 25 Gálvez wins"
    )


if __name__ == "__main__":
    main()
