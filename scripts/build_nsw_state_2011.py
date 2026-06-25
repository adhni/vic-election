#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import mercantile
import requests
from bs4 import BeautifulSoup
from mapbox_vector_tile import decode as decode_mvt
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union

from build_nsw_state import (
    BASE,
    LONG_FIELDS,
    SUMMARY_FIELDS,
    clean_int,
    clean_text,
    fetch_bytes,
    fetch_text,
    make_session,
    write_csv,
)


INDEX_URL = f"{BASE}/SGE2011/la_index.htm"
TILESET_URL = "https://vector-tiles.terria.io/FID_SED_2011_AUST/{z}/{x}/{y}.pbf"
RAW_TILE_BBOX = (140.5, -38.6, 154.8, -27.3)
TILE_ZOOM = 6


@dataclass
class DistrictLinks:
    district: str
    district_url: str
    distribution_url: str


def discover_districts(
    session: requests.Session,
    index_url: str,
    raw_dir: Path,
    expected_districts: int,
    refresh: bool = False,
) -> list[DistrictLinks]:
    html = fetch_text(session, index_url, raw_dir / "index.html", refresh=refresh, pause=0)
    soup = BeautifulSoup(html, "html.parser")
    districts: list[DistrictLinks] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="la/la_district_summary-"]'):
        href = link.get("href", "")
        district = clean_text(link.get_text(" ")).replace("\xa0", " ")
        if not href or not district or district in seen:
            continue
        district_url = urljoin(index_url, href)
        distribution_url = district_url.replace("la_district_summary-", "la_dop-")
        districts.append(DistrictLinks(district=district, district_url=district_url, distribution_url=distribution_url))
        seen.add(district)

    if len(districts) != expected_districts:
        raise SystemExit(f"Expected {expected_districts} NSW 2011 districts, found {len(districts)}")
    return districts


def parse_summary_table_rows(table) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [clean_text(td.get_text(" ")) for td in tr.find_all("td")]
        if cells:
            rows.append(cells)
    return rows


def parse_summary_page(html: str) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    enrolment_match = re.search(r"Electors Enrolled:\s*([\d,]+)", text)
    turnout_match = re.search(r"Voter Turnout:\s*([\d.]+)%", text)
    informal_rate_match = re.search(r"Informal Rate:\s*([\d.]+)%", text)

    enrolment = clean_int(enrolment_match.group(1)) if enrolment_match else None
    turnout_pct = float(turnout_match.group(1)) if turnout_match else None
    informal_rate = float(informal_rate_match.group(1)) if informal_rate_match else None

    tables = soup.find_all("table", class_="list")
    if len(tables) < 2:
        raise SystemExit("NSW 2011 district summary page did not contain the expected TCP and FP tables")

    tcp_rows_raw = parse_summary_table_rows(tables[0])
    fp_rows_raw = parse_summary_table_rows(tables[1])

    final_rows: list[dict[str, object]] = []
    for cells in tcp_rows_raw:
        if len(cells) < 4:
            continue
        votes = clean_int(cells[2])
        if votes is None:
            continue
        candidate = clean_text(cells[0].replace("+", ""))
        party = clean_text(cells[1].replace("+", "")) or "Independent"
        final_rows.append({
            "candidate": candidate,
            "candidate_party": party,
            "votes": votes,
        })

    first_rows: list[dict[str, object]] = []
    formal_votes = None
    informal_votes = None
    total_votes = None

    for cells in fp_rows_raw:
        if len(cells) < 8:
            continue
        label = clean_text(cells[0].replace("+", ""))
        if not label:
            continue
        if label == "Total Formal Votes Counted":
            formal_votes = clean_int(cells[-1])
            continue
        if label == "Informal":
            informal_votes = clean_int(cells[-1])
            continue
        if label == "Total Votes Counted":
            total_votes = clean_int(cells[-1])
            continue

        votes = clean_int(cells[-1])
        if votes is None:
            continue
        party = clean_text(cells[1].replace("+", "")) or "Independent"
        first_rows.append({
            "candidate": label,
            "candidate_party": party,
            "votes": votes,
        })

    if not first_rows or len(final_rows) < 2:
        raise SystemExit("NSW 2011 district summary page did not yield first/final candidate rows")

    if formal_votes is None:
        formal_votes = sum(int(row["votes"]) for row in first_rows)
    if informal_votes is None and total_votes is not None and formal_votes is not None:
        informal_votes = total_votes - formal_votes
    if total_votes is None and informal_votes is not None and formal_votes is not None:
        total_votes = formal_votes + informal_votes

    majority = formal_votes // 2 + 1 if formal_votes else None
    meta = {
        "enrolment": enrolment,
        "formal_votes": formal_votes,
        "informal_votes": informal_votes,
        "total_votes": total_votes,
        "turnout_pct": turnout_pct,
        "informal_rate": informal_rate,
        "majority": majority,
    }
    return meta, first_rows, final_rows


