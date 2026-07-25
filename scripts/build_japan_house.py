#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from svg.path import Close, Move, parse_path


SOURCES = {
    "candidates": (
        "https://www.kaggle.com/api/v1/datasets/download/kenichiyoshinaga/"
        "japan-house-of-representatives-election-candidates",
        "candidates.zip",
        "e2b24d5b2bb19f4091cb3c169b5029e30e7fa39a1bb4af5a0a9cc42874f88afd",
    ),
    "audit_2024": (
        "https://yukiyanai.github.io/jp/resources/data/hr2024_districts.csv",
        "hr2024_districts.csv",
        "937f39ebd73a82b35644afc71c4cf7b014f096f5c80ffdeeccff5f2ddcde3f58",
    ),
    "official_2026": (
        "https://www.soumu.go.jp/main_content/001061487.pdf",
        "soumu_candidates_2026.pdf",
        "14f2f22707be9e889bc843988555229766e8007b0f46dbd546423bfaa2c6ccd9",
    ),
    "official_2024": (
        "https://www.soumu.go.jp/main_content/000979134.pdf",
        "soumu_candidates_2024.pdf",
        "661f256e2b61efc55a1e3310e733d8d6153c0ebd6510ad3194235e115348bdaa",
    ),
    "boundaries": (
        "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
        "Japanese%20House%20of%20Representatives%20map%2C%202022%20redistricting.svg",
        "2022_redistricting.svg",
        "0f2f6b8004b87ad31091f58e2cf7e2b099ac359a2e9bd75b07f5dff80ab389fe",
    ),
}

