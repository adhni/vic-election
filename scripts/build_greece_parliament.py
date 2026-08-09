#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

import requests
from shapely.geometry import mapping, shape


ROOTS = {
    2023: "https://ekloges-prev.singularlogic.eu/2023/june",
    2019: "https://ekloges-prev.singularlogic.eu/2019",
}
SOURCE_PAGE = "https://www.ypes.gr/lipsi-archeion-apotelesmaton-ethnikon-eklogon/"
ASSETS = {
    2023: {
        "national": ("dyn1/v/epik_1.js", "a46205b04a1953a3f4bafb327847e616d9dcf4b8d4fe4ffe1b1f65de16eaa842"),
        "index": ("dyn/v/eps.js", "761a4ddd265ce507824fef70329d4fca0f720b8b787772616a53acd52ed21217"),
        "model": ("v/home/dist/model.el.js", "cc99a244a5c6543a76fa145e103cb15124b692f8675b6afec369a502915229c4"),
        "map": ("v/home/data/2023b/maps/ep.json", "a92bc3fafe826ad73ca68462a3e23b8c9bd35babc90178eb044fbfe47a317786"),
    },
    2019: {
        "national": ("dyn1/v/epik_1.js", "041d0cfb5a17aad93e6a6f71b15e0ecd270032930c907d749e657e832480d711"),
        "index": ("dyn/v/eps.js", "7ba58d1ff8d76df628d933872e65dba9eba708dccd9d0ba8b1c704e35fb32645"),
        "model": ("v/home/dist/model.el.js", "5e6ad4c0fadebc2e8dc915d71cb2602809bd7a9127eb02d7df4bd0948bf745d3"),
        "map": ("v/home/data/2019/maps/ep.json", "986f35ce10b53cd389b61133b39f9f317af1856372816e08e1ffaf170938bad5"),
    },
}
# Digest of the 59 detailed domestic constituency payloads in ascending EP_ID order.
RESULT_SET_SHA256 = {
    2023: "863d2ea57185beeea4c68006be961a85135d5258417b7b703ac83679e66e67b4",
    2019: "f683b3d03f1dbd530432ced8ed364f19f4ea602a50fb4413e5432812cf260688",
}

PARTY_LABELS = {
    2: "New Democracy", 4: "SYRIZA", 106: "PASOK–KINAL", 3: "KKE",
    108: "Greek Solution", 157: "Spartans", 131: "Niki",
    123: "Course of Freedom", 122: "MeRA25", 44: "ANTARSYA",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note", "district_seats",
)


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            response = session.get(url, timeout=600)
            response.raise_for_status()
            path.write_bytes(response.content)
            break
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    return path


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: checksum changed; expected {expected}, found {actual}")


def parse_model(path: Path) -> tuple[dict[int, str], dict[int, str]]:
    source = path.read_text(encoding="utf-8")
    parties = {
        int(match.group(1)): PARTY_LABELS.get(int(match.group(1)), match.group(2).strip())
        for match in re.finditer(
            r"(\d+):\{id:\1,name:(?:\"[^\"]*\"|'[^']*'),shortName:\"([^\"]+)\"",
            source,
        )
    }
    district_start = re.search(r"[a-zA-Z]=\{38:\{id:38,name:\"", source)
    if not district_start:
        raise SystemExit(f"{path}: constituency metadata block was not found")
    tail = source[district_start.start():]
    district_end = re.search(r"\},[a-zA-Z]=\{", tail)
    block = tail[:district_end.start() + 1] if district_end else tail
    districts = {
        int(match.group(1)): match.group(2)
        for match in re.finditer(
            r"(\d+):\{id:\d+,name:\"([^\"]+)\",order:\d+,countTm:", block
        )
    }
    if len(districts) not in {59, 60}:
        raise SystemExit(f"{path}: expected 59 domestic constituency labels, with optional overseas")
    return parties, districts


def decode_topology(path: Path, valid_ids: set[int], year: int, names: dict[int, str]) -> dict[str, object]:
    topology = json.loads(path.read_text(encoding="utf-8"))
    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]
    decoded_arcs = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append([x * scale[0] + translate[0], y * scale[1] + translate[1]])
        decoded_arcs.append(points)
    all_points = [point for arc in decoded_arcs for point in arc]
    min_x, max_x = min(p[0] for p in all_points), max(p[0] for p in all_points)
    min_y, max_y = min(p[1] for p in all_points), max(p[1] for p in all_points)

    def normalized(point: list[float]) -> list[float]:
        longitude = 19 + (point[0] - min_x) / (max_x - min_x) * 10
        latitude = 42 - (point[1] - min_y) / (max_y - min_y) * 7.5
        return [round(longitude, 5), round(latitude, 5)]

    def ring(indices: list[int]) -> list[list[float]]:
        points: list[list[float]] = []
        for index in indices:
            arc = decoded_arcs[index] if index >= 0 else list(reversed(decoded_arcs[-index - 1]))
            points.extend(arc if not points else arc[1:])
        output = [normalized(point) for point in points]
        if output and output[0] != output[-1]:
            output.append(output[0])
        return output

    features = []
    geometries = topology["objects"]["tracts"]["geometries"]
    for geometry in geometries:
        district_id = int(geometry["id"])
        if district_id not in valid_ids:
            continue
        if geometry["type"] == "Polygon":
            coordinates = [[ring(indices) for indices in geometry["arcs"]]]
            geo_type = "MultiPolygon"
        elif geometry["type"] == "MultiPolygon":
            coordinates = [[ring(indices) for indices in polygon] for polygon in geometry["arcs"]]
            geo_type = "MultiPolygon"
        else:
            raise SystemExit(f"Greece {year}: unsupported topology type {geometry['type']}")
        feature_geometry = {"type": geo_type, "coordinates": coordinates}
        repaired = shape(feature_geometry)
        if not repaired.is_valid:
            repaired = repaired.buffer(0)
        if repaired.is_empty or not repaired.is_valid:
            raise SystemExit(f"Greece {year}: invalid decoded geometry for district {district_id}")
        features.append({
            "type": "Feature",
            "properties": {
                "district": names[district_id],
                "constituency_code": f"GR{year}-{district_id:02d}",
                "electorate_type": "Greece",
            },
            "geometry": mapping(repaired),
        })
    if len(features) != 59:
        raise SystemExit(f"Greece {year}: expected 59 mapped domestic constituencies")
    return {
        "type": "FeatureCollection", "name": f"greece_{year}_electoral_constituencies",
        "source": "Greek Ministry of Interior / SingularLogic official election-site topology; affine georeferencing preserves its inset layout",
        "features": features,
    }