def build_rows_for_district(
    session: requests.Session,
    raw_dir: Path,
    links: DistrictLinks,
    refresh: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    slug = re.sub(r"[^a-z0-9]+", "-", links.district.lower()).strip("-")
    html = fetch_text(session, links.district_url, raw_dir / "districts" / f"{slug}_summary.html", refresh=refresh)
    parsed_meta, first_rows, final_rows = parse_summary_page(html)

    final_rows = sorted(final_rows, key=lambda row: (-int(row["votes"]), str(row["candidate"])))
    first_rows = sorted(first_rows, key=lambda row: (-int(row["votes"]), str(row["candidate"])))

    winner = final_rows[0]
    runner_up = final_rows[1]
    winner_first_votes = next((int(row["votes"]) for row in first_rows if row["candidate"] == winner["candidate"]), 0)

    meta = {
        "district": links.district,
        "district_url": links.district_url,
        "distribution_url": links.distribution_url,
        "elected_member": winner["candidate"],
        "elected_party": winner["candidate_party"],
        "enrolment": parsed_meta["enrolment"] or "",
        "formal_votes": parsed_meta["formal_votes"] or "",
        "informal_votes": parsed_meta["informal_votes"] or "",
        "total_votes": parsed_meta["total_votes"] or "",
        "turnout_pct": parsed_meta["turnout_pct"] if parsed_meta["turnout_pct"] is not None else "",
        "majority": parsed_meta["majority"] if parsed_meta["majority"] is not None else "",
    }

    long_rows: list[dict[str, object]] = []
    for row in first_rows:
        long_rows.append({
            **meta,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })
    for row in final_rows:
        long_rows.append({
            **meta,
            "round_number": 1,
            "row_type": "final",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })

    summary_row = {
        **meta,
        "primary_leader": first_rows[0]["candidate"],
        "primary_leader_party": first_rows[0]["candidate_party"],
        "primary_leader_votes": first_rows[0]["votes"],
        "winner": winner["candidate"],
        "winner_party": winner["candidate_party"],
        "winner_final_votes": winner["votes"],
        "runner_up": runner_up["candidate"],
        "runner_up_party": runner_up["candidate_party"],
        "runner_up_final_votes": runner_up["votes"],
        "final_margin": int(winner["votes"]) - int(runner_up["votes"]),
        "preference_changed_result": str(first_rows[0]["candidate"] != winner["candidate"]),
        "winner_transfer_gain": int(winner["votes"]) - winner_first_votes,
    }
    return long_rows, summary_row


def iter_coords(coords):
    if coords and isinstance(coords[0], (int, float)):
        yield coords
        return
    for part in coords or []:
        yield from iter_coords(part)


def tile_point_to_lonlat(z: int, x: int, y: int, px: float, py: float, extent: int) -> tuple[float, float]:
    world_x = (x + px / extent) / (2**z)
    world_y = (y + (extent - py) / extent) / (2**z)
    lon = world_x * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * world_y))))
    return lon, lat


def convert_geometry_coords(coords, z: int, x: int, y: int, extent: int):
    if coords and isinstance(coords[0], (int, float)):
        return list(tile_point_to_lonlat(z, x, y, coords[0], coords[1], extent))
    return [convert_geometry_coords(part, z, x, y, extent) for part in coords]


