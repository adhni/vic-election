#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_japan_house import EXPECTED, PREFECTURES


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Japan House constituency data")
    parser.add_argument("--year", type=int, choices=(2026, 2024), required=True)
    args = parser.parse_args()
    expected = EXPECTED[args.year]
    with Path(f"data/japan_{args.year}_house_fpp.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 289 or len(rows) != expected["candidates"]:
        raise SystemExit(f"{args.year}: expected 289 constituencies/{expected['candidates']} candidates")
    winners = Counter()
    codes = set()
    whole_votes = 0
    for district, district_rows in groups.items():
        metadata = district_rows[0]
        results = sorted(
            [(row["candidate"], row["candidate_party"], int(row["votes"])) for row in district_rows],
            key=lambda item: (-item[2], item[0]),
        )
        formal = sum(item[2] for item in results)
        if any(row["row_type"] != "first" or row["contest_status"] != "official" for row in district_rows):
            raise SystemExit(f"{district}: expected compact official FPTP rows")
        if int(metadata["formal_votes"]) != formal or int(metadata["total_votes"]) != formal:
            raise SystemExit(f"{district}: candidate totals do not reconcile")
        if metadata["enrolment"] != "0" or metadata["turnout_pct"] or metadata["informal_votes"] != "0":
            raise SystemExit(f"{district}: unavailable turnout fields must remain blank/zero")
        if (metadata["elected_member"], metadata["elected_party"]) != results[0][:2]:
            raise SystemExit(f"{district}: winner metadata does not match the vote leader")
        if "fractional ambiguous ballots" not in metadata["result_note"]:
            raise SystemExit(f"{district}: missing official-total disclosure")
        winners[results[0][1]] += 1
        codes.add(metadata["constituency_code"])
        whole_votes += formal
    if winners != expected["winners"] or whole_votes != expected["whole_votes"] or len(codes) != 289:
        raise SystemExit(f"{args.year}: national totals changed: {whole_votes}, {winners}")

    geojson = json.loads(Path("data/japan_2022_house_constituency_schematic.geojson").read_text())
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != 289 or boundary_names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"{args.year}: schematic/result mismatch")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{feature['properties']['district']}: invalid schematic geometry")
        if feature["properties"].get("geometry_note") != (
            "Schematic constituency map with metropolitan insets; not a legal-boundary GIS layer"
        ):
            raise SystemExit("Schematic features must retain the map disclosure")
    if sum(seats for _, _, seats in PREFECTURES.values()) != 289:
        raise SystemExit("Japanese post-2022 constituency allocation changed")
    print(
        f"Japan House {args.year} validation passed: 289 constituencies, "
        f"{len(rows):,} candidates, official winners and schematic matched"
    )


if __name__ == "__main__":
    main()
