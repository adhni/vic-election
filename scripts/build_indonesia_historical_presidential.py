#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from shapely.geometry import mapping, shape
from shapely.ops import unary_union


RESULTS_2019_URL = (
    "https://raw.githubusercontent.com/bipproduction/data-pemilu-2019/"
    "main/pupet/result.json"
)
KAWAL_2014_RESULTS_URL = (
    "https://raw.githubusercontent.com/kawalpemilu/kawalpemilu2014/"
    "master/extract/clean.csv"
)
KAWAL_2014_LOCATIONS_URL = (
    "https://raw.githubusercontent.com/kawalpemilu/kawalpemilu2014/"
    "master/extract/lokasi3.csv"
)
KPU_2019_SOURCE_URL = "https://opendata.kpu.go.id/ds/140"
KPU_2014_DECISION_URL = (
    "https://jdih.kpu.go.id/keputusan-kpu/detail/"
    "SmQxz_RkBop_QwpyyOJ79XJCcHIrTThRc005OXU3dWppcjBMWlE9PQ"
)
KAWAL_2014_SOURCE_URL = "https://github.com/kawalpemilu/kawalpemilu2014"

CSV_FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

CANDIDATES = {
    2019: (
        ("Joko Widodo–Ma'ruf Amin", "Jokowi–Ma'ruf"),
        ("Prabowo Subianto–Sandiaga Uno", "Prabowo–Sandiaga"),
    ),
    2014: (
        ("Prabowo Subianto–Hatta Rajasa", "Prabowo–Hatta"),
        ("Joko Widodo–Jusuf Kalla", "Jokowi–Kalla"),
    ),
}

NOTE_2014 = (
    "Kabupaten/kota totals are aggregated from KawalPemilu's archived KPU C1-scan "
    "digitisation. The archive covers about 98.2% of the certified domestic valid vote, "
    "so local totals can be below the final recapitulation. No missing votes were estimated."
)

# Official KPU domestic province totals. North Kalimantan was included in East
# Kalimantan in the 2014 recapitulation; overseas votes are outside the map.
PROVINCE_TOTALS_2014 = (
    ("Aceh", 1_089_290, 913_309),
    ("Sumatera Utara", 2_831_514, 3_494_835),
    ("Sumatera Barat", 1_797_505, 539_308),
    ("Riau", 1_349_338, 1_342_817),
    ("Jambi", 871_316, 897_787),
    ("Sumatera Selatan", 2_132_163, 2_027_049),
    ("Bengkulu", 433_173, 523_669),
    ("Lampung", 2_033_924, 2_299_889),
    ("Kepulauan Bangka Belitung", 200_706, 412_359),
    ("Kepulauan Riau", 332_908, 491_819),
    ("DKI Jakarta", 2_528_064, 2_859_894),
    ("Jawa Barat", 14_167_381, 9_530_315),
    ("Jawa Tengah", 6_485_720, 12_959_540),
    ("DI Yogyakarta", 977_342, 1_234_249),
    ("Jawa Timur", 10_277_088, 11_669_313),
    ("Banten", 3_192_671, 2_398_631),
    ("Bali", 614_241, 1_535_110),
    ("Nusa Tenggara Barat", 1_844_178, 701_238),
    ("Nusa Tenggara Timur", 769_391, 1_488_076),
    ("Kalimantan Barat", 1_032_354, 1_573_046),
    ("Kalimantan Tengah", 468_277, 696_199),
    ("Kalimantan Selatan", 941_809, 939_748),
    ("Kalimantan Timur", 687_734, 1_190_156),
    ("Sulawesi Utara", 620_095, 724_553),
    ("Sulawesi Tengah", 632_009, 767_151),
    ("Sulawesi Selatan", 1_214_857, 3_037_026),
    ("Sulawesi Tenggara", 511_134, 622_217),
    ("Gorontalo", 378_735, 221_497),
    ("Sulawesi Barat", 165_494, 456_021),
    ("Maluku", 433_981, 443_040),
    ("Maluku Utara", 306_792, 256_601),
    ("Papua", 769_132, 2_026_735),
    ("Papua Barat", 172_528, 360_379),
)

