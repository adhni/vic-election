#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED = {
    2025: {
        "ridings": 343,
        "candidates": 1959,
        "winners": {"Liberal": 169, "Conservative": 144, "Bloc Québécois": 22, "NDP": 7, "Green": 1},
        "provinces": {"Ontario": 122, "Quebec": 78, "British Columbia": 43, "Alberta": 37},
        "checks": {
            "Terrebonne": ("Tatiana Auguste", 23352, 1),
            "Windsor—Tecumseh—Lakeshore": ("Kathy Borrelli", 32090, 4),
            "Carleton": ("Bruce Fanjoy", 43846, 4513),
            "Nepean": ("Mark Carney", 46073, 22056),
        },
    },
    2021: {
        "ridings": 338,
        "candidates": 2010,
        "winners": {"Liberal": 160, "Conservative": 119, "Bloc Québécois": 32, "NDP": 25, "Green": 2},
        "provinces": {"Ontario": 121, "Quebec": 78, "British Columbia": 42, "Alberta": 34},
        "checks": {
            "Châteauguay—Lacolle": ("Brenda Shanahan", 18029, 12),
            "Davenport": ("Julie Dzerowicz", 19930, 76),
            "Papineau": ("Justin Trudeau", 22848, 12545),
            "Carleton": ("Pierre Poilievre", 35356, 11058),
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Canada federal election data")
    parser.add_argument("--year", type=int, choices=sorted(EXPECTED), default=2025)
    args = parser.parse_args()
    expected = EXPECTED[args.year]
    csv_path = Path(f"data/canada_{args.year}_fpp.csv")
    boundary_path = Path(f"data/canada_{args.year}_federal_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != expected["ridings"]:
        raise SystemExit(f"Expected {expected['ridings']} ridings, found {len(groups)}")

    candidate_count = 0
    winners = Counter()
    provinces = Counter()
    codes = set()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        if len(first) < 2 or len(first) != len(final):
            raise SystemExit(f"{district}: invalid FPTP row counts")
        first_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in first}
        final_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in final}
        if len(first_result) != len(first) or first_result != final_result:
            raise SystemExit(f"{district}: duplicate candidates or unequal first/final totals")
        metadata = first[0]
        formal = int(metadata["formal_votes"])
        informal = int(metadata["informal_votes"])
        total = int(metadata["total_votes"])
        enrolment = int(metadata["enrolment"])
        if sum(first_result.values()) != formal or total != formal + informal:
            raise SystemExit(f"{district}: vote totals do not reconcile")
        if abs(float(metadata["turnout_pct"]) - total / enrolment * 100) > 0.011:
            raise SystemExit(f"{district}: turnout metadata does not reconcile")
        ranked = sorted(first_result.items(), key=lambda item: (-item[1], item[0][0]))
        winner_name, winner_party = ranked[0][0]
        if metadata["elected_member"] != winner_name or metadata["elected_party"] != winner_party:
            raise SystemExit(f"{district}: elected member metadata does not match the vote result")
        candidate_count += len(first)
        winners[winner_party] += 1
        provinces[metadata["electorate_type"]] += 1
        codes.add(metadata["constituency_code"])

    if candidate_count != expected["candidates"] or len(codes) != expected["ridings"]:
        raise SystemExit(f"Unexpected candidate/code counts: {candidate_count} and {len(codes)}")
    if winners != expected["winners"]:
        raise SystemExit(f"Unexpected winning-party totals: {winners}")
    expected_provinces = {
        "Newfoundland and Labrador": 7, "Prince Edward Island": 4, "Nova Scotia": 11,
        "New Brunswick": 10, "Quebec": 78, "Ontario": 122, "Manitoba": 14,
        "Saskatchewan": 14, "Alberta": expected["provinces"]["Alberta"],
        "British Columbia": expected["provinces"]["British Columbia"], "Yukon": 1,
        "Northwest Territories": 1, "Nunavut": 1,
    }
    expected_provinces["Ontario"] = expected["provinces"]["Ontario"]
    if provinces != expected_provinces:
        raise SystemExit(f"Unexpected province/territory split: {provinces}")

    for district, (winner, votes, margin) in expected["checks"].items():
        ranked = sorted(
            ((row["candidate"], int(row["votes"])) for row in groups[district] if row["row_type"] == "final"),
            key=lambda item: (-item[1], item[0]),
        )
        if ranked[0] != (winner, votes) or ranked[0][1] - ranked[1][1] != margin:
            raise SystemExit(f"{district}: spot check failed: {ranked[:2]}")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != expected["ridings"] or len(boundary_codes) != expected["ridings"] or boundary_names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(boundary_names ^ set(groups))}")
    print(f"Canada GE{args.year} validation passed: {expected['ridings']} ridings, {expected['candidates']:,} candidates, all totals and boundaries matched")


if __name__ == "__main__":
    main()
