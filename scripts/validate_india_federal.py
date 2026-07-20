#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


EXPECTED_WINNERS = {
    "Bharatiya Janata Party": 240,
    "Indian National Congress": 99,
    "Samajwadi Party": 37,
    "All India Trinamool Congress": 29,
    "Dravida Munnetra Kazhagam": 22,
    "Telugu Desam": 16,
    "Janata Dal (United)": 12,
    "Shiv Sena (Uddhav Balasaheb Thackeray)": 9,
    "Nationalist Congress Party – Sharadchandra Pawar": 8,
    "Independent": 7,
    "Shiv Sena": 7,
    "Lok Janshakti Party(Ram Vilas)": 5,
    "Communist Party of India (Marxist)": 4,
    "Rashtriya Janata Dal": 4,
    "Yuvajana Sramika Rythu Congress Party": 4,
    "Aam Aadmi Party": 3,
    "Indian Union Muslim League": 3,
    "Jharkhand Mukti Morcha": 3,
    "Communist Party of India": 2,
    "Communist Party of India (Marxist-Leninist) (Liberation)": 2,
    "Jammu & Kashmir National Conference": 2,
    "Janasena Party": 2,
    "Janata Dal (Secular)": 2,
    "Rashtriya Lok Dal": 2,
    "Viduthalai Chiruthaigal Katchi": 2,
    "AJSU Party": 1,
    "Aazad Samaj Party (Kanshi Ram)": 1,
    "All India Majlis-E-Ittehadul Muslimeen": 1,
    "Apna Dal (Soneylal)": 1,
    "Asom Gana Parishad": 1,
    "Bharat Adivasi Party": 1,
    "Hindustani Awam Morcha (Secular)": 1,
    "Kerala Congress": 1,
    "Marumalarchi Dravida Munnetra Kazhagam": 1,
    "Nationalist Congress Party": 1,
    "Rashtriya Loktantrik Party": 1,
    "Revolutionary Socialist Party": 1,
    "Shiromani Akali Dal": 1,
    "Sikkim Krantikari Morcha": 1,
    "United People’s Party, Liberal": 1,
    "Voice of the People Party": 1,
    "Zoram People’s Movement": 1,
}

EXPECTED_AREAS = {
    "Uttar Pradesh": 80, "Maharashtra": 48, "West Bengal": 42, "Bihar": 40,
    "Tamil Nadu": 39, "Madhya Pradesh": 29, "Karnataka": 28, "Gujarat": 26,
    "Andhra Pradesh": 25, "Rajasthan": 25, "Odisha": 21, "Kerala": 20,
    "Telangana": 17, "Assam": 14, "Jharkhand": 14, "Punjab": 13,
    "Chhattisgarh": 11, "Haryana": 10, "NCT of Delhi": 7, "Jammu and Kashmir": 5,
    "Uttarakhand": 5, "Himachal Pradesh": 4, "Arunachal Pradesh": 2, "Goa": 2,
    "Manipur": 2, "Meghalaya": 2, "Tripura": 2, "Andaman & Nicobar Islands": 1,
    "Chandigarh": 1, "Dadra & Nagar Haveli and Daman & Diu": 2, "Ladakh": 1,
    "Lakshadweep": 1, "Mizoram": 1, "Nagaland": 1, "Puducherry": 1, "Sikkim": 1,
}

SPOT_CHECKS = {
    "Mumbai North West": ("Ravindra Dattaram Waikar", 452_644, 48),
    "Attingal": ("Adv Adoor Prakash", 328_051, 684),
    "Jajpur": ("Rabindra Narayan Behera", 534_239, 1_587),
    "Varanasi": ("Narendra Modi", 612_970, 152_513),
    "Rae Bareli": ("Rahul Gandhi", 687_649, 390_030),
}


