#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import mapping

from build_northern_europe_elections import FIELDS, election_rows


SOURCE_URLS = {
    "results_2022": (
        "https://dait.interno.gov.it/documenti/opendata/catalogoagid/"
        "camera-2022-Italia-livcomune.csv"
    ),
    "results_2018": (
        "https://raw.githubusercontent.com/ondata/elezionipolitiche2018/"
        "master/dati/scrutiniCI_cm.csv"
    ),
    "crosswalk_2018": (
        "https://raw.githubusercontent.com/ondata/elezionipolitiche2018/"
        "master/risorse/comuniViminaleISTAT.csv"
    ),
    "geography_2018": (
        "https://raw.githubusercontent.com/ondata/elezionipolitiche2018/"
        "master/dati/camera_geopolitico_italia.csv"
    ),
    "boundaries_2022": (
        "https://www.istat.it/storage/cartografia/confini_amministrativi/"
        "generalizzati/2022/Limiti01012022_g.zip"
    ),
    "boundaries_2018": (
        "https://www.istat.it/storage/cartografia/confini_amministrativi/"
        "generalizzati/Limiti01012018_g.zip"
    ),
}

SOURCE_PAGES = {
    2022: "https://dait.interno.gov.it/elezioni",
    2018: "https://github.com/ondata/elezionipolitiche2018",
}

SOURCE_SHA256 = {
    "results_2022": "9f4f49dd0dfde3d1ea32ccda9665d6d230959f97ce074418ef2553242aa675b3",
    "results_2018": "5c88e15febe087c45c608e378bb7a1b6266f65660b1d576b3996f7e83acabe9e",
    "crosswalk_2018": "fc151f60d220a22bc7deb6ee878fc85df9504d5ea091e725010b2a4886a2c1c8",
    "geography_2018": "d69ea901668009502f31cc7369a08cda3e384f2a942add1cda71fd5edae4ea07",
    "boundaries_2022": "fe3cf33f396ad3687128b83aff486813ca62ad9b2433e9f44fdb4cbe09aa5e8b",
    "boundaries_2018": "1e85d7785b0a2a5f4a6bee3e0b3ea0b7878c7e7c0461cff79d9fd9d15686aecb",
}

EXPECTED = {
    2022: {
        "areas": 106,
        "formal": 27_069_655,
        "major": {
            "Brothers of Italy": 7_098_555,
            "Democratic Party": 5_128_861,
            "Five Star Movement": 4_178_360,
        },
    },
    2018: {
        "areas": 106,
        "formal": 31_537_826,
        "major": {
            "Five Star Movement": 10_221_447,
            "Democratic Party": 5_872_264,
            "Lega": 5_568_120,
        },
    },
}

REGIONS = {
    1: "Piemonte",
    2: "Valle d'Aosta",
    3: "Lombardia",
    4: "Trentino-Alto Adige/Südtirol",
    5: "Veneto",
    6: "Friuli-Venezia Giulia",
    7: "Liguria",
    8: "Emilia-Romagna",
    9: "Toscana",
    10: "Umbria",
    11: "Marche",
    12: "Lazio",
    13: "Abruzzo",
    14: "Molise",
    15: "Campania",
    16: "Puglia",
    17: "Basilicata",
    18: "Calabria",
    19: "Sicilia",
    20: "Sardegna",
}