def build_year(
    year: int,
    paths: dict[str, Path],
    session: requests.Session,
    raw_dir: Path,
    out_dir: Path,
    refresh: bool,
) -> None:
    national = json.loads(paths["national"].read_text(encoding="utf-8"))
    index = json.loads(paths["index"].read_text(encoding="utf-8"))
    parties, names = parse_model(paths["model"])
    domestic_ids = sorted(int(row["EP_ID"]) for row in index if int(row["EP_ID"]) != 57)
    if len(domestic_ids) != 59:
        raise SystemExit(f"Greece {year}: expected 59 domestic result areas")

    payloads: dict[int, bytes] = {}
    for district_id in domestic_ids:
        url = f"{ROOTS[year]}/dyn/v/ep_{district_id}.js"
        path = download(session, url, raw_dir / str(year) / f"ep_{district_id}.json", refresh)
        payloads[district_id] = path.read_bytes()
    digest = hashlib.sha256(b"".join(payloads[district_id] for district_id in domestic_ids)).hexdigest()
    expected_digest = RESULT_SET_SHA256[year]
    if expected_digest and digest != expected_digest:
        raise SystemExit(f"Greece {year}: constituency result set changed to {digest}")
    if not expected_digest:
        print(f"Greece {year} constituency payload SHA256: {digest}")

    rows = []
    local_seats = Counter()
    local_votes = Counter()
    for district_id in domestic_ids:
        result = json.loads(payloads[district_id])
        votes = {parties[int(item["PARTY_ID"])]: int(item["VOTES"]) for item in result["party"]}
        seats = {parties[int(item["PARTY_ID"])]: int(item.get("Edres", 0)) for item in result["party"]}
        local_votes.update(votes)
        local_seats.update(seats)
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(result["Egkyra"])
        informal = int(result["Akyra"]) + int(result["Leyka"])
        enrolment = int(result["Gramenoi"])
        if sum(votes.values()) != formal:
            raise SystemExit(f"Greece {year} district {district_id}: party votes do not reconcile")
        district_seats = sum(seats.values())
        base = {
            "district": names[district_id],
            "district_url": f"{ROOTS[year]}/v/home/districts/{district_id}/",
            "distribution_url": SOURCE_PAGE,
            "elected_member": ranked[0][0], "elected_party": ranked[0][0],
            "enrolment": enrolment, "formal_votes": formal, "informal_votes": informal,
            "total_votes": formal + informal,
            "turnout_pct": round((formal + informal) / enrolment * 100, 2),
            "majority": ranked[0][1] - ranked[1][1], "round_number": 0,
            "row_type": "first", "excluded_candidate": "", "excluded_party": "",
            "electorate_type": "Greece", "constituency_code": f"GR{year}-{district_id:02d}",
            "contest_status": "archived-result-feed",
            "result_note": "Ministry-hosted election archive; the map shows the locally leading party list, while seats are allocated under the national parliamentary system.",
            "district_seats": district_seats,
        }
        for party, party_votes in ranked:
            rows.append({**base, "candidate": party, "candidate_party": party, "votes": party_votes})

    national_votes = {parties[int(item["PARTY_ID"])]: int(item["VOTES"]) for item in national["party"]}
    national_seats = {
        parties[int(item["PARTY_ID"])]: int(item["Edres"]) + int(item.get("EdresEpik", 0))
        for item in national["party"]
        if int(item["Edres"]) + int(item.get("EdresEpik", 0)) > 0
    }
    if sum(national_votes.values()) != int(national["Egkyra"]) or sum(national_seats.values()) != 300:
        raise SystemExit(f"Greece {year}: national vote or seat totals do not reconcile")
    if any(local_votes[party] > votes for party, votes in national_votes.items()):
        raise SystemExit(f"Greece {year}: a domestic party total exceeds the national feed")

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"greece_{year}_parliament_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    boundaries = decode_topology(paths["map"], set(domestic_ids), year, names)
    (out_dir / f"greece_{year}_parliament_boundaries.geojson").write_text(
        json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"Greece {year}: wrote {len(rows)} rows, 59 constituencies and 300 seats")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Greece June 2023 and July 2019 parliamentary maps")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/greece_parliament"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    for year in (2023, 2019):
        paths = {}
        for key, (relative_url, expected_hash) in ASSETS[year].items():
            path = download(session, f"{ROOTS[year]}/{relative_url}", args.raw_dir / str(year) / Path(relative_url).name, args.refresh)
            require_sha256(path, expected_hash)
            paths[key] = path
        build_year(year, paths, session, args.raw_dir, args.out_dir, args.refresh)


if __name__ == "__main__":
    main()
