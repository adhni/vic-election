#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REQUIRED = {
    "district", "elected_member", "elected_party", "formal_votes", "round_number",
    "row_type", "excluded_candidate", "excluded_party", "candidate", "candidate_party", "votes"
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_aec_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        next(f)
        return list(csv.DictReader(f))


def candidate_name(row: dict[str, str]) -> str:
    surname = (row.get("Surname") or "").strip()
    given = (row.get("GivenNm") or "").strip()
    return f"{surname}, {given}" if given else surname


def load_geojson(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_positions(geometry: dict):
    coordinates = geometry.get("coordinates", [])

    def walk(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            yield value
            return
        if isinstance(value, list):
            for item in value:
                yield from walk(item)

    yield from walk(coordinates)


def validate_lon_lat_geometry(geometry: dict, name: str) -> None:
    seen = False
    for lon, lat, *_ in iter_positions(geometry):
        seen = True
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit(f"{name}: boundary coordinate outside lon/lat range: {lon}, {lat}")
    if not seen:
        raise SystemExit(f"{name}: boundary geometry has no coordinates")


def validate_rows(rows: list[dict[str, str]], expected_divisions: int) -> set[str]:
    if not rows:
        raise SystemExit("Preference CSV is empty")
    missing = REQUIRED - set(rows[0])
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")
    districts = {row["district"] for row in rows}
    if len(districts) != expected_divisions:
        raise SystemExit(f"Expected {expected_divisions} Victorian federal divisions, found {len(districts)}")
    row_types = {row["row_type"] for row in rows}
    if not {"first", "transfer", "progressive", "final"}.issubset(row_types):
        raise SystemExit(f"Missing row types: {sorted({'first', 'transfer', 'progressive', 'final'} - row_types)}")
    missing_votes = [row for row in rows if row["votes"] == ""]
    if missing_votes:
        raise SystemExit(f"Rows with missing votes: {len(missing_votes)}")
    for district in districts:
        final_rows = [row for row in rows if row["district"] == district and row["row_type"] == "final"]
        if len(final_rows) != 2:
            raise SystemExit(f"{district}: expected 2 final rows, found {len(final_rows)}")
        first_rows = [row for row in rows if row["district"] == district and row["row_type"] == "first"]
        if not first_rows:
            raise SystemExit(f"{district}: missing first preference rows")
    return districts


def validate_against_aec(rows: list[dict[str, str]], aec_raw: Path | None) -> None:
    if not aec_raw:
        return
    aec_rows = [row for row in read_aec_csv(aec_raw) if row["StateAb"] == "VIC"]
    aec_divisions = {row["DivisionNm"] for row in aec_rows}
    csv_divisions = {row["district"] for row in rows}
    if csv_divisions != aec_divisions:
        raise SystemExit(f"CSV/AEC division mismatch: {sorted(csv_divisions ^ aec_divisions)}")
    aec_elected = {
        row["DivisionNm"]: candidate_name(row)
        for row in aec_rows
        if row["Elected"] == "Y"
    }
    for district, elected in aec_elected.items():
        csv_elected = next(row["elected_member"] for row in rows if row["district"] == district)
        if csv_elected != elected:
            raise SystemExit(f"{district}: elected member mismatch {csv_elected!r} != {elected!r}")


def validate_boundaries(path: Path, districts: set[str]) -> None:
    sys.path.insert(0, str(Path("tmp/pydeps")))
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
    except ImportError as exc:
        raise SystemExit("Install shapely to validate boundary topology") from exc

    geojson = load_geojson(path)
    features = geojson.get("features") or []
    names = {feature.get("properties", {}).get("district") for feature in features}
    if names != districts:
        raise SystemExit(f"Boundary/result name mismatch: {sorted(names ^ districts)}")

    geometries = []
    for feature in features:
        name = feature["properties"]["district"]
        validate_lon_lat_geometry(feature["geometry"], name)
        geom = shape(feature["geometry"])
        if geom.is_empty:
            raise SystemExit(f"{name}: empty geometry")
        if not geom.is_valid:
            raise SystemExit(f"{name}: invalid geometry")
        geometries.append(geom)

    summed_area = sum(geom.area for geom in geometries)
    union = unary_union(geometries)
    overlap_ratio = max(0.0, (summed_area - union.area) / summed_area)
    if overlap_ratio > 0.00001:
        raise SystemExit(f"Boundary overlap ratio too large: {overlap_ratio:.8f}")

    polygons = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    hole_area = sum(
        abs(shape({"type": "Polygon", "coordinates": [list(ring.coords)]}).area)
        for poly in polygons
        for ring in poly.interiors
    )
    gap_ratio = hole_area / union.area if union.area else 0
    if gap_ratio > 0.0005:
        raise SystemExit(f"Internal gap ratio too large: {gap_ratio:.8f}")

    print(f"Boundary topology: overlap_ratio={overlap_ratio:.8f}, internal_gap_ratio={gap_ratio:.8f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/federal_2025_vic_preferences_long.csv"))
    parser.add_argument("--boundaries", type=Path, default=Path("data/federal_2025_vic_division_boundaries.geojson"))
    parser.add_argument("--aec-dop", type=Path)
    parser.add_argument("--expected-divisions", type=int, default=38)
    args = parser.parse_args()

    rows = read_csv(args.csv)
    districts = validate_rows(rows, args.expected_divisions)
    validate_against_aec(rows, args.aec_dop)
    validate_boundaries(args.boundaries, districts)
    print(f"Rows: {len(rows)}")
    print(f"Victorian federal divisions: {len(districts)}")
    print("Federal VIC validation passed")


if __name__ == "__main__":
    main()
