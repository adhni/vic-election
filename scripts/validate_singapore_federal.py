#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED = {
    2025: {"divisions": 33, "entries": 71, "candidates": 211, "seats": {"PAP": 87, "WP": 10}, "types": {"SMC": 15, "GRC": 18}, "uncontested": ["Marine Parade-Braddell Heights"], "checks": {"Jalan Kayu": ("Ng Chee Meng", 14146, 809), "East Coast": ("PAP team", 80105, 23817), "Aljunied": ("WP team", 79254, 25783)}},
    2020: {"divisions": 31, "entries": 64, "candidates": 192, "seats": {"PAP": 83, "WP": 10}, "types": {"SMC": 14, "GRC": 17}, "uncontested": [], "checks": {"Marymount": ("GAN SIOW HUANG", 12173, 2230), "Bukit Panjang": ("LIANG ENG HWA", 18085, 2509), "Bukit Batok": ("MURALI PILLAI", 15500, 2713)}},
    2015: {"divisions": 29, "entries": 61, "candidates": 181, "seats": {"PAP": 83, "WP": 6}, "types": {"SMC": 13, "GRC": 16}, "uncontested": [], "checks": {"Punggol East": ("CHARLES CHONG YOU FOOK", 16977, 1159), "Aljunied": ("WP team", 70050, 2626), "Fengshan": ("CHERYL CHAN WEI LING", 12417, 3241)}},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Singapore General Election data")
    parser.add_argument("--year", type=int, choices=sorted(EXPECTED), default=2025)
    args = parser.parse_args()
    expected = EXPECTED[args.year]
    csv_path = Path(f"data/singapore_{args.year}_fpp.csv")
    boundary_path = Path(f"data/singapore_{args.year}_electoral_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != expected["divisions"]:
        raise SystemExit(f"Expected {expected['divisions']} electoral divisions, found {len(groups)}")

    contest_entries = 0
    elected_seats = Counter()
    types = Counter()
    uncontested = []
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        if not first or len(first) != len(final):
            raise SystemExit(f"{district}: unequal first/final rows")
        first_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in first}
        final_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in final}
        if len(first_result) != len(first) or first_result != final_result:
            raise SystemExit(f"{district}: duplicate teams or unequal first/final totals")
        if any(len([name for name in row["candidate_members"].split(";") if name]) != int(first[0]["members_to_elect"]) for row in first):
            raise SystemExit(f"{district}: candidate team membership does not match seat count")
        metadata = first[0]
        formal = int(metadata["formal_votes"])
        informal = int(metadata["informal_votes"])
        total = int(metadata["total_votes"])
        enrolment = int(metadata["enrolment"])
        if sum(first_result.values()) != formal or total != formal + informal:
            raise SystemExit(f"{district}: vote totals do not reconcile")
        if abs(float(metadata["turnout_pct"]) - total / enrolment * 100) > 0.011:
            raise SystemExit(f"{district}: turnout metadata does not reconcile")
        members = [name for name in metadata["elected_members"].split(";") if name]
        seats = int(metadata["members_to_elect"])
        if len(members) != seats or seats not in {1, 4, 5, 6}:
            raise SystemExit(f"{district}: invalid elected-member metadata")
        expected_type = "SMC" if seats == 1 else "GRC"
        if metadata["electorate_type"] != expected_type:
            raise SystemExit(f"{district}: electoral division type does not match member count")
        ranked = sorted(first_result.items(), key=lambda item: (-item[1], item[0][0]))
        if metadata["contest_status"] == "uncontested":
            uncontested.append(district)
            if len(first) != 1 or total != 0:
                raise SystemExit(f"{district}: invalid uncontested result")
        else:
            if len(first) < 2 or metadata["elected_member"] != ranked[0][0][0]:
                raise SystemExit(f"{district}: winner metadata does not match vote result")
        if metadata["elected_party"] != next(row["candidate_party"] for row in first if row["candidate"] == metadata["elected_member"]):
            raise SystemExit(f"{district}: elected party does not match winning team")
        contest_entries += len(first)
        elected_seats[metadata["elected_party"]] += seats
        types[expected_type] += 1

    # The results page has 71 party/candidate entries containing 211 named candidates.
    actual_candidate_members = sum(
        len([name for name in row["candidate_members"].split(";") if name])
        for district_rows in groups.values()
        for row in district_rows
        if row["row_type"] == "first"
    )
    if contest_entries != expected["entries"] or actual_candidate_members != expected["candidates"]:
        raise SystemExit(f"Expected {expected['entries']} entries and {expected['candidates']} candidates, found {contest_entries} and {actual_candidate_members}")
    if elected_seats != expected["seats"]:
        raise SystemExit(f"Unexpected elected seat totals: {elected_seats}")
    if types != expected["types"]:
        raise SystemExit(f"Unexpected division types: {types}")
    if uncontested != expected["uncontested"]:
        raise SystemExit(f"Unexpected uncontested divisions: {uncontested}")

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
    if len(features) != expected["divisions"] or boundary_names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(boundary_names ^ set(groups))}")
    print(f"Singapore {args.year} validation passed: {expected['divisions']} divisions, {sum(expected['seats'].values())} MPs, all totals and boundaries matched")


if __name__ == "__main__":
    main()
