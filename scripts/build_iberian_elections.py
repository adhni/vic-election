#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import requests
from pypdf import PdfReader
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union


PORTUGAL_BASE = "https://www.eleicoes.mai.gov.pt/legislativas{year}/assets/static"
PORTUGAL_SOURCE_PAGE = "https://www.eleicoes.mai.gov.pt/legislativas{year}/"
SPAIN_SOURCES = {
    2023: {
        "results": "https://www.boe.es/buscar/doc.php?id=BOE-A-2023-18907",
        "summary": "https://www.boe.es/boe/dias/2023/09/01/pdfs/BOE-A-2023-18907.pdf",
    },
    2019: {
        "results": "https://www.boe.es/buscar/doc.php?id=BOE-A-2019-18147",
        "summary": "https://www.boe.es/boe/dias/2019/12/02/pdfs/BOE-A-2019-17344.pdf",
    },
}
SPAIN_SOURCE_PAGES = {
    2023: "https://www.boe.es/buscar/doc.php?id=BOE-A-2023-18907",
    2019: "https://www.boe.es/buscar/doc.php?id=BOE-A-2019-18147",
}
SPAIN_BOUNDARY_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_03M_2021_4326.geojson"
)
SPAIN_BOUNDARY_PAGE = "https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics"

# Every upstream file is checksum-pinned. Portugal's manifest digest covers the
# children list, map, national result, and all 20 domestic district results.
PORTUGAL_MANIFEST_SHA256 = {
    2025: "5d16865ff4e4181f05302caddee1e16bbd52a4fa2675a436e69534395eeacf51",
    2024: "7233774eff78e4fc79056db8924aff24c97808263533a18c400c907aeec29015",
}
SPAIN_SOURCE_SHA256 = {
    (2023, "results"): "7c2ff9eac201fa23ce6e9621e97d62bbf574884b52aac7c618f92586fc73f537",
    (2023, "summary"): "f2146cfbf00d2b6eb6f8dd0dcdebc1e10298019589b2254e244e0ebc513d2f8a",
    (2019, "results"): "a9d2905276abab287f4c51d995bbac9783c2b42f4e24f40749b3eea49ca57b80",
    (2019, "summary"): "e0f00d6aab720757a538181682f854d50f851d42ce8cc01cf41b73deede6c51b",
    "boundaries": "f21c64c40c4bfc9e1bfa03dcefae7b099f1e2cea168ee9b6c52cceef2bd4c9e5",
}

EXPECTED_PORTUGAL_SEATS = {
    2025: {
        "PPD/PSD.CDS-PP": 88, "PS": 58, "CH": 60, "IL": 9, "L": 6,
        "PCP-PEV": 3, "B.E.": 1, "PAN": 1, "PPD/PSD.CDS-PP.PPM": 3, "JPP": 1,
    },
    2024: {
        "PPD/PSD.CDS-PP.PPM": 77, "PS": 78, "CH": 50, "IL": 8, "B.E.": 5,
        "PCP-PEV": 4, "L": 4, "PAN": 1, "PPD/PSD.CDS-PP": 3,
    },
}
EXPECTED_SPAIN_SEATS = {
    2023: {
        "PP": 137, "PSOE": 102, "VOX": 33, "SUMAR": 31, "PSC": 19,
        "ERC": 7, "JUNTS": 7, "EH Bildu": 6, "EAJ-PNV": 5, "BNG": 1,
        "CCa": 1, "UPN": 1,
    },
    2019: {
        "PSOE": 108, "PP": 87, "VOX": 52, "PODEMOS-IU": 26,
        "ERC-SOBIRANISTES": 13, "PSC": 12, "Cs": 10, "JxCAT-JUNTS": 8,
        "EAJ-PNV": 6, "EH Bildu": 5, "MÁS PAÍS-EQUO": 2, "CUP-PR": 2,
        "ECP-GUANYEM EL CANVI": 7, "PODEMOS-EU": 2, "PP-FORO": 2,
        "CCa-PNC-NC": 2, "NA+": 2, "MÉS COMPROMÍS": 1, "BNG": 1,
        "PRC": 1, "¡TERUEL EXISTE!": 1,
    },
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note", "district_seats",
)


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                handle.write(chunk)
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(path: Path, expected: str) -> None:
    actual = digest(path)
    if expected != "PENDING" and actual != expected:
        raise SystemExit(f"{path}: source checksum changed to {actual}; expected {expected}")


