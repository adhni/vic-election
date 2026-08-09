#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


ELECTIONS = {
    "poland_2025_president_round_1": {
        "areas": 16, "enrolment": 28_727_963, "formal": 19_137_917, "informal": 83_875,
        "wins": {"Rafał Trzaskowski": 10, "Karol Nawrocki": 6},
        "totals_hash": "d03bf4e56860dbd3434f110b050161d0793c1016885b20286760e60b66eb82fd",
        "boundaries": "poland_voivodeship_boundaries.geojson", "round": 1,
    },
    "poland_2025_president_round_2": {
        "areas": 16, "enrolment": 28_641_910, "formal": 20_239_632, "informal": 185_606,
        "wins": {"Rafał Trzaskowski": 10, "Karol Nawrocki": 6},
        "totals_hash": "764f18fb5c0a1f2e2c5907a017e0f27cb34af55676aebc9eca4cb76df6c17034",
        "boundaries": "poland_voivodeship_boundaries.geojson", "round": 2,
    },
    "poland_2020_president_round_1": {
        "areas": 16, "enrolment": 30_204_684, "formal": 19_425_459, "informal": 58_301,
        "wins": {"Andrzej Duda": 13, "Rafał Trzaskowski": 3},
        "totals_hash": "10d7fe598dfe9349e3346aecfce72192d5290f51f52d77475f987205fc4df440",
        "boundaries": "poland_voivodeship_boundaries.geojson", "round": 1,
    },
    "poland_2020_president_round_2": {
        "areas": 16, "enrolment": 30_268_460, "formal": 20_458_911, "informal": 177_724,
        "wins": {"Rafał Trzaskowski": 10, "Andrzej Duda": 6},
        "totals_hash": "59857db2b3080e4898cedb8e8f0b58239606722815bfad21d4bcd6e9fa4748ca",
        "boundaries": "poland_voivodeship_boundaries.geojson", "round": 2,
    },
    "greece_2023_parliament": {
        "areas": 59, "enrolment": 9_895_541, "formal": 5_197_949, "informal": 58_385,
        "wins": {"New Democracy": 58, "SYRIZA": 1},
        "totals_hash": "ffce819349a08bb9abea73e37652a71874ce4c4c9c701e63dfda18713dece8d5",
        "boundaries": "greece_2023_parliament_boundaries.geojson", "round": 0,
        "district_seats": 285,
    },
    "greece_2019_parliament": {
        "areas": 59, "enrolment": 9_984_934, "formal": 5_649_527, "informal": 120_117,
        "wins": {"New Democracy": 49, "SYRIZA": 10},
        "totals_hash": "f2d5755ad26f00101eb932445bfa3cb2d3117726e50408bdd1a4f62451040182",
        "boundaries": "greece_2019_parliament_boundaries.geojson", "round": 0,
        "district_seats": 288,
    },
    "belgium_2024_chamber": {
        "areas": 11, "enrolment": 8_368_029, "formal": 6_984_906, "informal": 416_577,
        "wins": {"N-VA": 2, "MR": 3, "VLAAMS BELANG": 3, "PS": 1, "LES ENGAGÉS": 2},
        "totals_hash": "d48ed95b7ad1e4a7b90fe83afb26852069a8daa6f3369f58fe663a7a1c596f50",
        "boundaries": "belgium_chamber_boundaries.geojson", "round": 0,
        "district_seats": 150,
    },
    "belgium_2019_chamber": {
        "areas": 11, "enrolment": 8_167_709, "formal": 6_780_538, "informal": 438_095,
        "wins": {"N-VA": 5, "ECOLO": 1, "MR": 2, "PS": 3},
        "totals_hash": "e123b1c5739993de4be315335e34499e5bd4318f919a92d7eb333e2810e94594",
        "boundaries": "belgium_chamber_boundaries.geojson", "round": 0,
        "district_seats": 150,
    },
}


def validate_election(stem: str, expected: dict[str, object]) -> None:
    csv_path = Path("data") / f"{stem}_fpp.csv"
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_district = defaultdict(list)
    totals = Counter()
    for row in rows:
        by_district[row["district"]].append(row)
        totals[row["candidate_party"]] += int(row["votes"])
    if len(by_district) != expected["areas"]:
        raise SystemExit(f"{csv_path}: expected {expected['areas']} areas")
    canonical = json.dumps(sorted(totals.items()), ensure_ascii=False, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != expected["totals_hash"]:
        raise SystemExit(f"{csv_path}: national candidate/party totals changed")

    wins = Counter()
    metadata = Counter()
    district_seats = 0
    codes = {}
    for district, district_rows in by_district.items():
        first = district_rows[0]
        for field in (
            "elected_member", "elected_party", "enrolment", "formal_votes", "informal_votes",
            "total_votes", "turnout_pct", "majority", "round_number", "constituency_code",
        ):
            if any(row[field] != first[field] for row in district_rows):
                raise SystemExit(f"{csv_path}: {district} repeats inconsistent {field}")
        votes = {row["candidate_party"]: int(row["votes"]) for row in district_rows}
        if len(votes) != len(district_rows):
            raise SystemExit(f"{csv_path}: {district} repeats a candidate/party")
        ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
        formal = int(first["formal_votes"])
        informal = int(first["informal_votes"])
        total = int(first["total_votes"])
        enrolment = int(first["enrolment"])
        if sum(votes.values()) != formal or formal + informal != total or total > enrolment:
            raise SystemExit(f"{csv_path}: {district} vote metadata does not reconcile")
        if first["elected_party"] != ranked[0][0] or first["elected_member"] != ranked[0][0]:
            raise SystemExit(f"{csv_path}: {district} local leader is wrong")
        if int(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{csv_path}: {district} margin is wrong")
        if float(first["turnout_pct"]) != round(total / enrolment * 100, 2):
            raise SystemExit(f"{csv_path}: {district} turnout is wrong")
        if int(first["round_number"]) != expected["round"]:
            raise SystemExit(f"{csv_path}: {district} round number is wrong")
        wins[first["elected_party"]] += 1
        metadata.update({"enrolment": enrolment, "formal": formal, "informal": informal})
        codes[district] = first["constituency_code"]
        district_seats += int(first.get("district_seats") or 0)

    if dict(wins) != expected["wins"]:
        raise SystemExit(f"{csv_path}: local leader counts changed: {dict(wins)}")
    for key in ("enrolment", "formal", "informal"):
        if metadata[key] != expected[key]:
            raise SystemExit(f"{csv_path}: election-wide {key} changed")
    if "district_seats" in expected and district_seats != expected["district_seats"]:
        raise SystemExit(f"{csv_path}: mapped district seats changed")

    boundary_path = Path("data") / str(expected["boundaries"])
    collection = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if len(features) != expected["areas"]:
        raise SystemExit(f"{boundary_path}: expected {expected['areas']} features")
    boundary_codes = {}
    for feature in features:
        properties = feature["properties"]
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{boundary_path}: invalid geometry for {properties.get('district')}")
        boundary_codes[properties["district"]] = properties["constituency_code"]
    if boundary_codes != codes:
        raise SystemExit(f"{boundary_path}: district names/codes do not match {csv_path}")


def main() -> None:
    for stem, expected in ELECTIONS.items():
        validate_election(stem, expected)
    print("Greece, Poland and Belgium validation passed: 8 selector entries, 198 mapped areas")


if __name__ == "__main__":
    main()
