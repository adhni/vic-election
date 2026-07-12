#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REQUIRED = {
    "district",
    "elected_member",
    "elected_party",
    "formal_votes",
    "round_number",
    "row_type",
    "excluded_candidate",
    "excluded_party",
    "candidate",
    "candidate_party",
    "votes",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_geojson(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_positions(geometry: dict):
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

    yield from walk(geometry.get("coordinates", []))


def validate_rows(
    rows: list[dict[str, str]],
    expected_districts: int,
    validate_vote_totals: bool = False,
) -> set[str]:
    if not rows:
        raise SystemExit("Preference CSV is empty")
    missing = REQUIRED - set(rows[0])
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")

    districts = {row["district"] for row in rows}
    if len(districts) != expected_districts:
        raise SystemExit(f"Expected {expected_districts} districts, found {len(districts)}")

    by_district: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["votes"] == "":
            raise SystemExit(f"{row['district']}: row with missing votes")
        by_district.setdefault(row["district"], []).append(row)

    for district, district_rows in by_district.items():
        first_rows = [row for row in district_rows if row["row_type"] == "first"]
        final_rows = [row for row in district_rows if row["row_type"] == "final"]
        if not first_rows:
            raise SystemExit(f"{district}: missing first preference rows")
        if len(final_rows) < 2:
            raise SystemExit(f"{district}: expected at least 2 final rows, found {len(final_rows)}")

        formal_votes = int(float(district_rows[0]["formal_votes"]))
        first_total = sum(int(float(row["votes"])) for row in first_rows)
        if first_total != formal_votes:
            raise SystemExit(f"{district}: first preference total {first_total} != formal votes {formal_votes}")

        metadata = district_rows[0]
        if (
            validate_vote_totals
            and metadata.get("informal_votes", "") != ""
            and metadata.get("total_votes", "") != ""
        ):
            informal_votes = int(float(metadata["informal_votes"]))
            total_votes = int(float(metadata["total_votes"]))
            if total_votes != formal_votes + informal_votes:
                raise SystemExit(
                    f"{district}: total votes {total_votes} != "
                    f"formal {formal_votes} + informal {informal_votes}"
                )

        winner = max(final_rows, key=lambda row: int(float(row["votes"])))["candidate"]
        elected = district_rows[0]["elected_member"]
        if winner != elected:
            raise SystemExit(f"{district}: final winner {winner!r} != elected member {elected!r}")

    return districts


def validate_boundaries(
    path: Path,
    districts: set[str],
    max_overlap_ratio: float = 0.00001,
    max_gap_ratio: float = 0.0005,
) -> None:
    sys.path.insert(0, str(Path("tmp/pydeps")))
    try:
        from shapely.geometry import Polygon, shape
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
        seen = False
        for lon, lat, *_ in iter_positions(feature["geometry"]):
            seen = True
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise SystemExit(f"{name}: boundary coordinate outside lon/lat range: {lon}, {lat}")
        if not seen:
            raise SystemExit(f"{name}: boundary geometry has no coordinates")
        geom = shape(feature["geometry"])
        if geom.is_empty:
            raise SystemExit(f"{name}: empty geometry")
        if not geom.is_valid:
            raise SystemExit(f"{name}: invalid geometry")
        geometries.append(geom)

    summed_area = sum(geom.area for geom in geometries)
    union = unary_union(geometries)
    overlap_ratio = max(0.0, (summed_area - union.area) / summed_area)
    if overlap_ratio > max_overlap_ratio:
        raise SystemExit(f"Boundary overlap ratio too large: {overlap_ratio:.8f}")

    polygons = list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    hole_area = sum(abs(Polygon(ring).area) for poly in polygons for ring in poly.interiors)
    gap_ratio = hole_area / union.area if union.area else 0
    if gap_ratio > max_gap_ratio:
        raise SystemExit(f"Internal gap ratio too large: {gap_ratio:.8f}")

    print(f"Boundary topology: overlap_ratio={overlap_ratio:.8f}, internal_gap_ratio={gap_ratio:.8f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/vic_2010_preferences_long.csv"))
    parser.add_argument("--boundaries", type=Path, default=Path("data/vic_2010_district_boundaries.geojson"))
    parser.add_argument("--expected-districts", type=int, default=88)
    parser.add_argument("--label", default="State")
    parser.add_argument("--max-overlap-ratio", type=float, default=0.00001)
    parser.add_argument("--max-gap-ratio", type=float, default=0.0005)
    parser.add_argument("--validate-vote-totals", action="store_true")
    args = parser.parse_args()

    rows = read_csv(args.csv)
    districts = validate_rows(rows, args.expected_districts, args.validate_vote_totals)
    validate_boundaries(
        args.boundaries,
        districts,
        max_overlap_ratio=args.max_overlap_ratio,
        max_gap_ratio=args.max_gap_ratio,
    )
    print(f"Rows: {len(rows)}")
    print(f"{args.label} districts: {len(districts)}")
    print(f"{args.label} validation passed")


if __name__ == "__main__":
    main()
