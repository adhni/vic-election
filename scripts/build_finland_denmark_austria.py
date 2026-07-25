#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import mapping, shape

from build_northern_europe_elections import (
    FIELDS,
    GISCO_URL,
    build_boundaries,
    download,
    election_rows,
    require_digest,
    write_matched_boundary,
)


FINLAND_API = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin/evaa/13sw.px"
FINLAND_SOURCE_PAGE = "https://stat.fi/en/statistics/evaa"
DENMARK_URL = (
    "https://api.statbank.dk/v1/data/FVKOM/CSV"
    "?valuePresentation=CodeAndValue&timeOrder=Ascending"
    "&VALRES=*&OMR%C3%85DE=*&Tid=2022,2026"
)
DENMARK_SOURCE_PAGES = {
    2026: "https://www.dst.dk/valg/Valg2546527/valgopg/valgopgHL.htm",
    2022: "https://www.dst.dk/valg/valg1968094/valgopg/valgopgHL.htm",
}
AUSTRIA_URLS = {
    2024: (
        "https://www.bmi.gv.at/412/Nationalratswahlen/Nationalratswahl_2024/files/"
        "endgueltiges_ergebnis_beschluss_bundeswahlbehoerde_16102024.xlsx"
    ),
    2019: (
        "https://www.bmi.gv.at/412/Nationalratswahlen/Nationalratswahl_2019/files/"
        "endgultiges_gesamtergebnis_nrw19_16102019.xlsx"
    ),
}
AUSTRIA_SOURCE_PAGES = {
    2024: "https://www.bmi.gv.at/412/Nationalratswahlen/Nationalratswahl_2024/",
    2019: "https://www.bmi.gv.at/412/Nationalratswahlen/Nationalratswahl_2019/",
}

SOURCE_SHA256 = {
    "finland": "2fe455fb806995d9ab59d57f49b52d63cccf36cb7778d6c5f5b32972f69771ae",
    "denmark": "b8f955ce5ff69574cbec709bb1a6eccde38aeb8867ff59f6286eedbab1f531c9",
    "austria_2024": "e85ce931f8f6e4b2eb19d7e2ee39461662a04cfb34aee308ce861f98cfb181dc",
    "austria_2019": "a32100f943222df5de585dd301a66dc645a64044af6cd567df32eb71569f9e33",
    "gisco_2024": "19eb8988026d325f46cfa242b6d252342875b13393c461f08d70d042feb51137",
    "gisco_2019": "b8ac93cfdb3bed9824b98b68e766532d886e2faf7e0b21f1773432a02a895137",
}

EXPECTED = {
    ("finland", 2023): {"areas": 309, "mapped_formal": 3_095_604},
    ("finland", 2019): {"areas": 311, "mapped_formal": 3_081_916},
    ("denmark", 2026): {"areas": 98, "mapped_formal": 3_567_625},
    ("denmark", 2022): {"areas": 99, "mapped_formal": 3_533_951},
    ("austria", 2024): {
        "areas": 2_093,
        "mapped_formal": 4_758_596,
        "national_formal": 4_882_888,
    },
    ("austria", 2019): {
        "areas": 2_096,
        "mapped_formal": 4_062_147,
        "national_formal": 4_777_246,
    },
}

FINLAND_QUERY = {
    "query": [
        {
            "code": "timeperiod_y",
            "selection": {"filter": "item", "values": ["2019", "2023"]},
        },
        {
            "code": "sukupuoli_9_20180101",
            "selection": {"filter": "item", "values": ["SSS"]},
        },
        {
            "code": "puolue_19_20230101",
            "selection": {"filter": "all", "values": ["*"]},
        },
        {
            "code": "kunta_109_20230101",
            "selection": {"filter": "all", "values": ["*"]},
        },
        {
            "code": "contentscode",
            "selection": {"filter": "item", "values": ["evaa_aanet"]},
        },
    ],
    "response": {"format": "csv"},
}

