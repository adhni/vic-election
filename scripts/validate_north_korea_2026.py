#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

from shapely.geometry import shape


CSV_PATH = Path("data/north_korea_2026_spa.csv")
BOUNDARY_PATH = Path("data/north_korea_2026_spa_cartogram.geojson")
EXPECTED_SEATS = 687


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_SEATS:
        raise SystemExit(f"Expected {EXPECTED_SEATS} result rows, found {len(rows)}")

    codes = {row["constituency_code"] for row in rows}
    districts = {row["district"] for row in rows}
    expected_codes = {f"KP-{number:03d}" for number in range(1, EXPECTED_SEATS + 1)}
    if codes != expected_codes or len(districts) != EXPECTED_SEATS:
        raise SystemExit("Constituency codes or names are incomplete")
    if rows[0]["district"] != "Mangyongdae No. 1" or rows[0]["candidate"] != "Jo Myong Chol":
        raise SystemExit("First official constituency control changed")
    if rows[-1]["district"] != "Kumgangsan No. 687" or rows[-1]["candidate"] != "Kim Pok Nam":
        raise SystemExit("Final official constituency control changed")

    for row in rows:
        if row["contest_status"] != "single-candidate":
            raise SystemExit(f"{row['district']}: unexpected contest status")
        if row["candidate"] != row["elected_member"]:
            raise SystemExit(f"{row['district']}: candidate and elected deputy differ")
        if row["candidate_party"] != "Affiliation not published":
            raise SystemExit(f"{row['district']}: unsupported party attribution")
        unavailable = (
            "enrolment", "formal_votes", "informal_votes", "total_votes",
            "turnout_pct", "majority", "votes",
        )
        if any(row[field] for field in unavailable):
            raise SystemExit(f"{row['district']}: invented constituency vote metadata")

    boundaries = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    features = boundaries["features"]
    if len(features) != EXPECTED_SEATS:
        raise SystemExit(f"Expected {EXPECTED_SEATS} cartogram cells")
    feature_codes = {
        feature["properties"]["constituency_code"] for feature in features
    }
    feature_districts = {
        feature["properties"]["district"] for feature in features
    }
    if feature_codes != codes or feature_districts != districts:
        raise SystemExit("Result/cartogram join mismatch")
    for feature in features:
        geometry = shape(feature["geometry"])
        if (
            geometry.is_empty
            or not geometry.is_valid
            or abs(geometry.area - 1) > 1e-9
        ):
            raise SystemExit(
                f"{feature['properties']['constituency_code']}: invalid seat cell"
            )
        if "not a geographic" not in feature["properties"]["geometry_note"]:
            raise SystemExit("Cartogram disclosure is missing")

    print(
        "North Korea 2026 validation passed: "
        "687 elected deputies, no invented constituency vote totals, 687 seat cells"
    )


if __name__ == "__main__":
    main()
