#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


YEARS = (2024, 2022, 2020, 2018, 2016)
EXPECTED_COUNTY_AREAS = {
    2024: 1875,
    2022: 2045,
    2020: 2284,
    2018: 1874,
    2016: 2059,
}
EXPECTED_STATE_RACES = {2024: 33, 2022: 34, 2020: 33, 2018: 33, 2016: 34}
EXPECTED_STATE_WINS = {
    2024: Counter({"Democratic": 17, "Republican": 14, "Independent": 2}),
    2022: Counter({"Republican": 19, "Democratic": 15}),
    2020: Counter({"Republican": 20, "Democratic": 13}),
    2018: Counter({"Democratic": 21, "Republican": 10, "Independent": 2}),
    2016: Counter({"Republican": 22, "Democratic": 12}),
}
SPOT_CHECKS = {
    2024: ("Texas", "Ted Cruz"),
    2022: ("Georgia", "Raphael Warnock"),
    2020: ("Georgia", "Jon Ossoff"),
    2018: ("Indiana", "Mike Braun"),
    2016: ("Louisiana", "John Kennedy"),
}
EXCLUDED_SPECIAL_CANDIDATES = {
    2022: {"Markwayne Mullin"},
    2020: {"Raphael Warnock", "Kelly Loeffler"},
    2018: {"Tina Smith", "Cindy Hyde-Smith"},
}
KNOWN_COUNTY_WINNER_DIFFERENCES = {
    (2016, "New Hampshire"): ("Kelly Ayotte", "Maggie Hassan"),
}
REQUIRED_FIELDS = {
    "district",
    "elected_member",
    "elected_party",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "row_type",
    "candidate",
    "candidate_party",
    "votes",
    "electorate_type",
    "constituency_code",
    "contest_status",
    "result_note",
}


def read_groups(path: Path) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED_FIELDS.issubset(reader.fieldnames or []):
            raise SystemExit(f"{path}: required Senate fields are missing")
        rows = list(reader)
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["constituency_code"]].append(row)
    return rows, groups


def validate_rows(
    year: int,
    geography: str,
) -> tuple[dict[str, list[dict[str, str]]], set[str], Counter]:
    path = Path(f"data/us_{year}_senate_{geography}_fpp.csv")
    rows, groups = read_groups(path)
    expected = (
        EXPECTED_COUNTY_AREAS[year]
        if geography == "county"
        else EXPECTED_STATE_RACES[year]
    )
    if len(groups) != expected:
        raise SystemExit(f"{path}: expected {expected} areas, found {len(groups)}")

    winners = Counter()
    state_names = set()
    expected_status = "compiled" if geography == "county" else "official"
    prefix = f"US-SENATE-{geography.upper()}-"
    for code, area_rows in groups.items():
        if not code.startswith(prefix):
            raise SystemExit(f"{path}: invalid constituency code {code}")
        candidates = [row["candidate"] for row in area_rows]
        if len(area_rows) < 2 or len(candidates) != len(set(candidates)):
            raise SystemExit(f"{path} {code}: candidates are missing or duplicated")
        metadata = area_rows[0]
        stable_fields = (
            "district",
            "elected_member",
            "elected_party",
            "formal_votes",
            "informal_votes",
            "total_votes",
            "turnout_pct",
            "electorate_type",
            "contest_status",
            "result_note",
        )
        if any(
            row[field] != metadata[field]
            for row in area_rows
            for field in stable_fields
        ):
            raise SystemExit(f"{path} {code}: inconsistent area metadata")
        if any(row["row_type"] != "first" or row["round_number"] != "0" for row in area_rows):
            raise SystemExit(f"{path} {code}: expected compact FPP rows at synthetic round zero")
        votes = [int(row["votes"]) for row in area_rows]
        formal = int(metadata["formal_votes"])
        if (
            min(votes) <= 0
            or sum(votes) != formal
            or int(metadata["informal_votes"]) != 0
            or int(metadata["total_votes"]) != formal
        ):
            raise SystemExit(f"{path} {code}: vote totals do not reconcile")
        if int(metadata["enrolment"]) or float(metadata["turnout_pct"]):
            raise SystemExit(f"{path} {code}: unsupported turnout metadata should be unavailable")
        if metadata["contest_status"] != expected_status:
            raise SystemExit(f"{path} {code}: expected {expected_status} source status")
        if "special elections are excluded" not in metadata["result_note"]:
            raise SystemExit(f"{path} {code}: regular-election scope note is missing")
        ranked = sorted(area_rows, key=lambda row: (-int(row["votes"]), row["candidate"]))
        winner = ranked[0]
        if (metadata["elected_member"], metadata["elected_party"]) != (
            winner["candidate"],
            winner["candidate_party"],
        ):
            raise SystemExit(f"{path} {code}: winner metadata does not match candidate totals")
        winners[winner["candidate_party"]] += 1
        if geography == "county":
            state_names.add(metadata["electorate_type"])
        else:
            state_names.add(metadata["district"])

    candidate_names = {row["candidate"] for row in rows}
    excluded = EXCLUDED_SPECIAL_CANDIDATES.get(year, set()) & candidate_names
    if excluded:
        raise SystemExit(f"{path}: concurrent special-election candidates leaked in: {sorted(excluded)}")
    return groups, state_names, winners


