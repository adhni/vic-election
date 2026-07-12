#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from pypdf import PdfReader

from build_nsw_state import LONG_FIELDS, SUMMARY_FIELDS, write_csv


NS = {"wa": "http://tempuri.org/MediaExportSchema.xsd"}
UA = "Mozilla/5.0 (compatible; australian-election-preference-explorer/0.1; +https://github.com/)"

ELECTIONS = {
    2025: {
        "date": "8 March 2025",
        "verbose_url": "https://media.waec.wa.gov.au/2025%20SGE%20Final/8%20March%202025%20State%20General%20Election%20-%20LA%20VERBOSE%20RESULTS.xml",
        "candidates_url": "https://media.waec.wa.gov.au/2025%20SGE%20Final/8%20March%202025%20State%20General%20Election%20-%20CANDIDATE%20SETUP.xml",
        "boundaries_url": "https://public-services.slip.wa.gov.au/public/rest/services/SLIP_Public_Services/Boundaries/MapServer/20/query?where=type_description%3D%27MLA%27&outFields=name%2Cboundary_id&returnGeometry=true&outSR=4326&f=geojson",
        "final_pdf_url": "https://www.elections.wa.gov.au/sites/default/files/SGE2025/Reports/WAEC9467%20State%20Election%20Stats%2BResults%20Report%20WEB.pdf",
        "final_pdf_pages": (25, 26, 27),
        "results_url": "https://www.elections.wa.gov.au/elections/state/reports",
    },
    2021: {
        "date": "13 March 2021",
        "verbose_url": "https://media.waec.wa.gov.au/2021%20SGE%20Final/13%20March%202021%20State%20General%20Election%20-%20LA%20VERBOSE%20RESULTS.xml",
        "candidates_url": "https://media.waec.wa.gov.au/2021%20SGE%20Final/13%20March%202021%20State%20General%20Election%20-%20CANDIDATE%20SETUP.xml",
        "boundaries_url": "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SED/FeatureServer/0/query?where=state_code_2021%3D%275%27&outFields=sed_code_2021%2Csed_name_2021%2Cstate_code_2021&returnGeometry=true&outSR=4326&f=geojson",
        "final_pdf_url": "https://www.elections.wa.gov.au/sites/default/files/content/SGE%202021/SGE%202021%20Reports/3_21_Res_Stats_Leg_Assem_0.pdf",
        "final_pdf_pages": (14, 15, 16),
        "results_url": "https://www.elections.wa.gov.au/elections/state-elections/reports/2021-state-election-results-and-statistics-report",
    },
}

PARTIES = {
    "ALP": "Australian Labor Party",
    "LIB": "Liberal Party",
    "NAT": "The Nationals",
    "NATS": "The Nationals",
    "GRN": "The Greens",
    "IND": "Independent",
    "PHON": "Pauline Hanson's One Nation",
    "ACP": "Australian Christians",
    "AC": "Australian Christians",
    "AJP": "Animal Justice Party",
    "LCWA": "Legalise Cannabis Party WA",
    "LDP": "Liberal Democrats",
    "SFF": "Shooters, Fishers and Farmers",
    "SFFP": "Shooters, Fishers and Farmers",
}


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def party_name(code: object, full_name: object = "") -> str:
    abbreviation = clean_text(code).upper()
    if abbreviation in PARTIES:
        return PARTIES[abbreviation]
    name = clean_text(full_name)
    aliases = {
        "WA Labor": "Australian Labor Party",
        "THE NATIONALS": "The Nationals",
        "The Nationals WA": "The Nationals",
        "The Greens (WA)": "The Greens",
        "Independent": "Independent",
    }
    return aliases.get(name, name or "Independent")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    return session


def download(session: requests.Session, url: str, path: Path, refresh: bool = False) -> None:
    if path.exists() and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(0.1)
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.write_bytes(response.content)


def candidate_setup(path: Path) -> dict[str, dict[int, dict[str, str]]]:
    root = ET.parse(path).getroot()
    setup: dict[str, dict[int, dict[str, str]]] = {}
    for district in root.findall(".//wa:ElectionDistrict", NS):
        district_name = district.attrib["Name"]
        candidates: dict[int, dict[str, str]] = {}
        for candidate in district.findall("./wa:LA/wa:Candidate", NS):
            order = int(candidate.attrib["BallotPaperOrder"])
            candidates[order] = {
                "candidate": clean_text(candidate.attrib["BallotPaperName"]),
                "candidate_party": party_name(
                    candidate.attrib.get("RegisteredPartyAbbreviation"),
                    candidate.attrib.get("RegisteredPartyBallotPaperName"),
                ),
                "surname": normalize_key(candidate.attrib.get("LastName")),
                "name_key": normalize_key(candidate.attrib["BallotPaperName"]),
            }
        setup[district_name] = candidates
    return setup


