#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


RESULTS = {
    (2025, 1): (
        "https://prezydent2025.pkw.gov.pl/prezydent2025/data/csv/"
        "wyniki_gl_na_kandydatow_po_wojewodztwach_csv.1758650309.zip",
        "d2bc7f2a694c439cd094e360488411bb3f02ad427591d401a059d78277725220",
    ),
    (2025, 2): (
        "https://prezydent2025.pkw.gov.pl/prezydent2025/data/csv/"
        "wyniki_gl_na_kandydatow_po_wojewodztwach_w_drugiej_turze_csv.1758650309.zip",
        "e191047e74232788d24bb86cdc059dfbcda8cc900bab1cab7272dd1f1080c4e4",
    ),
    (2020, 1): (
        "https://prezydent20200628.pkw.gov.pl/prezydent20200628/data/1/csv/"
        "wyniki_gl_na_kand_po_wojewodztwach_csv.zip",
        "87abcfe163baa9c8b50fa8ed48a24b96b4bb0aa969eb6f0327fbb99c37c49261",
    ),
    (2020, 2): (
        "https://prezydent20200628.pkw.gov.pl/prezydent20200628/data/2/csv/"
        "wyniki_gl_na_kand_po_wojewodztwach_csv.zip",
        "126d61eef750b94c851cd860bcdbe43b57212e07fd3e7d4bb6e47b12560c9144",
    ),
}
BOUNDARY_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_03M_2021_4326_LEVL_2.geojson"
)
BOUNDARY_SHA256 = "690c055cdaf583c5c2326dc8c36f2db9f60c42a256a498f8391d2d83fa89b5fb"
SOURCE_PAGE = {
    2025: "https://prezydent2025.pkw.gov.pl/prezydent2025/pl/dane_w_arkuszach",
    2020: "https://prezydent20200628.pkw.gov.pl/prezydent20200628/pl/dane_w_arkuszach",
}

EXPECTED = {
    (2025, 1): (28_727_963, 19_137_917, 83_875),
    (2025, 2): (28_641_910, 20_239_632, 185_606),
    (2020, 1): (30_204_684, 19_425_459, 58_301),
    (2020, 2): (30_268_460, 20_458_911, 177_724),
}

CANDIDATE_NAMES = {
    "BARTOSZEWICZ Artur": "Artur Bartoszewicz",
    "BIEJAT Magdalena Agnieszka": "Magdalena Biejat",
    "BRAUN Grzegorz Michał": "Grzegorz Braun",
    "HOŁOWNIA Szymon Franciszek": "Szymon Hołownia",
    "JAKUBIAK Marek": "Marek Jakubiak",
    "MACIAK Maciej": "Maciej Maciak",
    "MENTZEN Sławomir Jerzy": "Sławomir Mentzen",
    "NAWROCKI Karol Tadeusz": "Karol Nawrocki",
    "SENYSZYN Joanna": "Joanna Senyszyn",
    "STANOWSKI Krzysztof Jakub": "Krzysztof Stanowski",
    "TRZASKOWSKI Rafał Kazimierz": "Rafał Trzaskowski",
    "WOCH Marek Marian": "Marek Woch",
    "ZANDBERG Adrian Tadeusz": "Adrian Zandberg",
    "Robert BIEDROŃ": "Robert Biedroń",
    "Krzysztof BOSAK": "Krzysztof Bosak",
    "Andrzej Sebastian DUDA": "Andrzej Duda",
    "Szymon Franciszek HOŁOWNIA": "Szymon Hołownia",
    "Marek JAKUBIAK": "Marek Jakubiak",
    "Władysław Marcin KOSINIAK-KAMYSZ": "Władysław Kosiniak-Kamysz",
    "Mirosław Mariusz PIOTROWSKI": "Mirosław Piotrowski",
    "Paweł Jan TANAJNO": "Paweł Tanajno",
    "Rafał Kazimierz TRZASKOWSKI": "Rafał Trzaskowski",
    "Waldemar Włodzimierz WITKOWSKI": "Waldemar Witkowski",
    "Stanisław Józef ŻÓŁTEK": "Stanisław Żółtek",
}

NUTS_BY_VOIVODESHIP = {
    "dolnośląskie": ["PL51"], "kujawsko-pomorskie": ["PL61"],
    "lubelskie": ["PL81"], "lubuskie": ["PL43"], "łódzkie": ["PL71"],
    "małopolskie": ["PL21"], "mazowieckie": ["PL91", "PL92"],
    "opolskie": ["PL52"], "podkarpackie": ["PL82"], "podlaskie": ["PL84"],
    "pomorskie": ["PL63"], "śląskie": ["PL22"],
    "świętokrzyskie": ["PL72"], "warmińsko-mazurskie": ["PL62"],
    "wielkopolskie": ["PL41"], "zachodniopomorskie": ["PL42"],
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)
    return path


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: checksum changed; expected {expected}, found {actual}")


