#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


DATA = Path("data")
FILES = {
    "mayor": (
        DATA / "london_2024_mayor_fpp.csv",
        182,
        (2_484_432, 11_127, 2_495_559),
        {"Labour": 9, "Conservative": 5},
    ),
    "constituency": (
        DATA / "london_2024_assembly_constituency_fpp.csv",
        80,
        (2_473_555, 19_878, 2_493_433),
        {"Labour": 10, "Conservative": 3, "Liberal Democrats": 1},
    ),
    "london-wide": (
        DATA / "london_2024_assembly_london_wide_fpp.csv",
        210,
        (2_476_687, 17_226, 2_493_913),
        {"Labour": 10, "Conservative": 4},
    ),
}

EXPECTED_MAYOR_TOTALS = {
    "AMIN, Femy": 29_280,
    "BINFACE, Count": 24_260,
    "BLACKIE, Rob": 145_184,
    "CAMPBELL, Natalie Denise": 47_815,
    "COX, Howard": 78_865,
    "GALLAGHER, Amy": 34_449,
    "GARBETT, Zoë": 145_114,
    "GHULATI, Tarun": 24_702,
    "HALL, Susan Mary": 812_397,
    "KHAN, Sadiq": 1_088_225,
    "MICHLI, Andreas Christoffi": 26_121,
    "ROSE, Brian Benedict": 7_501,
    "SCANLON, Nick": 20_519,
}

EXPECTED_LIST_TOTALS = {
    "Animal Welfare Party - People, Animals, Environment": 41_303,
    "Britain First": 32_085,
    "Christian Peoples Alliance": 26_798,
    "Communist Party of Britain": 10_915,
    "Conservatives": 648_269,
    "Heritage Party": 4_431,
    "Labour Party": 951_056,
    "Liberal Democrats": 215_682,
    "ReformUK – London Deserves Better": 145_409,
    "Rejoin EU": 62_528,
    "Social Democratic Party": 23_021,
    "The Green Party": 286_746,
    "Laurence Fox": 13_795,
    "Farah London": 13_048,
    "Gabe Romualdo": 1_601,
}

EXPECTED_LONDON_WIDE_MEMBERS = (
    "Siân Berry", "Susan Mary Hall", "Alex Wilson", "Caroline Russell", "Shaun Bailey",
    "Emma Dawn Best", "Hina Bokhari", "Zack Polanski", "Andrew Boff", "Elly Baker",
    "Alessandro Georgiou",
)


