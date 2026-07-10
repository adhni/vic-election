#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


REQUIRED = {
    "district",
    "elected_members",
    "members_to_elect",
    "quota",
    "formal_votes",
    "row_type",
    "candidate",
    "candidate_party",
    "candidate_elected",
    "candidate_elected_order",
    "votes",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_geojson(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def surname_key(value: str) -> str:
    text = value.strip()
    if "," in text:
        text = text.split(",", 1)[0]
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def validate_rows(rows: list[dict[str, str]], expected_divisions: int, expected_members: int) -> set[str]:
    if not rows:
        raise SystemExit("Preference CSV is empty")
    missing = REQUIRED - set(rows[0])
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")

    divisions = {row["district"] for row in rows}
    if len(divisions) != expected_divisions:
        raise SystemExit(f"Expected {expected_divisions} divisions, found {len(divisions)}")

    for division in sorted(divisions):
        district_rows = [row for row in rows if row["district"] == division]
        first_rows = [row for row in district_rows if row["row_type"] == "first"]
        final_rows = [row for row in district_rows if row["row_type"] == "final"]
        if not first_rows:
            raise SystemExit(f"{division}: missing first preference rows")
        if not final_rows:
            raise SystemExit(f"{division}: missing final rows")
        for row in district_rows:
            candidate = row["candidate"].strip()
            if candidate.upper().startswith("RESULTS COUNT"):
                raise SystemExit(f"{division}: workbook header row was parsed as a candidate")

        formal_votes = int(float(district_rows[0]["formal_votes"]))
        first_total = sum(int(float(row["votes"])) for row in first_rows)
        if first_total != formal_votes:
            raise SystemExit(f"{division}: first preference total {first_total} != formal votes {formal_votes}")

        first_surnames = {surname_key(row["candidate"]) for row in first_rows}
        final_surnames = {
            surname_key(row["candidate"])
            for row in final_rows
            if int(float(row["votes"])) > 0 or row["candidate_elected"] == "True"
        }
        missing_first = sorted(final_surnames - first_surnames)
        missing_final = []
        if missing_first or missing_final:
            raise SystemExit(
                f"{division}: candidate surname mismatch between first and final rows; "
                f"missing first={missing_first}, missing final={missing_final}"
            )

        elected = [row for row in final_rows if row["candidate_elected"] == "True"]
        if len(elected) != expected_members:
            raise SystemExit(f"{division}: expected {expected_members} elected candidates, found {len(elected)}")
        orders = sorted(int(row["candidate_elected_order"]) for row in elected)
        if orders != list(range(1, expected_members + 1)):
            raise SystemExit(f"{division}: invalid elected order values {orders}")
        if int(float(district_rows[0]["quota"])) <= 0:
            raise SystemExit(f"{division}: missing quota")

    return divisions


def validate_boundaries(path: Path, divisions: set[str]) -> None:
    geojson = load_geojson(path)
    names = {feature.get("properties", {}).get("district") for feature in geojson.get("features", [])}
    if names != divisions:
        raise SystemExit(f"Boundary/result name mismatch: {sorted(names ^ divisions)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/tas_2025_preferences_long.csv"))
    parser.add_argument("--boundaries", type=Path, default=Path("data/tas_2025_district_boundaries.geojson"))
    parser.add_argument("--expected-divisions", type=int, default=5)
    parser.add_argument("--expected-members", type=int, default=7)
    args = parser.parse_args()

    rows = read_csv(args.csv)
    divisions = validate_rows(rows, args.expected_divisions, args.expected_members)
    validate_boundaries(args.boundaries, divisions)
    print(f"Rows: {len(rows)}")
    print(f"Tasmania divisions: {len(divisions)}")
    print("Tasmania Hare-Clark validation passed")


if __name__ == "__main__":
    main()
