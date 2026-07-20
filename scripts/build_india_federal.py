#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests
from pypdf import PdfReader
from shapely.geometry import mapping, shape


RESULTS_URL = (
    "https://data.opencity.in/dataset/85a345c6-78c0-4f57-adfc-236c726c5456/"
    "resource/d164b73a-b855-4b68-be0c-0f3450e7ab9f/download/"
    "1b837c18-4f7a-4acb-aad0-918c51186a54.csv"
)
REPORT_URL = (
    "https://www.eci.gov.in/eci-backend/public/all_files/GE-2024-statistical-report/"
    "33-Constituency-Wise-Detailed-Result.pdf"
)
BOUNDARY_URL = (
    "https://livingatlas.esri.in/server/rest/services/Election_Results_States/"
    "India_Election_Data_Parliamentary_2024/MapServer/0/query"
)
RESULTS_PAGE = "https://www.eci.gov.in/statistical-report/ge/2024/11"
EXPECTED_SEATS = 543
EXPECTED_CONTESTED = 542
EXPECTED_CANDIDATES = 8360
SURAT_ELECTORS = 1_786_287

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
]

PARTY_NAMES = {
    "Janata Dal  (United)": "Janata Dal (United)",
    "Janata Dal  (Secular)": "Janata Dal (Secular)",
    "Communist Party of India  (Marxist)": "Communist Party of India (Marxist)",
    "Communist Party of India  (Marxist-Leninist)  (Liberation)": "Communist Party of India (Marxist-Leninist) (Liberation)",
    "Shiv Sena (Uddhav Balasaheb Thackrey)": "Shiv Sena (Uddhav Balasaheb Thackeray)",
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"\bnct\s+of\b", "", text)
    text = re.sub(r"^the\s+", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def norm_constituency(value: object) -> str:
    text = re.sub(r"\(\s*(?:SC|ST)\s*\)", "", str(value or ""), flags=re.I)
    text = re.sub(r"\s+(?:SC|ST)\s*$", "", text, flags=re.I)
    normalized = norm(text)
    return "guwahati" if normalized == "gauhati" else normalized


def norm_candidate(value: object) -> str:
    return norm(re.sub(r"\s*\(ballot\s+\d+\)\s*$", "", str(value or ""), flags=re.I))


def display_candidate(value: str) -> str:
    value = re.sub(r"\s*\(\s*Uncontested\s*\)\s*$", "", value, flags=re.I).strip()
    if value.isupper():
        return value.title()
    return value


def read_results(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    expected = {"State", "PC No", "PC Name", "Candidate", "Party", "Total Votes"}
    if not rows or not expected.issubset(rows[0]):
        raise SystemExit("India result CSV is empty or has unexpected columns")
    return rows


def parse_report(path: Path, state_names: set[str]) -> dict[tuple[str, int], dict[str, int]]:
    states = {norm(state): state for state in state_names}
    heading = re.compile(
        r"Constituency:\s*(\d+)\s*\.\s*(.*?)\s*\(\s*Total Electors\s+(\d+)\s*\)", re.I
    )
    metadata: dict[tuple[str, int], dict[str, int]] = {}
    current_state = ""
    vote_sequence = re.compile(
        r"(\d{4,})\s+(\d{4,})\s+(\d+)\s+(\d+)\s+(\d+)\s+"
        r"\d+(?:\.\d+)?\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?"
    )
    for page_number, page in enumerate(PdfReader(path).pages, start=1):
        # Plain extraction is substantially faster than pypdf's layout mode. Joining
        # lines still preserves the eight-number sequence at the end of candidate rows.
        lines = page.extract_text().splitlines()
        for index, line in enumerate(lines):
            compact = " ".join(line.split())
            if norm(compact) in states:
                current_state = states[norm(compact)]
            match = heading.search(compact)
            if not match:
                continue
            if not current_state:
                raise SystemExit(f"PDF page {page_number}: constituency appeared before a state heading")
            result_text = " ".join(" ".join(value.split()) for value in lines[index + 1:])
            vote_match = vote_sequence.search(result_text)
            if not vote_match:
                raise SystemExit(f"PDF page {page_number}: could not parse total votes for {compact}")
            key = (norm(current_state), int(match.group(1)))
            if key in metadata:
                raise SystemExit(f"PDF page {page_number}: duplicate constituency {key}")
            metadata[key] = {"enrolment": int(match.group(3)), "total_votes": int(vote_match.group(1))}
    if len(metadata) != EXPECTED_CONTESTED:
        raise SystemExit(f"Expected {EXPECTED_CONTESTED} contested constituencies in ECI report, found {len(metadata)}")
    return metadata


def fetch_boundaries(session: requests.Session, cache_path: Path, refresh: bool) -> dict[str, object]:
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    features = []
    offset = 0
    while True:
        params = {
            "where": "elec_year=2024", "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "orderByFields": "objectid", "resultOffset": offset,
            "resultRecordCount": 50, "geometryPrecision": 5, "maxAllowableOffset": 0.002,
            "f": "geojson",
        }
        response = session.get(BOUNDARY_URL, params=params, timeout=180)
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise SystemExit(f"Esri boundary service returned: {payload['error']}")
        page = payload.get("features", [])
        features.extend(page)
        if len(page) < 50:
            break
        offset += len(page)
    payload = {"type": "FeatureCollection", "features": features}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload


def build_rows(
    source_rows: list[dict[str, str]], report: dict[tuple[str, int], dict[str, int]]
) -> tuple[list[dict[str, object]], dict[tuple[str, int], dict[str, object]]]:
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        groups[(norm(row["State"]), int(row["PC No"]))].append(row)
    if len(groups) != EXPECTED_SEATS:
        raise SystemExit(f"Expected {EXPECTED_SEATS} constituencies, found {len(groups)}")

    name_counts = Counter(norm(rows[0]["PC Name"]) for rows in groups.values())
    output = []
    seats: dict[tuple[str, int], dict[str, object]] = {}
    actual_candidates = 0
    for key, candidates in sorted(groups.items()):
        state = candidates[0]["State"].replace("NCT OF Delhi", "NCT of Delhi")
        district = candidates[0]["PC Name"].strip()
        if name_counts[norm(district)] > 1:
            district = f"{district} ({state})"
        uncontested = len(candidates) == 1 and candidates[0]["Total Votes"].strip() == "-"
        if uncontested:
            if state != "Gujarat" or int(candidates[0]["PC No"]) != 24:
                raise SystemExit(f"Unexpected uncontested constituency: {state} {district}")
            enrolment, total, formal, informal = SURAT_ELECTORS, 0, 0, 0
            results_with_ballot = [(display_candidate(candidates[0]["Candidate"]), PARTY_NAMES.get(candidates[0]["Party"], candidates[0]["Party"]), 0, candidates[0]["Sl no"])]
            actual_candidates += 1
        else:
            if key not in report:
                raise SystemExit(f"{state} {district}: missing from ECI detailed result report")
            results_with_ballot = [
                (display_candidate(row["Candidate"]), PARTY_NAMES.get(row["Party"], row["Party"]).strip(), int(row["Total Votes"]), row["Sl no"])
                for row in candidates
            ]
            enrolment = report[key]["enrolment"]
            total = report[key]["total_votes"]
            formal = sum(votes for _, _, votes, _ in results_with_ballot)
            informal = total - formal
            if informal < 0:
                raise SystemExit(f"{state} {district}: candidate votes exceed total ballots")
            actual_candidates += sum(name.casefold() != "nota" for name, _, _, _ in results_with_ballot)
        duplicate_names = Counter(name for name, _, _, _ in results_with_ballot)
        results = [
            (f"{name} (ballot {ballot})" if duplicate_names[name] > 1 else name, party, votes)
            for name, party, votes, ballot in results_with_ballot
        ]
        results.sort(key=lambda item: (-item[2], item[0]))
        ranked_candidates = [result for result in results if result[0].casefold() != "nota"]
        winner, winner_party, winner_votes = ranked_candidates[0]
        margin = winner_votes - ranked_candidates[1][2] if len(ranked_candidates) > 1 else 0
        base = {
            "district": district, "district_url": RESULTS_PAGE, "distribution_url": RESULTS_PAGE,
            "elected_member": winner, "elected_party": winner_party, "enrolment": enrolment,
            "formal_votes": formal, "informal_votes": informal, "total_votes": total,
            "turnout_pct": round(total / enrolment * 100, 2) if enrolment else 0,
            "majority": formal // 2 + 1 if formal else 0, "electorate_type": state,
            "constituency_code": "", "contest_status": "uncontested" if uncontested else "official",
        }
        for row_type, round_number in (("first", 0), ("final", 1)):
            output.extend({
                **base, "round_number": round_number, "row_type": row_type,
                "excluded_candidate": "", "excluded_party": "", "candidate": candidate,
                "candidate_party": party, "votes": votes,
            } for candidate, party, votes in results)
        seats[key] = {
            "district": district, "state": state, "winner": winner, "party": winner_party,
            "winner_votes": winner_votes, "margin": margin,
        }
    if actual_candidates != EXPECTED_CANDIDATES:
        raise SystemExit(f"Expected {EXPECTED_CANDIDATES} candidates excluding NOTA, found {actual_candidates}")
    return output, seats


def build_boundaries(
    raw: dict[str, object], seats: dict[tuple[str, int], dict[str, object]], rows: list[dict[str, object]]
) -> dict[str, object]:
    features = []
    codes = {}
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        key = (norm(props.get("state_ut")), int(props.get("cons_code")))
        if key not in seats:
            raise SystemExit(f"Boundary has no matching result: {props.get('state_ut')} {props.get('cons_name')}")
        info = seats[key]
        code = str(props["id"])
        geometry = feature.get("geometry")
        geom = shape(geometry)
        if not geom.is_valid:
            geom = geom.buffer(0)
            geometry = mapping(geom)
        if geom.is_empty or not geom.is_valid:
            raise SystemExit(f"{info['district']}: boundary could not be repaired")
        source_district = str(info["district"]).rsplit(" (", 1)[0]
        if norm_constituency(props.get("cons_name")) != norm_constituency(source_district):
            raise SystemExit(f"{info['district']}: boundary constituency name does not match")
        expected_votes = info["winner_votes"] or None
        expected_margin = info["margin"] or None
        # The layer's 14 Assam winner attributes are shifted between the newly
        # delimited seats, although their constituency codes and geometries match.
        # Everywhere else, require its independent winner/vote/margin check.
        if info["state"] != "Assam" and expected_votes is not None:
            if props.get("tot_votes") != expected_votes or props.get("margin") != expected_margin:
                raise SystemExit(f"{info['district']}: result does not match Esri winner totals")
            if norm_candidate(props.get("win_cndt")) != norm_candidate(info["winner"]):
                raise SystemExit(f"{info['district']}: winning candidate does not match Esri data")
        codes[key] = code
        features.append({
            "type": "Feature",
            "properties": {"district": info["district"], "constituency_code": code, "electorate_type": info["state"]},
            "geometry": geometry,
        })
    if len(features) != EXPECTED_SEATS or set(codes) != set(seats):
        raise SystemExit(f"Expected {EXPECTED_SEATS} matching boundaries, found {len(features)}")
    district_to_code = {seats[key]["district"]: code for key, code in codes.items()}
    for row in rows:
        row["constituency_code"] = district_to_code[row["district"]]
    return {"type": "FeatureCollection", "name": "india_2024_parliamentary_constituencies", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build India 2024 Lok Sabha FPTP data")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/india_2024"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; election-preference-explorer/0.1)"})
    results_path = args.raw_dir / "constituency_results.csv"
    report_path = args.raw_dir / "eci_constituency_detailed_results.pdf"
    boundary_cache = args.raw_dir / "esri_boundaries.geojson"
    download(session, RESULTS_URL, results_path, args.refresh)
    download(session, REPORT_URL, report_path, args.refresh)
    source_rows = read_results(results_path)
    report_cache = args.raw_dir / "eci_report_metadata.json"
    if report_cache.exists() and not args.refresh:
        cached = json.loads(report_cache.read_text(encoding="utf-8"))
        report = {(state, int(code)): values for state, code, values in cached}
    else:
        report = parse_report(report_path, {row["State"] for row in source_rows})
        report_cache.write_text(
            json.dumps([[state, code, values] for (state, code), values in sorted(report.items())], separators=(",", ":")),
            encoding="utf-8",
        )
    rows, seats = build_rows(source_rows, report)
    raw_boundaries = fetch_boundaries(session, boundary_cache, args.refresh)
    boundaries = build_boundaries(raw_boundaries, seats, rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "india_2024_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    boundary_path = args.out_dir / "india_2024_parliamentary_boundaries.geojson"
    boundary_path.write_text(json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {csv_path} ({len(rows):,} rows, {EXPECTED_SEATS} constituencies)")
    print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
