#!/usr/bin/env python3
"""Build the lightweight catalogue and coverage map used by the homepage."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
EXPLORER_HTML = ROOT / "app" / "index.html"
CATALOG_PATH = ROOT / "data" / "election_catalog.json"
WORLD_MAP_PATH = ROOT / "data" / "world_countries_simplified.geojson"

AUSTRALIAN_JURISDICTIONS = {
    "Australia",
    "Victoria",
    "New South Wales",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Northern Territory",
    "Tasmania",
}

NATURAL_EARTH_NAMES = {
    "Turkey": "Türkiye",
    "United States of America": "United States",
}


def load_election_definitions(path: Path = EXPLORER_HTML) -> list[dict[str, object]]:
    html = path.read_text(encoding="utf-8")
    match = re.search(r"const electionDefinitions = (\[.*?\]);", html, flags=re.S)
    if not match:
        raise SystemExit(f"Could not find electionDefinitions in {path}")
    return json.loads(match.group(1))


def catalogue_label(election: dict[str, object], country: str) -> str:
    label = str(election["label"])
    jurisdiction = str(election["jurisdiction"])
    if country == "Australia":
        return label.replace(" - Australia", "") if jurisdiction == "Australia" else label
    prefix = f"{country} "
    return label[len(prefix) :] if label.startswith(prefix) else label


def build_catalogue(definitions: list[dict[str, object]]) -> list[dict[str, object]]:
    catalogue = []
    for election in definitions:
        jurisdiction = str(election["jurisdiction"])
        country = "Australia" if jurisdiction in AUSTRALIAN_JURISDICTIONS else jurisdiction
        catalogue.append(
            {
                "key": election["key"],
                "label": election["label"],
                "pickerLabel": catalogue_label(election, country),
                "country": country,
                "jurisdiction": jurisdiction,
                "year": election["year"],
                "type": election["type"],
                "contestType": election.get("contestType", ""),
                "systemLabel": election.get("systemLabel", ""),
                "source": election["source"],
            }
        )
    return catalogue


def find_natural_earth_source(explicit: Path | None) -> Path:
    if explicit:
        if not explicit.exists():
            raise SystemExit(f"Natural Earth source does not exist: {explicit}")
        return explicit

    try:
        import pyogrio
    except ImportError as exc:
        raise SystemExit("Install requirements.txt or pass --world-source") from exc

    fixture = Path(pyogrio.__file__).resolve().parent / "tests" / "fixtures" / "naturalearth_lowres" / "naturalearth_lowres.shp"
    if not fixture.exists():
        raise SystemExit("Natural Earth fixture was not found; pass --world-source path/to/file.shp")
    return fixture


def rounded_coordinates(value):
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, list):
        return [rounded_coordinates(item) for item in value]
    return value


def build_world_map(source: Path, countries: set[str]) -> dict[str, object]:
    world = gpd.read_file(source)[["name", "geometry"]]
    world = world[world["name"] != "Antarctica"].copy()
    world["geometry"] = world.geometry.simplify(0.18, preserve_topology=True)

    features = []
    matched = set()
    for row in world.itertuples(index=False):
        natural_earth_name = str(row.name)
        catalogue_country = NATURAL_EARTH_NAMES.get(natural_earth_name, natural_earth_name)
        if catalogue_country not in countries:
            catalogue_country = ""
        else:
            matched.add(catalogue_country)
        geometry = json.loads(gpd.GeoSeries([row.geometry], crs=world.crs).to_json())["features"][0]["geometry"]
        geometry["coordinates"] = rounded_coordinates(geometry["coordinates"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": natural_earth_name,
                    "catalogueCountry": catalogue_country,
                },
                "geometry": geometry,
            }
        )

    # Natural Earth's low-resolution country layer omits city-state polygons.
    if "Singapore" in countries:
        features.append(
            {
                "type": "Feature",
                "properties": {"name": "Singapore", "catalogueCountry": "Singapore", "marker": True},
                "geometry": {"type": "Point", "coordinates": [103.82, 1.352]},
            }
        )
        matched.add("Singapore")

    missing = sorted(countries - matched)
    if missing:
        raise SystemExit(f"Coverage countries missing from Natural Earth map: {', '.join(missing)}")

    return {
        "type": "FeatureCollection",
        "name": "Natural Earth low resolution countries",
        "source": "Natural Earth public domain data",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-source", type=Path, help="Natural Earth country shapefile or compatible vector file")
    args = parser.parse_args()

    definitions = load_election_definitions()
    catalogue = build_catalogue(definitions)
    countries = {str(election["country"]) for election in catalogue}
    world_map = build_world_map(find_natural_earth_source(args.world_source), countries)

    CATALOG_PATH.write_text(
        json.dumps(catalogue, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    WORLD_MAP_PATH.write_text(
        json.dumps(world_map, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {CATALOG_PATH.relative_to(ROOT)} ({len(catalogue)} election views)")
    print(f"Wrote {WORLD_MAP_PATH.relative_to(ROOT)} ({len(countries)} covered countries)")


if __name__ == "__main__":
    main()
