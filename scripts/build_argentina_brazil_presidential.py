#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

import requests
import geopandas as gpd
from shapely import force_2d
from shapely.geometry import box, mapping, shape


ARGENTINA_RESULTS = {
    (2023, 1): (
        "https://www.argentina.gob.ar/sites/default/files/2023_generales_1.zip",
        "2562b18c741ba5740d264e5328f206cb25f709ed0a4f8cf962f301e423e79c6b",
    ),
    (2023, 2): (
        "https://www.argentina.gob.ar/sites/default/files/2023_segundavuelta.zip",
        "6d63298575984a9639cc51ed3fb60def789ceab0a4ae9b1b1003571f2b4fa530",
    ),
    (2019, 1): (
        "https://www.argentina.gob.ar/sites/default/files/2019-provisorios_generales.zip",
        "eb62f4e999a75754db1d3f446a5977679a0d34faba81de6afc13cb20943e4bf7",
    ),
}
ARGENTINA_SOURCE_PAGES = {
    2023: "https://www.argentina.gob.ar/dine/resultados-electorales/elecciones-2023",
    2019: "https://datos.gob.ar/dataset/interior-resultados-provisionales-elecciones-2019",
}
ARGENTINA_BOUNDARY = (
    "https://www.ign.gob.ar/descargas/geodatos/SHAPES/ign_provincia.zip",
    "b9fcf6f90f28f1bdfcc713a47ad4ed63e2db0b000c4642611597d4ea8b897c55",
)
ARGENTINA_BOUNDARY_PAGE = "https://datos.gob.ar/dataset/ign-unidades-territoriales"

BRAZIL_RESULTS = {
    2022: (
        "https://en.wikipedia.org/w/index.php?title=2022_Brazilian_general_election&oldid=1365659673",
        "60fd0fcac18874b97b6a1e2de7d4d3faf6fcdff0e87e5d19efc01a035de235d5",
    ),
    2018: (
        "https://en.wikipedia.org/w/index.php?title=2018_Brazilian_general_election&oldid=1361748195",
        "35b337665b114b1e52fee9e3aa584b401e25ecdc0b71770cfb32c4affb692278",
    ),
}
BRAZIL_OFFICIAL_PAGE = {
    2022: "https://dadosabertos.tse.jus.br/dataset/resultados-2022",
    2018: "https://dadosabertos.tse.jus.br/dataset/resultados-2018",
}
BRAZIL_BOUNDARY = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF",
    "07c671aa87aa1ab296c446de6294df9827112782537b996c0a160284907e7c0f",
)
BRAZIL_BOUNDARY_PAGE = "https://servicodados.ibge.gov.br/api/docs/malhas?versao=3"

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

ARGENTINA_CANDIDATES = {
    (2023, "UNION POR LA PATRIA"): "Sergio Massa",
    (2023, "LA LIBERTAD AVANZA"): "Javier Milei",
    (2023, "JUNTOS POR EL CAMBIO"): "Patricia Bullrich",
    (2023, "HACEMOS POR NUESTRO PAIS"): "Juan Schiaretti",
    (2023, "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD"): "Myriam Bregman",
    (2019, "FRENTE DE TODOS"): "Alberto Fernández",
    (2019, "JUNTOS POR EL CAMBIO"): "Mauricio Macri",
    (2019, "CONSENSO FEDERAL"): "Roberto Lavagna",
    (2019, "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD"): "Nicolás del Caño",
    (2019, "FRENTE NOS"): "Juan José Gómez Centurión",
    (2019, "UNITE POR LA LIBERTAD Y LA DIGNIDAD"): "José Luis Espert",
}

# Provisional national positive-vote totals from the same DINE archives.
ARGENTINA_EXPECTED = {
    (2023, 1): {
        "Sergio Massa": 9_645_983,
        "Javier Milei": 7_884_336,
        "Patricia Bullrich": 6_267_152,
        "Juan Schiaretti": 1_784_315,
        "Myriam Bregman": 709_932,
    },
    (2023, 2): {"Javier Milei": 14_476_462, "Sergio Massa": 11_516_142},
    (2019, 1): {
        "Alberto Fernández": 12_473_709,
        "Mauricio Macri": 10_470_607,
        "Roberto Lavagna": 1_599_707,
        "Nicolás del Caño": 561_214,
        "Juan José Gómez Centurión": 443_507,
        "José Luis Espert": 382_820,
    },
}

