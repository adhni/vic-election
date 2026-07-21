#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_indonesia_presidential import CANDIDATES, PAPUA_TENGAH_NOTE, PROVINCE_TOTALS


FILES = {
    "province": (
        Path("data/indonesia_2024_president_province_fpp.csv"),
        Path("data/indonesia_2024_province_boundaries.geojson"),
        38,
    ),
    "kabupaten/kota": (
        Path("data/indonesia_2024_president_kabupaten_kota_fpp.csv"),
        Path("data/indonesia_2024_kabupaten_kota_boundaries.geojson"),
        514,
    ),
}


def read_groups(path: Path) -> dict[str, list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    return groups


def validate_level(level: str, csv_path: Path, boundary_path: Path, expected: int):
    groups = read_groups(csv_path)
    if len(groups) != expected:
        raise SystemExit(f"{level}: expected {expected} areas, found {len(groups)}")
    expected_candidates = {candidate for candidate, _ in CANDIDATES}
    expected_tickets = {ticket for _, ticket in CANDIDATES}
    codes = set()
    winners = Counter()
    province_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    notes = set()
    for district, rows in groups.items():
        if len(rows) != 3 or {row["candidate"] for row in rows} != expected_candidates:
            raise SystemExit(f"{level} {district}: expected exactly three candidate-pair rows")
        if {row["candidate_party"] for row in rows} != expected_tickets:
            raise SystemExit(f"{level} {district}: unexpected candidate-pair labels")
        meta = rows[0]
        code = meta["constituency_code"]
        if code in codes or any(row["constituency_code"] != code for row in rows):
            raise SystemExit(f"{level} {district}: duplicate or inconsistent area code")
        codes.add(code)
        formal = int(meta["formal_votes"])
        candidate_votes = sum(int(row["votes"]) for row in rows)
        if candidate_votes != formal or int(meta["total_votes"]) != formal:
            raise SystemExit(f"{level} {district}: valid votes do not reconcile")
        if int(meta["enrolment"]) or int(meta["informal_votes"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{level} {district}: unavailable turnout metadata should remain zero")
        ranked = sorted(rows, key=lambda row: (-int(row["votes"]), row["candidate"]))
        if (meta["elected_member"], meta["elected_party"]) != (
            ranked[0]["candidate"], ranked[0]["candidate_party"]
        ):
            raise SystemExit(f"{level} {district}: winner metadata does not match candidate votes")
        if int(meta["majority"]) != int(ranked[0]["votes"]) - int(ranked[1]["votes"]):
            raise SystemExit(f"{level} {district}: majority does not match top-two gap")
        winners[meta["elected_party"]] += 1
        notes.add(meta["result_note"])
        if level == "kabupaten/kota":
            province_code = code[:2]
            for index, (_, ticket) in enumerate(CANDIDATES):
                province_totals[province_code][index] += int(next(row["votes"] for row in rows if row["candidate_party"] == ticket))

    expected_notes = {"", PAPUA_TENGAH_NOTE}
    if notes != expected_notes:
        raise SystemExit(f"{level}: unexpected result-note set")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {str(feature["properties"]["constituency_code"]) for feature in features}
    if len(features) != expected or names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"{level}: boundary/result mismatch")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{level} {feature['properties']['district']}: invalid geometry")

    return groups, winners, province_totals


def main() -> None:
    province_groups, province_winners, _ = validate_level("province", *FILES["province"])
    kabupaten_groups, kabupaten_winners, kabupaten_totals = validate_level(
        "kabupaten/kota", *FILES["kabupaten/kota"]
    )
    if province_winners != Counter({"Prabowo–Gibran": 36, "Anies–Muhaimin": 2}):
        raise SystemExit(f"Unexpected province winner counts: {province_winners}")
    if kabupaten_winners != Counter({"Prabowo–Gibran": 455, "Anies–Muhaimin": 49, "Ganjar–Mahfud": 10}):
        raise SystemExit(f"Unexpected kabupaten/kota winner counts: {kabupaten_winners}")

    certified = {code: tuple(votes) for code, _, *votes in PROVINCE_TOTALS}
    mismatches = {
        code: tuple(kabupaten_totals[code][index] - expected[index] for index in range(3))
        for code, expected in certified.items()
        if tuple(kabupaten_totals[code]) != expected
    }
    if mismatches != {"94": (-7_524, -46_859, -12_622)}:
        raise SystemExit(f"Unexpected kabupaten-to-province mismatches: {mismatches}")

    hulu = kabupaten_groups["Hulu Sungai Selatan"]
    ranked = sorted(hulu, key=lambda row: -int(row["votes"]))
    if ranked[0]["candidate_party"] != "Anies–Muhaimin" or int(ranked[0]["votes"]) - int(ranked[1]["votes"]) != 141:
        raise SystemExit("Hulu Sungai Selatan closest-area spot check failed")
    if int(province_groups["Aceh"][0]["formal_votes"]) != 3_221_235:
        raise SystemExit("Aceh certified-total spot check failed")

    print(
        "Indonesia Presidential 2024 validation passed: 38 certified provinces, "
        "514 kabupaten/kota, 1 disclosed Papua Tengah aggregate mismatch"
    )


if __name__ == "__main__":
    main()