FINLAND_PARTIES = {
    "Pirate Pty": "Pirate Party",
    "Other party": "Other",
    "Others": "Other",
}

DENMARK_PARTIES = {
    "5891": "Social Democrats",
    "5893": "Social Liberals",
    "5895": "Conservatives",
    "1675319": "New Right",
    "5897": "SF",
    "2559203": "Citizens' Party",
    "5907": "Liberal Alliance",
    "5901": "Christian Democrats",
    "1962293": "Moderates",
    "5899": "Danish People's Party",
    "1684467": "Hard Line",
    "1962272": "Independent Greens",
    "5903": "Venstre",
    "1968075": "Denmark Democrats",
    "5905": "Red-Green Alliance",
    "1487618": "Alternative",
    "UDENFOR_IALT": "Independent",
}

AUSTRIA_STATES = {
    "1": "Burgenland",
    "2": "Carinthia",
    "3": "Lower Austria",
    "4": "Upper Austria",
    "5": "Salzburg",
    "6": "Styria",
    "7": "Tyrol",
    "8": "Vorarlberg",
    "9": "Vienna",
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def download_post_csv(
    session: requests.Session,
    url: str,
    path: Path,
    payload: dict[str, object],
    refresh: bool,
) -> Path:
    if path.exists() and path.stat().st_size > 1_000 and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = session.post(url, json=payload, timeout=600)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def build_finland(path: Path, output_dir: Path) -> None:
    data = pd.read_csv(path)
    value_column = "Votes cast (number)"
    area_column = "Constituency and municipality in the election year"
    data[value_column] = pd.to_numeric(data[value_column], errors="coerce").fillna(0).astype(int)
    municipality = data[area_column].str.extract(r"^KU(?P<code>\d{3}) (?P<name>.+)$")
    data = data.join(municipality).dropna(subset=["code"])

    for year in (2023, 2019):
        year_data = data[data["Year"] == year]
        rows: list[dict[str, object]] = []
        note = (
            "Official municipality valid-vote totals. Seats are allocated through "
            "multi-member constituencies; compatible municipality turnout and invalid-ballot "
            "metadata are unavailable."
        )
        for (code, district), group in year_data.groupby(["code", "name"], sort=True):
            total_rows = group[group["Party"] == "Number of votes cast per party, total"]
            if total_rows.empty or int(total_rows.iloc[0][value_column]) == 0:
                continue
            formal = int(total_rows.iloc[0][value_column])
            votes: Counter[str] = Counter()
            for _, item in group.iterrows():
                party = str(item["Party"])
                count = int(item[value_column])
                if party == "Number of votes cast per party, total" or not count:
                    continue
                votes[FINLAND_PARTIES.get(party, party)] += count
            rows.extend(
                election_rows(
                    district,
                    f"FI_{code}",
                    dict(votes),
                    0,
                    formal,
                    0,
                    FINLAND_SOURCE_PAGE,
                    "Finland",
                    note,
                )
            )

        expected = EXPECTED[("finland", year)]
        codes = {row["constituency_code"] for row in rows}
        if len(codes) != expected["areas"]:
            raise SystemExit(f"Finland {year}: expected {expected['areas']} municipalities")
        if sum(row["votes"] for row in rows) != expected["mapped_formal"]:
            raise SystemExit(f"Finland {year}: official valid-vote control total changed")
        output = output_dir / f"finland_{year}_parliament_fpp.csv"
        write_csv(output, rows)
        print(f"Finland {year}: wrote {len(rows)} rows across {len(codes)} municipalities")


def split_code_label(value: object) -> tuple[str, str]:
    code, _, label = str(value).partition(" ")
    return code, label


def build_denmark(path: Path, output_dir: Path) -> None:
    data = pd.read_csv(path, sep=";")
    data["year"] = data["TID"].map(lambda value: int(str(value).split()[0]))
    data[["result_code", "result_label"]] = data["VALRES"].apply(
        lambda value: pd.Series(split_code_label(value))
    )
    data[["area_code", "area_name"]] = data["OMRÅDE"].apply(
        lambda value: pd.Series(split_code_label(value))
    )

    for year in (2026, 2022):
        rows: list[dict[str, object]] = []
        note = (
            "Official municipality party totals. Folketing seats are allocated through "
            "larger constituencies and national adjustment, not by municipality."
        )
        for (code, district), group in data[data["year"] == year].groupby(
            ["area_code", "area_name"], sort=True
        ):
            values = {
                str(row.result_code): int(row.INDHOLD)
                for row in group.itertuples()
            }
            if values["GYLD_IALT"] == 0:
                continue
            votes = {
                party: values.get(result_code, 0)
                for result_code, party in DENMARK_PARTIES.items()
                if values.get(result_code, 0)
            }
            rows.extend(
                election_rows(
                    district,
                    f"DK_{code}",
                    votes,
                    values["VAELG"],
                    values["GYLD_IALT"],
                    values["UGYLD_IALT"],
                    DENMARK_SOURCE_PAGES[year],
                    "Denmark",
                    note,
                )
            )

        expected = EXPECTED[("denmark", year)]
        codes = {row["constituency_code"] for row in rows}
        if len(codes) != expected["areas"]:
            raise SystemExit(f"Denmark {year}: expected {expected['areas']} municipalities")
        if sum(row["votes"] for row in rows) != expected["mapped_formal"]:
            raise SystemExit(f"Denmark {year}: official valid-vote control total changed")
        output = output_dir / f"denmark_{year}_folketing_fpp.csv"
        write_csv(output, rows)
        print(f"Denmark {year}: wrote {len(rows)} rows across {len(codes)} municipalities")


def integer(value: object) -> int:
    if pd.isna(value):
        return 0
    return int(value)


def repair_boundaries(boundary: dict[str, object]) -> None:
    for feature in boundary["features"]:
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                "Could not repair boundary "
                f"{feature['properties']['constituency_code']}"
            )
        feature["geometry"] = mapping(geometry)


