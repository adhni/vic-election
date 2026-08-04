#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


DATA = Path("data")


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def integer(value: str) -> int:
    return int(float(value or 0))


def validate_metadata(entries: list[dict[str, str]], district: str) -> None:
    keys = (
        "council", "ward", "elected_member", "elected_party", "members_to_elect",
        "quota", "enrolment", "formal_votes", "informal_votes", "total_votes",
        "turnout_pct", "majority", "constituency_code", "contest_status",
    )
    for key in keys:
        if len({row[key] for row in entries}) != 1:
            raise SystemExit(f"{district}: inconsistent {key}")
    first = entries[0]
    formal = integer(first["formal_votes"])
    informal = integer(first["informal_votes"])
    total = integer(first["total_votes"])
    if total != formal + informal:
        raise SystemExit(f"{district}: total votes do not equal formal plus informal")
    enrolment = integer(first["enrolment"])
    if enrolment:
        expected = round(total / enrolment * 100, 2)
        if abs(float(first["turnout_pct"]) - expected) > 0.001:
            raise SystemExit(f"{district}: turnout does not reconcile")


def group(entries: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in entries:
        grouped[row["district"]].append(row)
    return grouped


def validate_wards() -> set[str]:
    entries = rows(DATA / "vic_local_2024_wards.csv")
    districts = group(entries)
    if len(districts) != 288:
        raise SystemExit(f"Expected 288 ward contests, found {len(districts)}")
    if len({row["council"] for row in entries}) != 30:
        raise SystemExit("Expected 30 ordinary metropolitan councils")
    uncontested = 0
    codes = set()
    for district, district_rows in districts.items():
        validate_metadata(district_rows, district)
        first_row = district_rows[0]
        codes.add(first_row["constituency_code"])
        first = {row["candidate"]: integer(row["votes"]) for row in district_rows if row["row_type"] == "first"}
        final_round = max(integer(row["round_number"]) for row in district_rows if row["row_type"] == "final")
        final = {
            row["candidate"]: integer(row["votes"])
            for row in district_rows
            if row["row_type"] == "final" and integer(row["round_number"]) == final_round
        }
        if first_row["contest_status"] == "uncontested":
            uncontested += 1
            if integer(first_row["total_votes"]) or set(first) != {first_row["elected_member"]}:
                raise SystemExit(f"{district}: invalid uncontested result")
            continue
        if sum(first.values()) != integer(first_row["formal_votes"]):
            raise SystemExit(f"{district}: first preferences do not equal formal votes")
        winner = max(final, key=final.get)
        if winner != first_row["elected_member"]:
            raise SystemExit(f"{district}: elected candidate does not lead final count")
    if uncontested != 8:
        raise SystemExit(f"Expected 8 uncontested wards, found {uncontested}")

    boundaries = json.loads((DATA / "vic_local_2024_ward_boundaries.geojson").read_text(encoding="utf-8"))
    boundary_codes = {feature["properties"]["constituency_code"] for feature in boundaries["features"]}
    if len(boundaries["features"]) != 288 or boundary_codes != codes:
        raise SystemExit("Ward boundary/result identifiers do not match exactly")
    return codes


def validate_melbourne() -> None:
    leadership = rows(DATA / "melbourne_2024_leadership.csv")
    leadership_group = group(leadership)
    if set(leadership_group) != {"Melbourne — Leadership Team"}:
        raise SystemExit("Missing Melbourne leadership contest")
    validate_metadata(leadership, "Melbourne — Leadership Team")
    meta = leadership[0]
    if (integer(meta["formal_votes"]), integer(meta["informal_votes"])) != (87852, 4603):
        raise SystemExit("Melbourne leadership totals changed")
    if meta["elected_member"] != "REECE, Nick / CAMPBELL, Roshena":
        raise SystemExit("Unexpected Melbourne leadership winner")

    councillors = rows(DATA / "melbourne_2024_councillors.csv")
    councillor_group = group(councillors)
    if set(councillor_group) != {"Melbourne — Councillors"}:
        raise SystemExit("Missing Melbourne councillor contest")
    validate_metadata(councillors, "Melbourne — Councillors")
    meta = councillors[0]
    elected = [name.strip() for name in meta["elected_members"].split(";") if name.strip()]
    if len(elected) != 9 or integer(meta["members_to_elect"]) != 9:
        raise SystemExit("Melbourne councillor elected-member count is not 9")
    if (integer(meta["formal_votes"]), integer(meta["informal_votes"]), integer(meta["quota"])) != (89606, 2139, 8961):
        raise SystemExit("Melbourne councillor totals changed")
    first_total = sum(integer(row["votes"]) for row in councillors if row["row_type"] == "first")
    if first_total != 89606:
        raise SystemExit("Melbourne councillor first preferences do not reconcile")

    boundaries = json.loads((DATA / "melbourne_2024_lga_boundaries.geojson").read_text(encoding="utf-8"))
    districts = {feature["properties"]["district"] for feature in boundaries["features"]}
    if districts != {"Melbourne — Leadership Team", "Melbourne — Councillors"}:
        raise SystemExit("Melbourne contest boundaries do not match")


def main() -> None:
    validate_wards()
    validate_melbourne()
    print("Validated 30 councils, 288 ward contests, 8 uncontested wards, and both Melbourne contests")


if __name__ == "__main__":
    main()
