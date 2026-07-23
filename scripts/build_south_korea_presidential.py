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
import requests
from shapely.geometry import mapping
from shapely.ops import unary_union


RESULT_URLS = {
    2025: "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003525373&fileDetailSn=1&insertDataPrcus=N",
    2022: "https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003172225&fileDetailSn=1&insertDataPrcus=N",
}
BOUNDARY_URL = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do?"
    "atchFileId=FILE_000000003601705&fileDetailSn=1&insertDataPrcus=N"
)
RESULT_PAGE = "https://www.data.go.kr/data/15025528/fileData.do"
BOUNDARY_PAGE = "https://www.data.go.kr/data/15129688/fileData.do"
SOURCE_SHA256 = {
    2025: "4d1479e549e3ab0f6ae2a5b4436ec085f4326711a6a4163636be12a1a6e39e19",
    2022: "e9699556e1bf92cc8e61d61d4cc433506ed94439f67e1fb23b6a35a98cef09e5",
    "boundaries": "3f517984bfdf4bbe43ee2a8849cff010d70ac5a826f880e6976b9a1f2b30611b",
}

PROVINCES = {
    "서울특별시": ("11", "Seoul"),
    "부산광역시": ("21", "Busan"),
    "대구광역시": ("22", "Daegu"),
    "인천광역시": ("23", "Incheon"),
    "광주광역시": ("24", "Gwangju"),
    "대전광역시": ("25", "Daejeon"),
    "울산광역시": ("26", "Ulsan"),
    "세종특별자치시": ("29", "Sejong"),
    "경기도": ("31", "Gyeonggi"),
    "강원도": ("32", "Gangwon"),
    "강원특별자치도": ("32", "Gangwon"),
    "충청북도": ("33", "North Chungcheong"),
    "충청남도": ("34", "South Chungcheong"),
    "전라북도": ("35", "North Jeolla"),
    "전북특별자치도": ("35", "North Jeolla"),
    "전라남도": ("36", "South Jeolla"),
    "경상북도": ("37", "North Gyeongsang"),
    "경상남도": ("38", "South Gyeongsang"),
    "제주특별자치도": ("39", "Jeju"),
}

CANDIDATES = {
    2025: {
        "더불어민주당 이재명": ("Lee Jae-myung", "Democratic Party"),
        "국민의힘 김문수": ("Kim Moon-soo", "People Power Party"),
        "개혁신당 이준석": ("Lee Jun-seok", "Reform Party"),
        "민주노동당 권영국": ("Kwon Young-guk", "Democratic Labor Party"),
        "무소속 송진호": ("Song Jin-ho", "Independent"),
    },
    2022: {
        "더불어민주당 이재명": ("Lee Jae-myung", "Democratic Party"),
        "국민의힘 윤석열": ("Yoon Suk Yeol", "People Power Party"),
        "정의당 심상정": ("Sim Sang-jung", "Justice Party"),
        "기본소득당 오준호": ("Oh Jun-ho", "Basic Income Party"),
        "국가혁명당 허경영": ("Huh Kyung-young", "National Revolutionary Party"),
        "노동당 이백윤": ("Lee Baek-yoon", "Labor Party"),
        "새누리당 옥은호": ("Ok Eun-ho", "Saenuri Party"),
        "신자유민주연합 김경재": ("Kim Kyung-jae", "New Liberal Democratic Union"),
        "우리공화당 조원진": ("Cho Won-jin", "Our Republican Party"),
        "진보당 김재연": ("Kim Jae-yeon", "Progressive Party"),
        "통일한국당 이경희": ("Lee Kyung-hee", "Korean Unification Party"),
        "한류연합당 김민찬": ("Kim Min-chan", "Korean Wave Alliance Party"),
    },
}

