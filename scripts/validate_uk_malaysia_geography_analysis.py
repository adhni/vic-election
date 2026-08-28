#!/usr/bin/env python3
"""Validate the generated UK and Malaysia political-geography asset."""

from __future__ import annotations

import json

from build_uk_malaysia_geography_analysis import (
    BLOCS_BY_JURISDICTION,
    OUTPUT_PATH,
    build_payload,
    party_bloc,
)


def main() -> None:
    examples = {
        ("United Kingdom", "Labour"): "Labour",
        ("United Kingdom", "Conservative"): "Conservative",
        ("United Kingdom", "Liberal Democrat"): "Liberal Democrats",
        ("United Kingdom", "Reform UK"): "Reform / UKIP",
        ("United Kingdom", "The Brexit Party"): "Reform / UKIP",
        ("United Kingdom", "Scottish National Party"): "National / regional",
        ("Malaysia", "PH"): "PH / PKR-DAP",
        ("Malaysia", "DAP"): "PH / PKR-DAP",
        ("Malaysia", "BN"): "BN",
        ("Malaysia", "PAS"): "PN / PAS",
        ("Malaysia", "GPS"): "East Malaysian parties",
        ("Malaysia", "BEBAS"): "Independent",
    }
    for (jurisdiction, party), expected in examples.items():
        actual = party_bloc(jurisdiction, party)
        if actual != expected:
            raise SystemExit(f"Party normalisation failed for {jurisdiction} {party!r}: {actual}")

    actual = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    expected = build_payload()
    if actual != expected:
        raise SystemExit(
            f"{OUTPUT_PATH} is stale; run python3 scripts/build_uk_malaysia_geography_analysis.py"
        )

    elections = actual["elections"]
    if set(elections) != {
        "uk-2024", "uk-2019", "uk-2017",
        "malaysia-2022", "malaysia-2018", "malaysia-2013",
    }:
        raise SystemExit("Unexpected UK/Malaysia geography election set")

    comparison_count = 0
    for key, election in elections.items():
        areas = election["areas"]
        expected_count = 650 if election["jurisdiction"] == "United Kingdom" else 222
        if len(areas) != expected_count:
            raise SystemExit(f"{key}: expected {expected_count} areas, found {len(areas)}")
        expected_blocs = set(BLOCS_BY_JURISDICTION[election["jurisdiction"]])
        if set(election["blocs"]) != expected_blocs:
            raise SystemExit(f"{key}: unexpected election bloc list")
        for district, area in areas.items():
            shares = area["blocs"]
            if set(shares) != expected_blocs:
                raise SystemExit(f"{key} {district}: unexpected bloc set")
            if any(not 0 <= float(value) <= 100 for value in shares.values()):
                raise SystemExit(f"{key} {district}: vote share outside 0–100")
            if not 99.995 <= sum(float(value) for value in shares.values()) <= 100.005:
                raise SystemExit(f"{key} {district}: bloc shares do not sum to 100%")

        comparison_key = election.get("comparisonKey")
        if comparison_key:
            comparison_count += 1
            previous = elections.get(comparison_key)
            if not previous:
                raise SystemExit(f"{key}: missing comparison election {comparison_key}")
            if previous["boundaryGroup"] != election["boundaryGroup"]:
                raise SystemExit(f"{key}: comparison uses a different boundary group")
            if set(previous["areas"]) != set(areas):
                raise SystemExit(f"{key}: comparison constituency names differ")

    if comparison_count != 1:
        raise SystemExit(f"Expected one same-boundary comparison, found {comparison_count}")

    print(
        "UK/Malaysia geography analysis passed: "
        f"{len(elections)} elections, "
        f"{sum(len(election['areas']) for election in elections.values())} constituency records, "
        f"{comparison_count} same-boundary comparison"
    )


if __name__ == "__main__":
    main()
