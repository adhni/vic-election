#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import mapping, shape


NL_URLS = {
    2025: (
        "https://data.overheid.nl/sites/default/files/dataset/"
        "a16f3352-c9ce-4831-a314-f989d442a258/resources/"
        "Verkiezingsuitslag%20Tweede%20Kamer%202025%20%28CSV%20Formaat%29.zip"
    ),
    2023: (
        "https://data.overheid.nl/sites/default/files/dataset/"
        "e3fe6e42-06ab-4559-a466-a32b04247f68/resources/"
        "Verkiezingsuitslag%20Tweede%20Kamer%202023%20%28CSV%20formaat%29.zip"
    ),
}
NL_SOURCE_PAGES = {
    2025: "https://data.overheid.nl/dataset/verkiezingsuitslag-tweede-kamer-2025",
    2023: "https://data.overheid.nl/dataset/verkiezingsuitslag-tweede-kamer-2023",
}
SWEDEN_URLS = {
    2022: (
        "https://www.val.se/download/18.162047b519a91d0533118f4b/"
        "1764336897948/Roster-per-distrikt-slutligt-antal-roster-"
        "inklusive-totalt-valdeltagande-riksdagsvalet-2022.xlsx"
    ),
    2018: "https://historik.val.se/val/val2018/statistik/2018_R_per_kommun.xlsx",
}
SWEDEN_SOURCE_PAGES = {
    2022: "https://www.val.se/valresultat-och-statistik/statistik-och-data/radata-fran-val-2002-2022",
    2018: "https://historik.val.se/val/val2018/statistik/index.html",
}
NORWAY_API = "https://www.valgresultat.no/api"
NORWAY_SOURCE_PAGES = {
    2025: "https://www.valgresultat.no/valg/2025/st",
    2021: "https://www.valgresultat.no/valg/2021/st",
}
GISCO_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/lau/download/"
    "ref-lau-{year}-01m.json.zip"
)
GISCO_SOURCE_PAGE = "https://gisco-services.ec.europa.eu/distribution/v2/lau/download/"

SOURCE_SHA256 = {
    ("nl", 2025): "ffd9b0dbb61ff084577d809cffe40e66b4a42aff34723bd19d77794f3d0a83f5",
    ("nl", 2023): "5fc106bf26e22d6b16e071eb509a09f7b4e13a58f9019a16c185064b4b5895cd",
    ("se", 2022): "02220e73a7f497d02e23e11cc0765b9891f3a11b3738a5750182ca0c2c58a04d",
    ("se", 2018): "5fbd2b9227c473146b3d23f046c58ca2645d00bdfb76c73d8a30cb48445392de",
    ("gisco", 2024): "19eb8988026d325f46cfa242b6d252342875b13393c461f08d70d042feb51137",
    ("gisco", 2022): "a26a51ffed6c10aee0742913f956f064e820b5ce6f4c76d267d443f545c74a65",
    ("gisco", 2021): "a8b1788ae8232d79b2181536b138e2dcaf87d4beb986336ac3b3db2164ce53d6",
    ("gisco", 2018): "f202e59f8ca56cac03fdd035ffa14bcb1bd760cf98d527de3c3e0bd4fb0f89b0",
}

EXPECTED = {
    ("nl", 2025): {"areas": 342, "formal": 10_571_990, "seats": 150},
    ("nl", 2023): {"areas": 342, "formal": 10_432_726, "seats": 150},
    ("no", 2025): {"areas": 357, "formal": 3_219_888, "seats": 169},
    ("no", 2021): {"areas": 356, "formal": 2_984_187, "seats": 169},
    ("se", 2022): {"areas": 290, "formal": 6_477_970, "seats": 349},
    ("se", 2018): {"areas": 290, "formal": 6_476_725, "seats": 349},
}
NORWAY_MANIFEST_SHA256 = {
    2025: "bfafbab08ebf02044657377e633062ac3a3a15a5fa00ce04752500ff560d755f",
    2021: "4877e262aa48dabe905c7bda6b68d3452f4b3b62b43858e1cbc670f5ba7eee37",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note", "district_seats",
)