EXPECTED_NATIONAL = {
    2025: {
        "Lee Jae-myung": 17_287_513,
        "Kim Moon-soo": 14_395_639,
        "Lee Jun-seok": 2_917_523,
        "Kwon Young-guk": 344_150,
        "Song Jin-ho": 35_791,
    },
    2022: {
        "Yoon Suk Yeol": 16_394_815,
        "Lee Jae-myung": 16_147_738,
        "Sim Sang-jung": 803_358,
        "Huh Kyung-young": 281_481,
        "Kim Jae-yeon": 37_366,
        "Cho Won-jin": 25_972,
        "Oh Jun-ho": 18_105,
        "Kim Min-chan": 17_305,
        "Lee Kyung-hee": 11_708,
        "Lee Baek-yoon": 9_176,
        "Kim Kyung-jae": 8_317,
        "Ok Eun-ho": 4_970,
    },
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
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


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def normalize(text: str) -> str:
    return "".join(str(text).split())


def extract_boundaries(archive: Path, raw_dir: Path) -> Path:
    output = raw_dir / "bnd_sigungu_00_2025_2Q.shp"
    if output.exists() and output.stat().st_size:
        return output
    raw_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            suffix = Path(member.filename).name
            if suffix.startswith("bnd_sigungu_00_2025_2Q."):
                (raw_dir / suffix).write_bytes(source.read(member))
    if not output.exists():
        raise SystemExit("Official SGIS archive did not contain the municipal shapefile")
    return output


def result_key(year: int, province: str, municipality: str) -> tuple[str, str]:
    province_code = PROVINCES[province][0]
    name = normalize(municipality)
    if province_code == "29":
        name = "세종시"
    if year == 2025 and name in {"화성시갑", "화성시을"}:
        name = "화성시"
    return province_code, name


def parse_results(year: int, path: Path) -> dict[tuple[str, str], dict[str, object]]:
    areas: dict[tuple[str, str], dict[str, object]] = {}
    national = Counter()
    labels = CANDIDATES[year]
    metrics = {"선거인수", "투표수", "무효투표수", "기권자수"}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = result_key(year, row["시도명"], row["구시군명"])
            area = areas.setdefault(
                key,
                {
                    "korean_name": key[1],
                    "province": PROVINCES[row["시도명"]][1],
                    "votes": Counter(),
                    "enrolment": 0,
                    "total": 0,
                    "informal": 0,
                    "abstentions": 0,
                },
            )
            label = normalize(row["후보자"])
            votes = int(row["득표수"])
            if label in metrics:
                field = {
                    "선거인수": "enrolment",
                    "투표수": "total",
                    "무효투표수": "informal",
                    "기권자수": "abstentions",
                }[label]
                area[field] += votes
                continue
            original_label = " ".join(row["후보자"].split())
            if original_label not in labels:
                raise SystemExit(f"{year}: unknown candidate label {original_label!r}")
            candidate = labels[original_label][0]
            area["votes"][candidate] += votes
            national[candidate] += votes

    expected_areas = 252 if year == 2025 else 250
    if len(areas) != expected_areas:
        raise SystemExit(f"{year}: expected {expected_areas} mapped result areas, found {len(areas)}")
    if dict(national) != EXPECTED_NATIONAL[year]:
        raise SystemExit(f"{year}: national candidate totals changed: {dict(national)}")
    for key, area in areas.items():
        formal = sum(area["votes"].values())
        if formal + area["informal"] != area["total"]:
            raise SystemExit(f"{year} {key}: formal plus invalid votes does not equal total votes")
        if area["total"] + area["abstentions"] != area["enrolment"]:
            raise SystemExit(f"{year} {key}: total votes plus abstentions does not equal electorate")
    return areas


def district_name(korean_name: str, province: str) -> str:
    return f"{korean_name} — {province}"


def build_boundaries(
    year: int,
    source_path: Path,
    areas: dict[tuple[str, str], dict[str, object]],
) -> tuple[dict[str, object], dict[tuple[str, str], str]]:
    source = gpd.read_file(source_path).to_crs(epsg=4326)
    records: list[tuple[tuple[str, str], object]] = []
    bucheon = []
    for _, row in source.iterrows():
        source_key = (str(row["SIGUNGU_CD"])[:2], normalize(row["SIGUNGU_NM"]))
        if year == 2022 and source_key[0] == "31" and source_key[1].startswith("부천시"):
            bucheon.append(row.geometry)
            continue
        key = source_key
        if year == 2022 and key == ("22", "군위군"):
            key = ("37", "군위군")
        records.append((key, row.geometry))
    if year == 2022:
        records.append((("31", "부천시"), unary_union(bucheon)))

    expected_areas = 252 if year == 2025 else 250
    if len(records) != expected_areas or {key for key, _ in records} != set(areas):
        missing = sorted(set(areas) - {key for key, _ in records})
        extra = sorted({key for key, _ in records} - set(areas))
        raise SystemExit(f"{year}: boundary/result mismatch; missing={missing}, extra={extra}")

    features = []
    codes = {}
    for key, geometry in sorted(records):
        geometry = geometry.simplify(0.002, preserve_topology=True)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{year} {key}: invalid simplified geometry")
        area = areas[key]
        code = f"KR{year}-{key[0]}-{len(codes) + 1:03d}"
        codes[key] = code
        name = district_name(area["korean_name"], area["province"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": name,
                    "constituency_code": code,
                    "electorate_type": area["province"],
                },
                "geometry": mapping(geometry),
            }
        )
    return {
        "type": "FeatureCollection",
        "name": f"south_korea_{year}_presidential_municipalities",
        "source": "Statistics Korea SGIS 2025 Q2 municipal boundaries",
        "features": features,
    }, codes


