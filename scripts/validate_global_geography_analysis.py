#!/usr/bin/env python3
"""Validate all generated international political-geography assets."""

from __future__ import annotations

import json

from build_global_geography_analysis import (
    BLOCS,
    MAPPERS,
    OUTPUT_PATHS,
    SPECS,
    build_payloads,
)


EXAMPLES = {
    "New Zealand": {"Labour Party": "Labour", "National Party": "National", "Māori Party": "Te Pāti Māori"},
    "Sweden": {"S": "Social Democrats", "SD": "Sweden Democrats", "MP": "Greens"},
    "South Africa": {"ANC": "ANC", "DA": "DA", "MK": "MK", "COPE": "Other"},
    "Taiwan": {"Democratic Progressive Party": "DPP", "Kuomintang": "KMT", "People First Party": "Third party"},
    "Türkiye": {"Recep Tayyip Erdoğan": "Erdoğan", "Kemal Kılıçdaroğlu": "CHP / main opposition", "Selahattin Demirtaş": "Kurdish left"},
    "United States": {"Democratic": "Democratic", "Republican": "Republican", "Other": "Other"},
    "Germany": {"CDU": "CDU / CSU", "CSU": "CDU / CSU", "DIE LINKE": "The Left", "BSW": "BSW"},
    "Poland": {"Andrzej Duda": "PiS-backed", "Rafał Trzaskowski": "Civic Coalition", "Sławomir Mentzen": "Confederation right"},
    "Spain": {"PSOE": "PSOE / PSC", "PP": "PP", "VOX": "Vox", "SUMAR": "Broad left", "ERC": "Regional parties"},
    "Portugal": {"PPD/PSD.CDS-PP": "AD / PSD-CDS", "PS": "PS", "CH": "Chega", "B.E.": "Left Bloc"},
    "Netherlands": {"PVV": "PVV", "GL-PvdA": "GL-PvdA", "PvdD": "SP / PvdD", "Volt": "Other"},
}


def main() -> None:
    for jurisdiction, examples in EXAMPLES.items():
        mapper = MAPPERS[jurisdiction]
        for label, expected in examples.items():
            actual = mapper(label)
            if actual != expected:
                raise SystemExit(f"{jurisdiction}: {label!r} mapped to {actual!r}, expected {expected!r}")

    expected_payloads = build_payloads()
    actual_payloads = {
        jurisdiction: json.loads(path.read_text(encoding="utf-8"))
        for jurisdiction, path in OUTPUT_PATHS.items()
    }
    if actual_payloads != expected_payloads:
        raise SystemExit("Global geography assets are stale; run python3 scripts/build_global_geography_analysis.py")

    expected_keys = {str(specification["analysisKey"]) for specification in SPECS}
    actual_keys = {
        key
        for payload in actual_payloads.values()
        for key in payload["elections"]
    }
    if actual_keys != expected_keys:
        raise SystemExit(f"Unexpected analysis keys: missing={expected_keys - actual_keys}, extra={actual_keys - expected_keys}")

    elections = {
        key: election
        for payload in actual_payloads.values()
        for key, election in payload["elections"].items()
    }
    comparison_count = 0
    area_count = 0
    for key, election in elections.items():
        areas = election["areas"]
        area_count += len(areas)
        expected_blocs = set(BLOCS[election["jurisdiction"]])
        if set(election["blocs"]) != expected_blocs:
            raise SystemExit(f"{key}: unexpected bloc list")
        if set(election["colors"]) != expected_blocs:
            raise SystemExit(f"{key}: colour definitions do not match blocs")
        if not areas:
            raise SystemExit(f"{key}: no areas")
        for district, area in areas.items():
            shares = area["blocs"]
            if set(shares) != expected_blocs:
                raise SystemExit(f"{key} {district}: unexpected bloc set")
            if any(not 0 <= float(value) <= 100 for value in shares.values()):
                raise SystemExit(f"{key} {district}: vote share outside 0–100")
            total = sum(float(value) for value in shares.values())
            if not 99.99 <= total <= 100.01:
                raise SystemExit(f"{key} {district}: bloc shares sum to {total:.3f}%")

        comparison_key = election.get("comparisonKey")
        if comparison_key:
            comparison_count += 1
            previous = elections.get(comparison_key)
            if not previous:
                raise SystemExit(f"{key}: comparison {comparison_key} is missing")
            if previous["boundaryGroup"] != election["boundaryGroup"]:
                raise SystemExit(f"{key}: comparison crosses boundary groups")
            if previous["historyGroup"] != election["historyGroup"]:
                raise SystemExit(f"{key}: comparison crosses history groups")
            if set(previous["areas"]) != set(areas):
                raise SystemExit(f"{key}: comparison area names differ")

        neighbour_source_key = election.get("neighbourSourceKey")
        source = elections.get(neighbour_source_key) if neighbour_source_key else election
        if not source or set(source.get("neighbours", {})) != set(areas):
            raise SystemExit(f"{key}: nearest-neighbour coverage is incomplete")
        for district, neighbours in source["neighbours"].items():
            if district in neighbours or len(neighbours) != min(4, len(areas) - 1):
                raise SystemExit(f"{key} {district}: invalid nearest-neighbour list")
            if not set(neighbours) <= set(areas):
                raise SystemExit(f"{key} {district}: unknown nearest neighbour")

    if len(elections) != 40 or area_count != 20449 or comparison_count != 19:
        raise SystemExit(
            f"Unexpected totals: {len(elections)} views, {area_count} areas, {comparison_count} comparisons"
        )

    print(
        f"Global geography analysis passed: {len(elections)} views, "
        f"{area_count} area records, {comparison_count} same-boundary comparisons"
    )


if __name__ == "__main__":
    main()