NL_PARTIES = {
    "PVV (Partij voor de Vrijheid)": "PVV",
    "GROENLINKS / Partij van de Arbeid (PvdA)": "GL-PvdA",
    "Nieuw Sociaal Contract (NSC)": "NSC",
    "Nieuw Sociaal Contract": "NSC",
    "SP (Socialistische Partij)": "SP",
    "Partij voor de Dieren": "PvdD",
    "Forum voor Democratie": "FVD",
    "Staatkundig Gereformeerde Partij (SGP)": "SGP",
    "ChristenUnie": "CU",
    "Belang Van Nederland (BVNL)": "BVNL",
    "LP (Libertaire Partij)": "LP",
}
SE_PARTIES_2022 = {
    "Moderaterna": "M",
    "Arbetarepartiet-Socialdemokraterna": "S",
    "Liberalerna (tidigare Folkpartiet)": "L",
    "Centerpartiet": "C",
    "Kristdemokraterna": "KD",
    "Vänsterpartiet": "V",
    "Miljöpartiet de gröna": "MP",
    "Sverigedemokraterna": "SD",
    "övriga anmälda partier": "Other",
}
SEATS_SWEDEN = {
    2022: {"S": 107, "SD": 73, "M": 68, "V": 24, "C": 24, "KD": 19, "MP": 18, "L": 16},
    2018: {"S": 100, "M": 70, "SD": 62, "C": 31, "V": 28, "KD": 22, "L": 20, "MP": 16},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_digest(path: Path, expected: str) -> None:
    actual = digest(path)
    print(f"{path.name} SHA256: {actual}")
    if expected != "PENDING" and actual != expected:
        raise SystemExit(f"{path}: checksum changed; expected {expected}, found {actual}")


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size > 1_000 and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)
    return path


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def election_rows(
    district: str,
    code: str,
    votes: dict[str, int],
    enrolment: int,
    formal: int,
    informal: int,
    source_page: str,
    country: str,
    note: str,
) -> list[dict[str, object]]:
    if sum(votes.values()) != formal:
        raise SystemExit(f"{country} {district}: party votes do not equal valid votes")
    total = formal + informal
    winner = max(votes, key=votes.get)
    return [{
        "district": district,
        "district_url": source_page,
        "distribution_url": "",
        "elected_member": winner,
        "elected_party": winner,
        "enrolment": enrolment,
        "formal_votes": formal,
        "informal_votes": informal,
        "total_votes": total,
        "turnout_pct": round(total / enrolment * 100, 2) if enrolment else 0,
        "majority": formal // 2 + 1,
        "round_number": 0,
        "row_type": "first",
        "excluded_candidate": "",
        "excluded_party": "",
        "candidate": party,
        "candidate_party": party,
        "votes": count,
        "electorate_type": country,
        "constituency_code": code,
        "contest_status": "official",
        "result_note": note,
        "district_seats": 0,
    } for party, count in sorted(votes.items(), key=lambda item: (-item[1], item[0])) if count]


def build_netherlands(
    session: requests.Session, year: int, raw_dir: Path, output_dir: Path, refresh: bool
) -> None:
    archive = download(session, NL_URLS[year], raw_dir / f"netherlands_{year}.zip", refresh)
    require_digest(archive, SOURCE_SHA256[("nl", year)])
    with zipfile.ZipFile(archive) as bundle:
        member = next(name for name in bundle.namelist() if name.endswith("_uitslag.csv"))
        with bundle.open(member) as handle:
            data = pd.read_csv(handle, sep=";", low_memory=False, dtype={"RegioCode": str})

    municipalities = data[data["RegioCode"].str.fullmatch(r"G\d{4}", na=False)].copy()
    municipalities = municipalities[municipalities["RegioCode"] != "G9010"]
    if municipalities["RegioCode"].nunique() != EXPECTED[("nl", year)]["areas"]:
        raise SystemExit(f"Netherlands {year}: unexpected municipality count")

    rows: list[dict[str, object]] = []
    note = "Municipality totals; seats are allocated nationally."
    for region_code, group in municipalities.groupby("RegioCode", sort=True):
        district = str(group.iloc[0]["Regio"])
        metrics = {
            row.VeldType: int(row.Waarde)
            for row in group.itertuples()
            if row.VeldType in {
                "Kiesgerechtigden", "AantalGeldigeStemmen", "AantalBlancoStemmen",
                "AantalOngeldigeStemmen", "Opkomst",
            }
        }
        party_rows = group[group["VeldType"] == "LijstAantalStemmen"]
        votes = {
            NL_PARTIES.get(str(row.LijstNaam), str(row.LijstNaam)): int(row.Waarde)
            for row in party_rows.itertuples()
        }
        formal = metrics["AantalGeldigeStemmen"]
        informal = metrics["AantalBlancoStemmen"] + metrics["AantalOngeldigeStemmen"]
        if formal + informal != metrics["Opkomst"]:
            raise SystemExit(f"Netherlands {year} {district}: ballot totals do not reconcile")
        rows.extend(election_rows(
            district, f"NL_GM{region_code[1:]}", votes, metrics["Kiesgerechtigden"],
            formal, informal, NL_SOURCE_PAGES[year], "Netherlands", note,
        ))

    national = data[data["RegioCode"] == "L528"]
    national_valid = int(national[national["VeldType"] == "AantalGeldigeStemmen"].iloc[0]["Waarde"])
    seats = int(national[national["VeldType"] == "LijstAantalZetels"]["Waarde"].sum())
    if national_valid != EXPECTED[("nl", year)]["formal"] or seats != 150:
        raise SystemExit(f"Netherlands {year}: national control totals changed")
    write_csv(output_dir / f"netherlands_{year}_house_fpp.csv", rows)
    print(f"Netherlands {year}: wrote {len(rows)} rows across 342 municipalities")


