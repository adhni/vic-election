#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import mapping, shape


UA = "Mozilla/5.0 (compatible; election-preference-explorer/0.1; +https://github.com/)"
ELECTION_YEAR = 2023
RESULT_BASE = "https://archive.electionresults.govt.nz/electionresults_2023/statistics"
MIRROR_BASE = "https://r.jina.ai/https://media.election.net.nz/electionresults_2023/statistics"
CANDIDATE_LIST_URL = "https://en.wikipedia.org/wiki/Candidates_in_the_2023_New_Zealand_general_election_by_electorate"
GENERAL_BOUNDARY_URL = (
    "https://services2.arcgis.com/vKb0s8tBIA3bdocZ/arcgis/rest/services/"
    "General_Electorates_2020/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"
)
MAORI_BOUNDARY_URL = (
    "https://services2.arcgis.com/vKb0s8tBIA3bdocZ/arcgis/rest/services/"
    "M%C4%81ori_Electorates_2020/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson"
)

PARTY_ORDER = [
    "ACT New Zealand",
    "Animal Justice Party Aotearoa New Zealand",
    "DemocracyNZ",
    "Freedoms NZ",
    "Leighton Baker Party",
    "Green Party",
    "Labour Party",
    "New Nation Party",
    "National Party",
    "New Conservatives",
    "NewZeal",
    "New Zealand First Party",
    "New Zealand Loyal",
    "Women's Rights Party",
    "Te Pāti Māori",
    "The Opportunities Party",
    "Aotearoa Legalise Cannabis Party",
]

PARTY_NAMES = {
    "ACT": "ACT New Zealand",
    "Animal Justice": "Animal Justice Party Aotearoa New Zealand",
    "DemocracyNZ": "DemocracyNZ",
    "Freedoms NZ": "Freedoms NZ",
    "Green": "Green Party",
    "Labour": "Labour Party",
    "Legalise Cannabis": "Aotearoa Legalise Cannabis Party",
    "Māori": "Te Pāti Māori",
    "National": "National Party",
    "New Conservative": "New Conservatives",
    "New Nation": "New Nation Party",
    "NZ First": "New Zealand First Party",
    "NZ Loyal": "New Zealand Loyal",
    "Opportunities": "The Opportunities Party",
    "Rock The Vote NZ": "Rock the Vote NZ",
    "Vision NZ": "Vision New Zealand",
}

ELECTORATE_NAMES = {
    "Mount Albert": "Mt Albert",
    "Mount Roskill": "Mt Roskill",
}

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "contest_status",
]


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(value).lower())


def numbers(value: str) -> list[int]:
    return [int(item.replace(",", "")) for item in re.findall(r"\d[\d,]*", value)]


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        existing = path.read_bytes()
        if b"Performing security verification" not in existing and b"Enable JavaScript and cookies" not in existing:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    error: Exception | None = None
    urls = [url]
    if url.startswith("https://r.jina.ai/https://media.election.net.nz/"):
        suffix = url.split("media.election.net.nz/", 1)[1]
        urls.extend([
            f"https://r.jina.ai/http://archive.electionresults.govt.nz/{suffix}",
            f"https://r.jina.ai/https://archive.electionresults.govt.nz/{suffix}",
            f"https://r.jina.ai/https://www.electionresults.govt.nz/{suffix}",
        ])
    for attempt in range(8):
        try:
            time.sleep(0.2 * (attempt + 1))
            response = session.get(urls[attempt % len(urls)], timeout=90)
            response.raise_for_status()
            if len(response.content) < 300:
                raise RuntimeError(f"unexpectedly short response ({len(response.content)} bytes)")
            if b"Performing security verification" in response.content or b"Enable JavaScript and cookies" in response.content:
                raise RuntimeError("source returned a security verification page")
            path.write_bytes(response.content)
            return
        except (requests.RequestException, RuntimeError) as exc:
            error = exc
    raise SystemExit(f"Failed to download {url}: {error}")