OFFICIAL_PAGES = {
    2026: "https://www.soumu.go.jp/senkyo/senkyo_s/data/shugiin51/index.html",
    2024: "https://www.soumu.go.jp/senkyo/senkyo_s/data/shugiin50/index.html",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

PARTIES = {
    "自民": "Liberal Democratic Party",
    "中道": "Centrist Reform Alliance",
    "立民": "Constitutional Democratic Party",
    "維新": "Japan Innovation Party",
    "国民": "Democratic Party for the People",
    "参政": "Sanseitō",
    "共産": "Japanese Communist Party",
    "れいわ": "Reiwa Shinsengumi",
    "減ゆ": "Genzei Nippon–Yūkoku Alliance",
    "保守": "Conservative Party of Japan",
    "社民": "Social Democratic Party",
    "みらい": "Team Mirai",
    "公明": "Komeito",
    "みんな": "Minna de Tsukuru Tō",
    "無": "Independent",
    "諸派": "Other",
}

# Japanese label, English label, SVG id prefix, single-member seats after the 2022 redistribution.
PREFECTURES = {
    "北海道": ("Hokkaido", "Hokkaidō", 12),
    "青森県": ("Aomori", "Aomori", 3), "岩手県": ("Iwate", "Iwate", 3),
    "宮城県": ("Miyagi", "Miyagi", 5), "秋田県": ("Akita", "Akita", 3),
    "山形県": ("Yamagata", "Yamagata", 3), "福島県": ("Fukushima", "Fukushima", 4),
    "茨城県": ("Ibaraki", "Ibaraki", 7), "栃木県": ("Tochigi", "Tochigi", 5),
    "群馬県": ("Gunma", "Gunma", 5), "埼玉県": ("Saitama", "Saitama", 16),
    "千葉県": ("Chiba", "Chiba", 14), "東京都": ("Tokyo", "Tōkyō", 30),
    "神奈川県": ("Kanagawa", "Kanagawa", 20), "新潟県": ("Niigata", "Niigata", 5),
    "富山県": ("Toyama", "Toyama", 3), "石川県": ("Ishikawa", "Ishikawa", 3),
    "福井県": ("Fukui", "Fukui", 2), "山梨県": ("Yamanashi", "Yamanashi", 2),
    "長野県": ("Nagano", "Nagano", 5), "岐阜県": ("Gifu", "Gifu", 5),
    "静岡県": ("Shizuoka", "Shizuoka", 8), "愛知県": ("Aichi", "Aichi", 16),
    "三重県": ("Mie", "Mie", 4), "滋賀県": ("Shiga", "Shiga", 3),
    "京都府": ("Kyoto", "Kyotō", 6), "大阪府": ("Osaka", "_Ōsaka", 19),
    "兵庫県": ("Hyogo", "Hyōgo", 12), "奈良県": ("Nara", "Nara", 3),
    "和歌山県": ("Wakayama", "Wakayama", 2), "鳥取県": ("Tottori", "Tottori", 2),
    "島根県": ("Shimane", "Shimane", 2), "岡山県": ("Okayama", "Okayama", 4),
    "広島県": ("Hiroshima", "Hiroshima", 6), "山口県": ("Yamaguchi", "Yamaguchi", 3),
    "徳島県": ("Tokushima", "Tokushima", 2), "香川県": ("Kagawa", "Kagawa", 3),
    "愛媛県": ("Ehime", "Ehime", 3), "高知県": ("Kochi", "Kōchi", 2),
    "福岡県": ("Fukuoka", "Fukuoka", 11), "佐賀県": ("Saga", "Saga", 2),
    "長崎県": ("Nagasaki", "Nagasaki", 3), "熊本県": ("Kumamoto", "Kumamoto", 4),
    "大分県": ("Oita", "_Ōita", 3), "宮崎県": ("Miyazaki", "Miyazaki", 3),
    "鹿児島県": ("Kagoshima", "Kagoshima", 4), "沖縄県": ("Okinawa", "Okinawa", 4),
}

EXPECTED = {
    2026: {
        "candidates": 1119,
        "whole_votes": 56_446_718,
        "winners": {
            "Liberal Democratic Party": 249, "Japan Innovation Party": 20,
            "Democratic Party for the People": 8, "Centrist Reform Alliance": 7,
            "Independent": 4, "Genzei Nippon–Yūkoku Alliance": 1,
        },
    },
    2024: {
        "candidates": 1113,
        "whole_votes": 54_261_865,
        "winners": {
            "Liberal Democratic Party": 132, "Constitutional Democratic Party": 104,
            "Japan Innovation Party": 23, "Independent": 12,
            "Democratic Party for the People": 11, "Komeito": 4,
            "Conservative Party of Japan": 1, "Japanese Communist Party": 1,
            "Social Democratic Party": 1,
        },
    },
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and path.stat().st_size and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: source checksum changed to {actual}; expected {expected}")


def clean_candidate(value: str) -> str:
    value = re.sub(r"[♂♀]\(\d+\)$", "", value).replace("･", " ").strip()
    return re.sub(r"\s+", " ", value)


def candidate_rows(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        with archive.open("ja-election-shugiin-candidates.csv") as handle:
            return list(csv.DictReader(line.decode("utf-8-sig") for line in handle))


def audit_2024(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        audit = list(csv.DictReader(handle))
    audit_votes: dict[tuple[str, int], list[int]] = defaultdict(list)
    for row in audit:
        prefecture = row["prefecture"] if row["prefecture"] == "北海道" else f"{row['prefecture']}県"
        prefecture = {
            "東京県": "東京都", "大阪県": "大阪府", "京都県": "京都府",
            "東京都県": "東京都", "大阪府県": "大阪府", "京都府県": "京都府",
        }.get(prefecture, prefecture)
        audit_votes[(prefecture, int(row["dist_no"]))].append(int(row["votes"]))
    parsed_votes: dict[tuple[str, int], list[int]] = defaultdict(list)
    for row in rows:
        parsed_votes[(row["都道府県"], int(row["小選挙区"]))].append(int(row["得票数"]))
    normalized_audit = {key: sorted(values) for key, values in audit_votes.items()}
    normalized_parsed = {key: sorted(values) for key, values in parsed_votes.items()}
    if normalized_audit != normalized_parsed:
        raise SystemExit("2024 structured transcription does not reconcile with the independent academic audit")


def build_results(year: int, source_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    selected = [
        row for row in source_rows
        if row["選挙制度"] == "小選挙区" and row["日付"].startswith(str(year))
    ]
    if len(selected) != EXPECTED[year]["candidates"]:
        raise SystemExit(f"{year}: expected {EXPECTED[year]['candidates']} candidate rows, found {len(selected)}")
    if year == 2026 and {row["日付"] for row in selected} != {"2026-10-22"}:
        raise SystemExit("The pinned 2026 transcription's known erroneous date field changed; review before rebuilding")

    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        if row["都道府県"] not in PREFECTURES or row["政党"] not in PARTIES:
            raise SystemExit(f"{year}: unknown prefecture/party: {row['都道府県']} / {row['政党']}")
        groups[(row["都道府県"], int(row["小選挙区"]))].append(row)
    expected_keys = {
        (prefecture, number)
        for prefecture, (_, _, seats) in PREFECTURES.items()
        for number in range(1, seats + 1)
    }
    if set(groups) != expected_keys:
        raise SystemExit(f"{year}: constituency allocation mismatch: {sorted(set(groups) ^ expected_keys)}")

    output: list[dict[str, object]] = []
    district_info: dict[str, dict[str, str]] = {}
    winners = Counter()
    total_votes = 0
    for prefecture_number, key in enumerate(PREFECTURES, start=1):
        english, _, seats = PREFECTURES[key]
        for number in range(1, seats + 1):
            source = groups[(key, number)]
            candidates = sorted(
                [
                    clean_candidate(row["立候補者名"]),
                    PARTIES[row["政党"]],
                    int(row["得票数"]),
                    row["当選・落選"] == "当選",
                ]
                for row in source
            )
            candidates.sort(key=lambda item: (-item[2], item[0]))
            if len(candidates) < 2 or sum(item[3] for item in candidates) != 1 or not candidates[0][3]:
                raise SystemExit(f"{year} {key} {number}: winner flag does not match the vote leader")
            if len({item[0] for item in candidates}) != len(candidates):
                raise SystemExit(f"{year} {key} {number}: duplicate candidate name")
            district = f"{english} {number}"
            code = f"JP-{prefecture_number:02d}-{number:02d}"
            formal = sum(item[2] for item in candidates)
            winner, winner_party = candidates[0][:2]
            winners[winner_party] += 1
            total_votes += formal
            note = (
                "Candidate totals are the whole-vote figures in the official constituency table. "
                "Japan's national party summary separately allocates a very small number of "
                "fractional ambiguous ballots. District turnout and invalid-ballot metadata are unavailable."
            )
            base = {
                "district": district, "district_url": OFFICIAL_PAGES[year],
                "distribution_url": OFFICIAL_PAGES[year], "elected_member": winner,
                "elected_party": winner_party, "enrolment": 0, "formal_votes": formal,
                "informal_votes": 0, "total_votes": formal, "turnout_pct": "",
                "majority": formal // 2 + 1, "electorate_type": english,
                "constituency_code": code, "contest_status": "official",
            }
            for index, (candidate, party, votes, _) in enumerate(candidates):
                output.append({
                    **base, "round_number": 0, "row_type": "first", "excluded_candidate": "",
                    "excluded_party": "", "candidate": candidate, "candidate_party": party,
                    "votes": votes, "result_note": note if index == 0 else "",
                })
            district_info[code] = {"district": district, "prefecture": english}
    if total_votes != EXPECTED[year]["whole_votes"] or winners != EXPECTED[year]["winners"]:
        raise SystemExit(f"{year}: national totals changed: {total_votes:,}, {winners}")
    return output, district_info


def sampled_ring(path_data: str) -> list[list[list[float]]]:
    rings: list[list[list[float]]] = []
    ring: list[list[float]] = []
    for segment in parse_path(path_data):
        if isinstance(segment, Move):
            if len(ring) >= 4:
                rings.append(ring)
            ring = [[segment.end.real, 1600 - segment.end.imag]]
            continue
        if not ring:
            ring = [[segment.start.real, 1600 - segment.start.imag]]
        steps = 1 if segment.length(error=1e-3) < 4 else min(24, max(2, math.ceil(segment.length(error=1e-3) / 3)))
        for step in range(1, steps + 1):
            point = segment.point(step / steps)
            ring.append([round(point.real, 3), round(1600 - point.imag, 3)])
        if isinstance(segment, Close):
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            if len(ring) >= 4:
                rings.append(ring)
            ring = []
    if len(ring) >= 4:
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        rings.append(ring)
    return rings


def build_schematic(svg_path: Path, district_info: dict[str, dict[str, str]]) -> dict[str, object]:
    root = ET.parse(svg_path).getroot()
    parent = {child: node for node in root.iter() for child in node}
    by_id: dict[str, list[ET.Element]] = defaultdict(list)
    for element in root.iter():
        if element.get("id"):
            by_id[element.get("id", "")].append(element)
    features = []
    for prefecture_number, (japanese, (english, prefix, seats)) in enumerate(PREFECTURES.items(), start=1):
        for number in range(1, seats + 1):
            source_id = f"{prefix}-{number}"
            if japanese == "和歌山県" and number == 2:
                source_id = "Wakay-2ama"  # Typo retained in the pinned Wikimedia SVG.
            candidates = by_id.get(source_id, [])
            nodes_with_geometry = [
                element for element in candidates
                if element.get("d") or any(descendant.get("d") for descendant in element.iter())
            ]
            if not nodes_with_geometry:
                raise SystemExit(f"Schematic SVG is missing {source_id}")
            node = nodes_with_geometry[0]
            while parent.get(node) is not None and parent[node].get("id") == source_id:
                node = parent[node]
            polygons = []
            path_nodes = [node] if node.tag.endswith("path") else list(node.iter())
            for path_node in path_nodes:
                if not path_node.tag.endswith("path") or not path_node.get("d"):
                    continue
                for ring in sampled_ring(path_node.get("d", "")):
                    polygon = Polygon(ring).buffer(0)
                    if not polygon.is_empty and polygon.area > 0.001:
                        polygons.append(polygon)
            if not polygons:
                raise SystemExit(f"Schematic SVG produced no valid geometry for {source_id}")
            geometry = unary_union(polygons).buffer(0).simplify(0.25, preserve_topology=True).buffer(0)
            code = f"JP-{prefecture_number:02d}-{number:02d}"
            info = district_info[code]
            features.append({
                "type": "Feature",
                "properties": {
                    "district": info["district"], "constituency_code": code,
                    "prefecture": english,
                    "geometry_note": (
                        "Schematic constituency map with metropolitan insets; "
                        "not a legal-boundary GIS layer"
                    ),
                },
                "geometry": mapping(geometry),
            })
    return {
        "type": "FeatureCollection",
        "name": "japan_house_2022_redistricting_schematic",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Japan House 2026 and 2024 constituency results")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/japan_house"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; election-preference-explorer/1.0)"
    paths = {}
    for key, (url, filename, checksum) in SOURCES.items():
        path = args.raw_dir / filename
        download(session, url, path, args.refresh)
        require_sha256(path, checksum)
        paths[key] = path

    source_rows = candidate_rows(paths["candidates"])
    selected_2024 = [
        row for row in source_rows if row["選挙制度"] == "小選挙区" and row["日付"].startswith("2024")
    ]
    audit_2024(paths["audit_2024"], selected_2024)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    shared_info = None
    for year in (2026, 2024):
        rows, district_info = build_results(year, source_rows)
        shared_info = district_info
        output = args.out_dir / f"japan_{year}_house_fpp.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows):,} candidates in 289 constituencies to {output}")
    schematic = build_schematic(paths["boundaries"], shared_info or {})
    boundary_path = args.out_dir / "japan_2022_house_constituency_schematic.geojson"
    boundary_path.write_text(
        json.dumps(schematic, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"Wrote 289 schematic constituency features to {boundary_path}")


if __name__ == "__main__":
    main()