# Three arrays in the preserved 2019 scrape accidentally repeat the province
# table. These replacements are the certified province DC1 recapitulations.
REPAIRS_2019 = {
    "LAMPUNG": (
        ("PRINGSEWU", 149_481, 92_344), ("MESUJI", 85_471, 33_906),
        ("TULANG BAWANG BARAT", 105_789, 59_972), ("LAMPUNG SELATAN", 374_955, 201_440),
        ("LAMPUNG TENGAH", 490_901, 241_154), ("LAMPUNG UTARA", 153_406, 203_515),
        ("LAMPUNG BARAT", 101_247, 76_170), ("TULANG BAWANG", 152_265, 70_186),
        ("TANGGAMUS", 165_654, 174_866), ("LAMPUNG TIMUR", 417_155, 179_831),
        ("WAY KANAN", 143_456, 123_524), ("KOTA BANDAR LAMPUNG", 259_674, 296_741),
        ("KOTA METRO", 52_122, 47_184), ("PESAWARAN", 155_496, 111_879),
        ("PESISIR BARAT", 46_513, 42_977),
    ),
    "DKI JAKARTA": (
        ("KEPULAUAN SERIBU", 8_826, 8_281), ("JAKARTA PUSAT", 333_076, 315_078),
        ("JAKARTA UTARA", 572_567, 417_062), ("JAKARTA BARAT", 834_038, 615_101),
        ("JAKARTA SELATAN", 673_100, 723_008), ("JAKARTA TIMUR", 857_940, 987_607),
    ),
    "JAWA BARAT": (
        ("TASIKMALAYA", 302_132, 729_024), ("KOTA SUKABUMI", 61_835, 139_106),
        ("MAJALENGKA", 346_980, 425_877), ("KUNINGAN", 252_373, 376_259),
        ("KOTA BANJAR", 63_295, 55_732), ("SUMEDANG", 310_579, 408_929),
        ("GARUT", 412_136, 1_068_444), ("PURWAKARTA", 155_863, 406_988),
        ("PANGANDARAN", 164_073, 96_943), ("CIAMIS", 303_323, 440_240),
        ("INDRAMAYU", 707_324, 282_349), ("SUBANG", 537_114, 392_882),
        ("SUKABUMI", 400_644, 1_012_116), ("BANDUNG BARAT", 359_220, 649_988),
        ("KOTA CIREBON", 103_878, 93_036), ("KARAWANG", 584_682, 779_266),
        ("BANDUNG", 778_826, 1_246_921), ("KOTA TASIKMALAYA", 111_785, 314_247),
        ("CIREBON", 823_900, 449_455), ("KOTA CIMAHI", 120_813, 214_452),
        ("KOTA BOGOR", 228_112, 399_073), ("KOTA BANDUNG", 621_969, 867_945),
        ("CIANJUR", 461_787, 775_354), ("BOGOR", 862_122, 2_035_552),
        ("KOTA BEKASI", 617_907, 752_254), ("KOTA DEPOK", 464_472, 618_527),
        ("BEKASI", 593_424, 1_046_487),
    ),
}

# Modern districts that were not separate reporting units in the 2014 archive.
# Their geometry is dissolved into the named election-time parent.
SPLITS_AFTER_2014_HIERARCHY = {
    "BANGGAILAUT": "BANGGAIKEPULAUAN",
    "BUTONSELATAN": "BUTON",
    "BUTONTENGAH": "BUTON",
    "KOLAKATIMUR": "KOLAKA",
    "KONAWEKEPULAUAN": "KONAWE",
    "MAHAKAMULU": "KUTAIBARAT",
    "MALAKA": "BELU",
    "MAMUJUTENGAH": "MAMUJU",
    "MANOKWARISELATAN": "MANOKWARI",
    "MOROWALIUTARA": "MOROWALI",
    "MUNABARAT": "MUNA",
    "MUSIRAWASUTARA": "MUSIRAWAS",
    "PANGANDARAN": "CIAMIS",
    "PEGUNUNGANARFAK": "MANOKWARI",
    "PENUKALABABLEMATANGILIR": "MUARAENIM",
    "PESISIRBARAT": "LAMPUNGBARAT",
    "PULAUTALIABU": "KEPULAUANSULA",
}


def download(url: str, path: Path) -> Path:
    if path.exists() and path.stat().st_size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "vic-election-explorer/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        path.write_bytes(response.read())
    return path


