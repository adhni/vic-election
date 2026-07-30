#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


CONFIG = {
    "taiwan_2024_president_township_fpp.csv": {
        "Ko Wen-je–Cynthia Wu": 3_690_466,
        "Lai Ching-te–Hsiao Bi-khim": 5_586_019,
        "Hou Yu-ih–Jaw Shaw-kong": 4_671_021,
    },
    "taiwan_2020_president_township_fpp.csv": {
        "James Soong–Sandra Yu": 608_590,
        "Han Kuo-yu–Chang San-cheng": 5_522_119,
        "Tsai Ing-wen–Lai Ching-te": 8_170_231,
    },
    "taiwan_2016_president_township_fpp.csv": {
        "Eric Chu–Jennifer Wang": 3_813_365,
        "Tsai Ing-wen–Chen Chien-jen": 6_894_744,
        "James Soong–Hsu Hsin-ying": 1_576_861,
    },
}
BOUNDARY_NAME = "taiwan_township_boundaries.geojson"


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as exc:
        raise SystemExit(
            f"Invalid {field!r} in {row.get('district', 'unknown township')}"
        ) from exc


def validate_csv(
    data_dir: Path, name: str, expected: dict[str, int],
    boundary_counties: dict[str, str],
) -> None:
    path = data_dir / name
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_township: dict[str, list[dict[str, str]]] = defaultdict(list)
    totals: Counter[str] = Counter()
    for row in rows:
        if row["row_type"] != "first" or integer(row, "round_number") != 0:
            raise SystemExit(f"{path}: non-compact row in {row['district']}")
        if row["contest_status"] != "official":
            raise SystemExit(f"{path}: non-official row in {row['district']}")
        code = row["constituency_code"]
        by_township[code].append(row)
        votes = integer(row, "votes")
        if votes < 0:
            raise SystemExit(f"{path}: negative votes in {row['district']}")
        totals[row["candidate"]] += votes
    if set(by_township) != set(boundary_counties):
        raise SystemExit(f"{path}: CSV/boundary code mismatch")
    if dict(totals) != expected:
        raise SystemExit(
            f"{path}: candidate totals changed\nexpected {expected}\nactual {dict(totals)}"
        )

    metadata = (
        "district", "elected_member", "elected_party", "enrolment", "formal_votes",
        "informal_votes", "total_votes", "turnout_pct", "majority",
        "electorate_type", "contest_status", "result_note",
    )
    for code, township_rows in by_township.items():
        if len(township_rows) != 3:
            raise SystemExit(f"{path}: expected three tickets for {code}")
        for field in metadata:
            if len({row[field] for row in township_rows}) != 1:
                raise SystemExit(f"{path}: inconsistent {field} for {code}")
        first = township_rows[0]
        if first["electorate_type"] != boundary_counties[code]:
            raise SystemExit(f"{path}: county/city mismatch for {code}")
        ordered = sorted(
            (integer(row, "votes"), row["candidate"], row["candidate_party"])
            for row in township_rows
        )
        formal = sum(votes for votes, _, _ in ordered)
        if formal != integer(first, "formal_votes"):
            raise SystemExit(f"{path}: formal-vote mismatch for {code}")
        total = integer(first, "total_votes")
        if formal + integer(first, "informal_votes") != total:
            raise SystemExit(f"{path}: ballot-total mismatch for {code}")
        enrolment = integer(first, "enrolment")
        turnout = float(first["turnout_pct"])
        if abs(turnout - total * 100 / enrolment) > 0.01:
            raise SystemExit(f"{path}: turnout mismatch for {code}")
        winner_votes, winner, winner_party = ordered[-1]
        runner_up = ordered[-2][0]
        if (
            first["elected_member"] != winner
            or first["elected_party"] != winner_party
        ):
            raise SystemExit(f"{path}: winner mismatch for {code}")
        if integer(first, "majority") != winner_votes - runner_up:
            raise SystemExit(f"{path}: majority mismatch for {code}")
    print(f"{name}: 368 townships/districts, {len(rows)} candidate rows")


def main() -> None:
    data_dir = Path("data")
    boundary = json.loads((data_dir / BOUNDARY_NAME).read_text(encoding="utf-8"))
    features = boundary.get("features", [])
    codes = [feature.get("properties", {}).get("constituency_code") for feature in features]
    if len(codes) != 368 or len(set(codes)) != 368:
        raise SystemExit(f"{BOUNDARY_NAME}: expected 368 unique township codes")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{BOUNDARY_NAME}: invalid geometry for "
                f"{feature['properties'].get('constituency_code')}"
            )
    boundary_counties = {
        feature["properties"]["constituency_code"]: feature["properties"]["county"]
        for feature in features
    }
    for name, expected in CONFIG.items():
        validate_csv(data_dir, name, expected, boundary_counties)
    print("Taiwan presidential validation passed.")


if __name__ == "__main__":
    main()
