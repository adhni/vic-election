#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from pyproj import CRS
from shapely import force_2d
from shapely.geometry import mapping

from build_aec_federal import BOUNDARY_NAME_FIXES, build_preferences


SOURCE_FIXTURES = (
    {
        "state": "ACT",
        "zip_name": "act-tab-20072016.zip",
        "dataset_path": "ACT_ELB_new.TAB",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/act-tab-20072016.zip",
    },
    {
        "state": "NSW",
        "zip_name": "nsw-esri-06042016.zip",
        "dataset_path": "NSW_electoral_boundaries_25-02-2016.shp",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/nsw-esri-06042016.zip",
    },
    {
        "state": "NT",
        "zip_name": "nt-midmif-07022017.zip",
        "dataset_path": "E_Propos.MIF",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/nt-midmif-07022017.zip",
    },
    {
        "state": "QLD",
        "zip_name": "qld-shape-files-13012010.zip",
        "dataset_path": "QLD_ELB_031209_region.shp",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/gis/elb/qld-shape-files-13012010.zip",
    },
    {
        "state": "SA",
        "zip_name": "sa-esri-16122011.zip",
        "dataset_path": "E_SA16122011_region.shp",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/sa-esri-16122011.zip",
    },
    {
        "state": "TAS",
        "zip_name": "tas-november2017-midmif.zip",
        "dataset_path": "E_FINAL.TAB",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/tas-november2017-midmif.zip",
    },
    {
        "state": "VIC",
        "zip_name": "vic-esri-24122010.zip",
        "dataset_path": "vic 24122010.shp",
        "prj_path": "vic24122010.prj",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/vic-esri-24122010.zip",
    },
    {
        "state": "WA",
        "zip_name": "wa-esri-19012016.zip",
        "dataset_path": "Shape (ESRI)/WA_Electoral_Boundaries_19-01-2016.shp",
        "gis_source": "https://www.aec.gov.au/Electorates/gis/files/wa-esri-19012016.zip",
    },
)

DIVISION_NAME_FIELDS = ("Elect_div", "ELECT_DIV")
DIVISION_ID_FIELDS = ("E_div_number", "E_div_numb", "DIV_NUMBER")
YEAR_SPECIFIC_NAME_FIXES = {
    "Clark": "Denison",
}


def record_value(record: dict[str, object], fields: tuple[str, ...]) -> object:
    for field in fields:
        if field in record and record[field] not in ("", None):
            return record[field]
    raise KeyError(f"Missing expected field from {fields}")


def optional_record_value(record: dict[str, object], fields: tuple[str, ...]) -> object:
    for field in fields:
        if field in record and record[field] not in ("", None):
            return record[field]
    return ""


def extract_dataset(zip_path: Path, dataset_path: str, destination_root: Path) -> Path:
    out_dir = destination_root / zip_path.stem
    if not out_dir.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(out_dir)
    dataset = out_dir / dataset_path
    if not dataset.exists():
        raise SystemExit(f"{zip_path.name}: expected extracted dataset {dataset_path}")
    return dataset


def apply_missing_crs(gdf: gpd.GeoDataFrame, dataset: Path, fixture: dict[str, str]) -> gpd.GeoDataFrame:
    if gdf.crs is not None:
        return gdf

    prj_candidates = []
    if fixture.get("prj_path"):
        prj_candidates.append(dataset.parent / fixture["prj_path"])
    same_stem = dataset.with_suffix(".prj")
    prj_candidates.append(same_stem)
    local_prjs = sorted(dataset.parent.glob("*.prj"))
    prj_candidates.extend(local_prjs)

    for prj_path in prj_candidates:
        if prj_path.exists():
            return gdf.set_crs(CRS.from_wkt(prj_path.read_text(encoding="utf-8")))
    raise SystemExit(f"{dataset.name}: missing CRS metadata")


def load_state_boundaries(source_dir: Path, extract_dir: Path, fixture: dict[str, str]) -> list[dict[str, object]]:
    zip_path = source_dir / fixture["zip_name"]
    if not zip_path.exists():
        raise SystemExit(f"Missing 2016 AU boundary source: {zip_path}")

    dataset = extract_dataset(zip_path, fixture["dataset_path"], extract_dir)
    gdf = gpd.read_file(dataset)
    if gdf.empty:
        raise SystemExit(f"{zip_path.name}: no boundary rows loaded")
    gdf = apply_missing_crs(gdf, dataset, fixture)
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    features: list[dict[str, object]] = []
    for record in gdf.to_dict(orient="records"):
        geometry = record.pop("geometry")
        if geometry is None or geometry.is_empty:
            raise SystemExit(f"{zip_path.name}: encountered empty geometry")
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        geometry = force_2d(geometry)
        district = str(record_value(record, DIVISION_NAME_FIELDS))
        district = BOUNDARY_NAME_FIXES.get(district, district)
        district = YEAR_SPECIFIC_NAME_FIXES.get(district, district)
        division_id = optional_record_value(record, DIVISION_ID_FIELDS)
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "division_id": "" if division_id == "" else str(division_id),
                "state": fixture["state"],
                "source": fixture["gis_source"],
            },
            "geometry": mapping(geometry),
        })
    return features


def build_boundaries(source_dir: Path, out_dir: Path, extract_dir: Path) -> Path:
    features: list[dict[str, object]] = []
    for fixture in SOURCE_FIXTURES:
        state_features = load_state_boundaries(source_dir, extract_dir, fixture)
        print(f"{fixture['state']}: {len(state_features)} divisions")
        features.extend(state_features)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "federal_2016_au_division_boundaries.geojson"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))
        f.write("\n")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2016)
    parser.add_argument("--event-id", default="20499")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/aec_2016_au"))
    parser.add_argument("--source-dir", type=Path, default=Path("tmp/aec_2016_au_sources"))
    parser.add_argument("--extract-dir", type=Path, help="Optional directory for extracted boundary source files")
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()

    extract_dir = args.extract_dir or Path(tempfile.mkdtemp(prefix="aec_2016_au_boundaries_"))
    pref_path, summary_path = build_preferences(args.raw_dir, args.out, args.year, args.event_id, "au")
    boundary_path = build_boundaries(args.source_dir, args.out, extract_dir)
    print(f"Wrote {pref_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
