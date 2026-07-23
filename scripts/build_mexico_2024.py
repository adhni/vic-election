#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import py7zr
import requests
from shapely.geometry import mapping


RESULTS_URL = "https://computos2024.ine.mx/20240608_2030_COMPUTOS.zip"
BOUNDARY_URL = "https://cartografia.ine.mx/mapoteca/MGS_CCL/SHAPEFILE.7z"
RESULTS_PAGE = "https://computos2024.ine.mx/presidencia/nacional/candidatura"
BOUNDARY_PAGE = "https://cartografia.ine.mx/sige8/productosCartograficos/bases"
SOURCE_SHA256 = {
    "results": "f0b0f90483720374eaac50cfb356b43425697fabfa3f963d22a5b8f2d849312f",
    "boundaries": "ca156dd14c83703706c310dabda1a906b952b071b7bb3c0b25ea25b6e09d176f",
}

EXPECTED_NATIONAL = {
    "Sheinbaum": 35_924_519,
    "Gálvez": 16_502_697,
    "Máynez": 6_204_710,
    "Non-registered": 83_114,
    "Null": 1_400_144,
    "Total": 60_115_184,
}

CANDIDATES = (
    (
        "Claudia Sheinbaum Pardo",
        "Sheinbaum",
        ("PVEM", "PT", "MORENA", "PVEM_PT_MORENA", "PVEM_PT", "PVEM_MORENA", "PT_MORENA"),
    ),
    (
        "Bertha Xóchitl Gálvez Ruiz",
        "Gálvez",
        ("PAN", "PRI", "PRD", "PAN_PRI_PRD", "PAN_PRI", "PAN_PRD", "PRI_PRD"),
    ),
    ("Jorge Álvarez Máynez", "Máynez", ("MC",)),
)

