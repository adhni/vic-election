#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


CONFIG = {
    "argentina_2023_president_round_1_province_fpp.csv": (
        "argentina_province_boundaries.geojson", 24,
        {
            "Sergio Massa": 9_645_983, "Javier Milei": 7_884_336,
            "Patricia Bullrich": 6_267_152, "Juan Schiaretti": 1_784_315,
            "Myriam Bregman": 709_932,
        },
    ),
    "argentina_2023_president_round_2_province_fpp.csv": (
        "argentina_province_boundaries.geojson", 24,
        {"Javier Milei": 14_476_462, "Sergio Massa": 11_516_142},
    ),
    "argentina_2019_president_round_1_province_fpp.csv": (
        "argentina_province_boundaries.geojson", 24,
        {
            "Alberto Fernández": 12_473_709, "Mauricio Macri": 10_470_607,
            "Roberto Lavagna": 1_599_707, "Nicolás del Caño": 561_214,
            "Juan José Gómez Centurión": 443_507, "José Luis Espert": 382_820,
        },
    ),
    "brazil_2022_president_round_1_state_fpp.csv": (
        "brazil_state_boundaries.geojson", 27,
        {
            "Jair Bolsonaro": 50_949_797, "Luiz Inácio Lula da Silva": 57_120_571,
            "Simone Tebet": 4_902_256, "Ciro Gomes": 3_585_946,
            "Other candidates": 1_376_624,
        },
    ),
    "brazil_2022_president_round_2_state_fpp.csv": (
        "brazil_state_boundaries.geojson", 27,
        {"Jair Bolsonaro": 58_061_090, "Luiz Inácio Lula da Silva": 60_193_094},
    ),
    "brazil_2018_president_round_1_state_fpp.csv": (
        "brazil_state_boundaries.geojson", 27,
        {
            "Jair Bolsonaro": 49_163_300, "Fernando Haddad": 31_322_465,
            "Ciro Gomes": 13_316_293, "Geraldo Alckmin": 5_089_581,
            "Other candidates": 7_965_553,
        },
    ),
    "brazil_2018_president_round_2_state_fpp.csv": (
        "brazil_state_boundaries.geojson", 27,
        {"Jair Bolsonaro": 57_666_176, "Fernando Haddad": 46_987_176},
    ),
}


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as exc:
        raise SystemExit(f"Invalid {field!r} value in {row.get('district', 'unknown area')}") from exc


def validate(data_dir: Path, csv_name: str, boundary_name: str, expected_areas: int,
             expected_votes: dict[str, int]) -> None:
    csv_path = data_dir / csv_name
    boundary_path = data_dir / boundary_name
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{csv_path}: empty CSV")

    by_area: dict[str, list[dict[str, str]]] = defaultdict(list)
    candidate_totals: Counter[str] = Counter()
    for row in rows:
        if row["row_type"] != "first" or integer(row, "round_number") != 0:
            raise SystemExit(f"{csv_path}: non-compact row in {row['district']}")
        if row["contest_status"] != "official":
            raise SystemExit(f"{csv_path}: non-official row in {row['district']}")
        votes = integer(row, "votes")
        if votes < 0:
            raise SystemExit(f"{csv_path}: negative votes in {row['district']}")
        by_area[row["constituency_code"]].append(row)
        candidate_totals[row["candidate"]] += votes

    if len(by_area) != expected_areas:
        raise SystemExit(f"{csv_path}: expected {expected_areas} areas, got {len(by_area)}")
    if dict(candidate_totals) != expected_votes:
        raise SystemExit(
            f"{csv_path}: candidate totals changed\n"
            f"expected {expected_votes}\nactual {dict(candidate_totals)}"
        )

    for code, area_rows in by_area.items():
        metadata_fields = (
            "district", "elected_member", "elected_party", "enrolment", "formal_votes",
            "informal_votes", "total_votes", "turnout_pct", "majority", "electorate_type",
            "contest_status", "result_note",
        )
        for field in metadata_fields:
            if len({row[field] for row in area_rows}) != 1:
                raise SystemExit(f"{csv_path}: inconsistent {field} metadata for {code}")
        ordered = sorted((integer(row, "votes"), row["candidate"]) for row in area_rows)
        formal = sum(votes for votes, _ in ordered)
        winner_votes, winner = ordered[-1]
        runner_up = ordered[-2][0] if len(ordered) > 1 else 0
        first = area_rows[0]
        if formal != integer(first, "formal_votes"):
            raise SystemExit(f"{csv_path}: formal vote mismatch for {code}")
        if formal + integer(first, "informal_votes") != integer(first, "total_votes"):
            raise SystemExit(f"{csv_path}: ballot total mismatch for {code}")
        enrolment = integer(first, "enrolment")
        if enrolment:
            turnout = float(first["turnout_pct"])
            expected_turnout = integer(first, "total_votes") * 100 / enrolment
            if not 0 <= turnout <= 100 or abs(turnout - expected_turnout) > 0.01:
                raise SystemExit(f"{csv_path}: turnout mismatch for {code}")
        if winner != first["elected_member"]:
            raise SystemExit(f"{csv_path}: winner mismatch for {code}")
        if winner_votes - runner_up != integer(first, "majority"):
            raise SystemExit(f"{csv_path}: majority mismatch for {code}")

    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    boundary_codes = [
        feature.get("properties", {}).get("constituency_code")
        for feature in boundary.get("features", [])
    ]
    if len(boundary_codes) != expected_areas or len(set(boundary_codes)) != expected_areas:
        raise SystemExit(f"{boundary_path}: expected {expected_areas} unique boundary codes")
    if set(boundary_codes) != set(by_area):
        raise SystemExit(f"{csv_path}: CSV/boundary code mismatch")
    geometry_bounds = []
    for feature in boundary["features"]:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{boundary_path}: invalid geometry for "
                f"{feature['properties'].get('constituency_code')}"
            )
        geometry_bounds.append(geometry.bounds)
    if boundary_name == "argentina_province_boundaries.geojson":
        eastern_extent = max(bounds[2] for bounds in geometry_bounds)
        if eastern_extent >= -52:
            raise SystemExit(
                f"{boundary_path}: remote South Atlantic geometry expands the map extent"
            )
    print(f"{csv_name}: {expected_areas} areas, {len(rows)} rows")


def main() -> None:
    data_dir = Path("data")
    for csv_name, (boundary_name, expected_areas, expected_votes) in CONFIG.items():
        validate(data_dir, csv_name, boundary_name, expected_areas, expected_votes)
    print("Argentina/Brazil presidential validation passed.")


if __name__ == "__main__":
    main()
