#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CSV_PATH = Path("data/singapore_2025_fpp.csv")
BOUNDARY_PATH = Path("data/singapore_2025_electoral_boundaries.geojson")


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 33:
        raise SystemExit(f"Expected 33 electoral divisions, found {len(groups)}")

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
        if len(members) != seats or seats not in {1, 4, 5}:
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
    if contest_entries != 71 or actual_candidate_members != 211:
        raise SystemExit(f"Expected 71 entries and 211 candidates, found {contest_entries} and {actual_candidate_members}")
    if elected_seats != {"PAP": 87, "WP": 10}:
        raise SystemExit(f"Unexpected elected seat totals: {elected_seats}")
    if types != {"SMC": 15, "GRC": 18}:
        raise SystemExit(f"Unexpected division types: {types}")
    if uncontested != ["Marine Parade-Braddell Heights"]:
        raise SystemExit(f"Unexpected uncontested divisions: {uncontested}")

    checks = {
        "Jalan Kayu": ("Ng Chee Meng", 14146, 809),
        "East Coast": ("PAP team", 80105, 23817),
        "Aljunied": ("WP team", 79254, 25783),
    }
    for district, (winner, votes, margin) in checks.items():
        ranked = sorted(
            ((row["candidate"], int(row["votes"])) for row in groups[district] if row["row_type"] == "final"),
            key=lambda item: (-item[1], item[0]),
        )
        if ranked[0] != (winner, votes) or ranked[0][1] - ranked[1][1] != margin:
            raise SystemExit(f"{district}: spot check failed: {ranked[:2]}")

    geojson = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    if len(features) != 33 or boundary_names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(boundary_names ^ set(groups))}")
    print("Singapore GE2025 validation passed: 33 divisions, 97 MPs, all totals and boundaries matched")


if __name__ == "__main__":
    main()
