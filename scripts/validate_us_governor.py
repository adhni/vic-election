#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


YEARS = (2024, 2022, 2020, 2018, 2016)
EXPECTED_AREAS = {
    2024: (564, 11),
    2022: (2_148, 36),
    2020: (527, 11),
    2018: (2_145, 36),
    2016: (600, 12),
}
EXPECTED_STATE_WINS = {
    2024: Counter({"Republican": 8, "Democratic": 3}),
    2022: Counter({"Republican": 18, "Democratic": 18}),
    2020: Counter({"Republican": 8, "Democratic": 3}),
    2018: Counter({"Republican": 20, "Democratic": 16}),
    2016: Counter({"Republican": 6, "Democratic": 6}),
}
SPOT_CHECKS = {
    2024: ("North Carolina", "Josh Stein", 3_068_605),
    2022: ("Arizona", "Katie Hobbs", 1_290_701),
    2020: ("North Carolina", "Roy Cooper", 2_834_790),
    2018: ("Wisconsin", "Tony Evers", 1_324_307),
    2016: ("North Carolina", "Roy Cooper", 2_309_157),
}
STABLE_FIELDS = (
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "electorate_type",
    "constituency_code",
    "contest_status",
    "result_note",
)


def read_groups(path: Path) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    return rows, groups


def validate_rows(
    year: int, geography: str
) -> tuple[dict[str, list[dict[str, str]]], set[str], Counter[str]]:
    path = Path(f"data/us_{year}_governor_{geography}_fpp.csv")
    rows, groups = read_groups(path)
    expected = EXPECTED_AREAS[year][0 if geography == "county" else 1]
    if len(groups) != expected:
        raise SystemExit(f"{path}: expected {expected} areas, found {len(groups)}")

    codes: set[str] = set()
    winners: Counter[str] = Counter()
    for district, area_rows in groups.items():
        if len(area_rows) < 2 or len({row["candidate"] for row in area_rows}) != len(area_rows):
            raise SystemExit(f"{path} {district}: expected at least two unique candidates")
        if any(row["row_type"] != "first" or row["round_number"] != "0" for row in area_rows):
            raise SystemExit(f"{path} {district}: expected compact FPP rows at round zero")
        meta = area_rows[0]
        if any(
            row[field] != meta[field]
            for row in area_rows
            for field in STABLE_FIELDS
        ):
            raise SystemExit(f"{path} {district}: inconsistent area metadata")
        votes = [int(row["votes"]) for row in area_rows]
        formal = int(meta["formal_votes"])
        informal = int(meta["informal_votes"])
        total = int(meta["total_votes"])
        if min(votes) < 0 or sum(votes) != formal or informal != 0 or total != formal:
            raise SystemExit(f"{path} {district}: vote totals do not reconcile")
        if int(meta["enrolment"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{path} {district}: unsupported turnout metadata should be unavailable")
        ranked = sorted(area_rows, key=lambda row: (-int(row["votes"]), row["candidate"]))
        winner = ranked[0]
        if (meta["elected_member"], meta["elected_party"]) != (
            winner["candidate"], winner["candidate_party"]
        ):
            raise SystemExit(f"{path} {district}: winner metadata does not match totals")
        if int(meta["majority"]) != int(winner["votes"]) - int(ranked[1]["votes"]):
            raise SystemExit(f"{path} {district}: majority does not match top two candidates")
        if meta["contest_status"] != "compiled":
            raise SystemExit(f"{path} {district}: unexpected contest status")
        codes.add(meta["constituency_code"])
        winners[winner["candidate_party"]] += 1

    if len(codes) != expected:
        raise SystemExit(f"{path}: constituency codes are not unique")
    return groups, codes, winners


def validate_aggregation(
    year: int,
    county_groups: dict[str, list[dict[str, str]]],
    state_groups: dict[str, list[dict[str, str]]],
) -> None:
    county_totals: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    for area_rows in county_groups.values():
        state = area_rows[0]["electorate_type"]
        for row in area_rows:
            county_totals[state][(row["candidate"], row["candidate_party"])] += int(row["votes"])
    state_totals = {
        state: Counter({
            (row["candidate"], row["candidate_party"]): int(row["votes"])
            for row in area_rows
        })
        for state, area_rows in state_groups.items()
    }
    if state_totals != county_totals:
        changed = sorted(set(state_totals) ^ set(county_totals))
        raise SystemExit(f"{year}: county/state aggregation mismatch: {changed}")


def collect_longitudes(coordinates, target: list[float]) -> None:
    if coordinates and isinstance(coordinates[0], (int, float)):
        target.append(float(coordinates[0]))
        return
    for part in coordinates:
        collect_longitudes(part, target)


def validate_boundary(
    path: Path,
    groups: dict[str, list[dict[str, str]]],
    codes: set[str],
) -> None:
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
    total_areas = 0
    total_races = 0
    for year in YEARS:
        county_groups, county_codes, _ = validate_rows(year, "county")
        state_groups, state_codes, state_wins = validate_rows(year, "state")
        if state_wins != EXPECTED_STATE_WINS[year]:
            raise SystemExit(f"{year}: unexpected state winners {state_wins}")
        validate_aggregation(year, county_groups, state_groups)
        validate_boundary(
            Path(f"data/us_governor_{year}_county_boundaries.geojson"),
            county_groups,
            county_codes,
        )
        validate_boundary(
            Path(f"data/us_governor_{year}_state_boundaries.geojson"),
            state_groups,
            state_codes,
        )
        state, candidate, votes = SPOT_CHECKS[year]
        ranked = sorted(
            state_groups[state], key=lambda row: (-int(row["votes"]), row["candidate"])
        )
        if ranked[0]["candidate"] != candidate or int(ranked[0]["votes"]) != votes:
            raise SystemExit(f"{year} {state}: winner spot check failed")
        total_areas += len(county_groups)
        total_races += len(state_groups)

    alaska = next(iter(read_groups(Path("data/us_2022_governor_county_fpp.csv"))[1]["Alaska statewide"]))
    if "statewide fallback" not in alaska["result_note"].lower():
        raise SystemExit("2022 Alaska: ranked-choice statewide fallback note is missing")
    print(
        "U.S. governor validation passed: "
        f"{total_races} races across {total_areas:,} mapped county/reporting areas, "
        "exact county/state aggregation and boundary joins"
    )


if __name__ == "__main__":
    main()