def integer(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    if isinstance(value, str):
        value = value.strip().replace("\xa0", "").replace(" ", "")
        if not value:
            return 0
        value = value.replace(".", "")
    return int(float(value))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def portugal_paths(
    session: requests.Session, year: int, raw_dir: Path, refresh: bool
) -> tuple[dict[str, Path], list[dict[str, object]]]:
    base = PORTUGAL_BASE.format(year=year)
    prefix = raw_dir / f"portugal_{year}"
    paths = {
        "children": download(
            session, f"{base}/territory-children/territory-children-LOCAL-500000.json",
            prefix / "children.json", refresh,
        ),
        "map": download(
            session, f"{base}/territory-map-coords/territory-map-coords-LOCAL-500000.json",
            prefix / "map.json", refresh,
        ),
        "national": download(
            session, f"{base}/territory-results/territory-results-GLOBAL-990000-AR.json",
            prefix / "national.json", refresh,
        ),
    }
    children_payload = json.loads(paths["children"].read_text(encoding="utf-8"))
    children = children_payload if isinstance(children_payload, list) else children_payload["territories"]
    if len(children) != 20:
        raise SystemExit(f"Portugal {year}: expected 20 domestic districts, found {len(children)}")
    for child in children:
        key = str(child["territoryKey"])
        paths[key] = download(
            session, f"{base}/territory-results/territory-results-{key}-AR.json",
            prefix / f"{key}.json", refresh,
        )
    manifest = "\n".join(f"{key}:{digest(path)}" for key, path in sorted(paths.items()))
    actual_manifest = hashlib.sha256(manifest.encode()).hexdigest()
    expected_manifest = PORTUGAL_MANIFEST_SHA256[year]
    if expected_manifest != "PENDING" and actual_manifest != expected_manifest:
        raise SystemExit(
            f"Portugal {year}: source manifest changed to {actual_manifest}; "
            f"expected {expected_manifest}"
        )
    print(f"Portugal {year} source manifest: {actual_manifest}")
    return paths, children


def portugal_geometry(coords: list[str]) -> object:
    polygons = []
    for item in coords:
        values = [float(value) for value in item.split(",")]
        ring = [(values[index], -values[index + 1]) for index in range(0, len(values), 2)]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        polygon = Polygon(ring)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if isinstance(polygon, MultiPolygon):
            polygons.extend(polygon.geoms)
        elif not polygon.is_empty:
            polygons.append(polygon)
    if not polygons:
        raise SystemExit("Portugal map area contained no usable polygon")
    return polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)


def build_portugal(
    session: requests.Session, year: int, raw_dir: Path, output_dir: Path, refresh: bool
) -> None:
    paths, children = portugal_paths(session, year, raw_dir, refresh)
    source_page = PORTUGAL_SOURCE_PAGE.format(year=year)
    rows: list[dict[str, object]] = []
    district_by_key: dict[str, str] = {}
    domestic_seats = 0

    for child in children:
        key = str(child["territoryKey"])
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        current = payload["currentResults"]
        district = str(payload["territoryName"])
        district_by_key[key] = district
        votes = {
            str(party["acronym"]): int(party["votes"])
            for party in current["resultsParty"]
            if int(party["votes"]) > 0
        }
        formal = sum(votes.values())
        informal = int(current["blankVotes"]) + int(current["nullVotes"])
        total = int(current["numberVoters"])
        enrolment = int(current["subscribedVoters"])
        seats = int(current["totalMandates"])
        domestic_seats += seats
        if formal + informal != total:
            raise SystemExit(f"Portugal {year} {district}: votes do not reconcile")
        winner = max(votes, key=votes.get)
        note = (
            "Blank and null ballots are combined as non-party ballots so party-list votes "
            "plus non-party ballots reconcile to ballots cast."
        )
        for party, party_votes in votes.items():
            rows.append({
                "district": district,
                "district_url": source_page,
                "distribution_url": source_page,
                "elected_member": winner,
                "elected_party": winner,
                "enrolment": enrolment,
                "formal_votes": formal,
                "informal_votes": informal,
                "total_votes": total,
                "turnout_pct": round(total / enrolment * 100, 2) if enrolment else "",
                "majority": formal // 2 + 1,
                "round_number": 0,
                "row_type": "first",
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": party,
                "candidate_party": party,
                "votes": party_votes,
                "electorate_type": "Portugal",
                "constituency_code": f"PT-{key.rsplit('-', 1)[-1]}",
                "contest_status": "official",
                "result_note": note,
                "district_seats": seats,
            })

    if domestic_seats != 226:
        raise SystemExit(f"Portugal {year}: expected 226 domestic seats, found {domestic_seats}")
    national = json.loads(paths["national"].read_text(encoding="utf-8"))["currentResults"]
    seats = {
        str(party["acronym"]): int(party["mandates"])
        for party in national["resultsParty"]
        if int(party["mandates"]) > 0
    }
    if seats != EXPECTED_PORTUGAL_SEATS[year]:
        raise SystemExit(f"Portugal {year}: national seats changed: {seats}")

    map_payload = json.loads(paths["map"].read_text(encoding="utf-8"))
    features = []
    for area in map_payload["mapAreas"]:
        key = str(area["territoryKey"])
        district = district_by_key[key]
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "constituency_code": f"PT-{key.rsplit('-', 1)[-1]}",
                "source": "Portuguese Ministry of Internal Administration official inset map",
                "schematic": True,
            },
            "geometry": mapping(portugal_geometry(area["coords"])),
        })
    if len(features) != 20:
        raise SystemExit(f"Portugal {year}: expected 20 map features")

    write_csv(output_dir / f"portugal_{year}_legislative_fpp.csv", rows)
    boundary = output_dir / f"portugal_{year}_legislative_boundaries.geojson"
    boundary.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Portugal {year}: wrote {len(rows)} rows and {len(features)} districts")


