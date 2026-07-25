#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from pathlib import Path

import requests


SOURCE_URL = (
    "https://koreanewsservice.com/en-news/"
    "press-release-of-central-election-committee/"
)
SOURCE_LIST_SHA256 = "c368fb5026867cb814ee64e5292f36c242c5998f006fc46586ce5350cbed6ef1"
EXPECTED_SEATS = 687
GRID_COLUMNS = 24

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)


def download(path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size > 1_000 and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "election-preference-explorer/1.0"},
        timeout=120,
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def parse_deputies(path: Path) -> list[tuple[int, str, str]]:
    source = path.read_text(encoding="utf-8")
    deputies: list[tuple[int, str, str]] = []
    for paragraph in re.findall(r"<p>(.*?)</p>", source, flags=re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", paragraph)).strip()
        match = re.fullmatch(r"(.+?) Constituency No\. (\d+) (.+)", text)
        if match:
            deputies.append((int(match.group(2)), match.group(1), match.group(3)))

    expected_numbers = list(range(1, EXPECTED_SEATS + 1))
    if [number for number, _, _ in deputies] != expected_numbers:
        raise SystemExit(
            f"Expected constituencies 1–{EXPECTED_SEATS} in order; found {len(deputies)}"
        )
    normalized = "\n".join(
        f"{number}|{constituency}|{deputy}"
        for number, constituency, deputy in deputies
    ).encode()
    digest = hashlib.sha256(normalized).hexdigest()
    if digest != SOURCE_LIST_SHA256:
        raise SystemExit(
            f"Normalized official deputy list changed: expected "
            f"{SOURCE_LIST_SHA256}, found {digest}"
        )
    return deputies


def result_rows(deputies: list[tuple[int, str, str]]) -> list[dict[str, object]]:
    note = (
        "The state report publishes the elected deputy but no constituency-level vote "
        "totals or candidate affiliation. National turnout and support figures are "
        "state-reported and are not independently verified."
    )
    return [
        {
            "district": f"{constituency} No. {number}",
            "district_url": SOURCE_URL,
            "distribution_url": "",
            "elected_member": deputy,
            "elected_party": "Affiliation not published",
            "enrolment": "",
            "formal_votes": "",
            "informal_votes": "",
            "total_votes": "",
            "turnout_pct": "",
            "majority": "",
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": deputy,
            "candidate_party": "Affiliation not published",
            "votes": "",
            "electorate_type": "15th Supreme People's Assembly",
            "constituency_code": f"KP-{number:03d}",
            "contest_status": "single-candidate",
            "result_note": note,
        }
        for number, constituency, deputy in deputies
    ]


def cartogram(deputies: list[tuple[int, str, str]]) -> dict[str, object]:
    features = []
    cell = 1.0
    gap = 0.12
    for number, constituency, _ in deputies:
        index = number - 1
        row, column = divmod(index, GRID_COLUMNS)
        x = column * (cell + gap)
        y = -row * (cell + gap)
        ring = [
            [x, y],
            [x + cell, y],
            [x + cell, y - cell],
            [x, y - cell],
            [x, y],
        ]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": f"{constituency} No. {number}",
                    "constituency_code": f"KP-{number:03d}",
                    "geometry_note": (
                        "Equal-area seat grid ordered by official constituency number; "
                        "not a geographic or legal-boundary map"
                    ),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "north_korea_2026_spa_constituency_cartogram",
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the 2026 North Korean Supreme People's Assembly deputy list"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/north_korea_2026"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    source = args.source or download(args.raw_dir / "official_results.html", args.refresh)
    deputies = parse_deputies(source)
    rows = result_rows(deputies)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.out_dir / "north_korea_2026_spa.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    boundary_path = args.out_dir / "north_korea_2026_spa_cartogram.geojson"
    boundary_path.write_text(
        json.dumps(cartogram(deputies), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} elected-deputy rows to {csv_path}")
    print(f"Wrote {len(rows)} equal-area seat cells to {boundary_path}")


if __name__ == "__main__":
    main()
