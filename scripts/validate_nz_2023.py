#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CSV_PATH = Path("data/nz_2023_mmp.csv")
BOUNDARY_PATH = Path("data/nz_2023_electorate_boundaries.geojson")


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 72:
        raise SystemExit(f"Expected 72 electorates, found {len(groups)}")

    types = Counter(group[0]["electorate_type"] for group in groups.values())
    if types != {"General": 65, "Māori": 7}:
        raise SystemExit(f"Unexpected electorate split: {types}")

    for district, district_rows in groups.items():
        status = district_rows[0]["contest_status"]
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        party = [row for row in district_rows if row["row_type"] == "party_vote"]
        if len(party) != 17:
            raise SystemExit(f"{district}: expected 17 party-vote rows, found {len(party)}")
        if sum(int(row["votes"]) for row in party) <= 0:
            raise SystemExit(f"{district}: party votes are empty")
        if status == "cancelled":
            if district != "Port Waikato" or any(int(row["votes"]) for row in first + final):
                raise SystemExit(f"{district}: invalid cancelled-contest rows")
            continue
        if status != "official" or len(first) < 2 or len(first) != len(final):
            raise SystemExit(f"{district}: invalid candidate rows")
        formal = int(district_rows[0]["formal_votes"])
        informal = int(district_rows[0]["informal_votes"])
        total = int(district_rows[0]["total_votes"])
        if sum(int(row["votes"]) for row in first) != formal:
            raise SystemExit(f"{district}: candidate votes do not equal formal votes")
        if total != formal + informal:
            raise SystemExit(f"{district}: total votes do not equal formal plus informal")

    checks = {
        "Mt Albert": ("Helen White", 13238, 18),
        "Nelson": ("Rachel Boyack", 17541, 26),
        "Tāmaki Makaurau": ("Takutai Tarsh Kemp", 10068, 42),
    }
    for district, (winner, votes, margin) in checks.items():
        final = sorted(
            ((row["candidate"], int(row["votes"])) for row in groups[district] if row["row_type"] == "final"),
            key=lambda item: (-item[1], item[0]),
        )
        if final[0] != (winner, votes) or final[0][1] - final[1][1] != margin:
            raise SystemExit(f"{district}: spot check failed: {final[:2]}")

    geojson = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    if len(features) != 72 or boundary_names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(boundary_names ^ set(groups))}")
    boundary_types = Counter(feature["properties"]["electorate_type"] for feature in features)
    if boundary_types != {"General": 65, "Māori": 7}:
        raise SystemExit(f"Unexpected boundary split: {boundary_types}")
    print("NZ 2023 validation passed: 65 general + 7 Māori electorates, 71 contests + Port Waikato cancelled")


if __name__ == "__main__":
    main()
