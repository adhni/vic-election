#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED = {
    2025: {
        "first_vote_leaders": {"CDU": 143, "CSU": 47, "AfD": 46, "SPD": 45, "GRÜNE": 12, "Die Linke": 6},
        "awarded": {"CDU": 128, "AfD": 42, "SPD": 44, "GRÜNE": 12, "Die Linke": 6, "CSU": 44},
        "unawarded": 23,
    },
    2021: {
        "first_vote_leaders": {"SPD": 121, "CDU": 98, "CSU": 45, "AfD": 16, "GRÜNE": 16, "DIE LINKE": 3},
        "awarded": {"SPD": 121, "CDU": 98, "CSU": 45, "AfD": 16, "GRÜNE": 16, "DIE LINKE": 3},
        "unawarded": 0,
    },
    2017: {
        "first_vote_leaders": {"CDU": 185, "SPD": 59, "CSU": 46, "DIE LINKE": 5, "AfD": 3, "GRÜNE": 1},
        "awarded": {"CDU": 185, "SPD": 59, "CSU": 46, "DIE LINKE": 5, "AfD": 3, "GRÜNE": 1},
        "unawarded": 0,
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate German Bundestag app datasets")
    parser.add_argument("--year", type=int, choices=EXPECTED)
    args = parser.parse_args()
    years = (args.year,) if args.year else tuple(EXPECTED)

    for year in years:
        csv_path = Path(f"data/germany_{year}_bundestag.csv")
        boundary_path = Path(f"data/germany_{year}_constituency_boundaries.geojson")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[row["district"]].append(row)
        if len(groups) != 299:
            raise SystemExit(f"{year}: expected 299 constituencies, found {len(groups)}")

        winner_counts: Counter[str] = Counter()
        awarded_counts: Counter[str] = Counter()
        unawarded = 0
        for district, district_rows in groups.items():
            first = [row for row in district_rows if row["row_type"] == "first"]
            second = [row for row in district_rows if row["row_type"] == "party_vote"]
            if len(first) < 2 or len(second) < 2:
                raise SystemExit(f"{year} {district}: incomplete vote choices")
            formal = int(district_rows[0]["formal_votes"])
            informal = int(district_rows[0]["informal_votes"])
            total = int(district_rows[0]["total_votes"])
            if sum(int(row["votes"]) for row in first) != formal:
                raise SystemExit(f"{year} {district}: first-vote sum mismatch")
            if total != formal + informal:
                raise SystemExit(f"{year} {district}: ballot total mismatch")
            winner = max(first, key=lambda row: (int(row["votes"]), row["candidate"]))
            winner_counts[winner["candidate_party"]] += 1
            if district_rows[0]["mandate_awarded"] != "True":
                unawarded += 1
                if district_rows[0]["elected_member"]:
                    raise SystemExit(f"{year} {district}: unawarded seat has an elected member")
            else:
                awarded_counts[winner["candidate_party"]] += 1

        expected = EXPECTED[year]
        if dict(winner_counts) != expected["first_vote_leaders"]:
            raise SystemExit(f"{year}: first-vote leader totals differ: {winner_counts}")
        if dict(awarded_counts) != expected["awarded"]:
            raise SystemExit(f"{year}: awarded constituency totals differ: {awarded_counts}")
        if unawarded != expected["unawarded"]:
            raise SystemExit(f"{year}: expected {expected['unawarded']} unawarded seats, found {unawarded}")

        boundaries = json.loads(boundary_path.read_text(encoding="utf-8"))
        features = boundaries.get("features", [])
        boundary_names = {feature["properties"]["district"] for feature in features}
        if len(features) != 299 or boundary_names != set(groups):
            raise SystemExit(f"{year}: boundary mismatch")
        print(f"Germany {year} validation passed: 299 constituencies, {unawarded} unawarded")


if __name__ == "__main__":
    main()