def parse_number(value: str) -> int:
    return int(value.replace(".", "").replace(",", "").strip() or 0)


def title_name(raw: str) -> str:
    name = raw.strip().title()
    replacements = {
        "Daerah Istimewa Yogyakarta": "DI Yogyakarta",
        "Dki Jakarta": "DKI Jakarta",
        "Pahuwato": "Pohuwato",
    }
    return replacements.get(name, name)


def name_key(raw: str) -> str:
    value = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().upper()
    value = value.replace("KABUPATEN ", "").replace("KAB. ", "")
    return re.sub(r"[^A-Z0-9]", "", value)


def current_to_historical_key(current_name: str, historical_keys: set[str]) -> str:
    key = name_key(current_name)
    if key in historical_keys:
        return key
    aliases = {
        "KOTAJAKARTABARAT": "JAKARTABARAT",
        "KOTAJAKARTAPUSAT": "JAKARTAPUSAT",
        "KOTAJAKARTASELATAN": "JAKARTASELATAN",
        "KOTAJAKARTATIMUR": "JAKARTATIMUR",
        "KOTAJAKARTAUTARA": "JAKARTAUTARA",
        "KOTAPADANGSIDEMPUAN": "KOTAPADANGSIDIMPUAN",
        "KEPULAUANTANIMBAR": "MALUKUTENGGARABARAT",
        "PASANGKAYU": "MAMUJUUTARA",
        "MEMPAWAH": "PONTIANAK",
        "POHUWATO": "PAHUWATO",
        "TOBA": "TOBASAMOSIR",
        "KEPSIAUTAGULANDANGBIARO": "KEPULAUANSIAUTAGULANDANGBIARO",
    }
    target = aliases.get(key, key)
    if target not in historical_keys:
        target = SPLITS_AFTER_2014_HIERARCHY.get(key, target)
    return target