def candidate_tables(html: str) -> list[tuple[str, list[tuple[str, str]]]]:
    tables = pd.read_html(StringIO(html))
    out: list[tuple[str, list[tuple[str, str]]]] = []
    for table in tables:
        first_heading = clean(table.columns[0][0] if isinstance(table.columns, pd.MultiIndex) else table.columns[0])
        match = re.match(rf"{ELECTION_YEAR} general election:\s*(.+)", first_heading)
        if not match:
            continue
        table.columns = table.columns.get_level_values(-1) if isinstance(table.columns, pd.MultiIndex) else table.columns
        if "Candidate" not in table or "Party.1" not in table:
            continue
        rows = []
        for _, row in table.iterrows():
            candidate = clean(row["Candidate"])
            party = clean(row["Party.1"])
            if not candidate or candidate.lower() == "nan" or "withdrawn candidates" in candidate.lower():
                continue
            rows.append((candidate, PARTY_NAMES.get(party, party or "Independent")))
        raw_electorate = re.sub(r"\[\d+\]", "", match.group(1)).strip()
        electorate = ELECTORATE_NAMES.get(raw_electorate, raw_electorate)
        out.append((electorate, rows))
    if len(out) != 72:
        raise SystemExit(f"Expected 72 candidate tables, found {len(out)}")
    return out


def total_line(markdown: str, district: str) -> list[int]:
    wanted = normalize(district + " Total")
    for line in markdown.splitlines():
        if wanted in normalize(line):
            values = numbers(line)
            if values:
                return values
    raise SystemExit(f"{district}: total line not found")


def make_rows(
    district: str,
    electorate_type: str,
    candidates: list[tuple[str, str]],
    candidate_values: list[int],
    party_values: list[int],
    source_url: str,
) -> list[dict[str, object]]:
    cancelled = ELECTION_YEAR == 2023 and district == "Port Waikato"
    if cancelled:
        formal, informal = 0, 0
        candidate_results = [("Electorate vote cancelled", "Cancelled", 0)]
        winner_name, winner_party = "Electorate vote cancelled", "Cancelled"
    else:
        if len(candidate_values) < 3:
            raise SystemExit(f"{district}: incomplete candidate total")
        votes, formal, informal = candidate_values[:-2], candidate_values[-2], candidate_values[-1]
        if len(votes) > len(candidates):
            raise SystemExit(f"{district}: {len(votes)} vote columns but only {len(candidates)} candidates")
        candidate_results = [(name, party, vote) for (name, party), vote in zip(candidates[:len(votes)], votes)]
        if sum(votes) != formal:
            raise SystemExit(f"{district}: candidate votes {sum(votes)} != valid total {formal}")
        winner_name, winner_party, _ = max(candidate_results, key=lambda row: (row[2], row[0]))

    if len(party_values) != len(PARTY_ORDER) + 2:
        raise SystemExit(f"{district}: expected {len(PARTY_ORDER)} party columns, found {len(party_values) - 2}")
    party_votes, party_formal, party_informal = party_values[:-2], party_values[-2], party_values[-1]
    if sum(party_votes) != party_formal:
        raise SystemExit(f"{district}: party votes {sum(party_votes)} != valid total {party_formal}")

    base = {
        "district": district,
        "district_url": source_url,
        "distribution_url": source_url,
        "elected_member": winner_name,
        "elected_party": winner_party,
        "enrolment": 0,
        "formal_votes": formal,
        "informal_votes": informal,
        "total_votes": formal + informal,
        "turnout_pct": 0,
        "majority": formal // 2 + 1 if formal else 0,
        "electorate_type": electorate_type,
        "contest_status": "cancelled" if cancelled else "official",
    }
    rows = []
    for row_type in ("first", "final"):
        rows.extend({
            **base,
            "round_number": 0 if row_type == "first" else 1,
            "row_type": row_type,
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": name,
            "candidate_party": party,
            "votes": vote,
        } for name, party, vote in candidate_results)
    rows.extend({
        **base,
        "round_number": 0,
        "row_type": "party_vote",
        "excluded_candidate": "",
        "excluded_party": "",
        "candidate": party,
        "candidate_party": party,
        "votes": vote,
    } for party, vote in zip(PARTY_ORDER, party_votes))
    return rows


