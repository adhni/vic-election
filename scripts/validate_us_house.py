#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_us_house import EXPECTED_CANDIDATES, EXPECTED_SEATS, STATE_SEATS


SPOT_CHECKS = {
    "Alaska at-large": ("Nick Begich", 159_550, 6_722),
    "Maine 2nd": ("Jared F. Golden", 197_151, 2_706),
    "New York 4th": ("Laura A. Gillen", 191_760, 8_603),
}

EXPECTED_UNCONTESTED = {
    "Florida 20th", "Kentucky 5th", "Mississippi 3rd", "Oklahoma 3rd",
    "Pennsylvania 3rd", "Texas 1st", "Texas 9th", "Texas 11th", "Texas 13th", "Texas 20th",
}


def main() -> None:
    csv_path = Path("data/us_2024_house_fpp.csv")
    boundary_path = Path("data/us_2024_congressional_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != EXPECTED_SEATS or len(rows) != EXPECTED_CANDIDATES:
        raise SystemExit(f"Unexpected U.S. House dimensions: {len(groups)} districts, {len(rows)} rows")

    winners = Counter()
    states = Counter()
    codes = set()
    uncontested = []
    national = Counter()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        if len(first) != len(district_rows) or len({row["candidate"] for row in first}) != len(first):
            raise SystemExit(f"{district}: duplicate candidates or non-compact FPTP rows")
        meta = first[0]
        formal = int(meta["formal_votes"])
        informal = int(meta["informal_votes"])
        total = int(meta["total_votes"])
        candidate_votes = sum(int(row["votes"]) for row in first)
        if candidate_votes != formal or total != formal + informal:
            raise SystemExit(f"{district}: vote totals do not reconcile")
        if int(meta["enrolment"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{district}: unsupported turnout metadata should remain unavailable")
        ranked = sorted(first, key=lambda row: (-int(row["votes"]), row["candidate"]))
        winner = ranked[0]
        if (meta["elected_member"], meta["elected_party"]) != (winner["candidate"], winner["candidate_party"]):
            raise SystemExit(f"{district}: winner metadata does not match candidate totals")
        is_uncontested = meta["contest_status"] == "uncontested"
        if is_uncontested:
            uncontested.append(district)
            if len(first) != 1:
                raise SystemExit(f"{district}: invalid uncontested result")
        elif meta["contest_status"] != "official" or len(first) < 2:
            raise SystemExit(f"{district}: invalid contest status")
        winners[winner["candidate_party"]] += 1
        states[meta["electorate_type"]] += 1
        codes.add(meta["constituency_code"])
        national["formal"] += formal
        national["informal"] += informal
        national["total"] += total

    if winners != Counter({"Republican": 220, "Democratic": 215}):
        raise SystemExit(f"Unexpected winning-party totals: {winners}")
    if states != Counter(STATE_SEATS):
        raise SystemExit(f"Unexpected state apportionment: {states - Counter(STATE_SEATS)}")
    if set(uncontested) != EXPECTED_UNCONTESTED:
        raise SystemExit(f"Unexpected uncontested districts: {uncontested}")
    if len(codes) != EXPECTED_SEATS:
        raise SystemExit(f"Expected {EXPECTED_SEATS} unique Census district codes, found {len(codes)}")

    for district, (winner, votes, margin) in SPOT_CHECKS.items():
        ranked = sorted(groups[district], key=lambda row: (-int(row["votes"]), row["candidate"]))
        if ranked[0]["candidate"] != winner or int(ranked[0]["votes"]) != votes:
            raise SystemExit(f"{district}: winner spot check failed")
        if int(ranked[0]["votes"]) - int(ranked[1]["votes"]) != margin:
            raise SystemExit(f"{district}: margin spot check failed")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != EXPECTED_SEATS or names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"Boundary/result mismatch: {sorted(names ^ set(groups))}")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{feature['properties']['district']}: invalid boundary geometry")
    print(
        "U.S. House 2024 validation passed: "
        f"{EXPECTED_SEATS} districts, {EXPECTED_CANDIDATES:,} candidate rows, "
        f"220 Republican / 215 Democratic; {national['total']:,} district ballots represented"
    )


if __name__ == "__main__":
    main()