def validate_boundary(path: Path, groups: dict[str, list[dict[str, str]]]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    boundary_codes = {
        str(feature.get("properties", {}).get("constituency_code", ""))
        for feature in features
    }
    result_codes = set(groups)
    if len(features) != len(groups) or boundary_codes != result_codes:
        raise SystemExit(
            f"{path}: boundary/result mismatch "
            f"({len(features)} features, {len(groups)} result areas)"
        )
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{path}: invalid geometry for {feature['properties'].get('district')}"
            )


def aggregated_winner(groups: dict[str, list[dict[str, str]]], state: str) -> str:
    totals = Counter()
    for area_rows in groups.values():
        if area_rows[0]["electorate_type"] != state:
            continue
        for row in area_rows:
            totals[row["candidate"]] += int(row["votes"])
    return totals.most_common(1)[0][0]


def main() -> None:
    for year in YEARS:
        county_groups, county_states, _ = validate_rows(year, "county")
        state_groups, state_states, state_wins = validate_rows(year, "state")
        if county_states != state_states:
            raise SystemExit(f"{year}: county and official state coverage differ")
        if state_wins != EXPECTED_STATE_WINS[year]:
            raise SystemExit(f"{year}: regular-seat winner counts changed: {state_wins}")
        for state_code, rows in state_groups.items():
            state = rows[0]["district"]
            county_winner = aggregated_winner(county_groups, state)
            official_winner = rows[0]["elected_member"]
            known = KNOWN_COUNTY_WINNER_DIFFERENCES.get((year, state))
            if known:
                if (county_winner, official_winner) != known:
                    raise SystemExit(f"{year} {state}: known county/state difference changed")
            elif county_winner != official_winner:
                raise SystemExit(f"{year} {state}: county and official winner disagree")
        state, winner = SPOT_CHECKS[year]
        state_rows = next(
            rows for rows in state_groups.values() if rows[0]["district"] == state
        )
        if state_rows[0]["elected_member"] != winner:
            raise SystemExit(f"{year} {state}: decisive-result spot check failed")
        validate_boundary(
            Path(f"data/us_senate_{year}_county_boundaries.geojson"),
            county_groups,
        )
        validate_boundary(
            Path(f"data/us_senate_{year}_state_boundaries.geojson"),
            state_groups,
        )
    print(
        "U.S. Senate validation passed: 2016-2024 regular elections only, "
        "county/reporting-area and official state views, exact joins and totals"
    )


if __name__ == "__main__":
    main()