def primary_results(path: Path) -> dict[str, dict[str, object]]:
    root = ET.parse(path).getroot()
    results: dict[str, dict[str, object]] = {}
    for district in root.findall(".//wa:ElectionDistrict", NS):
        district_name = district.attrib["Name"]
        primary = district.find("./wa:LA/wa:DistrictVotes[@CountDefinitionCode='LAPC']", NS)
        if primary is None:
            raise SystemExit(f"{district_name}: missing WAEC primary count")
        votes = {
            int(row.attrib["CandidateBallotPaperOrder"]): int(row.attrib["Votes"])
            for row in primary.findall("./wa:CandidateVotes", NS)
        }
        results[district_name] = {
            "enrolment": int(district.attrib["Enrolment"]),
            "formal_votes": int(primary.attrib["FormalVotes"]),
            "informal_votes": int(primary.attrib["InformalVotes"]),
            "votes": votes,
        }
    return results


def final_results_pdf(
    pdf_path: Path,
    districts: set[str],
    setup: dict[str, dict[int, dict[str, str]]],
    page_indices: tuple[int, ...],
) -> dict[str, dict[int, int]]:
    reader = PdfReader(str(pdf_path))
    text = "\n".join((reader.pages[index].extract_text() or "") for index in page_indices)
    party_pattern = r"WA Labor|Liberal Party|THE NATIONALS|The Nationals WA|The Greens \(WA\)|Independent"
    row_pattern = re.compile(rf"^(.+?)\s+({party_pattern})\s+([\d,]+)\s+\d+\.\d+%$")
    district_names = sorted(districts, key=len, reverse=True)
    results: dict[str, dict[int, int]] = {}
    current_district = ""
    pending = ""
    for raw_line in text.splitlines():
        line = clean_text(raw_line)
        if line in districts:
            current_district = line
            pending = ""
            continue
        for district in district_names:
            if line.startswith(f"{district} "):
                current_district = district
                line = line[len(district) + 1 :]
                pending = ""
                break
        candidate_line = clean_text(f"{pending} {line}") if pending else line
        match = row_pattern.match(candidate_line)
        if not match:
            if current_district and (pending or "," in line) and "%" not in line:
                pending = candidate_line
            continue
        pending = ""
        left, _party, votes_text = match.groups()
        if not current_district:
            continue
        surname = normalize_key(left.split(",", 1)[0])
        matches = [order for order, candidate in setup[current_district].items() if candidate["surname"] == surname]
        if len(matches) > 1:
            full_name_key = normalize_key(left)
            matches = [
                order
                for order in matches
                if full_name_key.startswith(setup[current_district][order]["name_key"])
            ]
        if len(matches) != 1:
            raise SystemExit(f"{current_district}: cannot match final candidate {left!r}")
        results.setdefault(current_district, {})[matches[0]] = int(votes_text.replace(",", ""))
    invalid = {district: votes for district, votes in results.items() if len(votes) != 2}
    missing = districts - set(results)
    if missing or invalid:
        raise SystemExit(f"Invalid final table; missing={sorted(missing)}, invalid={invalid}")
    return results