def integer(row: dict[str, str], phrase: str) -> int:
    key = next((key for key in row if phrase in key), None)
    if key is None:
        raise SystemExit(f"Polish source is missing column containing {phrase!r}")
    return int(row[key])


def parse_results(path: Path, year: int, round_number: int) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(member) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
            source_rows = list(csv.DictReader(text, delimiter=";"))
    if len(source_rows) != 16:
        raise SystemExit(f"Poland {year} round {round_number}: expected 16 voivodeships")

    sample = source_rows[0]
    formal_key = next(key for key in sample if "ważnych oddanych łącznie" in key)
    informal_key = next(key for key in sample if key == "Liczba głosów nieważnych")
    enrolment_key = next(key for key in sample if "uprawnionych do głosowania" in key)
    candidate_keys = [
        key for key in list(sample)[list(sample).index(formal_key) + 1:]
        if "Liczba obwodów" not in key
    ]
    unknown = set(candidate_keys) - set(CANDIDATE_NAMES)
    if unknown:
        raise SystemExit(f"Poland {year}: unknown candidate columns {sorted(unknown)}")

    totals = Counter()
    output: list[dict[str, object]] = []
    for source in source_rows:
        district = source.get("Województwo", "").strip().lower()
        if district not in NUTS_BY_VOIVODESHIP:
            raise SystemExit(f"Poland {year}: unknown voivodeship {district!r}")
        votes = {CANDIDATE_NAMES[key]: int(source[key]) for key in candidate_keys}
        totals.update(votes)
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(source[formal_key])
        informal = int(source[informal_key])
        enrolment = int(source[enrolment_key])
        if sum(votes.values()) != formal:
            raise SystemExit(f"Poland {year} round {round_number} {district}: votes do not reconcile")
        base = {
            "district": district.title(),
            "district_url": SOURCE_PAGE[year],
            "distribution_url": BOUNDARY_URL,
            "elected_member": ranked[0][0], "elected_party": ranked[0][0],
            "enrolment": enrolment, "formal_votes": formal, "informal_votes": informal,
            "total_votes": formal + informal,
            "turnout_pct": round((formal + informal) / enrolment * 100, 2),
            "majority": ranked[0][1] - ranked[1][1], "round_number": round_number,
            "row_type": "first", "excluded_candidate": "", "excluded_party": "",
            "electorate_type": "Poland", "constituency_code": NUTS_BY_VOIVODESHIP[district][0],
            "contest_status": "official",
            "result_note": "Official PKW totals by voivodeship; local leaders do not elect separate presidents.",
        }
        for candidate, candidate_votes in ranked:
            output.append({**base, "candidate": candidate, "candidate_party": candidate, "votes": candidate_votes})

    expected = EXPECTED[(year, round_number)]
    observed = (
        sum(int(row[enrolment_key]) for row in source_rows),
        sum(int(row[formal_key]) for row in source_rows),
        sum(int(row[informal_key]) for row in source_rows),
    )
    if observed != expected:
        raise SystemExit(f"Poland {year} round {round_number}: national totals changed: {observed}")
    return output


def build_boundaries(path: Path) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    geometries = {feature["properties"]["NUTS_ID"]: shape(feature["geometry"]) for feature in source["features"]}
    features = []
    for name, codes in NUTS_BY_VOIVODESHIP.items():
        geometry = unary_union([geometries[code] for code in codes]).simplify(0.01, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "district": name.title(), "constituency_code": codes[0], "electorate_type": "Poland",
            },
            "geometry": mapping(geometry),
        })
    return {
        "type": "FeatureCollection", "name": "poland_voivodeships_2021",
        "source": "Eurostat GISCO NUTS 2021; Warsaw and Mazowiecki regionalny reunited as Mazowieckie",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Poland 2025 and 2020 presidential result maps")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/poland_presidential"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    boundary_path = download(session, BOUNDARY_URL, args.raw_dir / "nuts2_2021.geojson", args.refresh)
    require_sha256(boundary_path, BOUNDARY_SHA256)
    boundaries = build_boundaries(boundary_path)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "poland_voivodeship_boundaries.geojson").write_text(
        json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    for (year, round_number), (url, expected_hash) in RESULTS.items():
        path = download(session, url, args.raw_dir / f"poland_{year}_round_{round_number}.zip", args.refresh)
        require_sha256(path, expected_hash)
        rows = parse_results(path, year, round_number)
        output = args.out_dir / f"poland_{year}_president_round_{round_number}_fpp.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Poland {year} round {round_number}: wrote {len(rows)} rows")


if __name__ == "__main__":
    main()
