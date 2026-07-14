#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CSV_PATH = Path("data/uk_2024_fpp.csv")
BOUNDARY_PATH = Path("data/uk_2024_constituency_boundaries.geojson")


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 650:
        raise SystemExit(f"Expected 650 constituencies, found {len(groups)}")

    candidate_count = 0
    winners = Counter()
    countries = Counter()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        if len(first) < 2 or len(first) != len(final):
            raise SystemExit(f"{district}: invalid FPTP candidate rows")
        first_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in first}
        final_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in final}
        if first_result != final_result:
            raise SystemExit(f"{district}: FPTP first and final rows differ")
        formal = int(first[0]["formal_votes"])
        informal = int(first[0]["informal_votes"])
        total = int(first[0]["total_votes"])
        if sum(first_result.values()) != formal or total != formal + informal:
            raise SystemExit(f"{district}: vote totals do not reconcile")
        ranked = sorted(first_result.items(), key=lambda item: (-item[1], item[0][0]))
        winner_name, winner_party = ranked[0][0]
        if first[0]["elected_member"] != winner_name or first[0]["elected_party"] != winner_party:
            raise SystemExit(f"{district}: elected member metadata does not match result")
        candidate_count += len(first)
        winners[winner_party] += 1
        countries[first[0]["electorate_type"]] += 1

    if candidate_count != 4515:
        raise SystemExit(f"Expected 4,515 candidates, found {candidate_count}")
    expected_countries = {"England": 543, "Scotland": 57, "Wales": 32, "Northern Ireland": 18}
    if countries != expected_countries:
        raise SystemExit(f"Unexpected country split: {countries}")
    expected_winners = {
        "Labour": 411, "Conservative": 121, "Liberal Democrat": 72,
        "Scottish National Party": 9, "Sinn Féin": 7, "Independent": 6,
        "Reform UK": 5, "Democratic Unionist Party": 5, "Green Party": 4,
        "Plaid Cymru": 4, "Social Democratic & Labour Party": 2, "Speaker": 1,
        "Alliance": 1, "Traditional Unionist Voice": 1, "Ulster Unionist Party": 1,
    }
    if winners != expected_winners:
        raise SystemExit(f"Unexpected winning-party totals: {winners}")

    checks = {
        "Hendon": ("David Pinto-Duschinsky", 15855, 15),
        "Poole": ("Neil Duncan-Jordan", 14168, 18),
        "Bristol South": ("Karin Smyth", 18521, 7666),
        "Mid Buckinghamshire": ("Greg Smith (Conservative)", 20150, 5872),
    }
    for district, (winner, votes, margin) in checks.items():
        ranked = sorted(
            ((row["candidate"], int(row["votes"])) for row in groups[district] if row["row_type"] == "final"),
            key=lambda item: (-item[1], item[0]),
        )
        if ranked[0] != (winner, votes) or ranked[0][1] - ranked[1][1] != margin:
            raise SystemExit(f"{district}: spot check failed: {ranked[:2]}")

    mid_bucks_names = [
        row["candidate"] for row in groups["Mid Buckinghamshire"] if row["row_type"] == "first"
    ]
    if len(mid_bucks_names) != len(set(mid_bucks_names)) or "Greg Smith (Green Party)" not in mid_bucks_names:
        raise SystemExit("Mid Buckinghamshire: duplicate candidate names were not disambiguated")

    geojson = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != 650 or len(codes) != 650 or names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(names ^ set(groups))}")
    print("UK 2024 validation passed: 650 constituencies, 4,515 candidates, all totals and boundaries matched")


if __name__ == "__main__":
    main()