def build_rows(
    year: int,
    areas: dict[tuple[str, str], dict[str, object]],
    codes: dict[tuple[str, str], str],
) -> list[dict[str, object]]:
    rows = []
    note = (
        "Official NEC polling-district returns aggregated to municipality/election-commission areas. "
        + (
            "Hwaseong A and B are combined to the official municipal boundary."
            if year == 2025
            else "The map retains 2022-era Bucheon and North Gyeongsang attribution for Gunwi."
        )
    )
    for key, area in sorted(areas.items()):
        ranked = sorted(area["votes"].items(), key=lambda item: (-item[1], item[0]))
        winner = ranked[0][0]
        formal = sum(area["votes"].values())
        base = {
            "district": district_name(area["korean_name"], area["province"]),
            "district_url": RESULT_PAGE,
            "distribution_url": BOUNDARY_PAGE,
            "elected_member": winner,
            "elected_party": winner,
            "enrolment": area["enrolment"],
            "formal_votes": formal,
            "informal_votes": area["informal"],
            "total_votes": area["total"],
            "turnout_pct": round(area["total"] / area["enrolment"] * 100, 2),
            "majority": ranked[0][1] - ranked[1][1],
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": area["province"],
            "constituency_code": codes[key],
            "contest_status": "official",
            "result_note": note,
        }
        for candidate, votes in ranked:
            rows.append(
                {
                    **base,
                    "candidate": candidate,
                    "candidate_party": candidate,
                    "votes": votes,
                }
            )
    return rows


def write_outputs(
    year: int,
    rows: list[dict[str, object]],
    boundaries: dict[str, object],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"south_korea_{year}_president_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    boundary_path = out_dir / f"south_korea_{year}_municipal_boundaries.geojson"
    boundary_path.write_text(
        json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{year}: wrote {len(rows)} rows and {len(boundaries['features'])} map features")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build South Korean presidential municipality maps")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/south_korea_presidential"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    result_paths = {}
    for year in (2025, 2022):
        result_paths[year] = download(
            session,
            RESULT_URLS[year],
            args.raw_dir / f"nec_president_{year}_download",
            args.refresh,
        )
        require_sha256(result_paths[year], SOURCE_SHA256[year])
    boundary_archive = download(
        session,
        BOUNDARY_URL,
        args.raw_dir / "sgis_2025_boundaries_download",
        args.refresh,
    )
    require_sha256(boundary_archive, SOURCE_SHA256["boundaries"])
    boundary_source = extract_boundaries(boundary_archive, args.raw_dir / "sgis_sigungu")

    for year in (2025, 2022):
        areas = parse_results(year, result_paths[year])
        boundaries, codes = build_boundaries(year, boundary_source, areas)
        write_outputs(year, build_rows(year, areas, codes), boundaries, args.out_dir)


if __name__ == "__main__":
    main()
