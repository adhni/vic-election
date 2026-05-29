#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ELECTIONS = {
    "2022": ("data/vic_2022_preferences_long.csv", "data/vic_2022_district_boundaries.geojson"),
    "2018": ("data/vic_2018_preferences_long.csv", "data/vic_2018_district_boundaries.geojson"),
    "federal-2025-vic": (
        "data/federal_2025_vic_preferences_long.csv",
        "data/federal_2025_vic_division_boundaries.geojson",
    ),
    "federal-2022-vic": (
        "data/federal_2022_vic_preferences_long.csv",
        "data/federal_2022_vic_division_boundaries.geojson",
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def walk_coordinates(coords, visit) -> None:
    if coords and isinstance(coords[0], (int, float)):
        visit(coords[0], coords[1])
        return
    for part in coords or []:
        walk_coordinates(part, visit)


def ring_path(ring, min_lon, max_lon, min_lat, max_lat) -> str:
    width, height, pad = 960, 560, 14
    scale = min((width - pad * 2) / (max_lon - min_lon), (height - pad * 2) / (max_lat - min_lat))
    map_w = (max_lon - min_lon) * scale
    map_h = (max_lat - min_lat) * scale
    offset_x = (width - map_w) / 2
    offset_y = (height - map_h) / 2
    parts = []
    for i, (lon, lat) in enumerate(ring):
        x = offset_x + (lon - min_lon) * scale
        y = offset_y + (max_lat - lat) * scale
        parts.append(f"{'L' if i else 'M'}{x:.1f},{y:.1f}")
    return "".join(parts) + "Z"


def geometry_path(geometry, bounds) -> str:
    min_lon, max_lon, min_lat, max_lat = bounds
    if geometry["type"] == "Polygon":
        return "".join(ring_path(ring, min_lon, max_lon, min_lat, max_lat) for ring in geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return "".join(
            ring_path(ring, min_lon, max_lon, min_lat, max_lat)
            for polygon in geometry["coordinates"]
            for ring in polygon
        )
    return ""


def smoke_election(key: str, csv_path: Path, boundary_path: Path) -> None:
    rows = read_csv(csv_path)
    districts = {row["district"] for row in rows}
    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson["features"]
    names = {feature["properties"]["district"] for feature in features}
    if names != districts:
        raise SystemExit(f"{key}: CSV/boundary mismatch: {sorted(names ^ districts)}")

    min_lon, max_lon, min_lat, max_lat = float("inf"), float("-inf"), float("inf"), float("-inf")
    for feature in features:
        def visit(lon, lat):
            nonlocal min_lon, max_lon, min_lat, max_lat
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
        walk_coordinates(feature["geometry"]["coordinates"], visit)

    paths = [geometry_path(feature["geometry"], (min_lon, max_lon, min_lat, max_lat)) for feature in features]
    if len([path for path in paths if path.startswith("M") and len(path) > 20]) != len(features):
        raise SystemExit(f"{key}: map path generation failed")
    if not any(row["row_type"] == "final" for row in rows):
        raise SystemExit(f"{key}: no final rows")
    print(f"{key}: {len(districts)} districts, {len(rows)} rows, {len(paths)} map paths")


def main() -> None:
    html_files = [Path("index.html"), Path("app/index.html")]
    for html_file in html_files:
        html = html_file.read_text(encoding="utf-8")
        for key in ELECTIONS:
            if not re.search(rf'<option value="{re.escape(key)}"', html) or key not in html:
                raise SystemExit(f"{html_file}: missing election option/config for {key}")
    for key, (csv_file, boundary_file) in ELECTIONS.items():
        smoke_election(key, Path(csv_file), Path(boundary_file))
    print("Static app smoke passed")


if __name__ == "__main__":
    main()
