#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable


BOUNDARY_NAME_FIXES = {
    "Eden-monaro": "Eden-Monaro",
    "Mcewen": "McEwen",
    "Mcmahon": "McMahon",
    "Mcmillan": "McMillan",
    "Mcpherson": "McPherson",
    "O'connor": "O'Connor",
}
DIVISION_NAME_FIELDS = ("Elect_div", "ELECT_DIV")
DIVISION_ID_FIELDS = ("E_div_numb", "DIV_NUMBER")
STATE_FIELDS = ("STATE", "STATE_AB", "StateAb")
CoordinateTransformer = Callable[[float, float], tuple[float, float]]


def normalize_scope(scope: str) -> str:
    return scope.strip().lower()


def scope_matches_state(scope: str, value: str | None) -> bool:
    if scope == "au":
        return True
    return (value or "").strip().lower() == scope


def read_aec_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        next(f)
        return list(csv.DictReader(f))


def candidate_name(row: dict[str, str]) -> str:
    surname = (row.get("Surname") or "").strip()
    given = (row.get("GivenNm") or "").strip()
    return f"{surname}, {given}" if given else surname


def party_name(row: dict[str, str]) -> str:
    return (row.get("PartyNm") or "").strip() or "Independent"


def int_value(value: str | float | int | None) -> int:
    if value in (None, ""):
        return 0
    return int(round(float(value)))


def record_value(record: dict[str, object], fields: tuple[str, ...]) -> object:
    for field in fields:
        if field in record:
            return record[field]
    raise KeyError(f"Missing boundary field; expected one of {fields}")


def optional_record_value(record: dict[str, object], fields: tuple[str, ...]) -> object:
    for field in fields:
        if field in record:
            return record[field]
    return ""


def record_state(record: dict[str, object]) -> str:
    return str(optional_record_value(record, STATE_FIELDS)).strip().upper()


def record_matches_scope(record: dict[str, object], scope: str) -> bool:
    if scope == "au":
        return True
    return record_state(record).lower() == scope


def load_lookup(rows: list[dict[str, str]], scope: str, key: str = "DivisionNm") -> dict[str, dict[str, str]]:
    return {
        row[key]: row
        for row in rows
        if scope_matches_state(scope, row.get("StateAb"))
    }


