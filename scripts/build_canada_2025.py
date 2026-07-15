#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import mapping


TABLE_11_URL = "https://www.elections.ca/res/rep/off/ovrGE45/62/data_donnees/table_tableau11.csv"
TABLE_12_URL = "https://www.elections.ca/res/rep/off/ovrGE45/62/data_donnees/table_tableau12.csv"
BOUNDARIES_URL = "https://www.elections.ca/res/cir/mapsCorner/vector/FederalElectoralDistricts_2025_SHP.zip"
RESULTS_PAGE = "https://www.elections.ca/res/rep/off/ovrGE45/home.html"
UA = "Mozilla/5.0 (compatible; election-preference-explorer/0.1; +https://github.com/)"

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
]

PARTY_SUFFIXES = {
    "Liberal/Libéral": "Liberal",
    "Conservative/Conservateur": "Conservative",
    "NDP-New Democratic Party/NPD-Nouveau Parti démocratique": "NDP",
    "Green Party/Parti Vert": "Green",
    "Bloc Québécois/Bloc Québécois": "Bloc Québécois",
    "People's Party - PPC/Parti populaire - PPC": "People's Party",
    "Independent/Indépendant(e)": "Independent",
    "No Affiliation/Aucune appartenance": "No Affiliation",
    "Animal Protection Party/Parti Protection Animaux": "Animal Protection Party",
    "Canadian Future Party/Parti Avenir Canadien": "Canadian Future Party",
    "Centrist/Centriste": "Centrist",
    "Christian Heritage Party/Parti de l'Héritage Chrétien": "Christian Heritage Party",
    "Communist/Communiste": "Communist",
    "Libertarian/Libertarien": "Libertarian",
    "Marijuana Party/Parti Marijuana": "Marijuana Party",
    "Marxist-Leninist/Marxiste-Léniniste": "Marxist-Leninist",
    "Parti Rhinocéros Party/Parti Rhinocéros Party": "Rhinoceros Party",
    "United Party of Canada (UP)/Parti Uni du Canada (UP)": "United Party",
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def field(row: dict[str, str], prefix: str) -> str:
    key = next((key for key in row if key.startswith(prefix)), None)
    if not key:
        raise SystemExit(f"Official CSV is missing field beginning {prefix!r}")
    return row[key]


def english(value: str) -> str:
    return value.split("/", 1)[0].strip().replace("--", "—")


def parse_candidate(value: str) -> tuple[str, str]:
    matches = [(suffix, party) for suffix, party in PARTY_SUFFIXES.items() if value.endswith(f" {suffix}")]
    if len(matches) != 1:
        raise SystemExit(f"Could not identify candidate party: {value}")
    suffix, party = matches[0]
    name = value[: -(len(suffix) + 1)].replace(" **", "").strip()
    if not name:
        raise SystemExit(f"Candidate name is empty: {value}")
    return name, party


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def build_rows(metadata_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, dict[str, str]]]:
    metadata = {field(row, "Electoral District Number"): row for row in metadata_rows}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        groups[field(row, "Electoral District Number")].append(row)
    if len(metadata) != 343 or set(metadata) != set(groups):
        raise SystemExit(f"Expected the same 343 riding codes in Tables 11 and 12, found {len(metadata)} and {len(groups)}")

    output = []
    district_by_code: dict[str, dict[str, str]] = {}
    for code, source_rows in sorted(groups.items()):
        meta = metadata[code]
        district = english(field(meta, "Electoral District Name"))
        province = english(meta["Province"])
        results = []
        for row in source_rows:
            candidate, party = parse_candidate(field(row, "Candidate/"))
            results.append((candidate, party, int(field(row, "Votes Obtained"))))
        name_counts = Counter(name for name, _, _ in results)
        results = [
            (f"{name} ({party})" if name_counts[name] > 1 else name, party, votes)
            for name, party, votes in results
        ]
        results.sort(key=lambda item: (-item[2], item[0]))
        if len(results) < 2:
            raise SystemExit(f"{district}: expected a contested election")
        formal = int(field(meta, "Valid Ballots"))
        informal = int(field(meta, "Rejected Ballots"))
        total = int(field(meta, "Total Ballots Cast"))
        enrolment = int(field(meta, "Electors/"))
        if sum(votes for _, _, votes in results) != formal or total != formal + informal:
            raise SystemExit(f"{district}: candidate and ballot totals do not reconcile")
        winner, winner_party, _ = results[0]
        majority_rows = [row for row in source_rows if field(row, "Majority/").strip()]
        if len(majority_rows) != 1:
            raise SystemExit(f"{district}: expected one candidate with an official majority")
        official_winner, _ = parse_candidate(field(majority_rows[0], "Candidate/"))
        official_margin = int(field(majority_rows[0], "Majority/"))
        computed_margin = results[0][2] - results[1][2]
        if official_winner != winner or official_margin != computed_margin:
            raise SystemExit(f"{district}: official majority {official_margin} != computed {computed_margin}")
        official_turnout = float(field(meta, "Percentage of Voter Turnout"))
        computed_turnout = total / enrolment * 100 if enrolment else 0
        if abs(official_turnout - computed_turnout) > 0.051:
            raise SystemExit(f"{district}: official turnout does not match ballot totals")
        base = {
            "district": district,
            "district_url": RESULTS_PAGE,
            "distribution_url": RESULTS_PAGE,
            "elected_member": winner,
            "elected_party": winner_party,
            "enrolment": enrolment,
            "formal_votes": formal,
            "informal_votes": informal,
            "total_votes": total,
            "turnout_pct": round(computed_turnout, 2),
            "majority": formal // 2 + 1,
            "electorate_type": province,
            "constituency_code": code,
            "contest_status": "official",
        }
        for row_type, round_number in (("first", 0), ("final", 1)):
            output.extend({
                **base,
                "round_number": round_number,
                "row_type": row_type,
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": candidate,
                "candidate_party": party,
                "votes": votes,
            } for candidate, party, votes in results)
        district_by_code[code] = {"district": district, "province": province}
    return output, district_by_code


