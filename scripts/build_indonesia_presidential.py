#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import mapping, shape


RESULTS_URL = (
    "https://commons.wikimedia.org/w/api.php?action=jsondata&format=json&"
    "title=2024_Indonesian_presidential_election_results_by_city_and_regency.tab"
)
PROVINCE_BOUNDARY_URL = "https://satupetadata.kpu.go.id/assets/gis/ina.json"
KABUPATEN_BOUNDARY_URL = (
    "https://satupetadata.kpu.go.id/assets/gis/json/geojsonHPProv.php?x=pres&idwil={code}"
)
DECISION_URL = "https://jdih.kpu.go.id/data/data_kepkpu/2024kpt360_L1.pdf"
MAPSHAPER_VERSION = "0.7.45"

CANDIDATES = (
    ("Anies Baswedan–Muhaimin Iskandar", "Anies–Muhaimin"),
    ("Prabowo Subianto–Gibran Rakabuming Raka", "Prabowo–Gibran"),
    ("Ganjar Pranowo–Mahfud MD", "Ganjar–Mahfud"),
)

# Certified valid-vote totals from KPU Decision 360/2024, Appendix I.
PROVINCE_TOTALS = (
    ("11", "Aceh", 2_369_534, 787_024, 64_677),
    ("12", "Sumatera Utara", 2_339_620, 4_660_408, 999_528),
    ("13", "Sumatera Barat", 1_744_042, 1_217_314, 124_044),
    ("14", "Riau", 1_400_093, 1_931_113, 357_298),
    ("15", "Jambi", 532_605, 1_438_952, 234_251),
    ("16", "Sumatera Selatan", 997_299, 3_649_651, 606_681),
    ("17", "Bengkulu", 229_681, 893_499, 145_570),
    ("18", "Lampung", 791_892, 3_554_310, 764_486),
    ("19", "Kepulauan Bangka Belitung", 204_348, 529_883, 151_109),
    ("21", "Kepulauan Riau", 370_671, 641_388, 140_733),
    ("31", "DKI Jakarta", 2_653_762, 2_692_011, 1_115_138),
    ("32", "Jawa Barat", 9_099_674, 16_805_854, 2_820_995),
    ("33", "Jawa Tengah", 2_866_373, 12_096_454, 7_827_335),
    ("34", "DI Yogyakarta", 496_280, 1_269_265, 741_220),
    ("35", "Jawa Timur", 4_492_652, 16_716_603, 4_434_805),
    ("36", "Banten", 2_451_383, 4_035_052, 720_275),
    ("51", "Bali", 99_233, 1_454_640, 1_127_134),
    ("52", "Nusa Tenggara Barat", 850_539, 2_154_843, 241_106),
    ("53", "Nusa Tenggara Timur", 153_446, 1_798_753, 958_505),
    ("61", "Kalimantan Barat", 718_641, 1_964_183, 534_450),
    ("62", "Kalimantan Tengah", 256_811, 1_097_070, 158_788),
    ("63", "Kalimantan Selatan", 849_948, 1_407_684, 159_950),
    ("64", "Kalimantan Timur", 448_046, 1_542_346, 240_143),
    ("65", "Kalimantan Utara", 72_065, 284_209, 51_451),
    ("71", "Sulawesi Utara", 119_103, 1_229_069, 283_796),
    ("72", "Sulawesi Tengah", 386_743, 1_251_313, 160_594),
    ("73", "Sulawesi Selatan", 2_003_081, 3_010_726, 265_948),
    ("74", "Sulawesi Tenggara", 361_585, 1_113_344, 90_727),
    ("75", "Gorontalo", 227_354, 504_662, 41_508),
    ("76", "Sulawesi Barat", 223_153, 533_757, 62_514),
    ("81", "Maluku", 228_557, 665_371, 186_395),
    ("82", "Maluku Utara", 200_459, 454_943, 91_293),
    ("91", "Papua", 67_592, 378_908, 178_534),
    ("92", "Papua Barat", 37_459, 172_965, 120_565),
    ("93", "Papua Selatan", 41_906, 162_852, 110_003),
    ("94", "Papua Tengah", 128_577, 638_616, 335_089),
    ("95", "Papua Pegunungan", 284_184, 838_382, 175_956),
    ("96", "Papua Barat Daya", 48_405, 209_403, 99_899),
)

PAPUA_TENGAH_NOTE = (
    "The published structured kabupaten/kota figures for Papua Tengah sum to 1,035,277 "
    "valid votes—67,005 fewer than the certified KPU provincial total of 1,102,282. "
    "The local figures are shown as published and have not been adjusted."
)