BRAZIL_STATE_CODES = {
    "11": ("RO", "Rondônia"), "12": ("AC", "Acre"), "13": ("AM", "Amazonas"),
    "14": ("RR", "Roraima"), "15": ("PA", "Pará"), "16": ("AP", "Amapá"),
    "17": ("TO", "Tocantins"), "21": ("MA", "Maranhão"), "22": ("PI", "Piauí"),
    "23": ("CE", "Ceará"), "24": ("RN", "Rio Grande do Norte"),
    "25": ("PB", "Paraíba"), "26": ("PE", "Pernambuco"), "27": ("AL", "Alagoas"),
    "28": ("SE", "Sergipe"), "29": ("BA", "Bahia"), "31": ("MG", "Minas Gerais"),
    "32": ("ES", "Espírito Santo"), "33": ("RJ", "Rio de Janeiro"),
    "35": ("SP", "São Paulo"), "41": ("PR", "Paraná"),
    "42": ("SC", "Santa Catarina"), "43": ("RS", "Rio Grande do Sul"),
    "50": ("MS", "Mato Grosso do Sul"), "51": ("MT", "Mato Grosso"),
    "52": ("GO", "Goiás"), "53": ("DF", "Federal District"),
}

BRAZIL_NATIONAL = {
    (2022, 1): {
        "Luiz Inácio Lula da Silva": 57_259_504,
        "Jair Bolsonaro": 51_072_345,
        "Simone Tebet": 4_915_423,
        "Ciro Gomes": 3_599_287,
        "Other candidates": 1_383_160,
    },
    (2022, 2): {
        "Luiz Inácio Lula da Silva": 60_345_999,
        "Jair Bolsonaro": 58_206_354,
    },
    (2018, 1): {
        "Jair Bolsonaro": 49_277_010,
        "Fernando Haddad": 31_342_051,
        "Ciro Gomes": 13_344_371,
        "Geraldo Alckmin": 5_096_350,
        "Other candidates": 7_990_966,
    },
    (2018, 2): {
        "Jair Bolsonaro": 57_797_847,
        "Fernando Haddad": 47_040_906,
    },
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
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: source checksum changed to {actual}; expected {expected}")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def number(value: str) -> int:
    return int(re.sub(r"[^0-9]", "", value))


def output_row(
    *, district: str, source: str, boundary_source: str, votes: Counter[str],
    enrolment: int, informal: int, electorate_type: str, code: str, note: str,
) -> list[dict[str, object]]:
    ordered = votes.most_common()
    formal = sum(votes.values())
    total = formal + informal
    winner, winner_votes = ordered[0]
    runner_up = ordered[1][1] if len(ordered) > 1 else 0
    base = {
        "district": district,
        "district_url": source,
        "distribution_url": boundary_source,
        "elected_member": winner,
        "elected_party": winner,
        "enrolment": enrolment,
        "formal_votes": formal,
        "informal_votes": informal,
        "total_votes": total,
        "turnout_pct": round(total * 100 / enrolment, 2) if enrolment else "",
        "majority": winner_votes - runner_up,
        "round_number": 0,
        "row_type": "first",
        "excluded_candidate": "",
        "excluded_party": "",
        "electorate_type": electorate_type,
        "constituency_code": code,
        "contest_status": "official",
        "result_note": note,
    }
    return [
        {**base, "candidate": candidate, "candidate_party": candidate, "votes": candidate_votes}
        for candidate, candidate_votes in ordered
    ]


def argentina_results(path: Path, year: int) -> tuple[
    dict[str, Counter[str]], Counter[str], Counter[str], dict[str, int]
]:
    province_votes: dict[str, Counter[str]] = defaultdict(Counter)
    national: Counter[str] = Counter()
    non_positive: Counter[str] = Counter()
    enrolment: dict[str, int] = defaultdict(int)
    seen_tables: set[tuple[str, str, str, str, str, str]] = set()
    with zipfile.ZipFile(path) as archive:
        member = next(
            name for name in archive.namelist()
            if "resultado" in name.lower() and name.lower().endswith(".csv")
        )
        with archive.open(member) as raw:
            rows = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            for row in rows:
                if "PRESIDENTE" not in (row.get("cargo_nombre") or ""):
                    continue
                province = " ".join(row["distrito_nombre"].split())
                amount = int(row["votos_cantidad"])
                vote_type = row["votos_tipo"]
                table_key = (
                    province,
                    row["seccion_id"],
                    row["circuito_id"],
                    row["mesa_id"],
                    row["mesa_tipo"],
                    row["padron_tipo"],
                )
                if table_key not in seen_tables:
                    enrolment[province] += int(row["mesa_electores"])
                    seen_tables.add(table_key)
                if vote_type == "POSITIVO":
                    alliance = row["agrupacion_nombre"]
                    try:
                        candidate = ARGENTINA_CANDIDATES[(year, alliance)]
                    except KeyError as exc:
                        raise SystemExit(f"Unmapped Argentina presidential alliance: {alliance!r}") from exc
                    province_votes[province][candidate] += amount
                    national[candidate] += amount
                else:
                    non_positive[province] += amount
    return province_votes, national, non_positive, enrolment


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def find_table(tables: list[list[list[str]]], required: tuple[str, ...]) -> list[list[str]]:
    for table in tables:
        text = " ".join(cell for row in table[:6] for cell in row)
        if all(item in text for item in required):
            return table
    raise SystemExit(f"Could not find Brazil state result table containing {required}")


def brazil_results(path: Path, year: int) -> dict[int, dict[str, Counter[str]]]:
    parser = TableParser()
    parser.feed(path.read_text(encoding="utf-8"))
    output: dict[int, dict[str, Counter[str]]] = {1: {}, 2: {}}
    if year == 2022:
        table = find_table(
            parser.tables,
            ("Federative unit", "Second round", "Simone Tebet", "Ciro Gomes"),
        )
        for cells in table:
            if len(cells) != 15 or not re.search(r"\d", cells[1]):
                continue
            state = cells[0].replace(" (state)", "")
            if state == "Abroad":
                continue
            output[2][state] = Counter({
                "Luiz Inácio Lula da Silva": number(cells[1]),
                "Jair Bolsonaro": number(cells[3]),
            })
            output[1][state] = Counter({
                "Luiz Inácio Lula da Silva": number(cells[5]),
                "Jair Bolsonaro": number(cells[7]),
                "Simone Tebet": number(cells[9]),
                "Ciro Gomes": number(cells[11]),
                "Other candidates": number(cells[13]),
            })
    else:
        first = find_table(
            parser.tables,
            ("Federative unit", "Bolsonaro", "Haddad", "Gomes", "Alckmin", "Others"),
        )
        second = next(
            table for table in parser.tables
            if "Federative unit" in " ".join(cell for row in table[:6] for cell in row)
            and "Bolsonaro" in " ".join(cell for row in table[:6] for cell in row)
            and "Haddad" in " ".join(cell for row in table[:6] for cell in row)
            and "Gomes" not in " ".join(cell for row in table[:6] for cell in row)
        )
        for cells in first:
            if len(cells) != 11 or not re.search(r"\d", cells[1]):
                continue
            state = cells[0].replace(" (state)", "")
            if state == "Diaspora":
                continue
            # The pinned secondary table drops the leading 1 from Haddad's
            # Federal District total; its printed percentage confirms 190,508.
            haddad = number(cells[3])
            if state == "Federal District" and haddad == 90_508:
                haddad = 190_508
            output[1][state] = Counter({
                "Jair Bolsonaro": number(cells[1]),
                "Fernando Haddad": haddad,
                "Ciro Gomes": number(cells[5]),
                "Geraldo Alckmin": number(cells[7]),
                "Other candidates": number(cells[9]),
            })
        for cells in second:
            if len(cells) != 5 or not re.search(r"\d", cells[1]):
                continue
            state = cells[0].replace(" (state)", "")
            if state == "Diaspora":
                continue
            output[2][state] = Counter({
                "Jair Bolsonaro": number(cells[1]),
                "Fernando Haddad": number(cells[3]),
            })
    for round_number, states in output.items():
        if len(states) != 27:
            raise SystemExit(f"Brazil {year} round {round_number}: expected 27 states, got {len(states)}")
    return output


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_argentina(
    source_paths: dict[tuple[int, int], Path], boundary_path: Path, data_dir: Path,
) -> None:
    provinces = gpd.read_file(
        f"zip://{boundary_path.resolve()}!Provincia/ign_provincia.shp"
    ).to_crs("EPSG:4326")
    if len(provinces) != 24:
        raise SystemExit(f"Argentina boundary archive: expected 24 provinces, got {len(provinces)}")
    # Retain the South American province geometry (including the Falkland/
    # Malvinas polygons) while excluding Antarctica and the much farther-east
    # South Atlantic islands that would otherwise dominate the map extent.
    south_america_frame = box(-76, -60, -52, -20)
    output_features = []
    features_by_name: dict[str, dict[str, object]] = {}
    for _, row in provinces.iterrows():
        geometry = force_2d(row.geometry).intersection(south_america_frame).simplify(
            0.02, preserve_topology=True
        ).buffer(0)
        if geometry.is_empty:
            raise SystemExit(f"Argentina boundary became empty for {row['NAM']}")
        feature = {
            "type": "Feature",
            "properties": {
                "id": str(row["IN1"]).zfill(2),
                "nombre": row["NAM"],
                "district": row["NAM"],
                "constituency_code": f"AR-PROV-{str(row['IN1']).zfill(2)}",
            },
            "geometry": mapping(geometry),
        }
        output_features.append(feature)
        features_by_name[normalize(row["NAM"])] = feature
    features_by_name["tierra del fuego"] = features_by_name[
        "tierra del fuego antartida e islas del atlantico sur"
    ]
    output_features.sort(key=lambda feature: feature["properties"]["constituency_code"])
    (data_dir / "argentina_province_boundaries.geojson").write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": output_features},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    for (year, round_number), source_path in source_paths.items():
        province_votes, national, informal, enrolment = argentina_results(source_path, year)
        if dict(national) != ARGENTINA_EXPECTED[(year, round_number)]:
            raise SystemExit(
                f"Argentina {year} round {round_number}: national totals changed: {dict(national)}"
            )
        if len(province_votes) != 24:
            raise SystemExit(
                f"Argentina {year} round {round_number}: expected 24 provinces, got {len(province_votes)}"
            )
        rows: list[dict[str, object]] = []
        for province, votes in sorted(province_votes.items()):
            feature = features_by_name.get(normalize(province))
            if feature is None:
                raise SystemExit(f"Argentina province boundary missing for {province}")
            code = f"AR-PROV-{feature['properties']['id']}"
            rows.extend(output_row(
                district=feature["properties"]["district"],
                source=ARGENTINA_SOURCE_PAGES[year],
                boundary_source=ARGENTINA_BOUNDARY_PAGE,
                votes=votes,
                enrolment=enrolment[province],
                informal=informal[province],
                electorate_type="Province",
                code=code,
                note=(
                    "Provisional DINE presidential result aggregated from polling-table rows. "
                    "Province boundaries come from IGN; Antarctic and remote South Atlantic "
                    "geometry is omitted from this interactive map for legibility."
                ),
            ))
        write_csv(
            data_dir / f"argentina_{year}_president_round_{round_number}_province_fpp.csv",
            rows,
        )


def build_brazil(
    source_paths: dict[int, Path], boundary_path: Path, data_dir: Path,
) -> None:
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    state_by_name: dict[str, tuple[str, str]] = {}
    for feature in boundary["features"]:
        code = feature["properties"]["codarea"]
        abbreviation, state = BRAZIL_STATE_CODES[code]
        feature["geometry"] = mapping(shape(feature["geometry"]).buffer(0))
        feature["properties"].update({
            "district": state,
            "state_abbreviation": abbreviation,
            "constituency_code": f"BR-UF-{abbreviation}",
        })
        state_by_name[normalize(state)] = (abbreviation, state)
    boundary["features"].sort(key=lambda feature: feature["properties"]["constituency_code"])
    (data_dir / "brazil_state_boundaries.geojson").write_text(
        json.dumps(boundary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    for year, source_path in source_paths.items():
        rounds = brazil_results(source_path, year)
        for round_number, states in rounds.items():
            rows: list[dict[str, object]] = []
            for state, votes in sorted(states.items()):
                try:
                    abbreviation, canonical_state = state_by_name[normalize(state)]
                except KeyError as exc:
                    raise SystemExit(f"Brazil state boundary missing for {state}") from exc
                rows.extend(output_row(
                    district=canonical_state,
                    source=BRAZIL_OFFICIAL_PAGE[year],
                    boundary_source=BRAZIL_BOUNDARY_PAGE,
                    votes=votes,
                    enrolment=0,
                    informal=0,
                    electorate_type="State",
                    code=f"BR-UF-{abbreviation}",
                    note=(
                        "State candidate totals transcribed in a pinned TSE-attributed result table; "
                        "first-round minor candidates are grouped as Other candidates. National shares "
                        "use the official TSE totals. State boundaries come from IBGE."
                    ),
                ))
            write_csv(
                data_dir / f"brazil_{year}_president_round_{round_number}_state_fpp.csv",
                rows,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Argentina and Brazil presidential election maps."
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/argentina_brazil"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"

    argentina_paths: dict[tuple[int, int], Path] = {}
    for key, (url, checksum) in ARGENTINA_RESULTS.items():
        path = download(session, url, args.cache_dir / f"argentina_{key[0]}_r{key[1]}.zip", args.refresh)
        require_sha256(path, checksum)
        argentina_paths[key] = path
    ar_boundary = download(
        session, ARGENTINA_BOUNDARY[0], args.cache_dir / "argentina_provinces.zip", args.refresh
    )
    require_sha256(ar_boundary, ARGENTINA_BOUNDARY[1])

    brazil_paths: dict[int, Path] = {}
    for year, (url, checksum) in BRAZIL_RESULTS.items():
        path = download(session, url, args.cache_dir / f"brazil_{year}_state_results.html", args.refresh)
        require_sha256(path, checksum)
        brazil_paths[year] = path
    br_boundary = download(
        session, BRAZIL_BOUNDARY[0], args.cache_dir / "brazil_states.geojson", args.refresh
    )
    require_sha256(br_boundary, BRAZIL_BOUNDARY[1])

    build_argentina(argentina_paths, ar_boundary, args.data_dir)
    build_brazil(brazil_paths, br_boundary, args.data_dir)
    print("Built 7 Argentina/Brazil presidential election views.")


if __name__ == "__main__":
    main()