def decode_tile_geometries(tile_bytes: bytes, tile: mercantile.Tile) -> Iterable[tuple[str, object]]:
    data = decode_mvt(tile_bytes)
    layer = data.get("FID_SED_2011_AUST")
    if not layer:
        return []
    extent = int(layer.get("extent", 4096))
    converted = []
    for feature in layer.get("features", []):
        name = clean_text(feature.get("properties", {}).get("SED_NAME"))
        geometry = feature.get("geometry")
        if not name or not geometry:
            continue
        converted_geometry = {
            "type": geometry["type"],
            "coordinates": convert_geometry_coords(geometry["coordinates"], tile.z, tile.x, tile.y, extent),
        }
        converted.append((name, shape(converted_geometry)))
    return converted


def remove_holes(geom):
    if geom.geom_type == "Polygon":
        return Polygon(geom.exterior)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([Polygon(poly.exterior) for poly in geom.geoms if not poly.is_empty])
    return geom


def build_boundaries_from_tiles(
    session: requests.Session,
    raw_dir: Path,
    district_names: list[str],
    out_path: Path,
    zoom: int = TILE_ZOOM,
    refresh: bool = False,
) -> None:
    district_set = set(district_names)
    fragments: dict[str, list[object]] = defaultdict(list)

    for tile in mercantile.tiles(*RAW_TILE_BBOX, zooms=[zoom]):
        tile_path = raw_dir / "tiles" / str(tile.z) / str(tile.x) / f"{tile.y}.pbf"
        tile_url = TILESET_URL.format(z=tile.z, x=tile.x, y=tile.y)
        if tile_path.exists() and not refresh:
            raw = tile_path.read_bytes()
        else:
            response = session.get(tile_url, timeout=120)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            tile_path.write_bytes(response.content)
            raw = response.content
        if raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        for name, geom in decode_tile_geometries(raw, tile):
            if name not in district_set or geom.is_empty:
                continue
            fragments[name].append(geom)

    features = []
    missing = []
    for district in sorted(district_names):
        parts = fragments.get(district, [])
        if not parts:
            missing.append(district)
            continue
        geom = unary_union(parts)
        if not geom.is_valid:
            geom = geom.buffer(0)
        geom = remove_holes(geom)
        if geom.is_empty:
            missing.append(district)
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "source": f"{TILESET_URL} @ z={zoom}",
            },
            "geometry": mapping(geom),
        })

    if missing:
        raise SystemExit(f"Missing NSW 2011 boundary districts: {missing}")

    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/nsw_2011"))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--index-url", default=INDEX_URL)
    parser.add_argument("--prefix", default="nsw_2011")
    parser.add_argument("--expected-districts", type=int, default=93)
    parser.add_argument("--tile-zoom", type=int, default=TILE_ZOOM)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = make_session()
    districts = discover_districts(
        session,
        args.index_url,
        args.raw_dir,
        args.expected_districts,
        refresh=args.refresh,
    )

    all_long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for index, links in enumerate(districts, start=1):
        print(f"[{index:02d}/{len(districts)}] {links.district}")
        long_rows, summary_row = build_rows_for_district(session, args.raw_dir, links, refresh=args.refresh)
        all_long_rows.extend(long_rows)
        summary_rows.append(summary_row)

    summary_rows.sort(key=lambda row: str(row["district"]))
    all_long_rows.sort(key=lambda row: (str(row["district"]), int(row["round_number"]), str(row["row_type"]), str(row["candidate"])))

    pref_path = args.out / f"{args.prefix}_preferences_long.csv"
    summary_path = args.out / f"{args.prefix}_district_summary.csv"
    boundary_path = args.out / f"{args.prefix}_district_boundaries.geojson"
    write_csv(pref_path, all_long_rows, LONG_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    build_boundaries_from_tiles(
        session,
        args.raw_dir,
        [district.district for district in districts],
        boundary_path,
        zoom=args.tile_zoom,
        refresh=args.refresh,
    )


if __name__ == "__main__":
    main()
