#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import shape


CONFIG = {
    2025: (15_871_189, 567_305, 16_438_494),
    2022: (15_040_658, 532_003, 15_572_661),
    2019: (14_604_925, 579_160, 15_184_085),
}
BOUNDARY_NAME = "australia_senate_state_boundaries.geojson"
STATE_CODES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as exc:
        raise SystemExit(f"Invalid {field!r} in {row.get('district', 'unknown')}") from exc


def validate_year(year: int, expected: tuple[int, int, int], boundary_codes: set[str]) -> None:
    path = Path("data") / f"australia_senate_{year}_state_fpp.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_state: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["row_type"] != "first" or integer(row, "round_number") != 0:
            raise SystemExit(f"{path}: non-compact row")
        if row["contest_status"] != "official":
            raise SystemExit(f"{path}: non-official contest")
        by_state[row["constituency_code"]].append(row)
    if set(by_state) != boundary_codes:
        raise SystemExit(f"{path}: boundary/result code mismatch")

    formal_sum = informal_sum = total_sum = elected_sum = 0
    metadata = (
        "district", "elected_members", "elected_parties", "members_to_elect",
        "quota", "enrolment", "formal_votes", "informal_votes", "total_votes",
        "turnout_pct", "majority", "electorate_type", "result_note",
    )
    for code, state_rows in by_state.items():
        for field in metadata:
            if len({row[field] for row in state_rows}) != 1:
                raise SystemExit(f"{path}: inconsistent {field} for {code}")
        first = state_rows[0]
        members = [name.strip() for name in first["elected_members"].split(";") if name.strip()]
        parties = [name.strip() for name in first["elected_parties"].split(";") if name.strip()]
        seats = integer(first, "members_to_elect")
        if len(members) != seats or len(parties) != seats:
            raise SystemExit(f"{path}: elected senator metadata mismatch for {code}")
        if len(set(members)) != len(members):
            raise SystemExit(f"{path}: duplicate elected senator for {code}")
        votes = sorted((integer(row, "votes"), row["candidate"]) for row in state_rows)
        formal = sum(value for value, _ in votes)
        informal = integer(first, "informal_votes")
        total = integer(first, "total_votes")
        enrolment = integer(first, "enrolment")
        if formal != integer(first, "formal_votes") or formal + informal != total:
            raise SystemExit(f"{path}: ballot arithmetic mismatch for {code}")
        if integer(first, "quota") != formal // (seats + 1) + 1:
            raise SystemExit(f"{path}: quota mismatch for {code}")
        if integer(first, "majority") != votes[-1][0] - votes[-2][0]:
            raise SystemExit(f"{path}: primary-lead mismatch for {code}")
        if abs(float(first["turnout_pct"]) - total * 100 / enrolment) > 0.01:
            raise SystemExit(f"{path}: turnout mismatch for {code}")
        formal_sum += formal
        informal_sum += informal
        total_sum += total
        elected_sum += seats
    if (formal_sum, informal_sum, total_sum) != expected:
        raise SystemExit(f"{path}: national ballot totals changed")
    if elected_sum != 40:
        raise SystemExit(f"{path}: expected 40 elected senators")
    print(f"{path.name}: 8 contests, {len(rows)} group rows, 40 senators")


def main() -> None:
    boundary = json.loads((Path("data") / BOUNDARY_NAME).read_text(encoding="utf-8"))
    features = boundary.get("features", [])
    codes = [
        feature.get("properties", {}).get("constituency_code")
        for feature in features
    ]
    expected_codes = {f"AU-SEN-{state}" for state in STATE_CODES}
    if len(codes) != 8 or set(codes) != expected_codes:
        raise SystemExit(f"{BOUNDARY_NAME}: expected 8 state/territory codes")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{BOUNDARY_NAME}: invalid geometry")
    for year, expected in CONFIG.items():
        validate_year(year, expected, set(codes))
    print("Australian Senate validation passed.")


if __name__ == "__main__":
    main()
