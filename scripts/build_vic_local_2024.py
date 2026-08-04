#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
import xlrd
from bs4 import BeautifulSoup, Tag
from shapely.geometry import mapping, shape
from shapely.validation import make_valid


RESULTS_INDEX = "https://www.vec.vic.gov.au/2024-council-elections"
WARD_WFS = (
    "https://opendata.maps.vic.gov.au/geoserver/wfs?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=open-data-platform%3Award_2024"
    "&outputFormat=application%2Fjson&srsName=EPSG%3A4326"
)
MELBOURNE_LGA_WFS = (
    "https://opendata.maps.vic.gov.au/geoserver/wfs?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=open-data-platform%3Alga_polygon"
    "&outputFormat=application%2Fjson&srsName=EPSG%3A4326"
    "&CQL_FILTER=lga_name%3D%27MELBOURNE%27"
)
BOUNDARY_SOURCE = "https://discover.data.vic.gov.au/dataset/vicmap-admin-ward-polygon-2024"

SOURCE_SHA256 = {
    "wards": "09288b1742c2845e34fa2da53c06b32d5d3adbf90d2927521854e5ede99dd1e7",
    "melbourne_lga": "3fcafc2efc09a8b2160c4f1e1f08290e51fa28f29d518f8decbd6345906d1ff5",
}

METRO_COUNCILS = {
    "Banyule City Council": ("Banyule", 9),
    "Bayside City Council": ("Bayside", 7),
    "Boroondara City Council": ("Boroondara", 11),
    "Brimbank City Council": ("Brimbank", 11),
    "Cardinia Shire Council": ("Cardinia", 9),
    "Casey City Council": ("Casey", 12),
    "Darebin City Council": ("Darebin", 9),
    "Frankston City Council": ("Frankston", 9),
    "Glen Eira City Council": ("Glen Eira", 9),
    "Greater Dandenong City Council": ("Greater Dandenong", 11),
    "Hobsons Bay City Council": ("Hobsons Bay", 7),
    "Hume City Council": ("Hume", 11),
    "Kingston City Council": ("Kingston", 11),
    "Knox City Council": ("Knox", 9),
    "Manningham City Council": ("Manningham", 9),
    "Maribyrnong City Council": ("Maribyrnong", 7),
    "Maroondah City Council": ("Maroondah", 9),
    "Melbourne City Council": ("Melbourne", 0),
    "Melton City Council": ("Melton", 10),
    "Merri-bek City Council": ("Merri-bek", 11),
    "Monash City Council": ("Monash", 11),
    "Moonee Valley City Council": ("Moonee Valley", 9),
    "Mornington Peninsula Shire Council": ("Mornington Peninsula", 11),
    "Nillumbik Shire Council": ("Nillumbik", 7),
    "Port Phillip City Council": ("Port Phillip", 9),
    "Stonnington City Council": ("Stonnington", 9),
    "Whitehorse City Council": ("Whitehorse", 11),
    "Whittlesea City Council": ("Whittlesea", 11),
    "Wyndham City Council": ("Wyndham", 11),
    "Yarra City Council": ("Yarra", 9),
    "Yarra Ranges Shire Council": ("Yarra Ranges", 9),
}

FIELDS = (
    "district", "council", "ward", "district_url", "distribution_url",
    "elected_member", "elected_party", "elected_members", "elected_parties",
    "members_to_elect", "quota", "enrolment", "formal_votes", "informal_votes",
    "total_votes", "turnout_pct", "majority", "round_number", "row_type",
    "excluded_candidate", "excluded_party", "candidate", "candidate_party",
    "candidate_status", "candidate_elected", "candidate_elected_order", "votes",
    "electorate_type", "constituency_code", "contest_status", "result_note",
)


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def integer(value: object) -> int:
    match = re.search(r"-?\d[\d,]*", clean_text(value))
    return int(match.group(0).replace(",", "")) if match else 0


