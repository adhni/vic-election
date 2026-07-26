#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import requests
import urllib3
from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

YSK_RESULT_QUERY = (
    "https://acikveri.ysk.gov.tr/api/getSecimSandikSonucList"
    "?secimId={election_id}&secimTuru=9&ilId=&ilceId=&beldeId=&birimId="
    "&muhtarlikId=&cezaeviId=&sandikTuru=&sandikNoIlk=&sandikNoSon="
    "&ulkeId=&disTemsilcilikId=&gumrukId=&yurtIciDisi=1"
    "&sandikRumuzIlk=&sandikRumuzSon=&secimCevresiId=&sandikId=&sorguTuru=1"
)
BOUNDARY_URL = (
    "https://cbs1.tarimorman.gov.tr/server/rest/services/TATUS/MapServer/12/query"
    "?where=1%3D1&outFields=ID,ADI&returnGeometry=true&outSR=4326"
    "&geometryPrecision=5&maxAllowableOffset=0.01&f=geojson"
)
BOUNDARY_PAGE = (
    "https://cbs1.tarimorman.gov.tr/server/rest/services/TATUS/MapServer/12"
)
FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

# YSK's public open-data host currently presents a certificate chain that common
# command-line clients cannot verify. Source bodies are therefore checksum-pinned.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ELECTIONS = {
    (2023, 1): {
        "election_id": 20230,
        "checksum": "33d3902c2c4ed4cb05c41849d09220a4bf8d9e92209df893bbf3b4713a8863a3",
        "candidates": (
            "Recep Tayyip Erdoğan",
            "Muharrem İnce",
            "Kemal Kılıçdaroğlu",
            "Sinan Oğan",
        ),
        "expected": {
            "Recep Tayyip Erdoğan": 26_086_102,
            "Muharrem İnce": 216_470,
            "Kemal Kılıçdaroğlu": 23_873_749,
            "Sinan Oğan": 2_796_613,
        },
    },
    (2023, 2): {
        "election_id": 20240,
        "checksum": "fe99b4245009914e335b5182cc32b77a2d7e2cd164c9c57b26c9e5b958d3fb17",
        "candidates": ("Recep Tayyip Erdoğan", "Kemal Kılıçdaroğlu"),
        "expected": {
            "Recep Tayyip Erdoğan": 26_690_529,
            "Kemal Kılıçdaroğlu": 24_728_027,
        },
    },
    (2018, 1): {
        "election_id": 16300,
        "checksum": "b99dc843dab66b7ec7f560b530aecefbefdea514e3d1712ff7811c1db1f30c22",
        "candidates": (
            "Muharrem İnce",
            "Meral Akşener",
            "Recep Tayyip Erdoğan",
            "Selahattin Demirtaş",
            "Temel Karamollaoğlu",
            "Doğu Perinçek",
        ),
        "expected": {
            "Muharrem İnce": 14_951_788,
            "Meral Akşener": 3_603_858,
            "Recep Tayyip Erdoğan": 25_436_238,
            "Selahattin Demirtaş": 4_039_390,
            "Temel Karamollaoğlu": 434_882,
            "Doğu Perinçek": 95_928,
        },
    },
    (2014, 1): {
        "election_id": 13340,
        "checksum": "e0946262e4e9a865935404a8a42532a734173ca5375ec1bd66b733127d86ff2f",
        "candidates": (
            "Recep Tayyip Erdoğan",
            "Selahattin Demirtaş",
            "Ekmeleddin Mehmet İhsanoğlu",
        ),
        "expected": {
            "Recep Tayyip Erdoğan": 20_670_826,
            "Selahattin Demirtaş": 3_914_359,
            "Ekmeleddin Mehmet İhsanoğlu": 15_434_167,
        },
    },
}
BOUNDARY_CHECKSUM = "885e0cd9f303458ceed9909d3aeaf3f1bfa6f39fbac79a4dd9e0fb73e12e8e9d"


def download(url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=300, verify=False)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(
            f"{path}: source checksum changed to {actual}; expected {expected}"
        )