def normalize_spain_district(value: object) -> str:
    name = " ".join(str(value).replace("\xa0", " ").split()).rstrip(".")
    return name


def spain_party(column: tuple[object, ...], year: int) -> str:
    levels = [str(level).replace("\xa0", " ").strip() for level in column]
    if year == 2019:
        return levels[1]
    label = levels[0].rstrip(".")
    matches = re.findall(r"\(([^()]+)\)", label)
    return matches[-1].strip() if matches else label


def parse_spain_tables(path: Path, year: int) -> tuple[
    list[str], dict[str, Counter], dict[str, int], dict[str, int]
]:
    tables = pd.read_html(path, thousands=".")
    expected_tables = 13 if year == 2023 else 14
    if len(tables) != expected_tables:
        raise SystemExit(f"Spain {year}: expected {expected_tables} BOE tables, found {len(tables)}")
    district_order = [
        normalize_spain_district(value) for value in tables[0].iloc[:, 0].tolist()
        if "Total estatal" not in normalize_spain_district(value)
    ]
    if len(district_order) != 52:
        raise SystemExit(f"Spain {year}: expected 52 constituencies, found {len(district_order)}")
    votes = {district: Counter() for district in district_order}
    district_seats: dict[str, int] = {}
    national_seats: Counter = Counter()

    for table in tables:
        for _, record in table.iterrows():
            district = normalize_spain_district(record.iloc[0])
            if district == "Total estatal":
                is_total = True
            elif district in votes:
                is_total = False
            else:
                continue
            for column in table.columns[1:]:
                levels = tuple(column) if isinstance(column, tuple) else (column,)
                if str(levels[0]).startswith("Total escaños"):
                    if not is_total:
                        district_seats[district] = integer(record[column])
                    continue
                metric = str(levels[-1])
                party = spain_party(levels, year)
                amount = integer(record[column])
                if metric == "Votos" and amount and not is_total:
                    votes[district][party] = amount
                elif metric == "Escaños" and amount and is_total:
                    national_seats[party] = amount

    if set(district_seats) != set(district_order) or sum(district_seats.values()) != 350:
        raise SystemExit(f"Spain {year}: district seat allocation does not total 350")
    if dict(national_seats) != EXPECTED_SPAIN_SEATS[year]:
        raise SystemExit(f"Spain {year}: national seats changed: {dict(national_seats)}")
    return district_order, votes, district_seats, dict(national_seats)


def parse_spain_summary(path: Path, district_order: list[str]) -> dict[str, tuple[int, ...]]:
    text = PdfReader(path).pages[1].extract_text()
    numeric_rows = []
    pattern = re.compile(r"^\s*((?:\d[\d.]*\s+){5}\d[\d.]*)", re.M)
    for match in pattern.finditer(text):
        values = tuple(integer(value) for value in match.group(1).split())
        if len(values) == 6:
            numeric_rows.append(values)
    if len(numeric_rows) < 52:
        raise SystemExit(f"{path}: expected at least 52 constituency summary rows, found {len(numeric_rows)}")
    summary = dict(zip(district_order, numeric_rows[:52]))
    for district, (electors, voters, valid, candidature, blank, null) in summary.items():
        if valid != candidature + blank or voters != valid + null:
            raise SystemExit(f"{path}: {district} summary does not reconcile")
    return summary


def spain_boundary_name(nuts_id: str, nuts_name: str) -> str:
    special = {
        "ES111": "Coruña (A)",
        "ES211": "Araba/Álava",
        "ES521": "Alicante/Alacant",
        "ES522": "Castellón/Castelló",
        "ES523": "Valencia/València",
        "ES230": "Rioja (La)",
    }
    return special.get(nuts_id, nuts_name)