def build_preferences(raw_dir: Path, out_dir: Path, year: int, event_id: str, scope: str) -> tuple[Path, Path]:
    source_base = f"https://results.aec.gov.au/{event_id}/Website"
    dop = [r for r in read_aec_csv(raw_dir / f"HouseDopByDivisionDownload-{event_id}.csv") if scope_matches_state(scope, r.get("StateAb"))]
    members = load_lookup(read_aec_csv(raw_dir / f"HouseMembersElectedDownload-{event_id}.csv"), scope)
    enrolment = load_lookup(read_aec_csv(raw_dir / f"GeneralEnrolmentByDivisionDownload-{event_id}.csv"), scope)
    informal = load_lookup(read_aec_csv(raw_dir / f"HouseInformalByDivisionDownload-{event_id}.csv"), scope)
    turnout = load_lookup(read_aec_csv(raw_dir / f"HouseTurnoutByDivisionDownload-{event_id}.csv"), scope)

    by_division: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dop:
        by_division[row["DivisionNm"]].append(row)

    long_fields = [
        "district", "district_url", "distribution_url", "elected_member", "elected_party",
        "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
        "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
        "candidate", "candidate_party", "votes"
    ]
    summary_fields = [
        "district", "district_url", "distribution_url", "elected_member", "elected_party",
        "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
        "majority", "primary_leader", "primary_leader_party", "primary_leader_votes",
        "winner", "winner_party", "winner_final_votes", "runner_up", "runner_up_party",
        "runner_up_final_votes", "final_margin", "preference_changed_result", "winner_transfer_gain"
    ]

    long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for division in sorted(by_division):
        entries = by_division[division]
        div_id = entries[0]["DivisionID"]
        district_url = f"{source_base}/HouseDivisionPage-{event_id}-{div_id}.htm"
        distribution_url = f"{source_base}/HouseDop-{event_id}-{div_id}.htm"

        member = members[division]
        elected_member = candidate_name(member)
        elected_party = party_name(member)
        enrol = enrolment.get(division, {})
        inf = informal.get(division, {})
        turn = turnout.get(division, {})

        meta = {
            "district": division,
            "district_url": district_url,
            "distribution_url": distribution_url,
            "elected_member": elected_member,
            "elected_party": elected_party,
            "enrolment": int_value(enrol.get("Enrolment") or turn.get("Enrolment")),
            "formal_votes": int_value(inf.get("FormalVotes")),
            "informal_votes": int_value(inf.get("InformalVotes")),
            "total_votes": int_value(inf.get("TotalVotes") or turn.get("Turnout")),
            "turnout_pct": turn.get("TurnoutPercentage", ""),
            "majority": "",
        }

        counts: dict[int, dict[str, dict[str, str]]] = defaultdict(dict)
        parties: dict[str, str] = {}
        for row in entries:
            if row["CalculationType"] not in {"Preference Count", "Transfer Count"}:
                continue
            name = candidate_name(row)
            parties[name] = party_name(row)
            counts[int(row["CountNumber"])].setdefault(name, {})[row["CalculationType"]] = row["CalculationValue"]

        first = {
            candidate: int_value(values.get("Preference Count"))
            for candidate, values in counts[0].items()
        }
        for candidate, votes in sorted(first.items(), key=lambda item: (-item[1], item[0])):
            long_rows.append({
                **meta, "round_number": 0, "row_type": "first",
                "excluded_candidate": "", "excluded_party": "",
                "candidate": candidate, "candidate_party": parties[candidate], "votes": votes,
            })

        max_count = max(counts)
        final_totals: dict[str, int] = {}
        for count in range(1, max_count + 1):
            transfer_values = {
                candidate: int_value(values.get("Transfer Count"))
                for candidate, values in counts[count].items()
            }
            excluded = min(transfer_values.items(), key=lambda item: item[1])[0]
            excluded_party = parties[excluded]
            row_type = "final" if count == max_count else "progressive"

            for candidate, votes in sorted(transfer_values.items(), key=lambda item: item[0]):
                if candidate == excluded or votes <= 0:
                    continue
                long_rows.append({
                    **meta, "round_number": count, "row_type": "transfer",
                    "excluded_candidate": excluded, "excluded_party": excluded_party,
                    "candidate": candidate, "candidate_party": parties[candidate], "votes": votes,
                })

            totals = {
                candidate: int_value(values.get("Preference Count"))
                for candidate, values in counts[count].items()
                if candidate != excluded and int_value(values.get("Preference Count")) > 0
            }
            if count == max_count:
                final_totals = totals
            for candidate, votes in sorted(totals.items(), key=lambda item: (-item[1], item[0])):
                long_rows.append({
                    **meta, "round_number": count, "row_type": row_type,
                    "excluded_candidate": excluded, "excluded_party": excluded_party,
                    "candidate": candidate, "candidate_party": parties[candidate], "votes": votes,
                })

        primary = sorted(first.items(), key=lambda item: item[1], reverse=True)
        final = sorted(final_totals.items(), key=lambda item: item[1], reverse=True)
        winner, winner_votes = final[0]
        runner_up, runner_up_votes = final[1]
        margin = winner_votes - runner_up_votes
        meta["majority"] = margin
        for row in long_rows:
            if row["district"] == division:
                row["majority"] = margin

        summary_rows.append({
            **meta,
            "primary_leader": primary[0][0],
            "primary_leader_party": parties[primary[0][0]],
            "primary_leader_votes": primary[0][1],
            "winner": winner,
            "winner_party": parties[winner],
            "winner_final_votes": winner_votes,
            "runner_up": runner_up,
            "runner_up_party": parties[runner_up],
            "runner_up_final_votes": runner_up_votes,
            "final_margin": margin,
            "preference_changed_result": str(primary[0][0] != winner),
            "winner_transfer_gain": winner_votes - first.get(winner, 0),
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"federal_{year}_{scope}"
    pref_path = out_dir / f"{prefix}_preferences_long.csv"
    summary_path = out_dir / f"{prefix}_district_summary.csv"
    with pref_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=long_fields)
        writer.writeheader()
        writer.writerows(long_rows)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary_rows)
    return pref_path, summary_path


def ring_area(points: list[list[float]]) -> float:
    return sum(
        (points[i][0] * points[(i + 1) % len(points)][1]) - (points[(i + 1) % len(points)][0] * points[i][1])
        for i in range(len(points))
    ) / 2