def get_json(session: requests.Session, url: str, path: Path, refresh: bool) -> dict[str, object]:
    download(session, url, path, refresh)
    return json.loads(path.read_text(encoding="utf-8"))


def norway_sources(
    session: requests.Session, year: int, raw_dir: Path, refresh: bool
) -> tuple[dict[str, object], list[dict[str, object]]]:
    prefix = raw_dir / f"norway_{year}"
    root = get_json(session, f"{NORWAY_API}/{year}/st", prefix / "root.json", refresh)
    county_payloads = []
    for link in root["_links"]["related"]:
        county_payloads.append(get_json(
            session, NORWAY_API + link["href"], prefix / f"county_{link['nr']}.json", refresh
        ))
    municipality_links = {
        link["nr"]: (link, county["id"]["navn"])
        for county in county_payloads
        for link in county["_links"]["related"]
    }

    def fetch(item: tuple[dict[str, object], str]) -> dict[str, object]:
        link, county = item
        payload = get_json(
            session, NORWAY_API + str(link["href"]),
            prefix / f"municipality_{link['nr']}.json", refresh,
        )
        payload["_parent_county"] = county
        return payload

    with ThreadPoolExecutor(max_workers=8) as pool:
        municipalities = list(pool.map(fetch, municipality_links.values()))
    manifest = "\n".join(
        f"{path.name}:{digest(path)}" for path in sorted(prefix.glob("*.json"))
    )
    manifest_digest = hashlib.sha256(manifest.encode()).hexdigest()
    print(f"Norway {year} API manifest: {manifest_digest}")
    if manifest_digest != NORWAY_MANIFEST_SHA256[year]:
        raise SystemExit(
            f"Norway {year}: API manifest changed; expected "
            f"{NORWAY_MANIFEST_SHA256[year]}, found {manifest_digest}"
        )
    return root, municipalities


def build_norway(
    session: requests.Session, year: int, raw_dir: Path, output_dir: Path, refresh: bool
) -> None:
    root, municipalities = norway_sources(session, year, raw_dir, refresh)
    if len(municipalities) != EXPECTED[("no", year)]["areas"]:
        raise SystemExit(f"Norway {year}: unexpected municipality count {len(municipalities)}")
    if int(root["mandater"]["antall"]) != 169:
        raise SystemExit(f"Norway {year}: national seat total changed")

    rows: list[dict[str, object]] = []
    note = "Municipality totals; seats are not allocated by municipality."
    name_counts = Counter(str(item["id"]["navn"]) for item in municipalities)
    for payload in sorted(municipalities, key=lambda item: item["id"]["nr"]):
        parties = {
            str(party["id"]["partikode"]): int(party["stemmer"]["resultat"]["antall"]["total"])
            for party in payload["partier"]
            if int(party["id"]["partikategori"]) in {1, 2, 3}
            and party["id"]["partikode"] != "BLANKE"
        }
        blank = next(
            (int(party["stemmer"]["resultat"]["antall"]["total"])
             for party in payload["partier"] if party["id"]["partikode"] == "BLANKE"),
            0,
        )
        formal = int(payload["stemmer"]["total"]) - blank
        informal = blank + int(payload["stemmer"]["totalForkastede"])
        district = str(payload["id"]["navn"])
        if name_counts[district] > 1:
            district += f" ({payload['_parent_county']})"
        rows.extend(election_rows(
            district, f"NO_{payload['id']['nr']}", parties,
            int(payload["antallsb"]), formal, informal, NORWAY_SOURCE_PAGES[year],
            "Norway", note,
        ))

    national_blank = next(
        int(party["stemmer"]["resultat"]["antall"]["total"])
        for party in root["partier"] if party["id"]["partikode"] == "BLANKE"
    )
    national_formal = int(root["stemmer"]["total"]) - national_blank
    if national_formal != EXPECTED[("no", year)]["formal"]:
        raise SystemExit(f"Norway {year}: national valid-vote control total changed")
    write_csv(output_dir / f"norway_{year}_storting_fpp.csv", rows)
    print(f"Norway {year}: wrote {len(rows)} rows across {len(municipalities)} municipalities")