def build_rows(
    year: int,
    setup: dict[str, dict[int, dict[str, str]]],
    primary: dict[str, dict[str, object]],
    final: dict[str, dict[int, int]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    config = ELECTIONS[year]
    long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for district in sorted(primary):
        candidates = setup[district]
        primary_votes = primary[district]["votes"]
        if not isinstance(primary_votes, dict):
            raise SystemExit(f"{district}: invalid primary votes")
        first_sorted = sorted(primary_votes.items(), key=lambda item: (-item[1], item[0]))
        final_sorted = sorted(final[district].items(), key=lambda item: (-item[1], item[0]))
        winner_order, winner_final_votes = final_sorted[0]
        runner_up_order, runner_up_final_votes = final_sorted[1]
        formal_votes = int(primary[district]["formal_votes"])
        informal_votes = int(primary[district]["informal_votes"])
        total_votes = formal_votes + informal_votes
        enrolment = int(primary[district]["enrolment"])
        winner_first_votes = int(primary_votes[winner_order])
        base = {
            "district": district,
            "district_url": config["results_url"],
            "distribution_url": config.get("final_pdf_url", config["verbose_url"]),
            "elected_member": candidates[winner_order]["candidate"],
            "elected_party": candidates[winner_order]["candidate_party"],
            "enrolment": enrolment,
            "formal_votes": formal_votes,
            "informal_votes": informal_votes,
            "total_votes": total_votes,
            "turnout_pct": round(total_votes / enrolment * 100, 2),
            "majority": formal_votes // 2 + 1,
        }
        for order, votes in first_sorted:
            long_rows.append({
                **base,
                "round_number": 0,
                "row_type": "first",
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": candidates[order]["candidate"],
                "candidate_party": candidates[order]["candidate_party"],
                "votes": votes,
            })
        for order, votes in final_sorted:
            long_rows.append({
                **base,
                "round_number": 1,
                "row_type": "final",
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": candidates[order]["candidate"],
                "candidate_party": candidates[order]["candidate_party"],
                "votes": votes,
            })
        primary_leader_order, primary_leader_votes = first_sorted[0]
        summary_rows.append({
            **base,
            "primary_leader": candidates[primary_leader_order]["candidate"],
            "primary_leader_party": candidates[primary_leader_order]["candidate_party"],
            "primary_leader_votes": primary_leader_votes,
            "winner": candidates[winner_order]["candidate"],
            "winner_party": candidates[winner_order]["candidate_party"],
            "winner_final_votes": winner_final_votes,
            "runner_up": candidates[runner_up_order]["candidate"],
            "runner_up_party": candidates[runner_up_order]["candidate_party"],
            "runner_up_final_votes": runner_up_final_votes,
            "final_margin": winner_final_votes - runner_up_final_votes,
            "preference_changed_result": str(primary_leader_order != winner_order),
            "winner_transfer_gain": winner_final_votes - winner_first_votes,
        })
    return long_rows, summary_rows


def write_boundaries(source_path: Path, out_path: Path, districts: set[str], year: int) -> None:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    district_by_key = {normalize_key(district): district for district in districts}
    features = []
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        if year == 2025:
            source_name = clean_text(properties.get("name"))
        else:
            source_name = re.sub(r"\s+\([^)]*\)$", "", clean_text(properties.get("sed_name_2021")))
        district = district_by_key.get(normalize_key(source_name))
        if not district:
            continue
        feature["properties"] = {"district": district, "source_district": source_name}
        features.append(feature)
    found = {feature["properties"]["district"] for feature in features}
    if found != districts or len(features) != len(districts):
        raise SystemExit(f"WA {year} boundary mismatch: {sorted(found ^ districts)}")
    out_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": f"wa_{year}_state_electoral_districts",
        "features": features,
    }, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=sorted(ELECTIONS), required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    year = args.year
    config = ELECTIONS[year]
    raw_dir = args.raw_dir or Path(f"tmp/wa_{year}")
    session = make_session()
    verbose_path = raw_dir / "la_verbose.xml"
    candidates_path = raw_dir / "candidates.xml"
    boundaries_path = raw_dir / "boundaries_source.geojson"
    download(session, config["verbose_url"], verbose_path, args.refresh)
    download(session, config["candidates_url"], candidates_path, args.refresh)
    download(session, config["boundaries_url"], boundaries_path, args.refresh)
    final_pdf_path = raw_dir / "results_report.pdf"
    if year == 2021 and not final_pdf_path.exists() and (raw_dir / "legislative_assembly.pdf").exists():
        final_pdf_path = raw_dir / "legislative_assembly.pdf"
    download(session, config["final_pdf_url"], final_pdf_path, args.refresh)

    setup = candidate_setup(candidates_path)
    primary = primary_results(verbose_path)
    if set(setup) != set(primary) or len(primary) != 59:
        raise SystemExit(f"WA {year}: expected 59 matching districts")
    final = final_results_pdf(final_pdf_path, set(primary), setup, config["final_pdf_pages"])
    long_rows, summary_rows = build_rows(year, setup, primary, final)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    preferences_out = args.out_dir / f"wa_{year}_preferences_long.csv"
    summary_out = args.out_dir / f"wa_{year}_district_summary.csv"
    boundaries_out = args.out_dir / f"wa_{year}_district_boundaries.geojson"
    write_csv(preferences_out, long_rows, LONG_FIELDS)
    write_csv(summary_out, summary_rows, SUMMARY_FIELDS)
    write_boundaries(boundaries_path, boundaries_out, set(primary), year)
    print(f"Wrote {preferences_out} ({len(long_rows)} rows)")
    print(f"Wrote {summary_out} ({len(summary_rows)} rows)")
    print(f"Wrote {boundaries_out}")


if __name__ == "__main__":
    main()
