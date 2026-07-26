#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_us_house import ELECTIONS, EXPECTED_SEATS, YEARS


SPOT_CHECKS = {
    2024: ("Alaska at-large", "Nick Begich", 159_550, 6_722),
    2022: ("Maine 2nd", "Jared F. Golden", 165_136, 18_994),
    2020: ("Iowa 2nd", "Mariannette Miller-Meeks", 196_964, 6),
    2018: ("Maine 2nd", "Jared F. Golden", 142_440, 3_509),
    2016: ("Minnesota 1st", "Timothy J. Walz", 169_071, 2_547),
}


def validate_year(year: int) -> tuple[int, Counter[str]]:
    config = ELECTIONS[year]
    csv_path = Path(f"data/us_{year}_house_fpp.csv")
    boundary_path = Path(f"data/us_{year}_congressional_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != EXPECTED_SEATS or len(rows) != config["expected_candidates"]:
        raise SystemExit(
            f"{year}: unexpected dimensions: {len(groups)} districts, {len(rows)} rows"
        )

    winners: Counter[str] = Counter()
    states: Counter[str] = Counter()
    codes = set()
    national = Counter()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        if len(first) != len(district_rows) or len({row["candidate"] for row in first}) != len(first):
            raise SystemExit(f"{year} {district}: duplicate candidates or non-compact FPTP rows")
        meta = first[0]
        formal = int(meta["formal_votes"])
        informal = int(meta["informal_votes"])
        total = int(meta["total_votes"])
        if sum(int(row["votes"]) for row in first) != formal or total != formal + informal:
            raise SystemExit(f"{year} {district}: vote totals do not reconcile")
        if int(meta["enrolment"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{year} {district}: unsupported turnout metadata should be unavailable")

        ranked = sorted(first, key=lambda row: (-int(row["votes"]), row["candidate"]))
        status = meta["contest_status"]
        if status == "void":
            if year != 2018 or district != "North Carolina 9th":
                raise SystemExit(f"{year} {district}: unexpected void contest")
            if (meta["elected_member"], meta["elected_party"]) != ("No certified winner", "Other"):
                raise SystemExit("2018 North Carolina 9th: void-result metadata changed")
        else:
            winner = ranked[0]
            if (meta["elected_member"], meta["elected_party"]) != (
                winner["candidate"],
                winner["candidate_party"],
            ):
                raise SystemExit(f"{year} {district}: winner metadata does not match totals")
            expected_status = "uncontested" if len(first) == 1 else "official"
            if status != expected_status:
                raise SystemExit(f"{year} {district}: invalid contest status {status!r}")

        winners[meta["elected_party"]] += 1
        states[meta["electorate_type"]] += 1
        codes.add(meta["constituency_code"])
        national["total"] += total

    if winners != Counter(config["expected_winners"]):
        raise SystemExit(f"{year}: unexpected winning-party totals: {winners}")
    if states != Counter(config["seats"]):
        raise SystemExit(f"{year}: unexpected state apportionment")
    if len(codes) != EXPECTED_SEATS:
        raise SystemExit(f"{year}: expected {EXPECTED_SEATS} unique district codes")

    district, winner, votes, margin = SPOT_CHECKS[year]
    ranked = sorted(groups[district], key=lambda row: (-int(row["votes"]), row["candidate"]))
    if ranked[0]["candidate"] != winner or int(ranked[0]["votes"]) != votes:
        raise SystemExit(f"{year} {district}: winner spot check failed")
    if int(ranked[0]["votes"]) - int(ranked[1]["votes"]) != margin:
        raise SystemExit(f"{year} {district}: margin spot check failed")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != EXPECTED_SEATS or names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"{year}: boundary/result mismatch: {sorted(names ^ set(groups))}")

    longitudes = []

    def collect_longitudes(coordinates) -> None:
        if coordinates and isinstance(coordinates[0], (int, float)):
            longitudes.append(coordinates[0])
            return
        for part in coordinates:
            collect_longitudes(part)

    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{year} {feature['properties']['district']}: invalid geometry")
        collect_longitudes(feature["geometry"]["coordinates"])
    longitude_span = max(longitudes) - min(longitudes)
    if longitude_span > 130 or max(longitudes) > 0:
        raise SystemExit(
            f"{year}: U.S. map has an unnormalised longitude span of {longitude_span:.1f}"
        )
    return national["total"], winners


def main() -> None:
    for year in YEARS:
        total, winners = validate_year(year)
        result = " / ".join(
            f"{count} {party}" for party, count in sorted(winners.items())
        )
        print(
            f"U.S. House {year} validation passed: {EXPECTED_SEATS} districts, "
            f"{ELECTIONS[year]['expected_candidates']:,} candidate rows, {result}; "
            f"{total:,} district ballots represented"
        )


if __name__ == "__main__":
    main()
