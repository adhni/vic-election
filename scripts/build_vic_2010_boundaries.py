#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests


DEFAULT_WFS_URL = (
    "https://opendata.maps.vic.gov.au/geoserver/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=open-data-platform:state_assembly_2001"
    "&outputFormat=application/json"
)


def district_name(properties: dict) -> str:
    label = properties.get("district_label") or properties.get("district") or ""
    label = re.sub(r"\s+District$", "", str(label), flags=re.I).strip()
    if label.isupper():
        label = label.title()
    return label


def load_source(path: Path | None, url: str) -> dict:
    if path:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def build_boundaries(source: dict, source_url: str, year: int) -> dict:
    features = []
    for feature in source.get("features") or []:
        properties = feature.get("properties") or {}
        name = district_name(properties)
        if not name:
            raise ValueError(f"Boundary feature has no district name: {properties}")
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": name,
                    "district_code": properties.get("district_code", ""),
                    "source": "Vicmap Admin - State Assembly Polygon 2001",
                    "source_url": source_url,
                },
                "geometry": feature.get("geometry"),
            }
        )

    features.sort(key=lambda f: f["properties"]["district"])
    return {
        "type": "FeatureCollection",
        "name": f"vic_{year}_district_boundaries",
        "source": source_url,
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2010)
    parser.add_argument("--source", type=Path, help="Optional downloaded WFS GeoJSON source")
    parser.add_argument("--url", default=DEFAULT_WFS_URL)
    parser.add_argument("--out", type=Path, default=Path("data/vic_2010_district_boundaries.geojson"))
    args = parser.parse_args()

    source = load_source(args.source, args.url)
    out = build_boundaries(source, args.url, args.year)
    if len(out["features"]) != 88:
        raise SystemExit(f"Expected 88 district boundary features, found {len(out['features'])}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {args.out} ({len(out['features'])} features)")


if __name__ == "__main__":
    main()
