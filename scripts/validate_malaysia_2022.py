#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CSV_PATH = Path("data/malaysia_2022_fpp.csv")
BOUNDARY_PATH = Path("data/malaysia_2022_parliamentary_boundaries.geojson")


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 222:
        raise SystemExit(f"Expected 222 constituencies, found {len(groups)}")

    candidate_count = 0
    winners = Counter()
    states = Counter()
    codes = set()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        if len(first) < 2 or len(first) != len(final):
            raise SystemExit(f"{district}: invalid FPTP rows")
        first_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in first}
        final_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in final}
        if len(first_result) != len(first) or first_result != final_result:
            raise SystemExit(f"{district}: duplicate candidates or unequal first/final totals")
        formal = int(first[0]["formal_votes"])
        rejected = int(first[0]["informal_votes"])
        unreturned = int(first[0]["unreturned_votes"])
        total = int(first[0]["total_votes"])
        enrolment = int(first[0]["enrolment"])
        if sum(first_result.values()) != formal or total != formal + rejected + unreturned:
            raise SystemExit(f"{district}: vote totals do not reconcile")
        if abs(float(first[0]["turnout_pct"]) - total / enrolment * 100) > 0.011:
            raise SystemExit(f"{district}: turnout metadata does not reconcile")
        ranked = sorted(first_result.items(), key=lambda item: (-item[1], item[0][0]))
        winner_name, winner_party = ranked[0][0]
        if first[0]["elected_member"] != winner_name or first[0]["elected_party"] != winner_party:
            raise SystemExit(f"{district}: elected member metadata does not match result")
        candidate_count += len(first)
        winners[winner_party] += 1
        states[first[0]["electorate_type"]] += 1
        codes.add(first[0]["constituency_code"])

    if candidate_count != 945 or len(codes) != 222:
        raise SystemExit(f"Expected 945 candidates and 222 codes, found {candidate_count} and {len(codes)}")
    expected_winners = {
        "PH": 76, "PN": 52, "BN": 30, "GPS": 23, "PAS": 22, "GRS": 6,
        "DAP": 5, "WARISAN": 3, "BEBAS": 2, "MUDA": 1, "KDM": 1, "PBM": 1,
    }
    if winners != expected_winners:
        raise SystemExit(f"Unexpected winning-party totals: {winners}")
    expected_states = {
        "Johor": 26, "Kedah": 15, "Kelantan": 14, "Melaka": 6, "Negeri Sembilan": 8,
        "Pahang": 14, "Perak": 24, "Perlis": 3, "Pulau Pinang": 13, "Sabah": 25,
        "Sarawak": 31, "Selangor": 22, "Terengganu": 8, "W.P Kuala Lumpur": 11,
        "W.P Labuan": 1, "W.P Putrajaya": 1,
    }
    if states != expected_states:
        raise SystemExit(f"Unexpected state split: {states}")

    checks = {
        "Lubok Antu": ("Roy Angau Anak Gingkoi", 6644, 100),
        "Tambun": ("Anwar Ibrahim", 49655, 3716),
        "Padang Serai": ("Dato' Cikgu Azman", 51637, 16260),
        "Padang Besar": ("Rushdan Bin Rusmi", 24267, 12514),
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
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != 222 or len(boundary_codes) != 222 or boundary_names != set(groups):
        raise SystemExit(f"Boundary mismatch: {sorted(boundary_names ^ set(groups))}")
    print("Malaysia GE15 validation passed: 222 constituencies, 945 candidates, all totals and boundaries matched")


if __name__ == "__main__":
    main()