STATE_NAMES = {
    1: "Aguascalientes", 2: "Baja California", 3: "Baja California Sur", 4: "Campeche",
    5: "Coahuila", 6: "Colima", 7: "Chiapas", 8: "Chihuahua", 9: "Ciudad de México",
    10: "Durango", 11: "Guanajuato", 12: "Guerrero", 13: "Hidalgo", 14: "Jalisco",
    15: "México", 16: "Michoacán", 17: "Morelos", 18: "Nayarit", 19: "Nuevo León",
    20: "Oaxaca", 21: "Puebla", 22: "Querétaro", 23: "Quintana Roo",
    24: "San Luis Potosí", 25: "Sinaloa", 26: "Sonora", 27: "Tabasco",
    28: "Tamaulipas", 29: "Tlaxcala", 30: "Veracruz", 31: "Yucatán", 32: "Zacatecas",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

RESULT_NOTE = (
    "District totals aggregate INE polling-place computation records. National summary shares also "
    "include special-vote records that are not assigned to one of the 300 mapped federal districts."
)


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=300, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                handle.write(chunk)
    return path


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def extract_results(archive: Path, raw_dir: Path) -> Path:
    output = raw_dir / "PRES_2024.csv"
    if output.exists() and output.stat().st_size:
        return output
    with zipfile.ZipFile(archive) as outer:
        inner_name = next(name for name in outer.namelist() if name.endswith("_COMPUTOS_PRES.zip"))
        inner_path = raw_dir / Path(inner_name).name
        inner_path.write_bytes(outer.read(inner_name))
    with zipfile.ZipFile(inner_path) as inner:
        output.write_bytes(inner.read("PRES_2024.csv"))
    return output


def extract_boundaries(archive: Path, raw_dir: Path) -> Path:
    output = raw_dir / "DISTRITO_FEDERAL.shp"
    if output.exists() and output.stat().st_size:
        return output
    names = [f"DISTRITO_FEDERAL.{suffix}" for suffix in ("shp", "shx", "dbf", "prj")]
    with py7zr.SevenZipFile(archive, mode="r") as source:
        source.extract(path=raw_dir, targets=names)
    return output


def numeric(value: str) -> int:
    text = str(value or "").strip().replace(",", "")
    if text in {"", "-", "N/A"}:
        return 0
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    return int(text)


def title_case(value: str) -> str:
    text = " ".join(value.strip().title().split())
    for word in ("De", "Del", "Los", "Las", "Y"):
        text = text.replace(f" {word} ", f" {word.lower()} ")
    return text


def district_name(state_id: int, district_id: int, head: str) -> str:
    return f"{STATE_NAMES[state_id]} {district_id:02d} — {title_case(head)}"


def parse_results(path: Path):
    lines = path.read_text(encoding="cp1252").splitlines()
    header_index = next(index for index, line in enumerate(lines) if line.startswith("CLAVE_CASILLA|"))
    reader = csv.DictReader(lines[header_index:], delimiter="|")
    areas: dict[tuple[int, int], dict[str, object]] = {}
    national = Counter()

    for row in reader:
        ticket_votes = {
            ticket: sum(numeric(row[column]) for column in columns)
            for _, ticket, columns in CANDIDATES
        }
        non_registered = numeric(row["CANDIDATO/A NO REGISTRADO/A"])
        null = numeric(row["VOTOS NULOS"])
        total = numeric(row["TOTAL_VOTOS_CALCULADOS"])
        if sum(ticket_votes.values()) + non_registered + null != total:
            raise SystemExit(f"{row['CLAVE_CASILLA']}: polling-place votes do not reconcile")
        national.update(ticket_votes)
        national["Non-registered"] += non_registered
        national["Null"] += null
        national["Total"] += total

        state_id = numeric(row["ID_ENTIDAD"])
        district_id = numeric(row["ID_DISTRITO_FEDERAL"])
        if not district_id:
            continue
        key = (state_id, district_id)
        if key not in areas:
            areas[key] = {
                "head": row["DISTRITO_FEDERAL"], "votes": Counter(), "enrolment": 0,
                "non_registered": 0, "null": 0, "total": 0,
            }
        area = areas[key]
        if area["head"] != row["DISTRITO_FEDERAL"]:
            raise SystemExit(f"{key}: inconsistent district-head names")
        area["votes"].update(ticket_votes)
        area["enrolment"] += numeric(row["LISTA_NOMINAL"])
        area["non_registered"] += non_registered
        area["null"] += null
        area["total"] += total

    if len(areas) != 300:
        raise SystemExit(f"Expected 300 federal districts, found {len(areas)}")
    if dict(national) != EXPECTED_NATIONAL:
        raise SystemExit(f"National totals changed: {dict(national)}")
    return areas


def build_boundaries(path: Path, areas: dict[tuple[int, int], dict[str, object]]):
    source = gpd.read_file(path).to_crs(epsg=4326)
    if len(source) != 300:
        raise SystemExit(f"Expected 300 official boundary features, found {len(source)}")
    features = []
    codes = {}
    for _, row in source.sort_values(["ENTIDAD", "DISTRITO_F"]).iterrows():
        key = (int(row["ENTIDAD"]), int(row["DISTRITO_F"]))
        if key not in areas:
            raise SystemExit(f"Official boundary has no matching result: {key}")
        geometry = row.geometry.simplify(0.008, preserve_topology=True)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{key}: invalid simplified official geometry")
        code = f"MX2024-{key[0]:02d}-{key[1]:03d}"
        codes[key] = code
        name = district_name(key[0], key[1], str(areas[key]["head"]))
        features.append({
            "type": "Feature",
            "properties": {
                "district": name, "constituency_code": code,
                "electorate_type": STATE_NAMES[key[0]],
            },
            "geometry": mapping(geometry),
        })
    if set(codes) != set(areas):
        raise SystemExit("Official district boundaries do not match all 300 result areas")
    return {
        "type": "FeatureCollection", "name": "mexico_2024_federal_districts",
        "features": features,
    }, codes


def build_rows(areas: dict[tuple[int, int], dict[str, object]], codes: dict[tuple[int, int], str]):
    rows = []
    winners = Counter()
    for key, area in sorted(areas.items()):
        votes = area["votes"]
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        winner_ticket = ranked[0][0]
        winner_name = next(name for name, ticket, _ in CANDIDATES if ticket == winner_ticket)
        winners[winner_ticket] += 1
        formal = sum(votes.values())
        informal = int(area["non_registered"]) + int(area["null"])
        total = int(area["total"])
        enrolment = int(area["enrolment"])
        if formal + informal != total:
            raise SystemExit(f"{key}: district totals do not reconcile")
        base = {
            "district": district_name(key[0], key[1], str(area["head"])),
            "district_url": RESULTS_PAGE, "distribution_url": BOUNDARY_PAGE,
            "elected_member": winner_name, "elected_party": winner_ticket,
            "enrolment": enrolment, "formal_votes": formal, "informal_votes": informal,
            "total_votes": total, "turnout_pct": round(total / enrolment * 100, 2) if enrolment else 0,
            "majority": ranked[0][1] - ranked[1][1], "round_number": 0,
            "row_type": "first", "excluded_candidate": "", "excluded_party": "",
            "electorate_type": STATE_NAMES[key[0]], "constituency_code": codes[key],
            "contest_status": "official", "result_note": RESULT_NOTE,
        }
        for candidate, ticket, _ in CANDIDATES:
            rows.append({**base, "candidate": candidate, "candidate_party": ticket, "votes": votes[ticket]})
    return rows, winners


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Mexico's official 2024 presidential district results")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/mexico_2024"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--results-archive", type=Path)
    parser.add_argument("--boundary-archive", type=Path)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; election-preference-explorer/0.1)"})
    results_archive = args.results_archive or args.raw_dir / "20240608_2030_COMPUTOS.zip"
    boundary_archive = args.boundary_archive or args.raw_dir / "SHAPEFILE.7z"
    if not args.results_archive:
        download(session, RESULTS_URL, results_archive, args.refresh)
    if not args.boundary_archive:
        download(session, BOUNDARY_URL, boundary_archive, args.refresh)

    require_sha256(results_archive, SOURCE_SHA256["results"])
    require_sha256(boundary_archive, SOURCE_SHA256["boundaries"])

    areas = parse_results(extract_results(results_archive, args.raw_dir))
    boundaries, codes = build_boundaries(extract_boundaries(boundary_archive, args.raw_dir), areas)
    rows, winners = build_rows(areas, codes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "mexico_2024_president_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    boundary_path = args.out_dir / "mexico_2024_federal_district_boundaries.geojson"
    boundary_path.write_text(
        json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"Wrote {csv_path} ({len(rows):,} rows, 300 districts)")
    print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")
    print(f"District wins: {dict(winners)}")


if __name__ == "__main__":
    main()