PARTIES = {
    "FRATELLI D'ITALIA CON GIORGIA MELONI": "Brothers of Italy",
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA": "Democratic Party",
    "PARTITO DEMOCRATICO": "Democratic Party",
    "MOVIMENTO 5 STELLE": "Five Star Movement",
    "LEGA PER SALVINI PREMIER": "Lega",
    "LEGA": "Lega",
    "FORZA ITALIA": "Forza Italia",
    "AZIONE - ITALIA VIVA - CALENDA": "Action–Italia Viva",
    "ALLEANZA VERDI E SINISTRA": "Greens and Left Alliance",
    "+EUROPA": "More Europe",
    "LIBERI E UGUALI": "Free and Equal",
    "NOI MODERATI/LUPI - TOTI - BRUGNARO - UDC": "Us Moderates",
    "NOI CON L'ITALIA - UDC": "Us with Italy–UDC",
    "SUDTIROLER VOLKSPARTEI (SVP) - PATT": "SVP–PATT",
    "SVP - PATT": "SVP–PATT",
    "IMPEGNO CIVICO LUIGI DI MAIO - CENTRO DEMOCRATICO": "Civic Commitment",
    "UNIONE POPOLARE CON DE MAGISTRIS": "People's Union",
    "ITALIA SOVRANA E POPOLARE": "Sovereign and Popular Italy",
    "POTERE AL POPOLO!": "Power to the People",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def integer(value: object) -> int:
    text = str(value or "").strip().replace(".", "")
    return int(text) if text.isdigit() else 0


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def download(
    session: requests.Session, key: str, raw_dir: Path, refresh: bool
) -> Path:
    suffix = ".zip" if key.startswith("boundaries") else ".csv"
    path = raw_dir / f"{key}{suffix}"
    if not path.exists() or path.stat().st_size < 100 or refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        response = session.get(SOURCE_URLS[key], timeout=300)
        response.raise_for_status()
        path.write_bytes(response.content)
    actual = digest(path)
    if actual != SOURCE_SHA256[key]:
        raise SystemExit(f"{key}: checksum changed ({actual})")
    return path


def boundary_layers(
    archive: Path, year: int
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    root = f"Limiti0101{year}_g"
    provinces = gpd.read_file(
        f"zip://{archive.resolve()}!{root}/ProvCM0101{year}_g/"
        f"ProvCM0101{year}_g_WGS84.shp"
    )
    municipalities = gpd.read_file(
        f"zip://{archive.resolve()}!{root}/Com0101{year}_g/"
        f"Com0101{year}_g_WGS84.shp"
    )
    return provinces, municipalities


def build_boundaries(
    provinces: gpd.GeoDataFrame, year: int, output_dir: Path
) -> dict[int, str]:
    provinces = provinces[provinces["COD_REG"] != 2].copy()
    if len(provinces) != EXPECTED[year]["areas"]:
        raise SystemExit(f"Italy {year}: expected 106 mapped provinces")
    provinces["geometry"] = provinces.geometry.simplify(
        1_500, preserve_topology=True
    ).buffer(0)
    provinces = provinces.to_crs("EPSG:4326")

    features = []
    names = {}
    name_column = "DEN_UTS" if year == 2022 else "DEN_PCM"
    for row in provinces.itertuples():
        code_number = int(row.COD_PROV)
        code = f"IT-PROV-{code_number:03d}"
        name = str(getattr(row, name_column))
        geometry = row.geometry
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"Italy {year}: invalid province geometry {name}")
        features.append({
            "type": "Feature",
            "properties": {
                "district": name,
                "constituency_code": code,
                "province_code": f"{code_number:03d}",
                "region": REGIONS[int(row.COD_REG)],
            },
            "geometry": mapping(geometry),
        })
        names[code_number] = name
    features.sort(key=lambda feature: feature["properties"]["constituency_code"])
    output = {"type": "FeatureCollection", "features": features}
    (output_dir / f"italy_{year}_province_boundaries.geojson").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return names


def municipality_province_lookup(
    municipalities: gpd.GeoDataFrame,
) -> tuple[dict[tuple[str, str], int], dict[str, list[tuple[str, int]]]]:
    exact: dict[tuple[str, str], int] = {}
    by_region: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in municipalities.itertuples():
        region = normalize(REGIONS[int(row.COD_REG)])
        name = normalize(row.COMUNE)
        province = int(row.COD_PROV)
        exact[(region, name)] = province
        by_region[region].append((name, province))
    return exact, dict(by_region)


def source_region(value: str) -> str:
    return normalize(re.sub(r"\s+[1-4]$", "", value.strip()))


def match_2022_municipality(
    lookup: tuple[
        dict[tuple[str, str], int], dict[str, list[tuple[str, int]]]
    ],
    region: str,
    municipality: str,
) -> int:
    exact, by_region = lookup
    key = (source_region(region), normalize(municipality))
    if key in exact:
        return exact[key]
    candidates = [
        (len(name), province)
        for name, province in by_region[key[0]]
        if key[1].startswith(name)
    ]
    if not candidates:
        raise SystemExit(f"Italy 2022: unmatched municipality {municipality} ({region})")
    longest = max(length for length, _ in candidates)
    provinces = {province for length, province in candidates if length == longest}
    if len(provinces) != 1:
        raise SystemExit(f"Italy 2022: ambiguous municipality {municipality} ({region})")
    return provinces.pop()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def check_rows(year: int, rows: list[dict[str, object]]) -> None:
    codes = {str(row["constituency_code"]) for row in rows}
    if len(codes) != EXPECTED[year]["areas"]:
        raise SystemExit(f"Italy {year}: expected 106 result provinces")
    total = sum(int(row["votes"]) for row in rows)
    if total != EXPECTED[year]["formal"]:
        raise SystemExit(f"Italy {year}: mapped formal-vote total changed ({total})")
    party_totals = Counter()
    for row in rows:
        party_totals[str(row["candidate_party"])] += int(row["votes"])
    for party, expected in EXPECTED[year]["major"].items():
        if party_totals[party] != expected:
            raise SystemExit(f"Italy {year}: {party} total changed")


def build_2022(
    result_path: Path,
    municipalities: gpd.GeoDataFrame,
    province_names: dict[int, str],
    output_dir: Path,
) -> None:
    lookup = municipality_province_lookup(municipalities)
    votes: defaultdict[int, Counter[str]] = defaultdict(Counter)
    metadata: dict[tuple[str, str, str, str], tuple[int, int]] = {}
    with result_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            province = match_2022_municipality(
                lookup, row["CIRC-REG"], row["COMUNE"]
            )
            party = PARTIES.get(row["DESCRLISTA"], row["DESCRLISTA"].title())
            votes[province][party] += integer(row["VOTILISTA"])
            unit = (
                row["CIRC-REG"], row["COLLPLURI"], row["COLLUNINOM"], row["COMUNE"]
            )
            values = (integer(row["ELETTORITOT"]), integer(row["VOTANTITOT"]))
            if unit in metadata and metadata[unit] != values:
                raise SystemExit(f"Italy 2022: inconsistent metadata for {unit}")
            metadata[unit] = values

    area_metadata: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for unit, (enrolment, turnout) in metadata.items():
        province = match_2022_municipality(lookup, unit[0], unit[3])
        area_metadata[province]["enrolment"] += enrolment
        area_metadata[province]["turnout"] += turnout

    rows = []
    note = (
        "Official Ministry municipality party-list votes aggregated to province. "
        "Aosta Valley's separate direct seat and overseas constituencies are excluded "
        "from this local party-list map."
    )
    for province in sorted(votes):
        formal = sum(votes[province].values())
        turnout = area_metadata[province]["turnout"]
        informal = turnout - formal
        if informal < 0:
            raise SystemExit(f"Italy 2022: negative informal total in {province_names[province]}")
        rows.extend(election_rows(
            province_names[province],
            f"IT-PROV-{province:03d}",
            dict(votes[province]),
            area_metadata[province]["enrolment"],
            formal,
            informal,
            SOURCE_PAGES[2022],
            "Italy",
            note,
        ))
    check_rows(2022, rows)
    write_csv(output_dir / "italy_2022_chamber_province_fpp.csv", rows)
    print(f"Italy 2022: wrote {len(rows)} rows across 106 provinces")


def build_2018(
    result_path: Path,
    crosswalk_path: Path,
    geography_path: Path,
    province_names: dict[int, str],
    output_dir: Path,
) -> None:
    with crosswalk_path.open(newline="", encoding="utf-8-sig") as handle:
        crosswalk = list(csv.DictReader(handle))
    direct = {
        row["ELIGENDO_C_UID_CI"]: int(row["COD_PROV"])
        for row in crosswalk
    }
    by_name: defaultdict[str, list[int]] = defaultdict(list)
    for row in crosswalk:
        by_name[normalize(row["COMUNE"])].append(int(row["COD_PROV"]))
    with geography_path.open(newline="", encoding="utf-8-sig") as handle:
        geography = {row["id"]: row["nome"] for row in csv.DictReader(handle)}

    votes: defaultdict[int, Counter[str]] = defaultdict(Counter)
    malformed = Counter()
    with result_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["tipo_riga"] != "LI":
                continue
            source_code = row["codice"]
            province = direct.get(source_code)
            if province is None:
                municipality = geography[source_code].split(" - ")[0]
                candidates = set(by_name[normalize(municipality)])
                if len(candidates) != 1:
                    raise SystemExit(
                        f"Italy 2018: unmatched split-city unit {source_code}"
                    )
                province = candidates.pop()
            if province == 7:
                continue
            raw_votes = row["voti"].strip().replace(".", "")
            if raw_votes and not raw_votes.isdigit() and raw_votes != "-":
                malformed[(row["descr_lista"], raw_votes)] += 1
            party = PARTIES.get(row["descr_lista"], row["descr_lista"].title())
            votes[province][party] += integer(row["voti"])
    if malformed != Counter({
        ("IL POPOLO DELLA FAMIGLIA", "GUIDO PIANESELLI"): 1,
        ("LIBERI E UGUALI", "ANTONELLA VALER"): 1,
    }):
        raise SystemExit(f"Italy 2018: malformed-row control changed ({malformed})")

    rows = []
    note = (
        "Ministry-format municipality party-list rows preserved by the OnData mirror "
        "and aggregated to province. Compatible local turnout metadata is unavailable. "
        "Aosta Valley's separate direct seat and overseas constituencies are excluded."
    )
    for province in sorted(votes):
        formal = sum(votes[province].values())
        rows.extend(election_rows(
            province_names[province],
            f"IT-PROV-{province:03d}",
            dict(votes[province]),
            0,
            formal,
            0,
            SOURCE_PAGES[2018],
            "Italy",
            note,
        ))
    check_rows(2018, rows)
    write_csv(output_dir / "italy_2018_chamber_province_fpp.csv", rows)
    print(f"Italy 2018: wrote {len(rows)} rows across 106 provinces")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the 2022 and 2018 Italian Chamber election views"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/italy_chamber_raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"
    paths = {
        key: download(session, key, args.raw_dir, args.refresh)
        for key in SOURCE_URLS
    }
    layers = {
        year: boundary_layers(paths[f"boundaries_{year}"], year)
        for year in (2022, 2018)
    }
    province_names = {
        year: build_boundaries(layers[year][0], year, args.output_dir)
        for year in (2022, 2018)
    }
    build_2022(
        paths["results_2022"], layers[2022][1], province_names[2022], args.output_dir
    )
    build_2018(
        paths["results_2018"],
        paths["crosswalk_2018"],
        paths["geography_2018"],
        province_names[2018],
        args.output_dir,
    )


if __name__ == "__main__":
    main()