def transform_longitudes(coords: object) -> object:
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        lon, lat = coords[:2]
        return [lon + 360 if lon < 0 else lon, lat]
    return [transform_longitudes(part) for part in coords] if isinstance(coords, (list, tuple)) else coords


def boundary_features(path: Path, electorate_type: str, name_field: str) -> list[dict[str, object]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    features = []
    for feature in source.get("features", []):
        district = clean(feature.get("properties", {}).get(name_field))
        geometry = feature.get("geometry")
        geometry["coordinates"] = transform_longitudes(geometry["coordinates"])
        simplified = mapping(shape(geometry).simplify(0.002, preserve_topology=True))
        features.append({
            "type": "Feature",
            "properties": {"district": district, "electorate_type": electorate_type},
            "geometry": simplified,
        })
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Build NZ {ELECTION_YEAR} MMP election data")
    parser.add_argument("--raw-dir", type=Path, default=Path(f"tmp/nz_{ELECTION_YEAR}"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    candidate_list_path = args.raw_dir / "candidate_list.html"
    download(session, CANDIDATE_LIST_URL, candidate_list_path, args.refresh)
    tables = candidate_tables(candidate_list_path.read_text(encoding="utf-8"))

    all_rows: list[dict[str, object]] = []
    for electorate_id, (district, candidates) in enumerate(tables, start=1):
        candidate_path = args.raw_dir / "candidate" / f"{electorate_id:02d}.md"
        party_path = args.raw_dir / "party" / f"{electorate_id:02d}.md"
        candidate_url = f"{MIRROR_BASE}/candidate-votes-by-voting-place-{electorate_id}.html"
        party_url = f"{MIRROR_BASE}/party-votes-by-voting-place-{electorate_id}.html"
        download(session, candidate_url, candidate_path, args.refresh)
        download(session, party_url, party_path, args.refresh)
        candidate_values = (
            []
            if ELECTION_YEAR == 2023 and district == "Port Waikato"
            else total_line(candidate_path.read_text(encoding="utf-8"), district)
        )
        party_values = total_line(party_path.read_text(encoding="utf-8"), district)
        electorate_type = "Māori" if electorate_id > 65 else "General"
        source_url = f"{RESULT_BASE}/candidate-votes-by-voting-place-{electorate_id}.html"
        all_rows.extend(make_rows(district, electorate_type, candidates, candidate_values, party_values, source_url))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / f"nz_{ELECTION_YEAR}_mmp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)

    general_source = args.raw_dir / "general_boundaries.geojson"
    maori_source = args.raw_dir / "maori_boundaries.geojson"
    download(session, GENERAL_BOUNDARY_URL, general_source, args.refresh)
    download(session, MAORI_BOUNDARY_URL, maori_source, args.refresh)
    features = boundary_features(general_source, "General", "GED2020_V1_00_NAME")
    features.extend(boundary_features(maori_source, "Māori", "MED2020_V1_00_NAME"))
    if len(features) != 72:
        raise SystemExit(f"Expected 72 boundary features, found {len(features)}")
    boundary_path = args.out_dir / f"nz_{ELECTION_YEAR}_electorate_boundaries.geojson"
    boundary_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": f"new_zealand_{ELECTION_YEAR}_general_and_maori_electorates",
        "features": features,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Wrote {csv_path} ({len(all_rows)} rows, 72 electorates)")
    print(f"Wrote {boundary_path} ({len(features)} features)")


if __name__ == "__main__":
    main()
