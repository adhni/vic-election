#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union


ELECTIONS = {
    2025: {
        "areas": 252,
        "candidates": {
            "Lee Jae-myung": 17_287_513,
            "Kim Moon-soo": 14_395_639,
            "Lee Jun-seok": 2_917_523,
            "Kwon Young-guk": 344_150,
            "Song Jin-ho": 35_791,
        },
        "wins": {"Lee Jae-myung": 139, "Kim Moon-soo": 113},
        "enrolment": 44_391_871,
        "total_votes": 35_236_497,
        "informal": 255_881,
    },
    2022: {
        "areas": 250,
        "candidates": {
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
        "wins": {"Yoon Suk Yeol": 151, "Lee Jae-myung": 99},
        "enrolment": 44_197_692,
        "total_votes": 34_067_853,
        "informal": 307_542,
    },
}


def validate_year(year: int, expected: dict[str, object]) -> None:
    csv_path = Path(f"data/south_korea_{year}_president_fpp.csv")
    boundary_path = Path(f"data/south_korea_{year}_municipal_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    area_count = int(expected["areas"])
    candidate_totals_expected = expected["candidates"]
    if len(rows) != area_count * len(candidate_totals_expected):
        raise SystemExit(f"{csv_path}: unexpected row count {len(rows)}")

    by_district = defaultdict(list)
    candidate_totals = Counter()
    for row in rows:
        by_district[row["district"]].append(row)
        candidate_totals[row["candidate_party"]] += int(row["votes"])
    if len(by_district) != area_count:
        raise SystemExit(f"{csv_path}: expected {area_count} areas, found {len(by_district)}")
    if dict(candidate_totals) != candidate_totals_expected:
        raise SystemExit(f"{csv_path}: national candidate totals changed")

    codes, provinces, wins = {}, {}, Counter()
    enrolment = total_votes = informal_votes = 0
    for district, district_rows in by_district.items():
        first = district_rows[0]
        votes = {row["candidate_party"]: int(row["votes"]) for row in district_rows}
        if set(votes) != set(candidate_totals_expected):
            raise SystemExit(f"{csv_path}: {district} candidate set is incomplete")
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(first["formal_votes"])
        informal = int(first["informal_votes"])
        total = int(first["total_votes"])
        district_enrolment = int(first["enrolment"])
        if formal != sum(votes.values()) or formal + informal != total:
            raise SystemExit(f"{csv_path}: {district} vote totals do not reconcile")
        if total > district_enrolment:
            raise SystemExit(f"{csv_path}: {district} turnout exceeds enrolment")
        if first["elected_party"] != ranked[0][0]:
            raise SystemExit(f"{csv_path}: {district} winner is wrong")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{csv_path}: {district} margin is wrong")
        if float(first["turnout_pct"]) != round(total / district_enrolment * 100, 2):
            raise SystemExit(f"{csv_path}: {district} turnout is wrong")
        code = first["constituency_code"]
        if not code.startswith(f"KR{year}-"):
            raise SystemExit(f"{csv_path}: {district} has an invalid code")
        codes[district] = code
        provinces[district] = first["electorate_type"]
        wins[first["elected_party"]] += 1
        enrolment += district_enrolment
        total_votes += total
        informal_votes += informal

    if len(set(codes.values())) != area_count:
        raise SystemExit(f"{csv_path}: area codes are not unique")
    if len(set(provinces.values())) != 17:
        raise SystemExit(f"{csv_path}: expected all 17 first-level regions")
    if dict(wins) != expected["wins"]:
        raise SystemExit(f"{csv_path}: local winner counts changed: {dict(wins)}")
    if (enrolment, total_votes, informal_votes) != (
        expected["enrolment"],
        expected["total_votes"],
        expected["informal"],
    ):
        raise SystemExit(f"{csv_path}: election-wide metadata totals changed")

    collection = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != area_count:
        raise SystemExit(f"{boundary_path}: expected {area_count} features")
    if {f["properties"]["district"] for f in features} != set(by_district):
        raise SystemExit(f"{boundary_path}: names do not match the CSV")
    geometries = []
    for feature in features:
        properties = feature["properties"]
        district = properties["district"]
        if properties["constituency_code"] != codes[district]:
            raise SystemExit(f"{boundary_path}: {district} code does not match")
        if properties["electorate_type"] != provinces[district]:
            raise SystemExit(f"{boundary_path}: {district} region does not match")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{boundary_path}: {district} geometry is invalid")
        min_x, min_y, max_x, max_y = geometry.bounds
        if min_x < 124 or max_x > 132 or min_y < 32 or max_y > 39:
            raise SystemExit(f"{boundary_path}: {district} is outside plausible Korean bounds")
        geometries.append(geometry)
    summed_area = sum(geometry.area for geometry in geometries)
    overlap_ratio = (summed_area - unary_union(geometries).area) / summed_area
    if overlap_ratio > 0.001:
        raise SystemExit(f"{boundary_path}: areas materially overlap ({overlap_ratio:.3%})")


def main() -> None:
    for year, expected in ELECTIONS.items():
        validate_year(year, expected)
    print("South Korea validation passed: 2025 (252 areas) and 2022 (250 areas)")


if __name__ == "__main__":
    main()
