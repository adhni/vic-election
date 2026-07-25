#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import mapping


YEARS = (2025, 2021, 2017)
LAND_NAMES = {
    "01": "Schleswig-Holstein",
    "02": "Hamburg",
    "03": "Lower Saxony",
    "04": "Bremen",
    "05": "North Rhine-Westphalia",
    "06": "Hesse",
    "07": "Rhineland-Palatinate",
    "08": "Baden-Württemberg",
    "09": "Bavaria",
    "10": "Saarland",
    "11": "Berlin",
    "12": "Brandenburg",
    "13": "Mecklenburg-Vorpommern",
    "14": "Saxony",
    "15": "Saxony-Anhalt",
    "16": "Thuringia",
}
SOURCES = {
    2025: {
        "results_url": (
            "https://www.bundeswahlleiterin.de/bundestagswahlen/2025/"
            "ergebnisse/opendata/btw25/csv/kerg2.csv"
        ),
        "results_sha256": "c68b097e37da16b13a21c0b21871a7e06b1fd8d6c32e01a415d434becf761288",
        "shapes_url": (
            "https://www.bundeswahlleiterin.de/dam/jcr/556bec9c-be80-4818-a368-fe6596f15f08/"
            "btw25_geometrie_wahlkreise_shp_geo.zip"
        ),
        "shapes_sha256": "3e6fc89bba314a7840ad1dde3de29e7cd4116962b3f92aef698083e27a05784a",
        "results_page": "https://www.bundeswahlleiterin.de/bundestagswahlen/2025/ergebnisse.html",
    },
    2021: {
        "results_url": (
            "https://www.bundeswahlleiterin.de/dam/jcr/860495c9-83fb-4068-8a99-c1c985ffffd2/"
            "w-btw21_kerg2.csv"
        ),
        "results_sha256": "7057cef6234df64ce5c1724f035ceb1b798c7e80e518714d5903ab3500167c05",
        "shapes_url": (
            "https://www.bundeswahlleiterin.de/dam/jcr/8794eadd-fc0c-4889-a233-2ccae3b4cf5e/"
            "btw21_geometrie_wahlkreise_geo_shp.zip"
        ),
        "shapes_sha256": "bd54285fb0abf5c0abeed0704d4982a995bab9d509e6a1da0a641df541c5297b",
        "results_page": "https://www.bundeswahlleiterin.de/bundestagswahlen/2021/ergebnisse.html",
    },
    2017: {
        "results_url": (
            "https://www.bundeswahlleiterin.de/dam/jcr/0d1ea773-f3ca-40ea-b8ff-b031712707e1/"
            "btw17_kerg2.csv"
        ),
        "results_sha256": "be127ebed1c5cf35d25684ca1ce60f40e1fb431c9a9e27764feb7d9ff1410022",
        "shapes_url": (
            "https://www.bundeswahlleiterin.de/dam/jcr/f92e42fa-44f1-47e5-b775-924926b34268/"
            "btw17_geometrie_wahlkreise_geo_shp.zip"
        ),
        "shapes_sha256": "9ddc85fded528f962f9005e63b4fcbfb4adb7298a4e87d6d883cea972efed364",
        "results_page": "https://www.bundeswahlleiterin.de/bundestagswahlen/2017/ergebnisse.html",
    },
}
FIELDS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "round_number",
    "row_type",
    "excluded_candidate",
    "excluded_party",
    "candidate",
    "candidate_party",
    "votes",
    "electorate_type",
    "contest_status",
    "result_note",
    "mandate_awarded",
]


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: SHA-256 mismatch: expected {expected}, got {actual}")


def download(url: str, path: Path, refresh: bool) -> None:
    if not path.exists() or refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(
            url,
            headers={"User-Agent": "election-preference-explorer/1.0"},
            timeout=120,
        )
        response.raise_for_status()
        path.write_bytes(response.content)


