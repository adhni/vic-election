#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from shapely.geometry import shape


SPECS = {
    "finland-2023": {
        "csv": Path("data/finland_2023_parliament_fpp.csv"),
        "boundaries": Path("data/finland_2023_parliament_boundaries.geojson"),
        "areas": 309,
        "rows": 4_524,
        "formal": 3_095_604,
        "informal": 0,
        "enrolment": 0,
        "special_statuses": {"aggregated": 16},
    },
    "finland-2019": {
        "csv": Path("data/finland_2019_parliament_fpp.csv"),
        "boundaries": Path("data/finland_2019_parliament_boundaries.geojson"),
        "areas": 311,
        "rows": 4_819,
        "formal": 3_081_916,
        "informal": 0,
        "enrolment": 0,
        "special_statuses": {"aggregated": 16},
    },
    "denmark-2026": {
        "csv": Path("data/denmark_2026_folketing_fpp.csv"),
        "boundaries": Path("data/denmark_2026_folketing_boundaries.geojson"),
        "areas": 98,
        "rows": 1_199,
        "formal": 3_567_625,
        "informal": 46_647,
        "enrolment": 4_303_429,
    },
    "denmark-2022": {
        "csv": Path("data/denmark_2022_folketing_fpp.csv"),
        "boundaries": Path("data/denmark_2022_folketing_boundaries.geojson"),
        "areas": 99,
        "rows": 1_481,
        "formal": 3_533_951,
        "informal": 58_871,
        "enrolment": 4_269_048,
    },
    "austria-2024": {
        "csv": Path("data/austria_2024_national_council_fpp.csv"),
        "boundaries": Path("data/austria_2024_national_council_boundaries.geojson"),
        "areas": 2_093,
        "rows": 21_262,
        "formal": 4_758_596,
        "informal": 45_378,
        "enrolment": 0,
        "special_statuses": {"tied": 8},
    },
    "austria-2019": {
        "csv": Path("data/austria_2019_national_council_fpp.csv"),
        "boundaries": Path("data/austria_2019_national_council_boundaries.geojson"),
        "areas": 2_096,
        "rows": 16_752,
        "formal": 4_062_147,
        "informal": 52_089,
        "enrolment": 0,
        "special_statuses": {"tied": 1},
    },
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def validate(key: str, spec: dict[str, object]) -> None:
    rows = read_rows(spec["csv"])
    if len(rows) != spec["rows"]:
        raise SystemExit(f"{key}: expected {spec['rows']} rows, found {len(rows)}")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["constituency_code"], []).append(row)
    if len(grouped) != spec["areas"]:
        raise SystemExit(f"{key}: expected {spec['areas']} areas, found {len(grouped)}")

    formal_total = informal_total = enrolment_total = 0
    special_statuses: Counter[str] = Counter()
    district_names: set[str] = set()
    for code, district_rows in grouped.items():
        metadata = {
            (
                row["district"],
                int(row["formal_votes"]),
                int(row["informal_votes"]),
                int(row["total_votes"]),
                int(row["enrolment"]),
                row["row_type"],
                int(row["district_seats"]),
            )
            for row in district_rows
        }
        if len(metadata) != 1:
            raise SystemExit(f"{key} {code}: inconsistent district metadata")
        district, formal, informal, total, enrolment, row_type, district_seats = metadata.pop()
        if row_type != "first" or district_seats != 0:
            raise SystemExit(f"{key} {district}: expected compact local party rows")
        if formal + informal != total:
            raise SystemExit(f"{key} {district}: ballot totals do not reconcile")
        if sum(int(row["votes"]) for row in district_rows) != formal:
            raise SystemExit(f"{key} {district}: party votes do not equal valid votes")
        status = district_rows[0]["contest_status"]
        if status != "official":
            special_statuses[status] += 1
            if any(row["elected_member"] or row["elected_party"] for row in district_rows):
                raise SystemExit(f"{key} {district}: non-leader result declares a winner")
        if district in district_names:
            raise SystemExit(f"{key}: duplicate district name {district}")
        district_names.add(district)
        formal_total += formal
        informal_total += informal
        enrolment_total += enrolment

    expected_totals = (spec["formal"], spec["informal"], spec["enrolment"])
    actual_totals = (formal_total, informal_total, enrolment_total)
    if actual_totals != expected_totals:
        raise SystemExit(
            f"{key}: control totals changed; expected {expected_totals}, found {actual_totals}"
        )
    if dict(special_statuses) != spec.get("special_statuses", {}):
        raise SystemExit(
            f"{key}: unexpected special outcomes; expected "
            f"{spec.get('special_statuses', {})}, found {dict(special_statuses)}"
        )

    boundary_data = json.loads(spec["boundaries"].read_text(encoding="utf-8"))
    features = boundary_data["features"]
    if len(features) != spec["areas"]:
        raise SystemExit(f"{key}: unexpected boundary feature count")
    feature_codes = {
        feature["properties"]["constituency_code"]
        for feature in features
    }
    if feature_codes != set(grouped):
        raise SystemExit(f"{key}: result and boundary codes do not match")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{key}: invalid geometry for {feature['properties']['constituency_code']}"
            )

    print(
        f"{key}: {len(grouped)} areas, {len(rows)} rows, "
        f"{formal_total:,} mapped valid votes"
    )


def main() -> None:
    for key, spec in SPECS.items():
        validate(key, spec)
    print("Finland, Denmark, and Austria validation passed")


if __name__ == "__main__":
    main()
