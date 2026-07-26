#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


CONFIG = {
    2022: {
        "csv": "italy_2022_chamber_province_fpp.csv",
        "boundary": "italy_2022_province_boundaries.geojson",
        "formal": 27_069_655,
        "major": {
            "Brothers of Italy": 7_098_555,
            "Democratic Party": 5_128_861,
            "Five Star Movement": 4_178_360,
        },
    },
    2018: {
        "csv": "italy_2018_chamber_province_fpp.csv",
        "boundary": "italy_2018_province_boundaries.geojson",
        "formal": 31_537_826,
        "major": {
            "Five Star Movement": 10_221_447,
            "Democratic Party": 5_872_264,
            "Lega": 5_568_120,
        },
    },
}


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as exc:
        raise SystemExit(
            f"Invalid {field} in {row.get('district', 'unknown province')}"
        ) from exc


def validate(year: int, data_dir: Path) -> None:
    config = CONFIG[year]
    csv_path = data_dir / config["csv"]
    boundary_path = data_dir / config["boundary"]
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_area: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    party_totals: Counter[str] = Counter()
    for row in rows:
        if row["row_type"] != "first" or integer(row, "round_number") != 0:
            raise SystemExit(f"{csv_path}: non-compact row")
        if row["contest_status"] != "official":
            raise SystemExit(f"{csv_path}: unexpected contest status")
        by_area[row["constituency_code"]].append(row)
        party_totals[row["candidate_party"]] += integer(row, "votes")

    if len(by_area) != 106:
        raise SystemExit(f"{csv_path}: expected 106 provinces, got {len(by_area)}")
    if sum(party_totals.values()) != config["formal"]:
        raise SystemExit(f"{csv_path}: mapped formal-vote total changed")
    for party, expected in config["major"].items():
        if party_totals[party] != expected:
            raise SystemExit(f"{csv_path}: {party} total changed")

    metadata_fields = (
        "district", "elected_member", "elected_party", "enrolment", "formal_votes",
        "informal_votes", "total_votes", "turnout_pct", "majority", "result_note",
    )
    for code, area_rows in by_area.items():
        for field in metadata_fields:
            if len({row[field] for row in area_rows}) != 1:
                raise SystemExit(f"{csv_path}: inconsistent {field} for {code}")
        votes = sorted(
            (integer(row, "votes"), row["candidate_party"]) for row in area_rows
        )
        first = area_rows[0]
        formal = sum(value for value, _ in votes)
        if formal != integer(first, "formal_votes"):
            raise SystemExit(f"{csv_path}: formal-vote mismatch for {code}")
        if votes[-1][1] != first["elected_party"]:
            raise SystemExit(f"{csv_path}: local leader mismatch for {code}")
        informal = integer(first, "informal_votes")
        total = integer(first, "total_votes")
        if formal + informal != total:
            raise SystemExit(f"{csv_path}: ballot-total mismatch for {code}")
        enrolment = integer(first, "enrolment")
        if year == 2022:
            if not enrolment or total > enrolment:
                raise SystemExit(f"{csv_path}: invalid turnout metadata for {code}")
            expected_turnout = round(total / enrolment * 100, 2)
            if abs(float(first["turnout_pct"]) - expected_turnout) > 0.001:
                raise SystemExit(f"{csv_path}: turnout percentage mismatch for {code}")
        elif enrolment or informal or first["turnout_pct"] not in {"0", "0.0"}:
            raise SystemExit(f"{csv_path}: invented 2018 turnout metadata for {code}")

    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    boundary_codes = [
        feature.get("properties", {}).get("constituency_code")
        for feature in boundary.get("features", [])
    ]
    if len(boundary_codes) != 106 or len(set(boundary_codes)) != 106:
        raise SystemExit(f"{boundary_path}: expected 106 unique province codes")
    if set(boundary_codes) != set(by_area):
        raise SystemExit(f"{csv_path}: CSV/boundary code mismatch")
    for feature in boundary["features"]:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{boundary_path}: invalid geometry for "
                f"{feature['properties'].get('constituency_code')}"
            )
    print(f"Italy {year}: {len(by_area)} provinces, {len(rows)} rows")


def main() -> None:
    for year in (2022, 2018):
        validate(year, Path("data"))
    print("Italy Chamber validation passed.")


if __name__ == "__main__":
    main()