def build_spain_boundaries(path: Path, districts: set[str]) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    geometries: dict[str, list[object]] = {}
    for feature in source["features"]:
        props = feature["properties"]
        if props.get("CNTR_CODE") != "ES" or int(props.get("LEVL_CODE", -1)) != 3:
            continue
        nuts_id = str(props["NUTS_ID"])
        if nuts_id.startswith("ES53"):
            district = "Balears (Illes)"
        elif nuts_id in {"ES704", "ES705", "ES708"}:
            district = "Palmas (Las)"
        elif nuts_id in {"ES703", "ES706", "ES707", "ES709"}:
            district = "Santa Cruz de Tenerife"
        else:
            district = spain_boundary_name(nuts_id, str(props["NUTS_NAME"]))
        geometries.setdefault(district, []).append(shape(feature["geometry"]))
    if set(geometries) != districts:
        raise SystemExit(
            f"Spain boundaries mismatch: missing={sorted(districts - set(geometries))}, "
            f"extra={sorted(set(geometries) - districts)}"
        )
    features = []
    for index, district in enumerate(sorted(districts), start=1):
        geometry = unary_union(geometries[district]).simplify(0.01, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "constituency_code": f"ES-{index:02d}",
                "source": "Eurostat GISCO NUTS 2021",
            },
            "geometry": mapping(geometry),
        })
    return {"type": "FeatureCollection", "features": features}


def build_spain(
    session: requests.Session, year: int, raw_dir: Path, output_dir: Path,
    boundary_path: Path, boundary: dict[str, object], refresh: bool,
) -> None:
    prefix = raw_dir / f"spain_{year}"
    paths = {
        kind: download(session, url, prefix / f"{kind}{'.pdf' if kind == 'summary' else '.html'}", refresh)
        for kind, url in SPAIN_SOURCES[year].items()
    }
    for kind, path in paths.items():
        require_digest(path, SPAIN_SOURCE_SHA256[(year, kind)])
        print(f"Spain {year} {kind} SHA256: {digest(path)}")
    districts, party_votes, district_seats, _ = parse_spain_tables(paths["results"], year)
    summary = parse_spain_summary(paths["summary"], districts)

    rows: list[dict[str, object]] = []
    code_by_district = {
        feature["properties"]["district"]: feature["properties"]["constituency_code"]
        for feature in boundary["features"]
    }
    for district in districts:
        electors, voters, valid, candidature, blank, null = summary[district]
        votes = party_votes[district]
        if sum(votes.values()) != candidature:
            raise SystemExit(
                f"Spain {year} {district}: party votes {sum(votes.values())} "
                f"do not equal candidature votes {candidature}"
            )
        winner = max(votes, key=votes.get)
        note = (
            "Blank and null ballots are combined as non-party ballots so party-list votes "
            "plus non-party ballots reconcile to ballots cast."
        )
        for party, votes_count in votes.items():
            rows.append({
                "district": district,
                "district_url": SPAIN_SOURCE_PAGES[year],
                "distribution_url": SPAIN_SOURCE_PAGES[year],
                "elected_member": winner,
                "elected_party": winner,
                "enrolment": electors,
                "formal_votes": candidature,
                "informal_votes": blank + null,
                "total_votes": voters,
                "turnout_pct": round(voters / electors * 100, 2),
                "majority": candidature // 2 + 1,
                "round_number": 0,
                "row_type": "first",
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": party,
                "candidate_party": party,
                "votes": votes_count,
                "electorate_type": "Spain",
                "constituency_code": code_by_district[district],
                "contest_status": "official",
                "result_note": note,
                "district_seats": district_seats[district],
            })

    write_csv(output_dir / f"spain_{year}_congress_fpp.csv", rows)
    boundary_output = output_dir / f"spain_{year}_congress_boundaries.geojson"
    boundary_output.write_text(
        json.dumps(boundary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"Spain {year}: wrote {len(rows)} rows and {len(boundary['features'])} constituencies")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Portugal and Spain legislative election data")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/iberian_raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"
    for year in (2025, 2024):
        build_portugal(session, year, args.raw_dir, args.output_dir, args.refresh)

    boundary_path = download(
        session, SPAIN_BOUNDARY_URL, args.raw_dir / "spain_nuts_2021.geojson", args.refresh
    )
    require_digest(boundary_path, SPAIN_SOURCE_SHA256["boundaries"])
    print(f"Spain boundaries SHA256: {digest(boundary_path)}")
    # Both elections use the same stable province constituencies and one boundary build.
    districts_2023 = set(parse_spain_tables(
        download(
            session, SPAIN_SOURCES[2023]["results"],
            args.raw_dir / "spain_2023" / "results.html", args.refresh,
        ), 2023,
    )[0])
    boundary = build_spain_boundaries(boundary_path, districts_2023)
    for year in (2023, 2019):
        build_spain(session, year, args.raw_dir, args.output_dir, boundary_path, boundary, args.refresh)


if __name__ == "__main__":
    main()
