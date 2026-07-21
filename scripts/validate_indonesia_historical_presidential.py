#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

from build_indonesia_historical_presidential import CANDIDATES, NOTE_2014, PROVINCE_TOTALS_2014


EXPECTED = {
    2019: {
        "province_count": 34,
        "local_count": 514,
        "province_winners": Counter({"Jokowi–Ma'ruf": 21, "Prabowo–Sandiaga": 13}),
        "local_winners": Counter({"Jokowi–Ma'ruf": 297, "Prabowo–Sandiaga": 217}),
    },
    2014: {
        "province_count": 33,
        "local_count": 497,
        "province_winners": Counter({"Jokowi–Kalla": 23, "Prabowo–Hatta": 10}),
        "local_winners": Counter({"Jokowi–Kalla": 327, "Prabowo–Hatta": 166}),
    },
}


def read_groups(path: Path) -> dict[str, list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    return groups


def validate_level(year: int, level: str):
    stem = "province" if level == "province" else "kabupaten_kota"
    csv_path = Path(f"data/indonesia_{year}_president_{stem}_fpp.csv")
    boundary_path = (
        Path("data/indonesia_2024_kabupaten_kota_boundaries.geojson")
        if year == 2019 and level == "local"
        else Path(f"data/indonesia_{year}_{stem}_boundaries.geojson")
    )
    groups = read_groups(csv_path)
    expected_count = EXPECTED[year]["province_count" if level == "province" else "local_count"]
    if len(groups) != expected_count:
        raise SystemExit(f"{year} {level}: expected {expected_count} areas, found {len(groups)}")

    candidate_names = {candidate for candidate, _ in CANDIDATES[year]}
    ticket_names = {ticket for _, ticket in CANDIDATES[year]}
    codes = set()
    winners = Counter()
    unavailable = set()
    province_totals = defaultdict(lambda: defaultdict(int))
    for district, rows in groups.items():
        if len(rows) != 2 or {row["candidate"] for row in rows} != candidate_names:
            raise SystemExit(f"{year} {level} {district}: expected exactly two candidate rows")
        if {row["candidate_party"] for row in rows} != ticket_names:
            raise SystemExit(f"{year} {level} {district}: unexpected ticket labels")
        meta = rows[0]
        code = meta["constituency_code"]
        if code in codes or any(row["constituency_code"] != code for row in rows):
            raise SystemExit(f"{year} {level} {district}: duplicate or inconsistent code")
        codes.add(code)
        formal = sum(int(row["votes"]) for row in rows)
        informal = int(meta["informal_votes"])
        if int(meta["formal_votes"]) != formal or int(meta["total_votes"]) != formal + informal:
            raise SystemExit(f"{year} {level} {district}: ballot totals do not reconcile")
        if int(meta["enrolment"]) or float(meta["turnout_pct"]):
            raise SystemExit(f"{year} {level} {district}: unavailable turnout should remain zero")
        ranked = sorted(rows, key=lambda row: (-int(row["votes"]), row["candidate"]))
        if formal:
            if (meta["elected_member"], meta["elected_party"]) != (
                ranked[0]["candidate"], ranked[0]["candidate_party"]
            ):
                raise SystemExit(f"{year} {level} {district}: winner metadata mismatch")
            winners[meta["elected_party"]] += 1
        else:
            if meta["elected_member"] or meta["elected_party"] or meta["contest_status"] != "unavailable":
                raise SystemExit(f"{year} {level} {district}: zero-vote area must be marked unavailable")
            unavailable.add(district)
        if int(meta["majority"]) != int(ranked[0]["votes"]) - int(ranked[1]["votes"]):
            raise SystemExit(f"{year} {level} {district}: majority mismatch")
        expected_note = NOTE_2014 if year == 2014 and level == "local" else ""
        if meta["result_note"] != expected_note:
            raise SystemExit(f"{year} {level} {district}: unexpected disclosure note")
        if level == "local":
            for row in rows:
                province_totals[meta["electorate_type"]][row["candidate_party"]] += int(row["votes"])

    expected_winners = EXPECTED[year]["province_winners" if level == "province" else "local_winners"]
    if winners != expected_winners:
        raise SystemExit(f"{year} {level}: unexpected winner counts {winners}")
    expected_unavailable = {"Yahukimo", "Mamberamo Tengah", "Dogiyai", "Intan Jaya"} if year == 2014 and level == "local" else set()
    if unavailable != expected_unavailable:
        raise SystemExit(f"{year} {level}: unexpected unavailable areas {sorted(unavailable)}")

    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {str(feature["properties"]["constituency_code"]) for feature in features}
    if len(features) != expected_count or names != set(groups) or boundary_codes != codes:
        raise SystemExit(f"{year} {level}: boundary/result mismatch")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{year} {level} {feature['properties']['district']}: invalid geometry")
    return groups, province_totals


def main() -> None:
    province_2019, _ = validate_level(2019, "province")
    local_2019, aggregates_2019 = validate_level(2019, "local")
    province_2014, _ = validate_level(2014, "province")
    local_2014, aggregates_2014 = validate_level(2014, "local")

    for province, rows in province_2019.items():
        for row in rows:
            if aggregates_2019[province][row["candidate_party"]] != int(row["votes"]):
                raise SystemExit(f"2019 {province}: local rows do not reconcile to certified province total")

    official_2014 = {province: (prabowo, jokowi) for province, prabowo, jokowi in PROVINCE_TOTALS_2014}
    for province, rows in province_2014.items():
        expected_votes = official_2014[province]
        actual_votes = tuple(int(row["votes"]) for row in rows)
        if actual_votes != expected_votes:
            raise SystemExit(f"2014 {province}: certified province total mismatch")
    certified_domestic = sum(sum(votes) for votes in official_2014.values())
    archived_domestic = sum(
        int(rows[0]["formal_votes"])
        for rows in local_2014.values()
    )
    coverage = archived_domestic / certified_domestic
    if not 0.982 < coverage < 0.983:
        raise SystemExit(f"2014 archive coverage changed unexpectedly: {coverage:.6%}")
    if set(aggregates_2014) != set(province_2014):
        raise SystemExit("2014 local rows do not retain the 33-province hierarchy")

    repaired_2019 = {
        "Lampung": (2_853_585, 1_955_689),
        "DKI Jakarta": (3_279_547, 3_066_137),
        "Jawa Barat": (10_750_568, 16_077_446),
    }
    for province, expected in repaired_2019.items():
        rows = province_2019[province]
        if tuple(int(row["votes"]) for row in rows) != expected:
            raise SystemExit(f"2019 {province}: repaired total spot check failed")

    # Later-created units must not appear as 2014 result areas; their polygons
    # are incorporated into the election-time parents by the builder.
    forbidden_2014 = {"Pangandaran", "Pesisir Barat", "Mahakam Ulu", "Muna Barat"}
    if forbidden_2014 & set(local_2014):
        raise SystemExit("2014 contains post-hierarchy split districts")

    print(
        "Indonesia historical presidential validation passed: "
        "2019 has 34 provinces/514 local areas; 2014 has 33 provinces/497 election-time local areas "
        f"with {coverage:.2%} archived domestic coverage"
    )


if __name__ == "__main__":
    main()