CSV_FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)


def download(url: str, path: Path) -> Path:
    if path.exists() and path.stat().st_size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "vic-election-explorer/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        path.write_bytes(response.read())
    return path


def display_name(raw: str) -> str:
    raw = raw.strip().replace("P A P U A", "PAPUA")
    if raw == "DAERAH ISTIMEWA YOGYAKARTA":
        return "DI Yogyakarta"
    if raw == "ADM. KEP. SERIBU":
        return "Kepulauan Seribu"
    if raw.startswith("KOTA ADM. "):
        raw = "KOTA " + raw.removeprefix("KOTA ADM. ")
    if raw.startswith("KAB "):
        raw = raw.removeprefix("KAB ")
    return raw.title().replace("Dki ", "DKI ").replace("Di ", "DI ")


def load_results(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))["jsondata"]
    fields = [field["name"] for field in payload["schema"]["fields"]]
    rows = [dict(zip(fields, values)) for values in payload["data"]]
    if len(rows) != 514:
        raise SystemExit(f"Expected 514 kabupaten/kota rows, found {len(rows)}")
    if len({str(row['kode']) for row in rows}) != 514:
        raise SystemExit("Kabupaten/kota codes are not unique")
    return rows


def csv_rows_for_area(
    district: str,
    area: str,
    code: str,
    votes: tuple[int, int, int],
    source_url: str,
    note: str = "",
) -> list[dict[str, object]]:
    formal = sum(votes)
    order = sorted(range(3), key=lambda index: (-votes[index], CANDIDATES[index][0]))
    winner = order[0]
    majority = votes[order[0]] - votes[order[1]]
    common = {
        "district": district,
        "district_url": source_url,
        "distribution_url": source_url,
        "elected_member": CANDIDATES[winner][0],
        "elected_party": CANDIDATES[winner][1],
        "enrolment": 0,
        "formal_votes": formal,
        "informal_votes": 0,
        "total_votes": formal,
        "turnout_pct": 0,
        "majority": majority,
        "round_number": 0,
        "row_type": "first",
        "excluded_candidate": "",
        "excluded_party": "",
        "electorate_type": area,
        "constituency_code": code,
        "contest_status": "official",
        "result_note": note,
    }
    return [
        {
            **common,
            "candidate": candidate,
            "candidate_party": ticket,
            "votes": votes[index],
        }
        for index, (candidate, ticket) in enumerate(CANDIDATES)
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def province_rows() -> list[dict[str, object]]:
    output = []
    for code, name, *votes in PROVINCE_TOTALS:
        note = PAPUA_TENGAH_NOTE if code == "94" else ""
        output.extend(csv_rows_for_area(name, "Indonesia", code, tuple(votes), DECISION_URL, note))
    return output


def kabupaten_rows(source_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    provinces = {code: name for code, name, *_ in PROVINCE_TOTALS}
    output = []
    for row in source_rows:
        code = str(row["kode"])
        province_code = code[:2]
        if province_code not in provinces:
            raise SystemExit(f"{code}: unknown province code")
        votes = tuple(int(row[key]) for key in ("paslon1", "paslon2", "paslon3"))
        if sum(votes) != int(row["total"]):
            raise SystemExit(f"{code}: candidate votes do not equal total")
        note = PAPUA_TENGAH_NOTE if province_code == "94" else ""
        output.extend(
            csv_rows_for_area(
                display_name(str(row["name"])),
                provinces[province_code],
                code,
                votes,
                str(row["source"]),
                note,
            )
        )
    return output


def compact_feature(feature: dict[str, object], district: str, code: str, area: str) -> dict[str, object]:
    geometry = shape(feature["geometry"])
    if geometry.is_empty or not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or not geometry.is_valid:
        raise SystemExit(f"{district}: invalid source geometry")
    return {
        "type": "Feature",
        "properties": {"district": district, "constituency_code": code, "electorate_type": area},
        "geometry": mapping(geometry),
    }


def build_province_boundaries(source_path: Path, output_path: Path) -> None:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    names = {code: name for code, name, *_ in PROVINCE_TOTALS}
    features = []
    for feature in source.get("features", []):
        code = str(feature["properties"].get("KD_PROV", ""))
        if code in names:
            features.append(compact_feature(feature, names[code], code, "Province"))
    if len(features) != 38:
        raise SystemExit(f"Expected 38 province boundaries, found {len(features)}")
    output_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def build_kabupaten_boundaries(
    source_rows: list[dict[str, object]], source_dir: Path, output_path: Path
) -> None:
    district_by_code = {str(row["kode"]): display_name(str(row["name"])) for row in source_rows}
    province_by_code = {code: name for code, name, *_ in PROVINCE_TOTALS}
    features = []
    seen = set()
    for province_code, province_name in province_by_code.items():
        source_path = download(
            KABUPATEN_BOUNDARY_URL.format(code=province_code),
            source_dir / f"kabupaten_{province_code}.geojson",
        )
        source = json.loads(source_path.read_text(encoding="utf-8"))
        for feature in source.get("features", []):
            code = str(feature["properties"].get("KODE", ""))
            # KPU includes one separately drawn inter-regency overlap/disputed area in
            # North Sulawesi (7105/7110). It is not an electoral reporting unit.
            if "/" in code:
                continue
            if code not in district_by_code:
                raise SystemExit(f"Boundary code {code!r} is missing from result rows")
            if code in seen:
                raise SystemExit(f"Duplicate boundary code {code}")
            seen.add(code)
            features.append(compact_feature(feature, district_by_code[code], code, province_name))
    missing = set(district_by_code) - seen
    if missing or len(features) != 514:
        raise SystemExit(f"Boundary/result mismatch; missing {sorted(missing)}; features {len(features)}")

    with tempfile.TemporaryDirectory(prefix="indonesia-boundaries-") as temp_dir:
        raw_path = Path(temp_dir) / "raw.geojson"
        raw_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "npx", "--yes", f"mapshaper@{MAPSHAPER_VERSION}", str(raw_path),
                "-simplify", "5%", "keep-shapes",
                "-clean",
                "-o", "format=geojson", "precision=0.0001", str(output_path),
            ],
            check=True,
        )
    compact = json.loads(output_path.read_text(encoding="utf-8"))
    for feature in compact.get("features", []):
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
            if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
                raise SystemExit(f"{feature['properties']['district']}: simplification produced invalid geometry")
            feature["geometry"] = mapping(geometry)
    output_path.write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def validate_aggregates(source_rows: list[dict[str, object]]) -> None:
    certified = {code: tuple(votes) for code, _, *votes in PROVINCE_TOTALS}
    aggregates: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in source_rows:
        for index, key in enumerate(("paslon1", "paslon2", "paslon3")):
            aggregates[str(row["kode"])[:2]][index] += int(row[key])
    mismatches = {}
    for code, expected in certified.items():
        actual = tuple(aggregates[code])
        if actual != expected:
            mismatches[code] = tuple(actual[index] - expected[index] for index in range(3))
    expected_mismatch = {"94": (-7_524, -46_859, -12_622)}
    if mismatches != expected_mismatch:
        raise SystemExit(f"Unexpected province aggregate mismatches: {mismatches}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Indonesia 2024 presidential result and boundary files")
    parser.add_argument("--source-dir", type=Path, default=Path("tmp/indonesia_2024"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results_path = download(RESULTS_URL, args.source_dir / "kabupaten_results.json")
    province_boundary_path = download(PROVINCE_BOUNDARY_URL, args.source_dir / "province_boundaries.geojson")
    source_rows = load_results(results_path)
    validate_aggregates(source_rows)

    province_csv = args.output_dir / "indonesia_2024_president_province_fpp.csv"
    kabupaten_csv = args.output_dir / "indonesia_2024_president_kabupaten_kota_fpp.csv"
    province_geojson = args.output_dir / "indonesia_2024_province_boundaries.geojson"
    kabupaten_geojson = args.output_dir / "indonesia_2024_kabupaten_kota_boundaries.geojson"
    write_csv(province_csv, province_rows())
    write_csv(kabupaten_csv, kabupaten_rows(source_rows))
    build_province_boundaries(province_boundary_path, province_geojson)
    build_kabupaten_boundaries(source_rows, args.source_dir, kabupaten_geojson)

    winners = Counter()
    for row in source_rows:
        votes = [int(row[key]) for key in ("paslon1", "paslon2", "paslon3")]
        winners[CANDIDATES[votes.index(max(votes))][1]] += 1
    print(
        "Built Indonesia Presidential 2024: 38 provinces, 514 kabupaten/kota; "
        + ", ".join(f"{ticket} {winners[ticket]}" for _, ticket in CANDIDATES)
    )


if __name__ == "__main__":
    main()