def build_boundaries(zip_path: Path, extract_dir: Path, district_by_code: dict[str, dict[str, str]]) -> dict[str, object]:
    if not (extract_dir / "SHP" / "FED_CA_2025_EN.shp").exists():
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
    frame = gpd.read_file(extract_dir / "SHP" / "FED_CA_2025_EN.shp").to_crs(4326)
    frame["FED_NUM"] = frame["FED_NUM"].astype(str).str.zfill(5)
    frame["geometry"] = frame.geometry.simplify(0.005, preserve_topology=True)
    frame = frame.dissolve(by="FED_NUM", as_index=False)
    if len(frame) != 343 or set(frame["FED_NUM"]) != set(district_by_code):
        raise SystemExit("Official boundaries do not match the 343 result riding codes")
    features = []
    for row in frame.itertuples():
        info = district_by_code[row.FED_NUM]
        if not row.geometry.is_valid:
            raise SystemExit(f"{row.FED_NUM}: simplified boundary is invalid")
        features.append({
            "type": "Feature",
            "properties": {
                "district": info["district"],
                "constituency_code": row.FED_NUM,
                "electorate_type": info["province"],
            },
            "geometry": mapping(row.geometry),
        })
    return {"type": "FeatureCollection", "name": "canada_2025_federal_electoral_districts", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Canada 2025 federal election FPTP data")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/canada_2025"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    table11_path = args.raw_dir / "table11.csv"
    table12_path = args.raw_dir / "table12.csv"
    boundary_zip = args.raw_dir / "FederalElectoralDistricts_2025_SHP.zip"
    download(session, TABLE_11_URL, table11_path, args.refresh)
    download(session, TABLE_12_URL, table12_path, args.refresh)
    download(session, BOUNDARIES_URL, boundary_zip, args.refresh)

    rows, district_by_code = build_rows(read_csv(table11_path), read_csv(table12_path))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "canada_2025_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    boundaries = build_boundaries(boundary_zip, args.raw_dir / "boundaries", district_by_code)
    boundary_path = args.out_dir / "canada_2025_federal_boundaries.geojson"
    boundary_path.write_text(json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {csv_path} ({len(rows)} rows, 343 ridings, 1,959 candidates)")
    print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