def resolve_prj_path(shp_path: Path, explicit_prj_path: Path | None) -> Path | None:
    if explicit_prj_path:
        if not explicit_prj_path.exists():
            raise SystemExit(f"Projection file not found: {explicit_prj_path}")
        return explicit_prj_path

    same_stem = shp_path.with_suffix(".prj")
    if same_stem.exists():
        return same_stem

    matches = sorted(shp_path.parent.glob("*.prj"))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(
            f"Multiple projection files found beside {shp_path}; pass --prj explicitly"
        )
    return None


def build_coordinate_transformer(prj_path: Path | None) -> CoordinateTransformer | None:
    if not prj_path:
        return None
    try:
        from pyproj import CRS, Transformer
    except ImportError as exc:
        raise SystemExit("Install pyproj to reproject AEC boundaries: python3 -m pip install pyproj") from exc

    source_crs = CRS.from_wkt(prj_path.read_text(encoding="utf-8"))
    target_crs = CRS.from_epsg(4326)
    if source_crs.equals(target_crs):
        return None

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return transformer.transform


def iter_positions(geometry: dict[str, object]):
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


def validate_lon_lat_geometry(geometry: dict[str, object], name: str) -> None:
    for lon, lat, *_ in iter_positions(geometry):
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise SystemExit(
                f"{name}: boundary coordinate outside lon/lat range after projection: {lon}, {lat}"
            )


def shape_to_geometry(shape, transform_point: CoordinateTransformer | None = None) -> dict[str, object]:
    points = []
    for x, y in shape.points:
        if transform_point:
            x, y = transform_point(float(x), float(y))
        points.append([round(x, 6), round(y, 6)])
    parts = list(shape.parts) + [len(points)]
    rings = [points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
    polygons: list[list[list[list[float]]]] = []
    current: list[list[list[float]]] | None = None
    for ring in rings:
        if not ring or ring[0] != ring[-1]:
            ring = ring + [ring[0]]
        if ring_area(ring) < 0 or current is None:
            current = [ring]
            polygons.append(current)
        else:
            current.append(ring)
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def build_boundaries(
    shp_path: Path,
    out_dir: Path,
    year: int,
    scope: str,
    gis_source: str,
    prj_path: Path | None = None,
) -> Path:
    sys.path.insert(0, str(Path("tmp/pydeps")))
    try:
        import shapefile
        from shapely.geometry import mapping, shape as shapely_shape
    except ImportError as exc:
        raise SystemExit("Install pyshp and shapely to generate boundaries: python3 -m pip install pyshp shapely") from exc

    projection_path = resolve_prj_path(shp_path, prj_path)
    transform_point = build_coordinate_transformer(projection_path)

    reader = shapefile.Reader(str(shp_path))
    features = []
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        if not record_matches_scope(record, scope):
            continue
        raw_district = str(record_value(record, DIVISION_NAME_FIELDS))
        district = BOUNDARY_NAME_FIXES.get(raw_district, raw_district)
        geometry = shape_to_geometry(shape_record.shape, transform_point)
        geom = shapely_shape(geometry)
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            raise SystemExit(f"{district}: empty geometry after repair")
        geometry = mapping(geom)
        validate_lon_lat_geometry(geometry, district)
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "division_id": optional_record_value(record, DIVISION_ID_FIELDS),
                "state": record_state(record),
                "source": gis_source,
            },
            "geometry": geometry,
        })

    out_path = out_dir / f"federal_{year}_{scope}_division_boundaries.geojson"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))
        f.write("\n")
    return out_path


def main(
    default_scope: str = "au",
    default_raw_dir: str = "tmp/aec_2025_au",
    default_gis_source: str = "https://www.aec.gov.au/Electorates/files/2025/AUS-March-2025-esri.zip",
    default_shp: str = "tmp/aec_2025_au/AUS_ELB_region.shp",
) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--event-id", default="31496")
    parser.add_argument("--scope", default=default_scope, help="Use 'au' for Australia-wide data or a state abbreviation such as 'vic'")
    parser.add_argument("--raw-dir", type=Path, default=Path(default_raw_dir))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument(
        "--gis-source",
        default=default_gis_source,
    )
    parser.add_argument(
        "--shp",
        type=Path,
        default=Path(default_shp),
    )
    parser.add_argument("--prj", type=Path, help="Optional projection file for the shapefile")
    args = parser.parse_args()

    scope = normalize_scope(args.scope)
    pref_path, summary_path = build_preferences(args.raw_dir, args.out, args.year, args.event_id, scope)
    boundary_path = build_boundaries(args.shp, args.out, args.year, scope, args.gis_source, args.prj)
    print(f"Wrote {pref_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
