#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from shapely.geometry import shape


MAPSHAPER_VERSION = "0.7.45"
DEFAULT_KEEP_PERCENT = 20
DEFAULT_PRECISION = 0.000001
MAX_AREA_DELTA = 0.005
ALREADY_OPTIMIZED_BYTES = 8 * 1024 * 1024

FILE_OPTIONS = {
    # These VEC polygons contain invalid source rings. Mapshaper's shared-topology
    # clean pass repairs them before the more substantial simplification.
    "vic_2014_district_boundaries.geojson": {
        "keep_percent": 5,
        "precision": 0.00001,
        "clean": True,
    },
    # These files already passed through the original 20% optimizer. Retaining
    # 70% of their remaining vertices keeps every feature within the area guard.
    "federal_2016_au_division_boundaries.geojson": {"keep_percent": 70},
    "federal_2019_au_division_boundaries.geojson": {"keep_percent": 70},
    "federal_2022_au_division_boundaries.geojson": {"keep_percent": 70},
    "federal_2025_au_division_boundaries.geojson": {"keep_percent": 70},
}

BOUNDARY_FILES = [
    "data/federal_2010_vic_division_boundaries.geojson",
    "data/federal_2013_vic_division_boundaries.geojson",
    "data/federal_2016_au_division_boundaries.geojson",
    "data/federal_2019_au_division_boundaries.geojson",
    "data/federal_2022_au_division_boundaries.geojson",
    "data/federal_2025_au_division_boundaries.geojson",
    "data/nsw_2015_district_boundaries.geojson",
    "data/nsw_2019_district_boundaries.geojson",
    "data/nsw_2023_district_boundaries.geojson",
    "data/qld_2020_district_boundaries.geojson",
    "data/qld_2024_district_boundaries.geojson",
    "data/sa_2018_district_boundaries.geojson",
    "data/sa_2022_district_boundaries.geojson",
    "data/tas_2021_district_boundaries.geojson",
    "data/tas_2024_district_boundaries.geojson",
    "data/tas_2025_district_boundaries.geojson",
    "data/vic_2006_district_boundaries.geojson",
    "data/vic_2010_district_boundaries.geojson",
    "data/vic_2014_district_boundaries.geojson",
    "data/wa_2021_district_boundaries.geojson",
    "data/wa_2025_district_boundaries.geojson",
]


def validate(original: dict[str, object], candidate: dict[str, object], path: Path) -> float:
    original_features = original.get("features", [])
    candidate_features = candidate.get("features", [])
    if len(original_features) != len(candidate_features):
        raise SystemExit(f"{path}: feature count changed")
    if [feature["properties"] for feature in original_features] != [
        feature["properties"] for feature in candidate_features
    ]:
        raise SystemExit(f"{path}: feature properties or order changed")

    max_delta = 0.0
    for original_feature, candidate_feature in zip(original_features, candidate_features):
        original_geometry = shape(original_feature["geometry"])
        candidate_geometry = shape(candidate_feature["geometry"])
        if candidate_geometry.is_empty or not candidate_geometry.is_valid:
            raise SystemExit(f"{path}: optimization produced empty or invalid geometry")
        if original_geometry.area:
            delta = abs(candidate_geometry.area - original_geometry.area) / original_geometry.area
            max_delta = max(max_delta, delta)
    if max_delta > MAX_AREA_DELTA:
        raise SystemExit(
            f"{path}: maximum relative area change {max_delta:.6f} exceeds {MAX_AREA_DELTA:.3f}"
        )
    return max_delta


def optimize(path: Path, write: bool) -> None:
    original_bytes = path.stat().st_size
    if original_bytes <= ALREADY_OPTIMIZED_BYTES:
        print(f"{path}: already within optimized ceiling; skipped")
        return
    options = FILE_OPTIONS.get(path.name, {})
    keep_percent = options.get("keep_percent", DEFAULT_KEEP_PERCENT)
    precision = options.get("precision", DEFAULT_PRECISION)
    original = json.loads(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="boundary-opt-") as temp_dir:
        candidate_path = Path(temp_dir) / path.name
        command = ["npx", "--yes", f"mapshaper@{MAPSHAPER_VERSION}", str(path)]
        if options.get("clean"):
            command.append("-clean")
        command.extend(
            [
                "-simplify", f"{keep_percent}%", "keep-shapes",
                "-o", "format=geojson", f"precision={precision}", str(candidate_path),
            ]
        )
        subprocess.run(command, check=True)
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        max_delta = validate(original, candidate, path)
        for key, value in original.items():
            if key not in {"features", "bbox"}:
                candidate[key] = value
        output = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        optimized_bytes = len(output.encode("utf-8"))
        if optimized_bytes >= original_bytes:
            raise SystemExit(f"{path}: optimized output is not smaller")
        print(
            f"{path}: {original_bytes / 1048576:.1f} -> {optimized_bytes / 1048576:.1f} MiB "
            f"({optimized_bytes / original_bytes:.1%}), max area delta {max_delta:.4%}"
        )
        if write:
            path.write_text(output, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely simplify oversized election boundary GeoJSON")
    parser.add_argument("--write", action="store_true", help="replace validated source files")
    parser.add_argument("paths", nargs="*", type=Path, help="optional subset of boundary files")
    args = parser.parse_args()
    paths = args.paths or [Path(path) for path in BOUNDARY_FILES]
    for path in paths:
        optimize(path, args.write)


if __name__ == "__main__":
    main()