def integer(value: str) -> int:
    return int(float(value or 0))


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_file(
    label: str,
    path: Path,
    expected_rows: int,
    expected_totals: tuple[int, int, int],
    expected_winners: dict[str, int],
) -> tuple[set[str], dict[str, int]]:
    rows = load(path)
    if len(rows) != expected_rows:
        raise SystemExit(f"{label}: expected {expected_rows} rows, found {len(rows)}")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["district"]].append(row)
    if len(grouped) != 14:
        raise SystemExit(f"{label}: expected 14 constituencies, found {len(grouped)}")

    codes = set()
    national_candidates: Counter[str] = Counter()
    national_formal = national_informal = national_total = 0
    winner_counts: Counter[str] = Counter()
    for district, district_rows in grouped.items():
        first = district_rows[0]
        metadata = (
            "elected_member", "elected_party", "enrolment", "formal_votes", "informal_votes",
            "total_votes", "turnout_pct", "majority", "constituency_code", "contest_status",
        )
        for key in metadata:
            if len({row[key] for row in district_rows}) != 1:
                raise SystemExit(f"{label} / {district}: inconsistent {key}")
        if first["contest_status"] != "official" or first["row_type"] != "first":
            raise SystemExit(f"{label} / {district}: unexpected contest status or row type")
        formal = integer(first["formal_votes"])
        informal = integer(first["informal_votes"])
        total = integer(first["total_votes"])
        enrolment = integer(first["enrolment"])
        if formal + informal != total:
            raise SystemExit(f"{label} / {district}: ballot totals do not reconcile")
        if abs(float(first["turnout_pct"]) - round(total / enrolment * 100, 2)) > 0.001:
            raise SystemExit(f"{label} / {district}: turnout does not reconcile")
        candidate_votes = {row["candidate"]: integer(row["votes"]) for row in district_rows}
        if sum(candidate_votes.values()) != formal:
            raise SystemExit(f"{label} / {district}: candidate/list votes do not equal formal votes")
        ranked = sorted(candidate_votes.items(), key=lambda item: (-item[1], item[0]))
        winner = ranked[0][0]
        if winner != first["elected_member"]:
            raise SystemExit(f"{label} / {district}: stored local leader is incorrect")
        winner_party = next(row["candidate_party"] for row in district_rows if row["candidate"] == winner)
        if winner_party != first["elected_party"]:
            raise SystemExit(f"{label} / {district}: stored local leading party is incorrect")
        if integer(first["majority"]) != ranked[0][1] - ranked[1][1]:
            raise SystemExit(f"{label} / {district}: winning margin is incorrect")
        codes.add(first["constituency_code"])
        national_candidates.update(candidate_votes)
        national_formal += formal
        national_informal += informal
        national_total += total
        winner_counts[first["elected_party"]] += 1

    if (national_formal, national_informal, national_total) != expected_totals:
        raise SystemExit(f"{label}: London totals changed")
    if dict(winner_counts) != expected_winners:
        raise SystemExit(f"{label}: local winner composition changed: {dict(winner_counts)}")
    return codes, dict(national_candidates)


def main() -> None:
    result_codes = None
    candidate_totals: dict[str, dict[str, int]] = {}
    for label, (path, row_count, totals, winners) in FILES.items():
        codes, national = validate_file(label, path, row_count, totals, winners)
        if result_codes is not None and codes != result_codes:
            raise SystemExit(f"{label}: constituency identifiers differ across contests")
        result_codes = codes
        candidate_totals[label] = national

    if candidate_totals["mayor"] != EXPECTED_MAYOR_TOTALS:
        raise SystemExit("Mayor candidate totals do not match the official declaration")
    if candidate_totals["london-wide"] != EXPECTED_LIST_TOTALS:
        raise SystemExit("London-wide list totals do not match the official declaration")

    boundaries = json.loads(
        (DATA / "london_2024_assembly_constituencies.geojson").read_text(encoding="utf-8")
    )
    boundary_codes = {feature["properties"]["constituency_code"] for feature in boundaries["features"]}
    if len(boundaries["features"]) != 14 or boundary_codes != result_codes:
        raise SystemExit("London boundary/result identifiers do not match exactly")

    members = load(DATA / "london_2024_assembly_members.csv")
    if len(members) != 25:
        raise SystemExit(f"Expected 25 Assembly members, found {len(members)}")
    direct = [row for row in members if row["seat_type"] == "constituency"]
    london_wide = sorted(
        (row for row in members if row["seat_type"] == "london-wide"),
        key=lambda row: integer(row["seat_number"]),
    )
    if len(direct) != 14 or len(london_wide) != 11:
        raise SystemExit("Expected 14 direct and 11 London-wide Assembly members")
    if tuple(row["member"] for row in london_wide) != EXPECTED_LONDON_WIDE_MEMBERS:
        raise SystemExit("London-wide elected-member order does not match the official allocation")
    if Counter(row["party"] for row in members) != {
        "Labour": 11, "Conservative": 8, "Green Party": 3,
        "Liberal Democrats": 2, "Reform UK": 1,
    }:
        raise SystemExit("Complete 25-member Assembly composition is incorrect")
    print(
        "London 2024 validation passed: 14 constituencies, three ballots, "
        "official mayoral/list totals, 14 direct members, and 11 London-wide members"
    )


if __name__ == "__main__":
    main()
