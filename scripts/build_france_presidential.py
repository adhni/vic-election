#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

import requests
import xlrd
from shapely import affinity
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


RESULT_URLS = {
    (2022, 1, "department"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152356/resultats-par-niveau-dpt-t1-france-entiere.txt",
    (2022, 1, "region"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152331/resultats-par-niveau-reg-t1-france-entiere.txt",
    (2022, 1, "national"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour/20220414-152200/resultats-par-niveau-fe-t1-france-entiere.txt",
    (2022, 2, "department"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-142127/resultats-par-niveau-dpt-t2-france-entiere.txt",
    (2022, 2, "region"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-142058/resultats-par-niveau-reg-t2-france-entiere.txt",
    (2022, 2, "national"): "https://static.data.gouv.fr/resources/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour/20220428-141900/resultats-par-niveau-fe-t2-france-entiere.txt",
    (2017, 1, "workbook"): "https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-1er-tour-1/20170427-100131/Presidentielle_2017_Resultats_Tour_1_c.xls",
    (2017, 2, "workbook"): "https://static.data.gouv.fr/resources/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-2nd-tour/20170511-092258/Presidentielle_2017_Resultats_Tour_2_c.xls",
    (2012, 0, "workbook"): "https://static.data.gouv.fr/15/56da0680db5a23d2d1601aed81359f21e0dc8ed9f8abd49e2a7c66b5c02b6f.xls",
    (2007, 0, "workbook"): "https://static.data.gouv.fr/fb/b5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d43805a734479294899.xls",
}
BOUNDARY_URLS = {
    "department": "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-1000m.geojson",
    "region": "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/regions-1000m.geojson",
}
SOURCE_SHA256 = {
    (2022, 1, "department"): "772da37dd5bbe88b4c064130ab99f93114257a6ac84cc7cab3f5b72bb2b41472",
    (2022, 1, "region"): "2a4e59466a6b3777a9f8b80d53adf8b39a9c636f2393722d6095a4938b2d326f",
    (2022, 1, "national"): "6986b74e3d4fd86fdb16c1036e6273c8e5df12ffc53497249e760980a96ec260",
    (2022, 2, "department"): "313bfeb99f398c8432e5ea610698b27915c91b0a977cff566b1fd6f737659b3e",
    (2022, 2, "region"): "ef1512bfe1143e0a5fa0a8800cae083fbb98310d8a599dda425f3d69a72333c7",
    (2022, 2, "national"): "af8ba10aa9209eed1a18247c125fabcd7749b1f2ff380c4bc2d6b95431689859",
    (2017, 1, "workbook"): "de23d5d7f8fd8ca58f6c4813eedb95a3a1a503cf7462e9de46d6114a019376ae",
    (2017, 2, "workbook"): "903dd564aa9328e2826b0631bfd5022d2192ef743c75fa667e8390f33684319d",
    (2012, 0, "workbook"): "1556da0680db5a23d2d1601aed81359f21e0dc8ed9f8abd49e2a7c66b5c02b6f",
    (2007, 0, "workbook"): "fbb5de8c5118fab4c029f7289c6a46fcf3ebfa0936d93d43805a734479294899",
    "department_boundary": "c4be02f0454addb63d8a327d008fe983561d3e063340825f953b3a4e59a2198f",
    "region_boundary": "7f44a5c4deaeb710c9dc2b043ed4debcf50068a1b0740619a5873f9e878f9786",
}
SOURCE_PAGES = {
    (2022, 1): "https://www.data.gouv.fr/datasets/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-1er-tour",
    (2022, 2): "https://www.data.gouv.fr/datasets/election-presidentielle-des-10-et-24-avril-2022-resultats-definitifs-du-2nd-tour",
    (2017, 1): "https://www.data.gouv.fr/datasets/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-1er-tour-1",
    (2017, 2): "https://www.data.gouv.fr/datasets/election-presidentielle-des-23-avril-et-7-mai-2017-resultats-definitifs-du-2nd-tour",
    (2012, 1): "https://www.data.gouv.fr/datasets/election-presidentielle-2012-resultats-572126",
    (2012, 2): "https://www.data.gouv.fr/datasets/election-presidentielle-2012-resultats-572126",
    (2007, 1): "https://www.data.gouv.fr/datasets/election-presidentielle-2007-resultats-572120",
    (2007, 2): "https://www.data.gouv.fr/datasets/election-presidentielle-2007-resultats-572120",
}
BOUNDARY_PAGE = "https://www.data.gouv.fr/datasets/contours-administratifs"

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

OVERSEAS_SOURCE_CODES = {
    "ZA": ("971",),
    "ZB": ("972",),
    "ZC": ("973",),
    "ZD": ("974",),
    "ZM": ("976",),
    "ZN": ("988",),
    "ZP": ("987",),
    "ZS": ("975",),
    "ZW": ("986",),
    "ZX": ("977", "978"),
}
OVERSEAS_NAMES = {
    "ZA": "Guadeloupe",
    "ZB": "Martinique",
    "ZC": "Guyane",
    "ZD": "La Réunion",
    "ZM": "Mayotte",
    "ZN": "Nouvelle-Calédonie",
    "ZP": "Polynésie française",
    "ZS": "Saint-Pierre-et-Miquelon",
    "ZW": "Wallis-et-Futuna",
    "ZX": "Saint-Martin / Saint-Barthélemy",
}
INSET_TARGETS = {
    "ZA": (-5.5, 39.7),
    "ZB": (-3.5, 39.7),
    "ZC": (-1.4, 39.7),
    "ZD": (1.0, 39.7),
    "ZM": (3.0, 39.7),
    "ZS": (5.0, 39.7),
    "ZX": (7.0, 39.7),
    "ZW": (-4.5, 37.4),
    "ZP": (-1.8, 37.4),
    "ZN": (1.2, 37.4),
}

OLD_REGIONS = {
    "42": ("Alsace", ("67", "68")),
    "72": ("Aquitaine", ("24", "33", "40", "47", "64")),
    "83": ("Auvergne", ("03", "15", "43", "63")),
    "26": ("Bourgogne", ("21", "58", "71", "89")),
    "53": ("Bretagne", ("22", "29", "35", "56")),
    "21": ("Champagne-Ardenne", ("08", "10", "51", "52")),
    "43": ("Franche-Comté", ("25", "39", "70", "90")),
    "91": ("Languedoc-Roussillon", ("11", "30", "34", "48", "66")),
    "74": ("Limousin", ("19", "23", "87")),
    "41": ("Lorraine", ("54", "55", "57", "88")),
    "73": ("Midi-Pyrénées", ("09", "12", "31", "32", "46", "65", "81", "82")),
    "31": ("Nord-Pas-de-Calais", ("59", "62")),
    "25": ("Basse-Normandie", ("14", "50", "61")),
    "23": ("Haute-Normandie", ("27", "76")),
    "52": ("Pays de la Loire", ("44", "49", "53", "72", "85")),
    "22": ("Picardie", ("02", "60", "80")),
    "54": ("Poitou-Charentes", ("16", "17", "79", "86")),
    "93": ("Provence-Alpes-Côte d’Azur", ("04", "05", "06", "13", "83", "84")),
    "82": ("Rhône-Alpes", ("01", "07", "26", "38", "42", "69", "73", "74")),
    "11": ("Île-de-France", ("75", "77", "78", "91", "92", "93", "94", "95")),
    "24": ("Centre", ("18", "28", "36", "37", "41", "45")),
    "94": ("Corse", ("2A", "2B")),
    "01": ("Guadeloupe", ("ZA",)),
    "02": ("Martinique", ("ZB",)),
    "03": ("Guyane", ("ZC",)),
    "04": ("La Réunion", ("ZD",)),
    "06": ("Mayotte", ("ZM",)),
}

# Definitive national valid-vote totals from the same Ministry sources.
EXPECTED_NATIONAL: dict[tuple[int, int], dict[str, int]] = {
    (2022, 1): {
        "Nathalie Arthaud": 197_094, "Fabien Roussel": 802_422,
        "Emmanuel Macron": 9_783_058, "Jean Lassalle": 1_101_387,
        "Marine Le Pen": 8_133_828, "Éric Zemmour": 2_485_226,
        "Jean-Luc Mélenchon": 7_712_520, "Anne Hidalgo": 616_478,
        "Yannick Jadot": 1_627_853, "Valérie Pécresse": 1_679_001,
        "Philippe Poutou": 268_904, "Nicolas Dupont-Aignan": 725_176,
    },
    (2022, 2): {"Emmanuel Macron": 18_768_639, "Marine Le Pen": 13_288_686},
    (2017, 1): {
        "Marine Le Pen": 7_678_491, "Emmanuel Macron": 8_656_346,
        "François Fillon": 7_212_995, "Jean-Luc Mélenchon": 7_059_951,
        "Nicolas Dupont-Aignan": 1_695_000, "Benoît Hamon": 2_291_288,
        "François Asselineau": 332_547, "Jean Lassalle": 435_301,
        "Philippe Poutou": 394_505, "Nathalie Arthaud": 232_384,
        "Jacques Cheminade": 65_586,
    },
    (2017, 2): {"Emmanuel Macron": 20_743_128, "Marine Le Pen": 10_638_475},
    (2012, 1): {
        "Eva Joly": 828_345, "Marine Le Pen": 6_421_426,
        "Nicolas Sarkozy": 9_753_629, "Jean-Luc Mélenchon": 3_984_822,
        "Philippe Poutou": 411_160, "Nathalie Arthaud": 202_548,
        "Jacques Cheminade": 89_545, "François Bayrou": 3_275_122,
        "Nicolas Dupont-Aignan": 643_907, "François Hollande": 10_272_705,
    },
    (2012, 2): {"François Hollande": 18_000_668, "Nicolas Sarkozy": 16_860_685},
    (2007, 1): {
        "Olivier Besancenot": 1_498_581, "Marie-George Buffet": 707_268,
        "Gérard Schivardi": 123_540, "François Bayrou": 6_820_117,
        "José Bové": 483_009, "Dominique Voynet": 576_666,
        "Philippe de Villiers": 818_407, "Ségolène Royal": 9_500_112,
        "Frédéric Nihous": 420_645, "Jean-Marie Le Pen": 3_834_530,
        "Arlette Laguiller": 487_858, "Nicolas Sarkozy": 11_448_663,
    },
    (2007, 2): {"Nicolas Sarkozy": 18_983_138, "Ségolène Royal": 16_790_440},
}


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


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def clean_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().replace("_", " ").split())


def result_code(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):02d}"
    text = str(value).strip()
    if text.isdigit():
        return text.zfill(2)
    return text.upper()


def integer(value: object) -> int:
    if value in ("", None):
        return 0
    if isinstance(value, str):
        value = value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    return int(float(value))


def candidate_name(last: object, first: object) -> str:
    first_name = " ".join(str(first).split())
    last_name = " ".join(str(last).split())
    last_name = " ".join(
        token.title() if any(character.isalpha() for character in token) and token.isupper() else token
        for token in last_name.split()
    )
    last_name = last_name.replace("-Le-", "-le-").replace("-De-", "-de-")
    return f"{first_name} {last_name}".strip()


def parse_table(header: list[object], rows: list[list[object]]) -> dict[str, dict[str, object]]:
    normalized = [clean_header(value) for value in header]
    indices = {name: normalized.index(name) for name in ("inscrits", "votants", "exprimes")}
    blank_columns = [
        index for index, name in enumerate(normalized)
        if name in {"blancs", "nuls", "blancs et nuls"}
    ]
    candidate_starts = [index for index, name in enumerate(normalized) if name == "sexe"]
    if not candidate_starts:
        raise SystemExit("Could not find candidate columns in official result table")
    groups = []
    if len(candidate_starts) == 1 and rows:
        # The Ministry's 2022 delimited files print one six-column candidate
        # header even though every data row repeats that group for all candidates.
        # Some levels also put a panel-number column immediately before "Sexe".
        first_sex = candidate_starts[0]
        group_start = first_sex - 1 if "panneau" in normalized[first_sex - 1] else first_sex
        width = len(header) - group_start
        candidate_starts = list(range(first_sex, max(len(row) for row in rows), width))
    for position, start in enumerate(candidate_starts):
        end = candidate_starts[position + 1] if position + 1 < len(candidate_starts) else start + (candidate_starts[1] - candidate_starts[0] if len(candidate_starts) > 1 else len(header) - start)
        group_headers = normalized[candidate_starts[0]:candidate_starts[0] + (end - start)]
        try:
            groups.append((
                start + group_headers.index("nom"),
                start + group_headers.index("prenom"),
                start + group_headers.index("voix"),
            ))
        except ValueError as exc:
            raise SystemExit("Unexpected candidate column layout in official table") from exc

    output: dict[str, dict[str, object]] = {}
    for row in rows:
        if not row or row[0] in ("", None):
            continue
        code = result_code(row[0])
        if code in output:
            raise SystemExit(f"Duplicate result row for {code}")
        votes = Counter()
        for last_index, first_index, vote_index in groups:
            if last_index >= len(row) or not str(row[last_index]).strip():
                continue
            votes[candidate_name(row[last_index], row[first_index])] += integer(row[vote_index])
        formal = integer(row[indices["exprimes"]])
        total = integer(row[indices["votants"]])
        informal = sum(integer(row[index]) for index in blank_columns)
        if sum(votes.values()) != formal:
            raise SystemExit(f"{code}: candidate votes do not equal expressed votes")
        if formal + informal != total:
            raise SystemExit(f"{code}: expressed plus blank/invalid votes do not equal voters")
        output[code] = {
            "source_name": " ".join(str(row[1]).split()),
            "enrolment": integer(row[indices["inscrits"]]),
            "formal": formal,
            "informal": informal,
            "total": total,
            "votes": votes,
        }
    return output


def parse_xls_sheet(path: Path, sheet_name: str) -> dict[str, dict[str, object]]:
    book = xlrd.open_workbook(path, on_demand=True)
    sheet = book.sheet_by_name(sheet_name)
    header_index = next(
        index for index in range(min(10, sheet.nrows))
        if "inscrits" in [clean_header(value) for value in sheet.row_values(index)]
    )
    header = sheet.row_values(header_index)
    rows = [sheet.row_values(index) for index in range(header_index + 1, sheet.nrows)]
    result = parse_table(header, rows)
    book.unload_sheet(sheet_name)
    return result


def parse_txt(path: Path) -> dict[str, dict[str, object]]:
    with path.open(newline="", encoding="latin-1") as handle:
        reader = csv.reader(handle, delimiter=";")
        header = next(reader)
        return parse_table(header, list(reader))


def aggregate_departments_2012(path: Path, round_number: int) -> dict[str, dict[str, object]]:
    book = xlrd.open_workbook(path, on_demand=True)
    sheet = book.sheet_by_name(f"Tour {round_number}")
    header = sheet.row_values(0)
    normalized = [clean_header(value) for value in header]
    indices = {name: normalized.index(name) for name in ("inscrits", "votants", "exprimes")}
    blank_index = normalized.index("blancs et nuls")
    starts = [index for index, name in enumerate(normalized) if name == "sexe"]
    groups = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(header)
        names = normalized[start:end]
        groups.append((
            start + names.index("nom"),
            start + names.index("prenom"),
            start + names.index("voix"),
        ))
    output: dict[str, dict[str, object]] = {}
    for row_index in range(1, sheet.nrows):
        row = sheet.row_values(row_index)
        code = result_code(row[0])
        area = output.setdefault(code, {
            "source_name": " ".join(str(row[1]).split()),
            "enrolment": 0,
            "formal": 0,
            "informal": 0,
            "total": 0,
            "votes": Counter(),
        })
        area["enrolment"] += integer(row[indices["inscrits"]])
        area["formal"] += integer(row[indices["exprimes"]])
        area["informal"] += integer(row[blank_index])
        area["total"] += integer(row[indices["votants"]])
        for last_index, first_index, vote_index in groups:
            area["votes"][candidate_name(row[last_index], row[first_index])] += integer(row[vote_index])
    book.unload_sheet(f"Tour {round_number}")
    for code, area in output.items():
        if sum(area["votes"].values()) != area["formal"] or area["formal"] + area["informal"] != area["total"]:
            raise SystemExit(f"2012 round {round_number} {code}: aggregated totals do not reconcile")
    return output


def aggregate_regions(
    departments: dict[str, dict[str, object]],
    include_mayotte: bool,
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for region_code, (name, member_codes) in OLD_REGIONS.items():
        if region_code == "06" and not include_mayotte:
            continue
        area = {
            "source_name": name,
            "enrolment": 0,
            "formal": 0,
            "informal": 0,
            "total": 0,
            "votes": Counter(),
        }
        for code in member_codes:
            source = departments[code]
            for metric in ("enrolment", "formal", "informal", "total"):
                area[metric] += source[metric]
            area["votes"].update(source["votes"])
        output[region_code] = area
    return output


def load_results(paths: dict[tuple[int, int, str], Path]) -> tuple[
    dict[tuple[int, int, str], dict[str, dict[str, object]]],
    dict[tuple[int, int], Counter],
]:
    results: dict[tuple[int, int, str], dict[str, dict[str, object]]] = {}
    national: dict[tuple[int, int], Counter] = {}
    for round_number in (1, 2):
        for level in ("department", "region"):
            results[(2022, round_number, level)] = parse_txt(paths[(2022, round_number, level)])
        national_table = parse_txt(paths[(2022, round_number, "national")])
        national[(2022, round_number)] = next(iter(national_table.values()))["votes"]

    for round_number in (1, 2):
        path = paths[(2017, round_number, "workbook")]
        results[(2017, round_number, "department")] = parse_xls_sheet(
            path, f"Départements Tour {round_number}"
        )
        results[(2017, round_number, "region")] = parse_xls_sheet(
            path, f"Régions Tour {round_number}"
        )
        national[(2017, round_number)] = Counter()
        for area in results[(2017, round_number, "department")].values():
            national[(2017, round_number)].update(area["votes"])

    path_2012 = paths[(2012, 0, "workbook")]
    for round_number in (1, 2):
        departments = aggregate_departments_2012(path_2012, round_number)
        results[(2012, round_number, "department")] = departments
        results[(2012, round_number, "region")] = aggregate_regions(departments, True)
        national[(2012, round_number)] = Counter()
        for area in departments.values():
            national[(2012, round_number)].update(area["votes"])

    path_2007 = paths[(2007, 0, "workbook")]
    for round_number in (1, 2):
        departments = parse_xls_sheet(path_2007, f"Départements T{round_number}")
        results[(2007, round_number, "department")] = departments
        results[(2007, round_number, "region")] = parse_xls_sheet(
            path_2007, f"Régions T{round_number}"
        )
        national[(2007, round_number)] = Counter()
        for area in departments.values():
            national[(2007, round_number)].update(area["votes"])

    for key, expected in EXPECTED_NATIONAL.items():
        if dict(national[key]) != expected:
            raise SystemExit(f"{key}: national candidate totals changed: {dict(national[key])}")
    return results, national


def inset_geometry(geometry, target: tuple[float, float]):
    min_x, min_y, max_x, max_y = geometry.bounds
    scale = min(1.35 / max(max_x - min_x, max_y - min_y, 0.01), 1.0)
    scaled = affinity.scale(geometry, xfact=scale, yfact=scale, origin="center")
    return affinity.translate(
        scaled,
        xoff=target[0] - scaled.centroid.x,
        yoff=target[1] - scaled.centroid.y,
    )


def polygonal_geometry(geometry):
    if geometry.geom_type in {"Polygon", "MultiPolygon"}:
        return geometry
    polygon_parts = []
    for part in getattr(geometry, "geoms", ()):
        cleaned = polygonal_geometry(part)
        if cleaned is not None and not cleaned.is_empty:
            polygon_parts.append(cleaned)
    return unary_union(polygon_parts) if polygon_parts else None


def department_geometry(
    year: int,
    code: str,
    source: dict[str, object],
):
    if code == "ZZ":
        return None
    if code in OVERSEAS_SOURCE_CODES:
        source_codes = list(OVERSEAS_SOURCE_CODES[code])
        if year == 2007 and code == "ZA":
            source_codes.extend(("977", "978"))
        geometry = unary_union([source[item] for item in source_codes])
        return inset_geometry(geometry, INSET_TARGETS[code])
    source_code = code.zfill(2) if code.isdigit() and len(code) < 3 else code
    return source.get(source_code)


def region_geometry(
    year: int,
    code: str,
    department_source: dict[str, object],
    region_source: dict[str, object],
):
    if year >= 2017:
        geometry = region_source[code]
        overseas_key = {"01": "ZA", "02": "ZB", "03": "ZC", "04": "ZD", "06": "ZM"}.get(code)
        return inset_geometry(geometry, INSET_TARGETS[overseas_key]) if overseas_key else geometry
    _, member_codes = OLD_REGIONS[code]
    pieces = []
    overseas_key = None
    for member_code in member_codes:
        if member_code in OVERSEAS_SOURCE_CODES:
            overseas_key = member_code
            source_codes = list(OVERSEAS_SOURCE_CODES[member_code])
            if year == 2007 and member_code == "ZA":
                source_codes.extend(("977", "978"))
            pieces.extend(department_source[item] for item in source_codes)
        else:
            pieces.append(department_source[member_code])
    geometry = unary_union(pieces)
    return inset_geometry(geometry, INSET_TARGETS[overseas_key]) if overseas_key else geometry


def display_name(
    year: int,
    level: str,
    code: str,
    area: dict[str, object],
    department_names: dict[str, str],
    region_names: dict[str, str],
) -> str:
    if level == "region":
        if year < 2017:
            return OLD_REGIONS[code][0]
        return region_names[code]
    if code in OVERSEAS_NAMES:
        if year == 2007 and code == "ZA":
            return "Guadeloupe (including Saint-Martin and Saint-Barthélemy)"
        return OVERSEAS_NAMES[code]
    return department_names.get(code, str(area["source_name"]).title())


def build_level(
    year: int,
    round_number: int,
    level: str,
    areas: dict[str, dict[str, object]],
    department_source: dict[str, object],
    department_names: dict[str, str],
    region_source: dict[str, object],
    region_names: dict[str, str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = []
    features = []
    for code, area in sorted(areas.items()):
        if code == "ZZ":
            continue
        geometry = (
            department_geometry(year, code, department_source)
            if level == "department"
            else region_geometry(year, code, department_source, region_source)
        )
        if geometry is None or geometry.is_empty:
            raise SystemExit(f"{year} round {round_number} {level} {code}: missing geometry")
        name = display_name(
            year, level, code, area, department_names, region_names
        )
        ranked = sorted(area["votes"].items(), key=lambda item: (-item[1], item[0]))
        constituency_code = f"FR{year}-T{round_number}-{'DPT' if level == 'department' else 'REG'}-{code}"
        area_type = "Region" if level == "region" else (
            "Overseas department / territory" if code.startswith("Z") else "Department"
        )
        note = (
            "Definitive Ministry of the Interior result. Overseas areas are shown in compact "
            "schematic insets; inset positions and scales are not geographic."
        )
        base = {
            "district": name,
            "district_url": SOURCE_PAGES[(year, round_number)],
            "distribution_url": BOUNDARY_PAGE,
            "elected_member": ranked[0][0],
            "elected_party": ranked[0][0],
            "enrolment": area["enrolment"],
            "formal_votes": area["formal"],
            "informal_votes": area["informal"],
            "total_votes": area["total"],
            "turnout_pct": round(area["total"] / area["enrolment"] * 100, 2),
            "majority": ranked[0][1] - ranked[1][1],
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": area_type,
            "constituency_code": constituency_code,
            "contest_status": "official",
            "result_note": note,
        }
        for candidate, votes in ranked:
            rows.append({
                **base,
                "candidate": candidate,
                "candidate_party": candidate,
                "votes": votes,
            })
        features.append({
            "type": "Feature",
            "properties": {
                "district": name,
                "constituency_code": constituency_code,
                "electorate_type": area_type,
            },
            "geometry": mapping(geometry),
        })
    return rows, {"type": "FeatureCollection", "features": features}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_geojson(path: Path, collection: dict[str, object]) -> None:
    path.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build France presidential department/territory and region maps"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/france_presidential"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    paths: dict[tuple[int, int, str], Path] = {}
    for key, url in RESULT_URLS.items():
        suffix = ".txt" if url.endswith(".txt") else ".xls"
        path = download(
            session,
            url,
            args.raw_dir / f"france_{key[0]}_t{key[1]}_{key[2]}{suffix}",
            args.refresh,
        )
        require_sha256(path, SOURCE_SHA256[key])
        paths[key] = path
    boundary_paths = {}
    for level, url in BOUNDARY_URLS.items():
        path = download(
            session,
            url,
            args.raw_dir / f"france_2025_{level}_boundaries.geojson",
            args.refresh,
        )
        require_sha256(path, SOURCE_SHA256[f"{level}_boundary"])
        boundary_paths[level] = path

    department_collection = json.loads(boundary_paths["department"].read_text(encoding="utf-8"))
    region_collection = json.loads(boundary_paths["region"].read_text(encoding="utf-8"))
    department_source = {
        feature["properties"]["code"]: polygonal_geometry(make_valid(shape(feature["geometry"])))
        for feature in department_collection["features"]
    }
    department_names = {
        feature["properties"]["code"]: feature["properties"]["nom"]
        for feature in department_collection["features"]
    }
    region_source = {
        feature["properties"]["code"]: polygonal_geometry(make_valid(shape(feature["geometry"])))
        for feature in region_collection["features"]
    }
    region_names = {
        feature["properties"]["code"]: feature["properties"]["nom"]
        for feature in region_collection["features"]
    }

    results, national = load_results(paths)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    boundary_outputs: dict[tuple[int, str], dict[str, object]] = {}
    for year in (2022, 2017, 2012, 2007):
        for round_number in (1, 2):
            for level in ("department", "region"):
                rows, boundaries = build_level(
                    year,
                    round_number,
                    level,
                    results[(year, round_number, level)],
                    department_source,
                    department_names,
                    region_source,
                    region_names,
                )
                write_csv(
                    args.out_dir / f"france_{year}_president_round_{round_number}_{level}_fpp.csv",
                    rows,
                )
                boundary_outputs.setdefault((year, level), boundaries)
                print(
                    f"{year} round {round_number} {level}: "
                    f"{len(boundaries['features'])} areas, {len(rows)} rows"
                )
        for round_number in (1, 2):
            total = sum(national[(year, round_number)].values())
            shares = {
                candidate: round(votes / total * 100, 2)
                for candidate, votes in sorted(
                    national[(year, round_number)].items(),
                    key=lambda item: (-item[1], item[0]),
                )
            }
            print(f"{year} round {round_number} national: {dict(national[(year, round_number)])}")
            print(f"{year} round {round_number} shares: {shares}")

    # The result geometry does not change between rounds in a given election year.
    for (year, level), collection in boundary_outputs.items():
        write_geojson(
            args.out_dir / f"france_{year}_{level}_boundaries.geojson",
            collection,
        )


if __name__ == "__main__":
    main()
