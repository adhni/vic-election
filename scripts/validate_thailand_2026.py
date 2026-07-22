#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


CSV_PATH = Path("data/thailand_2026_fpp.csv")
BOUNDARY_PATH = Path("data/thailand_2026_constituency_cartogram.geojson")
EXPECTED_WINNERS = {
    "Bhumjaithai": 173,
    "People's Party": 88,
    "Pheu Thai": 58,
    "Klatham": 56,
    "Democrat": 10,
    "Thai Ruam Palang": 5,
    "Prachachat": 4,
    "Palang Pracharath": 4,
    "Thai Sang Thai": 1,
    "New Opportunity": 1,
}


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["district"]].append(row)
    if len(groups) != 400 or len(rows) != 3527:
        raise SystemExit(f"Expected 400 constituencies and 3,527 candidates, found {len(groups)} and {len(rows)}")

    winners = Counter()
    codes = set()
    provinces = set()
    for district, district_rows in groups.items():
        if any(row["row_type"] != "first" for row in district_rows):
            raise SystemExit(f"{district}: expected compact first-past-the-post rows only")
        metadata = district_rows[0]
        votes = [(row["candidate"], row["candidate_party"], int(row["votes"])) for row in district_rows]
        if len({name for name, _, _ in votes}) != len(votes):
            raise SystemExit(f"{district}: duplicate candidate names")
        ranked = sorted(votes, key=lambda item: (-item[2], item[0]))
        if (metadata["elected_member"], metadata["elected_party"]) != ranked[0][:2]:
            raise SystemExit(f"{district}: elected-member metadata does not match candidate votes")
        formal = int(metadata["formal_votes"])
        if sum(votes for _, _, votes in ranked) != formal:
            raise SystemExit(f"{district}: candidate votes do not equal valid votes")
        if district == "Suphan Buri 2":
            if any(metadata[field] for field in ("enrolment", "informal_votes", "total_votes", "turnout_pct")):
                raise SystemExit("Suphan Buri 2 must not invent unavailable post-recount ballot metadata")
            if ranked[:2] != [
                ("Natthawut Prasoetsuwan", "Bhumjaithai", 45267),
                ("Nutra Sisangngam", "People's Party", 23277),
            ]:
                raise SystemExit(f"Suphan Buri 2 final certification check failed: {ranked[:2]}")
            if not metadata["result_note"]:
                raise SystemExit("Suphan Buri 2 is missing its recount disclosure")
        else:
            informal = int(metadata["informal_votes"])
            total = int(metadata["total_votes"])
            enrolment = int(metadata["enrolment"])
            if total != formal + informal or total > enrolment:
                raise SystemExit(f"{district}: ballot totals do not reconcile")
            if abs(float(metadata["turnout_pct"]) - total / enrolment * 100) > 0.011:
                raise SystemExit(f"{district}: turnout does not reconcile")
        winners[ranked[0][1]] += 1
        codes.add(metadata["constituency_code"])
        provinces.add(metadata["electorate_type"])
    if winners != Counter(EXPECTED_WINNERS):
        raise SystemExit(f"Unexpected winning-party totals: {winners}")
    if len(codes) != 400 or len(provinces) != 77:
        raise SystemExit(f"Expected 400 unique codes and 77 provinces, found {len(codes)} and {len(provinces)}")

    geojson = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    boundary_names = {feature["properties"]["district"] for feature in features}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in features}
    if len(features) != 400 or boundary_names != set(groups) or boundary_codes != codes:
        raise SystemExit("Thailand cartogram does not match all 400 result constituencies")
    if any(feature["properties"].get("geometry_note") != "Equal-area constituency cartogram cell; not a legal boundary" for feature in features):
        raise SystemExit("Thailand cartogram cells must retain their geometry disclosure")
    print("Thailand 2026 validation passed: 400 constituencies, 3,527 candidates, 77 provinces, final 8 April certification included")


if __name__ == "__main__":
    main()