def build_boundary(source_path: Path, data_dir: Path) -> dict[int, str]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    features = []
    names: dict[int, str] = {}
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        province_id = int(properties["ID"])
        name = str(properties["ADI"]).strip()
        if province_id in names:
            raise SystemExit(f"Duplicate boundary province ID {province_id}")
        names[province_id] = name
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        if geometry.geom_type == "GeometryCollection":
            geometry = unary_union([
                part for part in geometry.geoms
                if part.geom_type in {"Polygon", "MultiPolygon"}
            ])
        if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise SystemExit(
                f"Boundary province {province_id} has unusable {geometry.geom_type} geometry"
            )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": name,
                    "constituency_code": f"TR-{province_id:02d}",
                    "province_code": province_id,
                },
                "geometry": mapping(geometry),
            }
        )
    if set(names) != set(range(1, 82)):
        raise SystemExit(f"Expected province IDs 1–81, got {sorted(names)}")
    output = {"type": "FeatureCollection", "features": sorted(
        features, key=lambda item: item["properties"]["province_code"]
    )}
    (data_dir / "turkiye_province_boundaries.geojson").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return names


def output_rows(
    source_path: Path,
    config: dict[str, object],
    province_names: dict[int, str],
    year: int,
    round_number: int,
) -> list[dict[str, object]]:
    source_rows = json.loads(source_path.read_text(encoding="utf-8"))
    candidate_names = tuple(config["candidates"])
    rows: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    seen: set[int] = set()
    source_url = YSK_RESULT_QUERY.format(election_id=config["election_id"])
    for source in source_rows:
        province_id = source.get("il_ID")
        if not isinstance(province_id, int):
            continue
        if province_id in seen:
            raise SystemExit(f"{year} round {round_number}: duplicate province {province_id}")
        seen.add(province_id)
        votes = Counter({
            candidate: int(source[f"bagimsiz{index}_ALDIGI_OY"])
            for index, candidate in enumerate(candidate_names, start=1)
        })
        formal = int(source["gecerli_OY_TOPLAMI"])
        informal = int(source["gecersiz_OY_TOPLAMI"])
        total = int(source["oy_KULLANAN_SECMEN_SAYISI"])
        enrolment = int(source["secmen_SAYISI"])
        if sum(votes.values()) != formal:
            raise SystemExit(
                f"{year} round {round_number} {province_id}: candidate/formal mismatch"
            )
        if formal + informal != total:
            raise SystemExit(
                f"{year} round {round_number} {province_id}: ballot-total mismatch"
            )
        ordered = votes.most_common()
        winner, winner_votes = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else 0
        district = province_names[province_id]
        base = {
            "district": district,
            "district_url": source_url,
            "distribution_url": BOUNDARY_PAGE,
            "elected_member": winner,
            "elected_party": winner,
            "enrolment": enrolment,
            "formal_votes": formal,
            "informal_votes": informal,
            "total_votes": total,
            "turnout_pct": round(total * 100 / enrolment, 2),
            "majority": winner_votes - runner_up,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": "Province",
            "constituency_code": f"TR-{province_id:02d}",
            "contest_status": "official",
            "result_note": (
                "Official YSK domestic province total. Overseas and customs votes "
                "are included in the national result but are not assigned to provinces."
            ),
        }
        for candidate, candidate_votes in ordered:
            rows.append({
                **base,
                "candidate": candidate,
                "candidate_party": candidate,
                "votes": candidate_votes,
            })
            totals[candidate] += candidate_votes
    if seen != set(range(1, 82)):
        raise SystemExit(
            f"{year} round {round_number}: expected province IDs 1–81, got {sorted(seen)}"
        )
    if dict(totals) != config["expected"]:
        raise SystemExit(
            f"{year} round {round_number}: candidate totals changed\n"
            f"expected {config['expected']}\nactual {dict(totals)}"
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Türkiye 2023, 2018, and 2014 presidential province views."
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/turkiye"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)

    boundary_path = download(
        BOUNDARY_URL, args.cache_dir / "provinces.geojson", args.refresh
    )
    require_sha256(boundary_path, BOUNDARY_CHECKSUM)
    province_names = build_boundary(boundary_path, args.data_dir)

    for (year, round_number), config in ELECTIONS.items():
        suffix = f"_{round_number}" if year == 2023 else ""
        source_path = download(
            YSK_RESULT_QUERY.format(election_id=config["election_id"]),
            args.cache_dir / (
                f"ysk_{year}_round_{round_number}.json"
                if year == 2023 else f"ysk_{year}.json"
            ),
            args.refresh,
        )
        require_sha256(source_path, config["checksum"])
        rows = output_rows(
            source_path, config, province_names, year, round_number
        )
        output_name = (
            f"turkiye_{year}_president_round{suffix}_province_fpp.csv"
            if year == 2023
            else f"turkiye_{year}_president_province_fpp.csv"
        )
        with (args.data_dir / output_name).open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{output_name}: 81 provinces, {len(rows)} candidate rows")
    print("Built four Türkiye presidential election views.")


if __name__ == "__main__":
    main()
