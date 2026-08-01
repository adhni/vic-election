#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

from shapely.geometry import shape


SPECS = {
    2024: {"areas": 213, "rows": 10_538, "formal": 16_039_009, "informal": 213_391,
           "enrolment": 27_723_279, "boundary": "data/south_africa_2016_municipality_boundaries.geojson"},
    2019: {"areas": 213, "rows": 9_708, "formal": 17_417_497, "informal": 235_445,
           "enrolment": 26_748_966, "boundary": "data/south_africa_2016_municipality_boundaries.geojson"},
    2014: {"areas": 234, "rows": 6_596, "formal": 18_384_365, "informal": 251_960,
           "enrolment": 25_381_293, "boundary": "data/south_africa_2011_municipality_boundaries.geojson"},
}


def validate_dataset(csv_path: Path, boundary_path: Path, expected_areas: int) -> tuple[int, int, int, int]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["constituency_code"], []).append(row)
    if len(grouped) != expected_areas:
        raise SystemExit(f"{csv_path}: expected {expected_areas} areas, found {len(grouped)}")
    formal_total = informal_total = enrolment_total = 0
    for code, area_rows in grouped.items():
        metadata = {
            (row["district"], int(row["formal_votes"]), int(row["informal_votes"]),
             int(row["total_votes"]), int(row["enrolment"]), row["row_type"],
             int(row["district_seats"]))
            for row in area_rows
        }
        if len(metadata) != 1:
            raise SystemExit(f"{csv_path} {code}: inconsistent metadata")
        _, formal, informal, total, enrolment, row_type, district_seats = metadata.pop()
        if row_type != "first" or district_seats != 0:
            raise SystemExit(f"{csv_path} {code}: expected compact local party rows")
        if formal + informal != total:
            raise SystemExit(f"{csv_path} {code}: ballot arithmetic does not reconcile")
        if sum(int(row["votes"]) for row in area_rows) != formal:
            raise SystemExit(f"{csv_path} {code}: party votes do not equal valid votes")
        formal_total += formal
        informal_total += informal
        enrolment_total += enrolment

    boundaries = json.loads(boundary_path.read_text(encoding="utf-8"))["features"]
    boundary_codes = {feature["properties"]["constituency_code"] for feature in boundaries}
    if boundary_codes != set(grouped):
        raise SystemExit(f"{csv_path}: result and boundary codes do not match")
    for feature in boundaries:
        geom = shape(feature["geometry"])
        if geom.is_empty or not geom.is_valid:
            raise SystemExit(f"{boundary_path}: invalid geometry")
    return len(rows), formal_total, informal_total, enrolment_total


def main() -> None:
    for year, spec in SPECS.items():
        municipality = validate_dataset(
            Path(f"data/south_africa_{year}_national_municipality_fpp.csv"),
            Path(spec["boundary"]), spec["areas"],
        )
        province = validate_dataset(
            Path(f"data/south_africa_{year}_national_province_fpp.csv"),
            Path("data/south_africa_province_boundaries.geojson"), 9,
        )
        if municipality[1:] != province[1:]:
            raise SystemExit(f"South Africa {year}: municipality and province totals differ")
        expected = (spec["rows"], spec["formal"], spec["informal"], spec["enrolment"])
        if municipality != expected:
            raise SystemExit(
                f"South Africa {year}: mapped control totals changed; expected {expected}, found {municipality}"
            )
        print(
            f"South Africa {year}: {spec['areas']} municipalities, 9 provinces, "
            f"{municipality[1]:,} mapped valid votes"
        )
    print("South Africa National Assembly validation passed")


if __name__ == "__main__":
    main()