def build_sweden_2022(path: Path, output_dir: Path) -> None:
    data = pd.read_excel(path, sheet_name="roster_RD")
    data.columns = data.columns.str.strip()
    code_match = data["Distrikt"].str.extract(r"^RD-(\d{2})-(\d{2})-")
    data["municipality_code"] = code_match[0] + code_match[1]
    if data["municipality_code"].isna().any():
        raise SystemExit("Sweden 2022: could not derive all municipality codes")

    rows: list[dict[str, object]] = []
    special = {
        "Summa giltiga röster", "Valdeltagande", "blanka röster",
        "övriga ogiltiga", "ej anmält deltagande",
    }
    note = "District results aggregated to municipalities; seats are allocated elsewhere."
    for code, group in data.groupby("municipality_code", sort=True):
        district = str(group.iloc[0]["Kommun"])
        by_party = group.groupby("Parti")["Röster"].sum()
        votes = {
            SE_PARTIES_2022.get(str(party).strip(), str(party).strip()): int(count)
            for party, count in by_party.items()
            if str(party).strip() not in special and int(count)
        }
        formal = int(by_party["Summa giltiga röster"])
        total = int(by_party["Valdeltagande"])
        enrolment = int(group.drop_duplicates("Valdistriktskod")["Röstberättigade"].sum())
        rows.extend(election_rows(
            district, f"SE_{code}", votes, enrolment, formal, total - formal,
            SWEDEN_SOURCE_PAGES[2022], "Sweden", note,
        ))
    if len({row["constituency_code"] for row in rows}) != 290:
        raise SystemExit("Sweden 2022: unexpected municipality count")
    if sum(row["votes"] for row in rows) != EXPECTED[("se", 2022)]["formal"]:
        raise SystemExit("Sweden 2022: national valid-vote control total changed")
    write_csv(output_dir / "sweden_2022_riksdag_fpp.csv", rows)
    print(f"Sweden 2022: wrote {len(rows)} rows across 290 municipalities")


def build_sweden_2018(path: Path, output_dir: Path) -> None:
    data = pd.read_excel(path, sheet_name="R antal").fillna(0)
    party_columns = list(data.columns[4:data.columns.get_loc("OGEJ")])
    party_names = {**{key: key for key in party_columns}, "ÖVR": "Other"}
    rows: list[dict[str, object]] = []
    note = "Municipality totals; seats are not allocated by municipality."
    for _, row in data.iterrows():
        code = f"{int(row['LÄNSKOD']):02d}{int(row['KOMMUNKOD']):02d}"
        votes = {
            party_names[column]: int(row[column])
            for column in party_columns if int(row[column])
        }
        formal = int(row["RÖSTER GILTIGA"])
        total = int(row["RÖSTANDE"])
        rows.extend(election_rows(
            str(row["KOMMUNNAMN"]), f"SE_{code}", votes, int(row["RÖSTBERÄTTIGADE"]),
            formal, total - formal, SWEDEN_SOURCE_PAGES[2018], "Sweden", note,
        ))
    if len({row["constituency_code"] for row in rows}) != 290:
        raise SystemExit("Sweden 2018: unexpected municipality count")
    if sum(row["votes"] for row in rows) != EXPECTED[("se", 2018)]["formal"]:
        raise SystemExit("Sweden 2018: national valid-vote control total changed")
    write_csv(output_dir / "sweden_2018_riksdag_fpp.csv", rows)
    print(f"Sweden 2018: wrote {len(rows)} rows across 290 municipalities")


def decode_arc(
    arcs: list[list[list[int]]], index: int, scale: list[float], translate: list[float]
) -> list[list[float]]:
    raw = arcs[index if index >= 0 else ~index]
    x = y = 0
    points = []
    for dx, dy in raw:
        x += dx
        y += dy
        points.append([
            round(x * scale[0] + translate[0], 5),
            round(y * scale[1] + translate[1], 5),
        ])
    return points if index >= 0 else list(reversed(points))