def main() -> None:
    csv_path = Path("data/india_2024_fpp.csv")
    boundary_path = Path("data/india_2024_parliamentary_boundaries.geojson")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 543:
        raise SystemExit(f"Expected 543 constituencies, found {len(groups)}")

    winners = Counter()
    areas = Counter()
    codes = set()
    candidates = 0
    nota_rows = 0
    uncontested = []
    national_totals = Counter()
    for district, district_rows in groups.items():
        first = [row for row in district_rows if row["row_type"] == "first"]
        final = [row for row in district_rows if row["row_type"] == "final"]
        first_result = {(row["candidate"], row["candidate_party"]): int(row["votes"]) for row in first}
        if len(first_result) != len(first) or final:
            raise SystemExit(f"{district}: duplicate candidates or non-compact FPTP rows")
        meta = first[0]
        is_uncontested = meta["contest_status"] == "uncontested"
        if is_uncontested:
            uncontested.append(district)
            if len(first) != 1 or any(int(meta[field]) for field in ("formal_votes", "informal_votes", "total_votes")):
                raise SystemExit(f"{district}: invalid uncontested result")
            ranked = list(first_result.items())
        else:
            if len(first) < 2 or meta["contest_status"] != "official":
                raise SystemExit(f"{district}: invalid contested result")
            formal = int(meta["formal_votes"])
            informal = int(meta["informal_votes"])
            total = int(meta["total_votes"])
            enrolment = int(meta["enrolment"])
            if sum(first_result.values()) != formal or total != formal + informal:
                raise SystemExit(f"{district}: vote totals do not reconcile")
            if enrolment <= 0 or abs(float(meta["turnout_pct"]) - total / enrolment * 100) > 0.011:
                raise SystemExit(f"{district}: turnout metadata does not reconcile")
            ranked = sorted(first_result.items(), key=lambda item: (-item[1], item[0][0]))
        winner_name, winner_party = ranked[0][0]
        if (meta["elected_member"], meta["elected_party"]) != (winner_name, winner_party):
            raise SystemExit(f"{district}: winner metadata does not match the result")
        winners[winner_party] += 1
        areas[meta["electorate_type"]] += 1
        codes.add(meta["constituency_code"])
        candidates += sum(candidate.casefold() != "nota" for candidate, _ in first_result)
        nota_rows += sum(candidate.casefold() == "nota" for candidate, _ in first_result)
        for field in ("enrolment", "formal_votes", "informal_votes", "total_votes"):
            national_totals[field] += int(meta[field])

    if uncontested != ["Surat"]:
        raise SystemExit(f"Unexpected uncontested seats: {uncontested}")
    if candidates != 8360 or nota_rows != 542 or len(rows) != 8_902:
        raise SystemExit(f"Unexpected row totals: {candidates} candidates, {nota_rows} NOTA, {len(rows)} rows")
    if winners != Counter(EXPECTED_WINNERS):
        raise SystemExit(f"Unexpected winning-party totals: {winners - Counter(EXPECTED_WINNERS)}")
    if areas != Counter(EXPECTED_AREAS):
        raise SystemExit(f"Unexpected state/territory split: {areas - Counter(EXPECTED_AREAS)}")
    if len(codes) != 543:
        raise SystemExit(f"Expected 543 unique constituency codes, found {len(codes)}")
    expected_national = Counter({
        "enrolment": 979_751_847, "formal_votes": 645_363_445,
        "informal_votes": 1_057_424, "total_votes": 646_420_869,
    })
    if national_totals != expected_national:
        raise SystemExit(f"Unexpected national ballot totals: {national_totals}")

    for district, (winner, votes, margin) in SPOT_CHECKS.items():
        ranked = sorted(
            ((row["candidate"], int(row["votes"])) for row in groups[district] if row["row_type"] == "first"),
            key=lambda item: (-item[1], item[0]),
        )
        if ranked[0] != (winner, votes) or ranked[0][1] - ranked[1][1] != margin:
            raise SystemExit(f"{district}: spot check failed: {ranked[:2]}")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != 543 or boundary_names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"Boundary/result mismatch: {sorted(boundary_names ^ set(groups))}")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{feature['properties']['district']}: invalid boundary geometry")
    print("India GE2024 validation passed: 543 constituencies, 8,360 candidates, 542 NOTA options, all totals and boundaries matched")


if __name__ == "__main__":
    main()
