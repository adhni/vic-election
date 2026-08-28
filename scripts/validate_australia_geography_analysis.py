#!/usr/bin/env python3
"""Validate the generated Australian political-geography analysis asset."""

from __future__ import annotations

import json

from build_australia_geography_analysis import BLOCS, OUTPUT_PATH, build_payload, party_bloc


def main() -> None:
    bloc_examples = {
        "Australian Labor Party - Victorian Branch": "Labor",
        "Democratic Labour Party (DLP)": "Other",
        "Liberal Party": "Coalition",
        "Liberal Democrats": "Other",
        "Australian Greens": "Greens",
        "Outdoor Recreation Party (Stop The Greens)": "Other",
        "Independent": "Independent",
    }
    for label, expected_bloc in bloc_examples.items():
        if party_bloc(label) != expected_bloc:
            raise SystemExit(f"Party normalisation failed for {label!r}")

    actual = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    expected = build_payload()
    if actual != expected:
        raise SystemExit(
            f"{OUTPUT_PATH} is stale; run python3 scripts/build_australia_geography_analysis.py"
        )

    elections = actual["elections"]
    comparison_count = 0
    for key, election in elections.items():
        areas = election["areas"]
        if not areas:
            raise SystemExit(f"{key}: no geography-analysis areas")
        for district, area in areas.items():
            shares = area["blocs"]
            if set(shares) != set(BLOCS):
                raise SystemExit(f"{key} {district}: unexpected bloc set")
            if any(not 0 <= float(value) <= 100 for value in shares.values()):
                raise SystemExit(f"{key} {district}: vote share outside 0–100")
            represented_votes = sum(float(value) for value in shares.values())
            if not 99.5 <= represented_votes <= 100.01:
                raise SystemExit(f"{key} {district}: bloc shares sum to {represented_votes:.3f}%")

        comparison_key = election.get("comparisonKey")
        if comparison_key:
            comparison_count += 1
            previous = elections.get(comparison_key)
            if not previous:
                raise SystemExit(f"{key}: comparison election {comparison_key} is missing")
            if previous["boundaryGroup"] != election["boundaryGroup"]:
                raise SystemExit(f"{key}: comparison does not use the same boundary group")
            if int(previous["year"]) >= int(election["year"]):
                raise SystemExit(f"{key}: comparison election is not earlier")
            if set(previous["areas"]) != set(areas):
                raise SystemExit(f"{key}: same-boundary comparison electorate names do not match")

    if comparison_count != 5:
        raise SystemExit(f"Expected 5 same-boundary comparison pairs, found {comparison_count}")

    print(
        "Australian geography analysis passed: "
        f"{len(elections)} elections, "
        f"{sum(len(election['areas']) for election in elections.values())} electorate records, "
        f"{comparison_count} same-boundary comparisons"
    )


if __name__ == "__main__":
    main()
