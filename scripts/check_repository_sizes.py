#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


MIB = 1024 * 1024
MAX_BOUNDARY_BYTES = 15 * MIB
WARN_DATA_BYTES = 400 * MIB
MAX_DATA_BYTES = 500 * MIB
MAX_OPTIMIZED_BOUNDARY_BYTES = 8 * MIB
OPTIMIZED_BOUNDARIES = [
    Path("data/vic_2014_district_boundaries.geojson"),
    Path("data/federal_2016_au_division_boundaries.geojson"),
    Path("data/federal_2019_au_division_boundaries.geojson"),
    Path("data/federal_2022_au_division_boundaries.geojson"),
    Path("data/federal_2025_au_division_boundaries.geojson"),
]
REMOVED_DUPLICATES = [Path("data/vic_2018_district_boundaries.geojson")]


def main() -> None:
    data_files = [path for path in Path("data").rglob("*") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in data_files)
    oversized = [
        (path, path.stat().st_size)
        for path in data_files
        if path.name.endswith("boundaries.geojson") and path.stat().st_size > MAX_BOUNDARY_BYTES
    ]
    if oversized:
        details = ", ".join(f"{path} ({size / MIB:.1f} MiB)" for path, size in oversized)
        raise SystemExit(f"Boundary size limit exceeded: {details}")
    if total_bytes > MAX_DATA_BYTES:
        raise SystemExit(
            f"data/ size limit exceeded: {total_bytes / MIB:.1f} MiB > {MAX_DATA_BYTES / MIB:.0f} MiB"
        )
    optimization_regressions = [
        path
        for path in OPTIMIZED_BOUNDARIES
        if not path.is_file() or path.stat().st_size > MAX_OPTIMIZED_BOUNDARY_BYTES
    ]
    if optimization_regressions:
        raise SystemExit(
            "Optimized boundary limit exceeded or file missing: "
            + ", ".join(str(path) for path in optimization_regressions)
        )
    restored_duplicates = [path for path in REMOVED_DUPLICATES if path.exists()]
    if restored_duplicates:
        raise SystemExit(
            "Duplicate boundary files restored: "
            + ", ".join(str(path) for path in restored_duplicates)
        )
    largest = max(data_files, key=lambda path: path.stat().st_size)
    if total_bytes > WARN_DATA_BYTES:
        print(
            f"Repository size warning: data/ is {total_bytes / MIB:.1f} MiB; "
            f"review storage before the {MAX_DATA_BYTES / MIB:.0f} MiB hard guard."
        )
    print(
        f"Repository size checks passed: data/ {total_bytes / MIB:.1f}/{MAX_DATA_BYTES / MIB:.0f} MiB; "
        f"largest file {largest} {largest.stat().st_size / MIB:.1f}/{MAX_BOUNDARY_BYTES / MIB:.0f} MiB"
    )


if __name__ == "__main__":
    main()
