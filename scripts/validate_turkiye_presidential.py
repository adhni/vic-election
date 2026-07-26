#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape


CONFIG = {
    "turkiye_2023_president_round_1_province_fpp.csv": {
        "Recep Tayyip Erdoğan": 26_086_102,
        "Muharrem İnce": 216_470,
        "Kemal Kılıçdaroğlu": 23_873_749,
        "Sinan Oğan": 2_796_613,
    },
    "turkiye_2023_president_round_2_province_fpp.csv": {
        "Recep Tayyip Erdoğan": 26_690_529,
        "Kemal Kılıçdaroğlu": 24_728_027,
    },
    "turkiye_2018_president_province_fpp.csv": {
        "Muharrem İnce": 14_951_788,
        "Meral Akşener": 3_603_858,
        "Recep Tayyip Erdoğan": 25_436_238,
        "Selahattin Demirtaş": 4_039_390,
        "Temel Karamollaoğlu": 434_882,
        "Doğu Perinçek": 95_928,
    },
    "turkiye_2014_president_province_fpp.csv": {
        "Recep Tayyip Erdoğan": 20_670_826,
        "Selahattin Demirtaş": 3_914_359,
        "Ekmeleddin Mehmet İhsanoğlu": 15_434_167,
    },
}
BOUNDARY_NAME = "turkiye_province_boundaries.geojson"


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, ValueError) as exc:
        raise SystemExit(
            f"Invalid {field!r} in {row.get('district', 'unknown province')}"
        ) from exc


def validate_csv(data_dir: Path, name: str, expected: dict[str, int],
                 boundary_codes: set[str]) -> None:
    path = data_dir / name
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_province: dict[str, list[dict[str, str]]] = defaultdict(list)
    totals: Counter[str] = Counter()
    for row in rows:
        if row["row_type"] != "first" or integer(row, "round_number") != 0:
            raise SystemExit(f"{path}: non-compact row in {row['district']}")
        if row["contest_status"] != "official":
            raise SystemExit(f"{path}: non-official row in {row['district']}")
        code = row["constituency_code"]
        by_province[code].append(row)
        votes = integer(row, "votes")
        if votes < 0:
            raise SystemExit(f"{path}: negative votes in {row['district']}")
        totals[row["candidate"]] += votes
    if set(by_province) != boundary_codes:
        raise SystemExit(f"{path}: CSV/boundary code mismatch")
    if dict(totals) != expected:
        raise SystemExit(
            f"{path}: candidate totals changed\nexpected {expected}\nactual {dict(totals)}"
        )

    metadata = (
        "district", "elected_member", "elected_party", "enrolment", "formal_votes",
        "informal_votes", "total_votes", "turnout_pct", "majority",
        "electorate_type", "contest_status", "result_note",
    )
    for code, province_rows in by_province.items():
        for field in metadata:
            if len({row[field] for row in province_rows}) != 1:
                raise SystemExit(f"{path}: inconsistent {field} metadata for {code}")
        first = province_rows[0]
        ordered = sorted(
            (integer(row, "votes"), row["candidate"]) for row in province_rows
        )
        formal = sum(votes for votes, _ in ordered)
        if formal != integer(first, "formal_votes"):
            raise SystemExit(f"{path}: formal-vote mismatch for {code}")
        total = integer(first, "total_votes")
        if formal + integer(first, "informal_votes") != total:
            raise SystemExit(f"{path}: ballot-total mismatch for {code}")
        enrolment = integer(first, "enrolment")
        turnout = float(first["turnout_pct"])
        if abs(turnout - total * 100 / enrolment) > 0.01:
            raise SystemExit(f"{path}: turnout mismatch for {code}")
        winner_votes, winner = ordered[-1]
        runner_up = ordered[-2][0]
        if first["elected_member"] != winner or first["elected_party"] != winner:
            raise SystemExit(f"{path}: winner mismatch for {code}")
        if integer(first, "majority") != winner_votes - runner_up:
            raise SystemExit(f"{path}: majority mismatch for {code}")
    print(f"{name}: 81 provinces, {len(rows)} candidate rows")


def main() -> None:
    data_dir = Path("data")
    boundary = json.loads(
        (data_dir / BOUNDARY_NAME).read_text(encoding="utf-8")
    )
    features = boundary.get("features", [])
    codes = [
        feature.get("properties", {}).get("constituency_code")
        for feature in features
    ]
    if len(codes) != 81 or len(set(codes)) != 81:
        raise SystemExit(f"{BOUNDARY_NAME}: expected 81 unique province codes")
    for feature in features:
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(
                f"{BOUNDARY_NAME}: invalid geometry for "
                f"{feature['properties'].get('constituency_code')}"
            )
    boundary_codes = set(codes)
    for name, expected in CONFIG.items():
        validate_csv(data_dir, name, expected, boundary_codes)
    print("Türkiye presidential validation passed.")


if __name__ == "__main__":
    main()
