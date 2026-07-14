#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import requests
from shapely.geometry import mapping, shape


RESULTS_URL = "https://electionresults.parliament.uk/general-elections/6/candidacies.csv"
BOUNDARIES_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BSC/FeatureServer/0/query"
    "?where=1%3D1&outFields=PCON24CD%2CPCON24NM%2CPCON24NMW"
    "&returnGeometry=true&outSR=4326&f=geojson"
)
UA = "Mozilla/5.0 (compatible; election-preference-explorer/0.1; +https://github.com/)"

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "contest_status",
]

# Parliament's result feed and ONS boundaries differ only in this diacritic.
BOUNDARY_NAME_ALIASES = {"Montgomeryshire and Glyndwr": "Montgomeryshire and Glyndŵr"}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def as_int(value: str) -> int:
    return int(float(value or 0))


def candidate_name(row: dict[str, str]) -> str:
    return " ".join(part.strip() for part in (row["Candidate given name"], row["Candidate family name"]) if part.strip())


def candidate_party(row: dict[str, str]) -> str:
    if row["Candidate is standing as Commons Speaker"].lower() == "true":
        return "Speaker"
    if row["Candidate is standing as independent"].lower() == "true":
        return "Independent"
    return row["Main party name"].strip()


def build_rows(source_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        groups[row["Constituency geographic code"]].append(row)
    if len(groups) != 650:
        raise SystemExit(f"Expected 650 constituencies, found {len(groups)}")

    output: list[dict[str, object]] = []
    for code, rows in sorted(groups.items(), key=lambda item: item[1][0]["Constituency name"]):
        rows.sort(key=lambda row: as_int(row["Candidate result position"]))
        first = rows[0]
        formal = as_int(first["Election valid vote count"])
        informal = as_int(first["Election invalid vote count"])
        total = formal + informal
        enrolment = as_int(first["Electorate"])
        raw_results = [(candidate_name(row), candidate_party(row), as_int(row["Candidate vote count"])) for row in rows]
        name_counts = Counter(name for name, _, _ in raw_results)
        results = [
            (f"{name} ({party})" if name_counts[name] > 1 else name, party, votes)
            for name, party, votes in raw_results
        ]
        if sum(votes for _, _, votes in results) != formal:
            raise SystemExit(f"{first['Constituency name']}: candidate votes do not equal valid votes")
        winner, winner_party, _ = results[0]
        if len(results) < 2 or results[0][2] - results[1][2] != as_int(first["Majority"]):
            raise SystemExit(f"{first['Constituency name']}: official majority does not match candidate totals")
        base = {
            "district": first["Constituency name"],
            "district_url": first["Election URL"],
            "distribution_url": first["Election URL"],
            "elected_member": winner,
            "elected_party": winner_party,
            "enrolment": enrolment,
            "formal_votes": formal,
            "informal_votes": informal,
            "total_votes": total,
            "turnout_pct": round(total / enrolment * 100, 2) if enrolment else 0,
            "majority": formal // 2 + 1,
            "electorate_type": first["Country name"],
            "contest_status": "official",
        }
        for row_type, round_number in (("first", 0), ("final", 1)):
            output.extend({
                **base,
                "round_number": round_number,
                "row_type": row_type,
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": name,
                "candidate_party": party,
                "votes": votes,
            } for name, party, votes in results)
    return output


def country_for_code(code: str) -> str:
    return {
        "E": "England",
        "N": "Northern Ireland",
        "S": "Scotland",
        "W": "Wales",
    }.get(code[:1], "")


def build_boundaries(source: dict[str, object]) -> dict[str, object]:
    features = []
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        code = str(properties.get("PCON24CD", "")).strip()
        district = str(properties.get("PCON24NM", "")).strip()
        district = BOUNDARY_NAME_ALIASES.get(district, district)
        geometry = mapping(shape(feature["geometry"]).simplify(0.001, preserve_topology=True))
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "constituency_code": code,
                "electorate_type": country_for_code(code),
            },
            "geometry": geometry,
        })
    if len(features) != 650:
        raise SystemExit(f"Expected 650 boundary features, found {len(features)}")
    return {"type": "FeatureCollection", "name": "uk_2024_westminster_constituencies", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UK 2024 House of Commons FPTP election data")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/uk_2024"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    results_path = args.raw_dir / "candidacies.csv"
    boundaries_path = args.raw_dir / "boundaries.geojson"
    download(session, RESULTS_URL, results_path, args.refresh)
    download(session, BOUNDARIES_URL, boundaries_path, args.refresh)

    with results_path.open(newline="", encoding="utf-8-sig") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = build_rows(source_rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.out_dir / "uk_2024_fpp.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    boundaries = build_boundaries(json.loads(boundaries_path.read_text(encoding="utf-8")))
    output_boundaries = args.out_dir / "uk_2024_constituency_boundaries.geojson"
    output_boundaries.write_text(
        json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"Wrote {output_csv} ({len(rows)} rows, 650 constituencies)")
    print(f"Wrote {output_boundaries} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