def area_rows(
    year: int,
    district: str,
    area: str,
    code: str,
    votes: tuple[int, int],
    source_url: str,
    informal: int = 0,
    note: str = "",
) -> list[dict[str, object]]:
    candidates = CANDIDATES[year]
    formal = sum(votes)
    order = sorted(range(2), key=lambda index: (-votes[index], candidates[index][0]))
    winner, runner_up = order
    has_result = formal > 0
    common = {
        "district": district,
        "district_url": source_url,
        "distribution_url": source_url,
        "elected_member": candidates[winner][0] if has_result else "",
        "elected_party": candidates[winner][1] if has_result else "",
        "enrolment": 0,
        "formal_votes": formal,
        "informal_votes": informal,
        "total_votes": formal + informal,
        "turnout_pct": 0,
        "majority": votes[winner] - votes[runner_up],
        "round_number": 0,
        "row_type": "first",
        "excluded_candidate": "",
        "excluded_party": "",
        "electorate_type": area,
        "constituency_code": code,
        "contest_status": "official" if has_result else "unavailable",
        "result_note": note,
    }
    return [
        {**common, "candidate": candidate, "candidate_party": ticket, "votes": votes[index]}
        for index, (candidate, ticket) in enumerate(candidates)
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_2019(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    provinces = []
    districts = []
    for province in raw:
        if province["name"].startswith("+"):
            continue
        province_name = title_name(province["name"])
        province_votes = (parse_number(province["value1"]), parse_number(province["value2"]))
        provinces.append({"name": province_name, "votes": province_votes, "code": str(province["no"])})
        if province["name"] in REPAIRS_2019:
            local_rows = REPAIRS_2019[province["name"]]
        else:
            local_rows = tuple(
                (row["name"], parse_number(row["value1"]), parse_number(row["value2"]))
                for row in province["kab"]
            )
        if tuple(sum(row[index] for row in local_rows) for index in (1, 2)) != province_votes:
            raise SystemExit(f"2019 {province_name}: kabupaten/kota do not reconcile to province")
        for raw_name, jokowi, prabowo in local_rows:
            districts.append({
                "raw_name": raw_name,
                "name": title_name(raw_name),
                "province": province_name,
                "votes": (jokowi, prabowo),
            })
    if len(provinces) != 34 or len(districts) != 514:
        raise SystemExit(f"Unexpected 2019 structure: {len(provinces)} provinces, {len(districts)} districts")
    return provinces, districts


def load_2014_locations(path: Path):
    locations = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            locations[int(row["id"])] = row
    province_names = {
        location_id: title_name(row["nama"])
        for location_id, row in locations.items()
        if int(row["level"]) == 1
    }
    districts = {
        location_id: {
            "name": title_name(row["nama"]),
            "province": province_names[int(row["parent"])],
            "code": str(location_id),
        }
        for location_id, row in locations.items()
        if int(row["level"]) == 2
    }
    if len(province_names) != 33 or len(districts) != 497:
        raise SystemExit(f"Unexpected 2014 hierarchy: {len(province_names)} provinces, {len(districts)} districts")
    return province_names, districts


def load_2014_results(path: Path, districts: dict[int, dict[str, str]]):
    totals = defaultdict(lambda: [0, 0, 0])
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            district_id = int(row["Kabupaten"])
            totals[district_id][0] += int(row["Prabowo"] or 0)
            totals[district_id][1] += int(row["Jokowi"] or 0)
            totals[district_id][2] += int(row["TidakSah"] or 0)
    if set(totals) != set(districts):
        raise SystemExit("2014 result/hierarchy district mismatch")
    return totals


def clean_geometry(geometry, label: str):
    if geometry.is_empty or not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise SystemExit(f"{label}: invalid geometry")
    return geometry


def build_historical_boundaries(
    source_path: Path,
    historical_districts: list[dict[str, object]],
    local_path: Optional[Path],
    province_path: Path,
    province_codes: dict[str, str],
) -> None:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    historical_by_key = {name_key(str(row["raw_name"])): row for row in historical_districts}
    if len(historical_by_key) != len(historical_districts):
        raise SystemExit("Historical district names are not unique")
    grouped = defaultdict(list)
    for feature in source.get("features", []):
        current_name = str(feature["properties"]["district"])
        target_key = current_to_historical_key(current_name, set(historical_by_key))
        if target_key not in historical_by_key:
            raise SystemExit(f"No historical district match for boundary {current_name!r} ({target_key})")
        grouped[target_key].append(shape(feature["geometry"]))
    if set(grouped) != set(historical_by_key):
        missing = set(historical_by_key) - set(grouped)
        raise SystemExit(f"Historical districts without geometry: {sorted(missing)}")

    local_features = []
    province_geometries = defaultdict(list)
    for key, row in historical_by_key.items():
        geometry = clean_geometry(unary_union(grouped[key]), str(row["name"]))
        province_geometries[str(row["province"])].append(geometry)
        local_features.append({
            "type": "Feature",
            "properties": {
                "district": row["name"],
                "constituency_code": str(row["code"]),
                "electorate_type": row["province"],
            },
            "geometry": mapping(geometry),
        })
    province_features = []
    if set(province_geometries) != set(province_codes):
        raise SystemExit("Province boundary/result mismatch")
    for province in sorted(province_geometries):
        geometry = clean_geometry(
            unary_union(province_geometries[province]).simplify(0.02, preserve_topology=True),
            province,
        )
        province_features.append({
            "type": "Feature",
            "properties": {
                "district": province,
                "constituency_code": province_codes[province],
                "electorate_type": "Indonesia",
            },
            "geometry": mapping(geometry),
        })
    outputs = [(province_path, province_features)]
    if local_path is not None:
        outputs.insert(0, (local_path, local_features))
    for path, features in outputs:
        path.write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def build_2019(source_dir: Path, output_dir: Path, boundary_source: Path) -> None:
    source_path = download(RESULTS_2019_URL, source_dir / "2019_result.json")
    provinces, districts = load_2019(source_path)
    source_boundaries = json.loads(boundary_source.read_text(encoding="utf-8"))
    current_by_key = {name_key(f["properties"]["district"]): f for f in source_boundaries["features"]}
    historical_keys = {name_key(str(row["raw_name"])) for row in districts}
    used = set()
    for row in districts:
        historical_key = name_key(str(row["raw_name"]))
        matches = [
            key for key, feature in current_by_key.items()
            if current_to_historical_key(str(feature["properties"]["district"]), historical_keys) == historical_key
        ]
        if len(matches) != 1:
            raise SystemExit(f"2019 {row['name']}: expected one modern boundary, found {matches}")
        feature = current_by_key[matches[0]]
        # No kabupaten/kota split occurred between 2019 and 2024, so reuse the
        # compact current boundary layer and its modern labels. Province
        # membership still comes from the 2019 result hierarchy.
        row["name"] = str(feature["properties"]["district"])
        row["code"] = str(feature["properties"]["constituency_code"])
        used.add(matches[0])
    if len(used) != 514:
        raise SystemExit(f"2019 matched {len(used)} of 514 boundaries")

    province_csv_rows = []
    for province in provinces:
        province_csv_rows.extend(area_rows(
            2019, str(province["name"]), "Indonesia", str(province["code"]),
            tuple(province["votes"]), KPU_2019_SOURCE_URL,
        ))
    local_csv_rows = []
    for row in districts:
        local_csv_rows.extend(area_rows(
            2019, str(row["name"]), str(row["province"]), str(row["code"]),
            tuple(row["votes"]), KPU_2019_SOURCE_URL,
        ))
    write_csv(output_dir / "indonesia_2019_president_province_fpp.csv", province_csv_rows)
    write_csv(output_dir / "indonesia_2019_president_kabupaten_kota_fpp.csv", local_csv_rows)
    build_historical_boundaries(
        boundary_source, districts,
        None,
        output_dir / "indonesia_2019_province_boundaries.geojson",
        {str(province["name"]): str(province["code"]) for province in provinces},
    )


def build_2014(source_dir: Path, output_dir: Path, boundary_source: Path) -> None:
    result_path = download(KAWAL_2014_RESULTS_URL, source_dir / "2014_clean.csv")
    location_path = download(KAWAL_2014_LOCATIONS_URL, source_dir / "2014_lokasi3.csv")
    _, districts_by_id = load_2014_locations(location_path)
    totals = load_2014_results(result_path, districts_by_id)
    districts = []
    for district_id, district in districts_by_id.items():
        districts.append({
            **district,
            "raw_name": district["name"],
            "votes": tuple(totals[district_id][:2]),
            "informal": totals[district_id][2],
        })

    province_csv_rows = []
    for index, (province, prabowo, jokowi) in enumerate(PROVINCE_TOTALS_2014, 1):
        province_csv_rows.extend(area_rows(
            2014, province, "Indonesia", str(index), (prabowo, jokowi), KPU_2014_DECISION_URL,
        ))
    local_csv_rows = []
    for row in districts:
        local_csv_rows.extend(area_rows(
            2014, str(row["name"]), str(row["province"]), str(row["code"]),
            tuple(row["votes"]), KAWAL_2014_SOURCE_URL, int(row["informal"]), NOTE_2014,
        ))
    write_csv(output_dir / "indonesia_2014_president_province_fpp.csv", province_csv_rows)
    write_csv(output_dir / "indonesia_2014_president_kabupaten_kota_fpp.csv", local_csv_rows)
    build_historical_boundaries(
        boundary_source, districts,
        output_dir / "indonesia_2014_kabupaten_kota_boundaries.geojson",
        output_dir / "indonesia_2014_province_boundaries.geojson",
        {province: str(index) for index, (province, *_votes) in enumerate(PROVINCE_TOTALS_2014, 1)},
    )


def winner_counts(csv_path: Path) -> Counter:
    winners = Counter()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        seen = set()
        for row in csv.DictReader(handle):
            if row["district"] not in seen:
                if row["elected_party"]:
                    winners[row["elected_party"]] += 1
                seen.add(row["district"])
    return winners


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Indonesia 2019 and 2014 presidential datasets")
    parser.add_argument("--source-dir", type=Path, default=Path("tmp/indonesia_historical"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--boundary-source", type=Path,
        default=Path("data/indonesia_2024_kabupaten_kota_boundaries.geojson"),
    )
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    build_2019(args.source_dir, args.output_dir, args.boundary_source)
    build_2014(args.source_dir, args.output_dir, args.boundary_source)
    for year in (2019, 2014):
        local_path = args.output_dir / f"indonesia_{year}_president_kabupaten_kota_fpp.csv"
        counts = winner_counts(local_path)
        print(f"Built Indonesia Presidential {year}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