def stitch_ring(
    indices: list[int], arcs: list[list[list[int]]], scale: list[float], translate: list[float]
) -> list[list[float]]:
    ring: list[list[float]] = []
    for index in indices:
        points = decode_arc(arcs, index, scale, translate)
        ring.extend(points if not ring else points[1:])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def topology_geometry(
    geometry: dict[str, object], arcs: list[list[list[int]]],
    scale: list[float], translate: list[float],
) -> dict[str, object]:
    if geometry["type"] == "Polygon":
        coordinates = [
            stitch_ring(ring, arcs, scale, translate) for ring in geometry["arcs"]
        ]
    elif geometry["type"] == "MultiPolygon":
        coordinates = [[
            stitch_ring(ring, arcs, scale, translate) for ring in polygon
        ] for polygon in geometry["arcs"]]
    else:
        raise SystemExit(f"Unsupported GISCO geometry {geometry['type']}")
    return {"type": geometry["type"], "coordinates": coordinates}


def build_boundaries(
    archive: Path, year: int, countries: set[str]
) -> dict[str, dict[str, object]]:
    with zipfile.ZipFile(archive) as bundle:
        member = f"LAU_RG_01M_{year}_4326.json"
        topology = json.loads(bundle.read(member))
    object_data = next(iter(topology["objects"].values()))
    scale = topology["transform"]["scale"]
    translate = topology["transform"]["translate"]
    result = {country: {"type": "FeatureCollection", "features": []} for country in countries}
    for item in object_data["geometries"]:
        properties = item["properties"]
        country = properties["CNTR_CODE"]
        if country not in countries:
            continue
        geometry = topology_geometry(item, topology["arcs"], scale, translate)
        cleaned = shape(geometry).simplify(0.0025, preserve_topology=True)
        result[country]["features"].append({
            "type": "Feature",
            "properties": {
                "district": properties["LAU_NAME"],
                "constituency_code": properties["GISCO_ID"],
                "source": GISCO_SOURCE_PAGE,
                "boundary_year": year,
            },
            "geometry": mapping(cleaned),
        })
    return result


def write_matched_boundary(
    output: Path, boundary: dict[str, object], csv_path: Path
) -> None:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    codes = {row["constituency_code"] for row in rows}
    district_by_code = {
        row["constituency_code"]: row["district"] for row in rows
    }
    features = [
        feature for feature in boundary["features"]
        if feature["properties"]["constituency_code"] in codes
    ]
    for feature in features:
        feature["properties"]["district"] = district_by_code[
            feature["properties"]["constituency_code"]
        ]
    feature_codes = {feature["properties"]["constituency_code"] for feature in features}
    if feature_codes != codes:
        missing = sorted(codes - feature_codes)
        raise SystemExit(f"{output}: boundary is missing {missing[:10]}")
    payload = {"type": "FeatureCollection", "features": features}
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"{output.name}: wrote {len(features)} municipality boundaries")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Netherlands, Norway, and Sweden national election datasets"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/northern_europe_raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"

    for year in (2025, 2023):
        build_netherlands(session, year, args.raw_dir, args.output_dir, args.refresh)
    for year in (2025, 2021):
        build_norway(session, year, args.raw_dir, args.output_dir, args.refresh)

    sweden_paths = {}
    for year in (2022, 2018):
        path = download(
            session, SWEDEN_URLS[year], args.raw_dir / f"sweden_{year}.xlsx", args.refresh
        )
        require_digest(path, SOURCE_SHA256[("se", year)])
        sweden_paths[year] = path
    build_sweden_2022(sweden_paths[2022], args.output_dir)
    build_sweden_2018(sweden_paths[2018], args.output_dir)

    boundary_jobs = {
        2024: {"NL", "NO"},
        2022: {"SE"},
        2021: {"NO"},
        2018: {"SE"},
    }
    boundary_sets = {}
    for year, countries in boundary_jobs.items():
        archive = download(
            session, GISCO_URL.format(year=year),
            args.raw_dir / f"gisco_lau_{year}.zip", args.refresh,
        )
        require_digest(archive, SOURCE_SHA256[("gisco", year)])
        boundary_sets[year] = build_boundaries(archive, year, countries)

    boundary_specs = (
        ("netherlands", 2025, 2024, "NL", "house"),
        ("netherlands", 2023, 2024, "NL", "house"),
        ("norway", 2025, 2024, "NO", "storting"),
        ("norway", 2021, 2021, "NO", "storting"),
        ("sweden", 2022, 2022, "SE", "riksdag"),
        ("sweden", 2018, 2018, "SE", "riksdag"),
    )
    for country, election_year, boundary_year, code, chamber in boundary_specs:
        write_matched_boundary(
            args.output_dir / f"{country}_{election_year}_{chamber}_boundaries.geojson",
            boundary_sets[boundary_year][code],
            args.output_dir / f"{country}_{election_year}_{chamber}_fpp.csv",
        )


if __name__ == "__main__":
    main()
