#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_us_presidential import (
    CANDIDATES,
    EXPECTED_STATE_RECONCILIATION_SHA256,
    STATE_BY_NAME,
    YEARS,
)


EXPECTED_AREAS = {2008: 3113, 2012: 3113, 2016: 3113, 2020: 3113, 2024: 3114}
EXPECTED_LOCAL_WINS = {
    2008: Counter({"Republican": 2238, "Democratic": 875}),
    2012: Counter({"Republican": 2417, "Democratic": 696}),
    2016: Counter({"Republican": 2623, "Democratic": 490}),
    2020: Counter({"Republican": 2575, "Democratic": 538}),
    2024: Counter({"Republican": 2662, "Democratic": 452}),
}
EXPECTED_NATIONAL = {
    2008: Counter({"Democratic": 69_498_516, "Republican": 59_948_323, "Other": 1_866_981}),
    2012: Counter({"Democratic": 65_915_795, "Republican": 60_933_504, "Other": 2_236_111}),
    2016: Counter({"Democratic": 65_853_514, "Republican": 62_984_828, "Other": 7_830_934}),
    2020: Counter({"Democratic": 81_283_501, "Republican": 74_223_975, "Other": 2_922_155}),
    2024: Counter({"Democratic": 75_017_613, "Republican": 77_302_580, "Other": 2_918_109}),
}
SPOT_CHECKS = {
    2008: ("Lake County, Indiana", "Barack Obama", 139_301),
    2012: ("Miami-Dade County, Florida", "Barack Obama", 541_440),
    2016: ("Los Angeles County, California", "Hillary Clinton", 2_464_364),
    2020: ("Maricopa County, Arizona", "Joe Biden", 1_040_774),
    2024: ("Maricopa County, Arizona", "Donald Trump", 1_051_531),
}