def build_austria(
    path: Path,
    year: int,
    boundary_codes: set[str],
    output_dir: Path,
) -> None:
    data = pd.read_excel(path, header=None)
    data_start = 2 if year == 2019 else 1
    party_columns = [
        column
        for column in range(6, len(data.columns), 2)
        if not pd.isna(data.iloc[0, column])
    ]
    party_names = {
        column: str(data.iloc[0, column]).strip()
        for column in party_columns
    }
    by_source_code = {
        str(row.iloc[0]): row
        for _, row in data.iloc[data_start:].iterrows()
        if isinstance(row.iloc[0], str)
    }
    district_by_boundary_code = {}
    for boundary_code in boundary_codes:
        municipal_code = boundary_code.split("_", 1)[1]
        source_code = "G90000" if municipal_code == "90001" else f"G{municipal_code}"
        district_by_boundary_code[boundary_code] = str(
            by_source_code[source_code].iloc[1]
        ).strip()
    name_counts = Counter(district_by_boundary_code.values())

    rows: list[dict[str, object]] = []
    note = (
        "Official municipality totals excluding separately reported postal ballots. "
        "National vote and seat totals include those postal ballots; they are not assigned "
        "to false municipality polygons."
    )
    for boundary_code in sorted(boundary_codes):
        municipal_code = boundary_code.split("_", 1)[1]
        source_code = "G90000" if municipal_code == "90001" else f"G{municipal_code}"
        if source_code not in by_source_code:
            raise SystemExit(f"Austria {year}: missing source row {source_code}")
        source = by_source_code[source_code]
        district = district_by_boundary_code[boundary_code]
        if name_counts[district] > 1:
            district += f" ({AUSTRIA_STATES[municipal_code[0]]})"
        votes = {
            party_names[column]: integer(source.iloc[column])
            for column in party_columns
            if integer(source.iloc[column])
        }
        rows.extend(
            election_rows(
                district,
                boundary_code,
                votes,
                0,
                integer(source.iloc[5]),
                integer(source.iloc[4]),
                AUSTRIA_SOURCE_PAGES[year],
                "Austria",
                note,
            )
        )

    expected = EXPECTED[("austria", year)]
    if len(boundary_codes) != expected["areas"]:
        raise SystemExit(f"Austria {year}: expected {expected['areas']} municipalities")
    if sum(row["votes"] for row in rows) != expected["mapped_formal"]:
        raise SystemExit(f"Austria {year}: mapped valid-vote control total changed")
    national = by_source_code["G00000"]
    if integer(national.iloc[5]) != expected["national_formal"]:
        raise SystemExit(f"Austria {year}: national valid-vote control total changed")
    if sum(integer(national.iloc[column]) for column in party_columns) != integer(
        national.iloc[5]
    ):
        raise SystemExit(f"Austria {year}: national party totals do not reconcile")
    output = output_dir / f"austria_{year}_national_council_fpp.csv"
    write_csv(output, rows)
    print(f"Austria {year}: wrote {len(rows)} rows across {len(boundary_codes)} municipalities")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Finland, Denmark, and Austria parliamentary election datasets"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/europe_batch_raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"

    finland_path = download_post_csv(
        session,
        FINLAND_API,
        args.raw_dir / "finland_votes.csv",
        FINLAND_QUERY,
        args.refresh,
    )
    denmark_path = download(
        session,
        DENMARK_URL,
        args.raw_dir / "denmark_2022_2026.csv",
        args.refresh,
    )
    austria_paths = {
        year: download(
            session,
            url,
            args.raw_dir / f"austria_{year}.xlsx",
            args.refresh,
        )
        for year, url in AUSTRIA_URLS.items()
    }
    for key, path in {
        "finland": finland_path,
        "denmark": denmark_path,
        **{f"austria_{year}": path for year, path in austria_paths.items()},
    }.items():
        require_digest(path, SOURCE_SHA256[key])

    boundary_sets: dict[int, dict[str, dict[str, object]]] = {}
    for year, countries in {2024: {"FI", "DK", "AT"}, 2019: {"FI", "AT"}}.items():
        archive = download(
            session,
            GISCO_URL.format(year=year),
            args.raw_dir / f"gisco_lau_{year}.zip",
            args.refresh,
        )
        require_digest(archive, SOURCE_SHA256[f"gisco_{year}"])
        boundary_sets[year] = build_boundaries(archive, year, countries)
        for boundary in boundary_sets[year].values():
            repair_boundaries(boundary)

    build_finland(finland_path, args.output_dir)
    build_denmark(denmark_path, args.output_dir)
    for year in (2024, 2019):
        boundary_codes = {
            feature["properties"]["constituency_code"]
            for feature in boundary_sets[year]["AT"]["features"]
        }
        build_austria(austria_paths[year], year, boundary_codes, args.output_dir)

    boundary_specs = (
        ("finland", 2023, 2024, "FI", "parliament"),
        ("finland", 2019, 2019, "FI", "parliament"),
        ("denmark", 2026, 2024, "DK", "folketing"),
        ("denmark", 2022, 2024, "DK", "folketing"),
        ("austria", 2024, 2024, "AT", "national_council"),
        ("austria", 2019, 2019, "AT", "national_council"),
    )
    for country, election_year, boundary_year, code, chamber in boundary_specs:
        write_matched_boundary(
            args.output_dir / f"{country}_{election_year}_{chamber}_boundaries.geojson",
            boundary_sets[boundary_year][code],
            args.output_dir / f"{country}_{election_year}_{chamber}_fpp.csv",
        )


if __name__ == "__main__":
    main()