def integer(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def parse_results(path: Path, year: int) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for _ in range(9):
            next(handle)
        source_rows = list(csv.DictReader(handle, delimiter=";"))

    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        if row["Gebietsart"] == "Wahlkreis":
            groups[row["Gebietsnummer"]].append(row)
    if len(groups) != 299:
        raise SystemExit(f"{year}: expected 299 constituencies, found {len(groups)}")

    output: list[dict[str, object]] = []
    for code in sorted(groups):
        rows = groups[code]
        district = rows[0]["Gebietsname"].strip()
        state = LAND_NAMES[rows[0]["UegGebietsnummer"]]

        system: dict[tuple[str, str], int] = {}
        for row in rows:
            if row["Gruppenart"] != "System-Gruppe":
                continue
            count = integer(row["Anzahl"])
            if count is not None:
                system[(row["Gruppenname"], row["Stimme"])] = count

        enrolment = system[("Wahlberechtigte", "")]
        total_votes = system.get(("Wählende", ""), system.get(("Wähler", "")))
        formal_votes = system[("Gültige", "1")]
        informal_votes = system[("Ungültige", "1")]
        party_formal = system[("Gültige", "2")]
        if total_votes is None:
            raise SystemExit(f"{year} {code}: missing voter total")
        if total_votes != formal_votes + informal_votes:
            raise SystemExit(f"{year} {code}: first-vote total does not reconcile")

        first: list[tuple[str, str, int]] = []
        second: list[tuple[str, str, int]] = []
        for row in rows:
            if row["Gruppenart"] == "System-Gruppe":
                continue
            count = integer(row["Anzahl"])
            if count is None:
                continue
            group = row["Gruppenname"].strip()
            party = group if row["Gruppenart"] == "Partei" else "Independent"
            target = first if row["Stimme"] == "1" else second if row["Stimme"] == "2" else None
            if target is not None:
                target.append((group, party, count))

        if sum(votes for _, _, votes in first) != formal_votes:
            raise SystemExit(f"{year} {code}: first votes do not equal valid first votes")
        if sum(votes for _, _, votes in second) != party_formal:
            raise SystemExit(f"{year} {code}: second votes do not equal valid second votes")

        winner, winner_party, _ = max(first, key=lambda item: (item[2], item[0]))
        elected_marker = rows[0].get("Gewählt", "").strip()
        mandate_awarded = year != 2025 or elected_marker not in {"", "–", "-"}
        if year == 2025 and mandate_awarded and elected_marker != winner:
            raise SystemExit(
                f"{year} {code}: awarded party {elected_marker!r} differs from first-vote winner {winner!r}"
            )
        result_note = (
            "The Erststimme leader did not receive a constituency mandate because the party lacked "
            "sufficient Zweitstimme coverage under the 2025 electoral law."
            if not mandate_awarded
            else ""
        )
        base = {
            "district": f"{int(code):03d} {district}",
            "district_url": SOURCES[year]["results_page"],
            "distribution_url": SOURCES[year]["results_page"],
            "elected_member": winner if mandate_awarded else "",
            "elected_party": winner_party,
            "enrolment": enrolment,
            "formal_votes": formal_votes,
            "informal_votes": informal_votes,
            "total_votes": total_votes,
            "turnout_pct": round(total_votes * 100 / enrolment, 6),
            "majority": formal_votes // 2 + 1,
            "round_number": 0,
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": state,
            "contest_status": "official",
            "result_note": result_note,
            "mandate_awarded": str(mandate_awarded),
        }
        output.extend(
            {
                **base,
                "row_type": "first",
                "candidate": group,
                "candidate_party": party,
                "votes": votes,
            }
            for group, party, votes in first
        )
        output.extend(
            {
                **base,
                "row_type": "party_vote",
                "candidate": group,
                "candidate_party": party,
                "votes": votes,
            }
            for group, party, votes in second
        )
    return output


def build_boundaries(zip_path: Path, out_path: Path, result_names: set[str]) -> None:
    extract_dir = zip_path.with_suffix("")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    shape_path = next(extract_dir.glob("*.shp"))
    frame = gpd.read_file(shape_path).to_crs(4326)
    if len(frame) != 299:
        raise SystemExit(f"{zip_path}: expected 299 shapes, found {len(frame)}")

    features = []
    for _, row in frame.iterrows():
        code = f"{int(row['WKR_NR']):03d}"
        district = f"{code} {str(row['WKR_NAME']).strip()}"
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": district,
                    "constituency_code": code,
                    "state": LAND_NAMES[f"{int(row['LAND_NR']):02d}"],
                },
                "geometry": mapping(row.geometry.simplify(0.003, preserve_topology=True)),
            }
        )
    boundary_names = {feature["properties"]["district"] for feature in features}
    if boundary_names != result_names:
        raise SystemExit(f"{zip_path}: result/boundary mismatch: {sorted(boundary_names ^ result_names)[:10]}")
    out_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def build_year(year: int, raw_dir: Path, out_dir: Path, refresh: bool) -> None:
    source = SOURCES[year]
    result_path = raw_dir / f"btw{str(year)[-2:]}_kerg2.csv"
    shape_path = raw_dir / f"btw{str(year)[-2:]}_shapes.zip"
    download(source["results_url"], result_path, refresh)
    download(source["shapes_url"], shape_path, refresh)
    require_sha256(result_path, source["results_sha256"])
    require_sha256(shape_path, source["shapes_sha256"])

    rows = parse_results(result_path, year)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"germany_{year}_bundestag.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    names = {row["district"] for row in rows}
    boundary_path = out_dir / f"germany_{year}_constituency_boundaries.geojson"
    build_boundaries(shape_path, boundary_path, names)
    print(f"Germany {year}: {len(names)} constituencies, {len(rows)} vote rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build official German Bundestag constituency results")
    parser.add_argument("--year", type=int, choices=YEARS)
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/germany_bundestag"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    for year in (args.year,) if args.year else YEARS:
        build_year(year, args.raw_dir, args.out_dir, args.refresh)


if __name__ == "__main__":
    main()