def clean_candidate(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\s*\((?:Unopposed|\d+(?:st|nd|rd|th) elected)\)\s*$", "", text)
    text = re.sub(r"\s*\((?:Lord Mayor|Deputy Lord Mayor)\)\s*", "", text)
    return clean_text(text)


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_sha256(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"{path}: source checksum changed to {actual}; expected {expected}")


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(0.08)
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def next_table(heading: Tag) -> Tag:
    table = heading.find_next("table")
    if table is None:
        raise SystemExit(f"Missing table after {clean_text(heading.get_text(' '))}")
    return table


def table_rows(table: Tag) -> list[list[str]]:
    return [
        [clean_text(cell.get_text(" ")) for cell in row.find_all(["th", "td"], recursive=False)]
        for row in table.find_all("tr")
    ]


def summary_values(section: Tag) -> dict[str, int]:
    heading = next((h for h in section.find_all(["h3", "h4"]) if clean_text(h.get_text(" ")) == "Count summary"), None)
    if heading is None:
        return {}
    values: dict[str, int] = {}
    for row in table_rows(next_table(heading)):
        if len(row) >= 2:
            values[row[0].rstrip(":").lower()] = integer(row[1])
    return values


def candidate_vote_table(section: Tag, heading_prefix: str, vote_column: int = 1) -> dict[str, int]:
    heading = next(
        (
            h for h in section.find_all(["h3", "h4"])
            if heading_prefix.lower() in clean_text(h.get_text(" ")).lower()
        ),
        None,
    )
    if heading is None:
        return {}
    votes: dict[str, int] = {}
    for row in table_rows(next_table(heading)):
        if len(row) <= vote_column or row[0].lower() in {"candidate", ""}:
            continue
        if not re.search(r"\d", row[vote_column]):
            continue
        votes[clean_candidate(row[0])] = integer(row[vote_column])
    return votes


def elected_names(section: Tag) -> list[str]:
    heading = next((h for h in section.find_all(["h3", "h4"]) if clean_text(h.get_text(" ")) == "Elected candidates"), None)
    if heading is None:
        return []
    return [clean_candidate(row[1]) for row in table_rows(next_table(heading)) if len(row) >= 2 and row[0].startswith("Elected")]


def base_values(
    *, district: str, council: str, ward: str, district_url: str, distribution_url: str,
    elected_member: str, elected_party: str, elected_members: str = "", elected_parties: str = "",
    members_to_elect: int = 1, quota: int = 0, enrolment: int = 0, formal: int = 0,
    informal: int = 0, majority: int = 0, constituency_code: str, contest_status: str = "official",
    result_note: str = "",
) -> dict[str, object]:
    total = formal + informal
    return {
        "district": district, "council": council, "ward": ward,
        "district_url": district_url, "distribution_url": distribution_url,
        "elected_member": elected_member, "elected_party": elected_party,
        "elected_members": elected_members or elected_member,
        "elected_parties": elected_parties or elected_party,
        "members_to_elect": members_to_elect, "quota": quota, "enrolment": enrolment,
        "formal_votes": formal, "informal_votes": informal, "total_votes": total,
        "turnout_pct": round(total / enrolment * 100, 2) if enrolment else "",
        "majority": majority, "electorate_type": council,
        "constituency_code": constituency_code, "contest_status": contest_status,
        "result_note": result_note,
    }


def result_row(base: dict[str, object], **values: object) -> dict[str, object]:
    row = {field: "" for field in FIELDS}
    row.update(base)
    row.update(values)
    return row


def parse_preferential_workbook(path: Path) -> tuple[dict[str, int], list[dict[str, object]]]:
    sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
    header_row = next((r for r in range(sheet.nrows) if clean_text(sheet.cell_value(r, 0)).startswith("Candidates Names")), -1)
    if header_row < 0:
        raise SystemExit(f"{path}: missing candidate header")
    candidate_columns = [
        (column, clean_candidate(sheet.cell_value(header_row, column)))
        for column in range(1, sheet.ncols)
        if clean_text(sheet.cell_value(header_row, column)).upper() != "TOTAL"
    ]
    candidate_columns = [(column, name) for column, name in candidate_columns if name]
    first_row = header_row + 1
    first = {name: integer(sheet.cell_value(first_row, column)) for column, name in candidate_columns}
    rounds: list[dict[str, object]] = []
    count = 0
    row = first_row + 1
    while row < sheet.nrows:
        label = clean_text(sheet.cell_value(row, 0))
        if not label.startswith("Transfer of "):
            row += 1
            continue
        excluded_match = re.search(r"ballot papers of (.+?) \(", label)
        if not excluded_match:
            raise SystemExit(f"{path}: could not parse exclusion label {label!r}")
        excluded = clean_candidate(excluded_match.group(1))
        totals_row = row + 1
        totals_label = clean_text(sheet.cell_value(totals_row, 0)).upper()
        if totals_label not in {"PROGRESSIVE TOTAL", "FINAL TOTAL"}:
            raise SystemExit(f"{path}: transfer row is not followed by a total row")
        count += 1
        rounds.append({
            "round": count,
            "excluded": excluded,
            "final": totals_label == "FINAL TOTAL",
            "transfers": {name: integer(sheet.cell_value(row, column)) for column, name in candidate_columns if sheet.cell_value(row, column) != ""},
            "totals": {name: integer(sheet.cell_value(totals_row, column)) for column, name in candidate_columns if sheet.cell_value(totals_row, column) != ""},
        })
        row = totals_row + 1
    if not rounds or not rounds[-1]["final"]:
        raise SystemExit(f"{path}: missing final total")
    return first, rounds


def parse_ordinary_council(
    session: requests.Session, official_name: str, display_name: str, page_url: str,
    page_path: Path, cache: Path, refresh: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
    output: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    sections: list[tuple[str, Tag]] = []
    for section in soup.select("div.cm"):
        heading = section.find(["h2", "h3"], recursive=False)
        if heading is None:
            continue
        match = re.fullmatch(r"(.+? Ward) \(1 vacancy\)", clean_text(heading.get_text(" ")))
        if match:
            sections.append((match.group(1), section))

    expected = METRO_COUNCILS[official_name][1]
    if len(sections) != expected:
        raise SystemExit(f"{official_name}: expected {expected} wards, found {len(sections)}")

    for ward, section in sections:
        district = f"{display_name} — {ward}"
        code = f"VICL24-{slug(display_name)}-{slug(ward.removesuffix(' Ward'))}"
        elected = elected_names(section)
        if len(elected) != 1:
            raise SystemExit(f"{district}: expected one elected candidate, found {elected}")
        winner = elected[0]
        first = candidate_vote_table(section, "First preference votes")
        uncontested = not first and "uncontested" in section.get_text(" ").lower()
        distribution = section.find("a", href=re.compile(r"\.xls(?:\?|$)", re.I))
        distribution_url = distribution.get("href", "") if distribution else ""
        summary = summary_values(section)
        enrolment = summary.get("enrolment", 0)
        formal = summary.get("formal votes", 0)
        informal = summary.get("informal votes", 0)
        if uncontested:
            first = {winner: 0}
            rounds = [{"round": 1, "excluded": "", "final": True, "transfers": {}, "totals": {winner: 0}}]
            status = "uncontested"
            note = "The only nominated candidate was elected unopposed; no poll was held."
        elif distribution_url:
            workbook_path = download(session, distribution_url, cache / "distributions" / f"{code}.xls", refresh)
            workbook_first, rounds = parse_preferential_workbook(workbook_path)
            if workbook_first != first:
                if "recount results" not in section.get_text(" ").lower():
                    raise SystemExit(f"{district}: webpage and distribution first preferences differ")
                recount_final = candidate_vote_table(section, "results after distribution")
                if not recount_final or sum(recount_final.values()) != formal:
                    raise SystemExit(f"{district}: recount final totals do not reconcile")
                rounds = [{"round": 1, "excluded": "", "final": True, "transfers": {}, "totals": recount_final}]
                distribution_url = page_url
            status = "official"
            note = (
                "Official VEC recount first preferences and final standing; the recount replaced the earlier distribution. "
                "Candidate affiliations are not stated on the official result page."
                if workbook_first != first
                else "Official VEC first preferences and complete preference distribution. Candidate affiliations are not stated on the official result page."
            )
        else:
            published_final = candidate_vote_table(section, "results after distribution")
            rounds = [{
                "round": 1, "excluded": "", "final": True, "transfers": {},
                "totals": published_final or dict(first),
            }]
            status = "official"
            note = (
                "Official VEC first preferences and final preference standing; a downloadable distribution workbook is not published on the result page. "
                "Candidate affiliations are not stated on the official result page."
                if published_final
                else "The winner received an absolute majority of first preferences, so no distribution was required. Candidate affiliations are not stated on the official result page."
            )

        final = rounds[-1]["totals"]
        ranked_final = sorted(final.items(), key=lambda item: (-int(item[1]), item[0]))
        if not uncontested and (not ranked_final or ranked_final[0][0] != winner):
            raise SystemExit(f"{district}: elected candidate does not lead the final count")
        majority = int(ranked_final[0][1]) - int(ranked_final[1][1]) if len(ranked_final) > 1 else 0
        base = base_values(
            district=district, council=display_name, ward=ward, district_url=page_url,
            distribution_url=distribution_url or page_url, elected_member=winner,
            elected_party="Affiliation not stated", enrolment=enrolment, formal=formal,
            informal=informal, majority=majority, constituency_code=code,
            contest_status=status, result_note=note,
        )
        if not uncontested and sum(first.values()) != formal:
            raise SystemExit(f"{district}: first preferences {sum(first.values())} != formal votes {formal}")
        if formal + informal != summary.get("voter turnout", formal + informal):
            raise SystemExit(f"{district}: formal and informal votes do not equal turnout")
        for candidate, votes in first.items():
            output.append(result_row(
                base, round_number=0, row_type="first", candidate=candidate,
                candidate_party="Affiliation not stated", candidate_elected=str(candidate == winner),
                candidate_elected_order=1 if candidate == winner else "", votes=votes,
            ))
        for item in rounds:
            for candidate, votes in item["transfers"].items():
                output.append(result_row(
                    base, round_number=item["round"], row_type="transfer",
                    excluded_candidate=item["excluded"], excluded_party="Affiliation not stated",
                    candidate=candidate, candidate_party="Affiliation not stated",
                    candidate_elected=str(candidate == winner), candidate_elected_order=1 if candidate == winner else "",
                    votes=votes,
                ))
            row_type = "final" if item["final"] else "progressive"
            for candidate, votes in item["totals"].items():
                output.append(result_row(
                    base, round_number=item["round"], row_type=row_type,
                    excluded_candidate=item["excluded"], excluded_party="Affiliation not stated" if item["excluded"] else "",
                    candidate=candidate, candidate_party="Affiliation not stated",
                    candidate_elected=str(candidate == winner), candidate_elected_order=1 if candidate == winner else "",
                    votes=votes,
                ))
        summaries.append({"district": district, "council": display_name, "ward": ward, "winner": winner, "formal": formal, "uncontested": uncontested})
    return output, summaries


def parse_leadership(page_path: Path, page_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
    section = soup.select_one("#LeadershipTeamResults")
    if section is None:
        raise SystemExit("Melbourne: missing leadership result")
    summary = summary_values(section)
    first_section = section.select_one("#fpvLeadership")
    final_section = section.select_one("#radLeadership")
    if first_section is None or final_section is None:
        raise SystemExit("Melbourne: missing leadership vote tables")
    first: dict[str, int] = {}
    parties: dict[str, str] = {}
    members: dict[str, list[str]] = {}
    for row in table_rows(first_section.find("table")):
        if len(row) < 3 or not re.search(r"\d", row[2]):
            continue
        people = [clean_candidate(part) for part in re.split(r"(?<=\))\s+", row[0]) if clean_candidate(part)]
        if len(people) != 2:
            # BeautifulSoup flattens the two BR-separated candidates; split at the second surname block.
            raw = re.sub(r"\s*\((?:Lord Mayor|Deputy Lord Mayor)\)", "|", row[0])
            people = [clean_candidate(part) for part in raw.split("|") if clean_candidate(part)]
        if len(people) != 2:
            raise SystemExit(f"Melbourne leadership: could not split team {row[0]!r}")
        team = " / ".join(people)
        first[team] = integer(row[2])
        parties[team] = row[1]
        members[team] = people
    final = candidate_vote_table(final_section, "Results for single vacancy")
    # The generic table parser sees each two-person team as one flattened string; match by member names.
    matched_final: dict[str, int] = {}
    for raw, votes in final.items():
        key = next((team for team, people in members.items() if all(person in clean_candidate(raw) for person in people)), "")
        if not key:
            compact = re.sub(r"\s+", " ", raw)
            key = next((team for team in first if all(part in compact for part in team.split(" / "))), "")
        if not key:
            raise SystemExit(f"Melbourne leadership: could not match final team {raw!r}")
        matched_final[key] = votes
    final = matched_final
    winner = max(final, key=final.get)
    runner_up = sorted(final.values(), reverse=True)[1]
    distribution = section.find("a", href=re.compile(r"\.xls(?:\?|$)", re.I))
    base = base_values(
        district="Melbourne — Leadership Team", council="Melbourne", ward="Leadership Team",
        district_url=page_url, distribution_url=distribution.get("href", page_url) if distribution else page_url,
        elected_member=winner, elected_party=parties[winner], elected_members="; ".join(members[winner]),
        elected_parties="; ".join([parties[winner]] * 2), members_to_elect=2,
        enrolment=summary["enrolment"], formal=summary["formal votes"], informal=summary["informal votes"],
        majority=final[winner] - runner_up, constituency_code="VICL24-melbourne-leadership",
        result_note="Lord Mayor and Deputy Lord Mayor candidates nominate and are elected as a paired leadership team.",
    )
    if sum(first.values()) != summary["formal votes"] or sum(final.values()) != summary["formal votes"]:
        raise SystemExit("Melbourne leadership totals do not reconcile")
    rows = []
    for candidate, votes in first.items():
        rows.append(result_row(base, round_number=0, row_type="first", candidate=candidate, candidate_party=parties[candidate], candidate_elected=str(candidate == winner), candidate_elected_order=1 if candidate == winner else "", votes=votes))
    for candidate, votes in final.items():
        rows.append(result_row(base, round_number=1, row_type="final", candidate=candidate, candidate_party=parties[candidate], candidate_elected=str(candidate == winner), candidate_elected_order=1 if candidate == winner else "", votes=votes))
    return rows


def councillor_parties(section: Tag) -> dict[str, str]:
    parties: dict[str, str] = {}
    current = "Ungrouped"
    for row in section.select("table tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = clean_text(cells[0].get_text(" "))
        value = clean_text(cells[1].get_text(" "))
        classes = set(cells[0].get("class", []))
        if "list-item-title" in classes and label and label.upper() != "GROUP TOTAL":
            current = label
        elif "list-item-body" in classes and label and label not in {"Above the line votes (ticket votes)", "Below the line votes"} and re.search(r"\d", value):
            parties[clean_candidate(label)] = current
    return parties


def parse_councillors(page_path: Path, page_url: str, workbook_path: Path) -> list[dict[str, object]]:
    soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
    section = soup.select_one("#CouncillorResults")
    first_section = soup.select_one("#fpvCouncillor")
    elected_section = soup.select_one("#councillors")
    if section is None or first_section is None or elected_section is None:
        raise SystemExit("Melbourne: missing councillor result sections")
    summary = summary_values(section)
    parties = councillor_parties(first_section)
    elected = elected_names(elected_section)
    if len(elected) != 9:
        raise SystemExit(f"Melbourne: expected 9 councillors, found {elected}")
    sheet = xlrd.open_workbook(str(workbook_path)).sheet_by_index(0)
    header_row = next(r for r in range(sheet.nrows) if clean_text(sheet.cell_value(r, 0)).startswith("Count"))
    columns = [(column, clean_candidate(sheet.cell_value(header_row, column))) for column in range(5, sheet.ncols)]
    columns = [(column, candidate) for column, candidate in columns if candidate and candidate not in {"Gain/Loss", "Exhausted", "TOTAL", "Candidates elected at this count"}]
    first_row = next(r for r in range(header_row + 1, sheet.nrows) if clean_text(sheet.cell_value(r, 1)) == "1st Preferences")
    final_row = max(r for r in range(first_row, sheet.nrows) if clean_text(sheet.cell_value(r, 3)) == "PTotal")
    first = {candidate: integer(sheet.cell_value(first_row, column)) for column, candidate in columns}
    final = {candidate: integer(sheet.cell_value(final_row, column)) for column, candidate in columns}
    missing_parties = sorted(set(first) - set(parties))
    if missing_parties:
        raise SystemExit(f"Melbourne: missing councillor groups for {missing_parties}")
    workbook_final_total = integer(sheet.cell_value(final_row, sheet.ncols - 2))
    if sum(first.values()) != summary["formal votes"] or workbook_final_total != summary["formal votes"]:
        raise SystemExit("Melbourne councillor totals do not reconcile")
    elected_set = set(elected)
    final_gap = min(final[name] for name in elected) - max(votes for name, votes in final.items() if name not in elected_set)
    distribution = section.find("a", href=re.compile(r"\.xls(?:\?|$)", re.I))
    base = base_values(
        district="Melbourne — Councillors", council="Melbourne", ward="Councillors",
        district_url=page_url, distribution_url=distribution.get("href", page_url) if distribution else page_url,
        elected_member="; ".join(elected), elected_party="; ".join(parties[name] for name in elected),
        elected_members="; ".join(elected), elected_parties="; ".join(parties[name] for name in elected),
        members_to_elect=9, quota=summary["quota"], enrolment=summary["enrolment"],
        formal=summary["formal votes"], informal=summary["informal votes"], majority=final_gap,
        constituency_code="VICL24-melbourne-councillors",
        result_note="Nine councillors are elected citywide by proportional representation. First preferences include above-the-line ticket votes allocated in the official count.",
    )
    order = {candidate: index + 1 for index, candidate in enumerate(elected)}
    rows = []
    for candidate, votes in first.items():
        rows.append(result_row(base, round_number=0, row_type="first", candidate=candidate, candidate_party=parties[candidate], candidate_status="Elected" if candidate in elected_set else "", candidate_elected=str(candidate in elected_set), candidate_elected_order=order.get(candidate, ""), votes=votes))
    for candidate, votes in final.items():
        rows.append(result_row(base, round_number=1, row_type="final", candidate=candidate, candidate_party=parties[candidate], candidate_status="Elected" if candidate in elected_set else "", candidate_elected=str(candidate in elected_set), candidate_elected_order=order.get(candidate, ""), votes=votes))
    return rows


def rounded_geometry(raw: dict[str, object], tolerance: float = 0.00018) -> dict[str, object]:
    geometry = make_valid(shape(raw)).simplify(tolerance, preserve_topology=True)
    geometry = make_valid(geometry)
    result = mapping(geometry)

    def rounded(value):
        if isinstance(value, (list, tuple)):
            return [rounded(item) for item in value]
        return round(float(value), 5)

    result["coordinates"] = rounded(result["coordinates"])
    return result


def build_boundaries(ward_path: Path, melbourne_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    source = json.loads(ward_path.read_text(encoding="utf-8"))
    by_lga = {display.upper(): display for official, (display, _) in METRO_COUNCILS.items() if display != "Melbourne"}
    ward_features = []
    for feature in source["features"]:
        props = feature["properties"]
        council = by_lga.get(clean_text(props.get("lga_name")).upper())
        if not council:
            continue
        ward = clean_text(props.get("ward_label"))
        district = f"{council} — {ward}"
        ward_features.append({
            "type": "Feature",
            "properties": {
                "district": district, "council": council, "ward": ward,
                "constituency_code": f"VICL24-{slug(council)}-{slug(ward.removesuffix(' Ward'))}",
            },
            "geometry": rounded_geometry(feature["geometry"]),
        })
    if len(ward_features) != 288:
        raise SystemExit(f"Expected 288 metropolitan ward boundaries, found {len(ward_features)}")
    ward_features.sort(key=lambda feature: feature["properties"]["district"])
    melbourne_source = json.loads(melbourne_path.read_text(encoding="utf-8"))
    if len(melbourne_source.get("features", [])) != 1:
        raise SystemExit("Expected one Melbourne LGA boundary")
    geometry = rounded_geometry(melbourne_source["features"][0]["geometry"], 0.00008)
    city_features = [
        {"type": "Feature", "properties": {"district": district, "council": "Melbourne", "constituency_code": code}, "geometry": geometry}
        for district, code in (
            ("Melbourne — Leadership Team", "VICL24-melbourne-leadership"),
            ("Melbourne — Councillors", "VICL24-melbourne-councillors"),
        )
    ]
    return ({"type": "FeatureCollection", "features": ward_features}, {"type": "FeatureCollection", "features": city_features})


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_geojson(path: Path, collection: dict[str, object]) -> None:
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Greater Melbourne 2024 local council election datasets")
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/vic_local_2024"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": "vic-election-preference-explorer/1.0 (+https://github.com/adhni/vic-election)"})
    args.output_dir.mkdir(parents=True, exist_ok=True)

    index_path = download(session, RESULTS_INDEX, args.cache_dir / "results-index.html", args.refresh)
    index = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser")
    links = {
        clean_text(anchor.get_text(" ")): urljoin(RESULTS_INDEX, anchor.get("href", ""))
        for anchor in index.select("a[href]")
        if clean_text(anchor.get_text(" ")) in METRO_COUNCILS
    }
    if set(links) != set(METRO_COUNCILS):
        raise SystemExit(f"Result index metro council mismatch: missing {sorted(set(METRO_COUNCILS) - set(links))}")

    ordinary_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    melbourne_page: Path | None = None
    melbourne_url = ""
    for official_name, (display_name, _) in METRO_COUNCILS.items():
        page_url = links[official_name]
        page_path = download(session, page_url, args.cache_dir / "pages" / f"{slug(official_name)}.html", args.refresh)
        if display_name == "Melbourne":
            melbourne_page, melbourne_url = page_path, page_url
            continue
        rows, council_summaries = parse_ordinary_council(session, official_name, display_name, page_url, page_path, args.cache_dir, args.refresh)
        ordinary_rows.extend(rows)
        summaries.extend(council_summaries)

    if len(summaries) != 288 or sum(bool(row["uncontested"]) for row in summaries) != 8:
        raise SystemExit("Ordinary metro contest totals changed; expected 288 wards including 8 uncontested")
    if len({row["district"] for row in summaries}) != 288:
        raise SystemExit("Ordinary metro district identifiers are not unique")

    assert melbourne_page is not None
    melbourne_soup = BeautifulSoup(melbourne_page.read_text(encoding="utf-8"), "html.parser")
    councillor_link = melbourne_soup.select_one("#CouncillorResults a[href$='.xls']")
    if councillor_link is None:
        raise SystemExit("Melbourne councillor distribution link is missing")
    councillor_workbook = download(session, councillor_link["href"], args.cache_dir / "distributions" / "melbourne-councillors.xls", args.refresh)
    leadership_rows = parse_leadership(melbourne_page, melbourne_url)
    councillor_rows = parse_councillors(melbourne_page, melbourne_url, councillor_workbook)

    ward_path = download(session, WARD_WFS, args.cache_dir / "ward_2024.geojson", args.refresh)
    melbourne_boundary_path = download(session, MELBOURNE_LGA_WFS, args.cache_dir / "melbourne_lga.geojson", args.refresh)
    require_sha256(ward_path, SOURCE_SHA256["wards"])
    require_sha256(melbourne_boundary_path, SOURCE_SHA256["melbourne_lga"])
    ward_boundaries, city_boundaries = build_boundaries(ward_path, melbourne_boundary_path)
    result_codes = {row["constituency_code"] for row in ordinary_rows}
    boundary_codes = {feature["properties"]["constituency_code"] for feature in ward_boundaries["features"]}
    if result_codes != boundary_codes:
        raise SystemExit(f"Ward result/boundary mismatch: results-only {sorted(result_codes-boundary_codes)}, boundaries-only {sorted(boundary_codes-result_codes)}")

    write_csv(args.output_dir / "vic_local_2024_wards.csv", ordinary_rows)
    write_csv(args.output_dir / "melbourne_2024_leadership.csv", leadership_rows)
    write_csv(args.output_dir / "melbourne_2024_councillors.csv", councillor_rows)
    write_geojson(args.output_dir / "vic_local_2024_ward_boundaries.geojson", ward_boundaries)
    write_geojson(args.output_dir / "melbourne_2024_lga_boundaries.geojson", city_boundaries)
    for feature in city_boundaries["features"]:
        contest = "leadership" if feature["properties"]["district"].endswith("Leadership Team") else "councillors"
        write_geojson(
            args.output_dir / f"melbourne_2024_{contest}_boundary.geojson",
            {"type": "FeatureCollection", "features": [feature]},
        )
    print(f"Built 30 councils, 288 wards ({len(ordinary_rows):,} CSV rows), and both Melbourne contests")
    print(f"Sources: {RESULTS_INDEX} and {BOUNDARY_SOURCE}")


if __name__ == "__main__":
    main()