def read_groups(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    return rows, groups


def validate_rows(year: int, geography: str):
    path = Path(f"data/us_{year}_president_{geography}_fpp.csv")
    rows, groups = read_groups(path)
    expected_areas = EXPECTED_AREAS[year] if geography == "county" else 51
    if len(groups) != expected_areas or len(rows) != expected_areas * 3:
        raise SystemExit(
            f"{path}: expected {expected_areas} areas / {expected_areas * 3} rows, "
            f"found {len(groups)} / {len(rows)}"
        )

    expected_candidates = {*CANDIDATES[year], "Other candidates"}
    codes = set()
    winners = Counter()
    totals = Counter()
    for district, area_rows in groups.items():
        if {row["candidate"] for row in area_rows} != expected_candidates:
            raise SystemExit(f"{path} {district}: candidate rows changed")
        if any(row["row_type"] != "first" or row["round_number"] != "0" for row in area_rows):
            raise SystemExit(f"{path} {district}: expected compact FPP rows at synthetic round zero")
        meta = area_rows[0]
        if any(
            row[field] != meta[field]
            for row in area_rows
            for field in (
                "formal_votes", "informal_votes", "total_votes", "elected_member",
                "elected_party", "constituency_code", "electorate_type", "contest_status",
            )
        ):
            raise SystemExit(f"{path} {district}: inconsistent area metadata")
        votes = {row["candidate"]: int(row["votes"]) for row in area_rows}
        formal = int(meta["formal_votes"])
        informal = int(meta["informal_votes"])
        total = int(meta["total_votes"])
        if min(votes.values()) < 0 or sum(votes.values()) != formal or informal != 0 or total != formal:
            raise SystemExit(f"{path} {district}: vote totals do not reconcile")
        if int(meta["enrolment"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{path} {district}: unsupported turnout metadata should remain unavailable")
        ranked = sorted(area_rows, key=lambda row: (-int(row["votes"]), row["candidate"]))
        if (meta["elected_member"], meta["elected_party"]) != (
            ranked[0]["candidate"], ranked[0]["candidate_party"]
        ):
            raise SystemExit(f"{path} {district}: winner metadata does not match totals")
        expected_status = "compiled" if geography == "county" else "official"
        if meta["contest_status"] != expected_status:
            raise SystemExit(f"{path} {district}: incorrect source status")
        codes.add(meta["constituency_code"])
        winners[ranked[0]["candidate_party"]] += 1
        for row in area_rows:
            totals[row["candidate_party"]] += int(row["votes"])

    if len(codes) != expected_areas:
        raise SystemExit(f"{path}: constituency codes are not unique")
    if geography == "county":
        if winners != EXPECTED_LOCAL_WINS[year]:
            raise SystemExit(f"{path}: unexpected local winner counts {winners}")
        district, winner, votes = SPOT_CHECKS[year]
        ranked = sorted(groups[district], key=lambda row: (-int(row["votes"]), row["candidate"]))
        if ranked[0]["candidate"] != winner or int(ranked[0]["votes"]) != votes:
            raise SystemExit(f"{path}: {district} spot check failed")
    elif totals != EXPECTED_NATIONAL[year]:
        raise SystemExit(f"{path}: official FEC national totals changed: {totals}")
    return groups, codes


def collect_longitudes(coordinates, target: list[float]) -> None:
    if coordinates and isinstance(coordinates[0], (int, float)):
        target.append(float(coordinates[0]))
        return
    for part in coordinates:
        collect_longitudes(part, target)


def validate_state_reconciliation(year: int, county_groups, state_groups) -> None:
    county_totals = defaultdict(Counter)
    state_totals = defaultdict(Counter)
    for area_rows in county_groups.values():
        state = area_rows[0]["electorate_type"]
        for row in area_rows:
            county_totals[state][row["candidate_party"].lower()] += int(row["votes"])
    for state, area_rows in state_groups.items():
        for row in area_rows:
            state_totals[state][row["candidate_party"].lower()] += int(row["votes"])
    report = {}
    for state in sorted(state_totals):
        abbr = STATE_BY_NAME[state.lower()][1]
        report[abbr] = [
            state_totals[state][party] - county_totals[state][party]
            for party in ("democratic", "republican", "other")
        ]
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_STATE_RECONCILIATION_SHA256[year]:
        changed = {abbr: delta for abbr, delta in report.items() if any(delta)}
        raise SystemExit(
            f"{year}: generated county/FEC reconciliation changed to {digest}: {changed}"
        )


def validate_boundary(path: Path, groups, codes) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != len(groups) or names != set(groups) or boundary_codes != codes:
        raise SystemExit(
            f"{path}: boundary/result mismatch "
            f"({len(features)} features, {len(groups)} result areas)"
        )
    longitudes: list[float] = []
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{path}: invalid geometry for {feature['properties']['district']}")
        collect_longitudes(feature["geometry"]["coordinates"], longitudes)
    if max(longitudes) > 0 or max(longitudes) - min(longitudes) > 130:
        raise SystemExit(f"{path}: unnormalised U.S. antimeridian span")


def main() -> None:
    historical_groups = None
    historical_codes = None
    state_boundary = Path("data/us_president_state_boundaries.geojson")
    for year in YEARS:
        county_groups, county_codes = validate_rows(year, "county")
        state_groups, state_codes = validate_rows(year, "state")
        validate_state_reconciliation(year, county_groups, state_groups)
        if year <= 2016:
            boundary = Path("data/us_president_2008_2016_county_boundaries.geojson")
            if historical_groups is None:
                historical_groups, historical_codes = county_groups, county_codes
                validate_boundary(boundary, county_groups, county_codes)
            elif set(county_groups) != set(historical_groups) or county_codes != historical_codes:
                raise SystemExit(f"{year}: shared historical county boundary is unsafe")
        else:
            boundary = Path(f"data/us_president_{year}_county_boundaries.geojson")
            validate_boundary(boundary, county_groups, county_codes)
        validate_boundary(state_boundary, state_groups, state_codes)
    print(
        "U.S. presidential validation passed: 2008-2024 county/reporting-area and "
        "official state views, exact joins, reconciled totals"
    )


if __name__ == "__main__":
    main()
