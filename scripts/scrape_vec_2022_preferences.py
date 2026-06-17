#!/usr/bin/env python3
"""
Scrape Victorian state election Legislative Assembly district results
and preference distributions from official VEC pages.

Outputs:
  data/vic_<year>_preferences_long.csv
  data/vic_<year>_district_summary.csv

Notes:
- Source: Victorian Electoral Commission state election results pages.
- The VEC pages are ordinary HTML, but table shapes can differ slightly by district.
- This script is intentionally defensive: it logs any district it cannot parse so you can fix edge cases.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://www.vec.vic.gov.au"
HISTORICAL_RESULTS_BASE = "https://itsitecoreblobvecprd01.blob.core.windows.net/public-files/historical-results"
INDICATIVE_URL = f"{BASE}/voting/electoral-statistics/state-election-statistics/full-preference-distributions"
UA = "Mozilla/5.0 (compatible; vic-election-preference-research/0.1; +https://www.vec.vic.gov.au/)"

EXPECTED_LONG_COLUMNS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "round_number",
    "row_type",
    "excluded_candidate",
    "excluded_party",
    "candidate",
    "candidate_party",
    "votes",
]

EXPECTED_SUMMARY_COLUMNS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "primary_leader",
    "primary_leader_party",
    "primary_leader_votes",
    "winner",
    "winner_party",
    "winner_final_votes",
    "runner_up",
    "runner_up_party",
    "runner_up_final_votes",
    "final_margin",
    "preference_changed_result",
    "winner_transfer_gain",
]


@dataclass
class DistrictMeta:
    district: str
    district_url: str
    distribution_url: str = ""
    elected_member: str = ""
    elected_party: str = ""
    enrolment: Optional[int] = None
    formal_votes: Optional[int] = None
    informal_votes: Optional[int] = None
    total_votes: Optional[int] = None
    turnout_pct: Optional[float] = None
    majority: Optional[int] = None


def clean_text(x: object) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(x or "")).strip()


def clean_int(x: object) -> Optional[int]:
    if x is None:
        return None
    s = clean_text(x)
    if not s or s.lower() == "nan":
        return None
    # remove percentages, commas, spaces, footnotes
    m = re.search(r"-?\d[\d,]*", s)
    if not m:
        return None
    return int(m.group(0).replace(",", ""))


def clean_float(x: object) -> Optional[float]:
    if x is None:
        return None
    s = clean_text(x)
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    return float(m.group(0))


def fetch(session: requests.Session, url: str, sleep: float = 0.25) -> str:
    time.sleep(sleep)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_bytes(session: requests.Session, url: str, sleep: float = 0.25) -> bytes:
    time.sleep(sleep)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def read_html_tables(html: str) -> List[pd.DataFrame]:
    return pd.read_html(StringIO(html))


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    return session


def get_indicative_distribution_links(session: requests.Session) -> Dict[str, str]:
    html = fetch(session, INDICATIVE_URL)
    soup = BeautifulSoup(html, "html.parser")
    links: Dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        label = clean_text(a.get_text(" "))
        if "indicative distribution of preference" not in label.lower():
            continue
        if "District" not in label:
            continue
        district = re.sub(r"\s+District\b.*$", "", label).strip()
        if not district or "supplementary election" in label.lower():
            continue
        links[district] = urljoin(BASE, a["href"])

    return links


def election_index_url(year: int) -> str:
    return f"{BASE}/results/state-election-results/{year}-state-election-results/results-by-district"


def historical_summary_url(year: int) -> str:
    if year in {2006, 2010}:
        return f"{HISTORICAL_RESULTS_BASE}/state{year}/state{year}resultsummary.html"
    return f"{HISTORICAL_RESULTS_BASE}/state{year}/summary.html"


def discover_districts(session: requests.Session, year: int, limit: Optional[int] = None) -> List[DistrictMeta]:
    if year < 2022:
        return discover_historical_districts(session, year, limit=limit)

    html = fetch(session, election_index_url(year), sleep=0)
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    districts: List[DistrictMeta] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        url = urljoin(BASE, href)
        if "/results-by-district/" not in url:
            continue
        if not re.search(r"-district-results/?$", url):
            continue
        if url in seen:
            continue
        seen.add(url)
        label = clean_text(a.get_text(" "))
        # Link text is like "Melbourne District Elected member: ..."
        district = re.sub(r"\s+District\s+Elected member:.*$", "", label).strip()
        if not district:
            district = url.rstrip("/").split("/")[-1].replace("-district-results", "").replace("-", " ").title()
        districts.append(DistrictMeta(district=district, district_url=url))
        if limit and len(districts) >= limit:
            break

    return districts


def discover_historical_districts(session: requests.Session, year: int, limit: Optional[int] = None) -> List[DistrictMeta]:
    summary_url = historical_summary_url(year)
    html = fetch(session, summary_url, sleep=0)
    soup = BeautifulSoup(html, "html.parser")
    districts: List[DistrictMeta] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = clean_text(a.get_text(" "))
        if not re.search(r"district\.html$", href, flags=re.I):
            continue
        if not label.endswith("District"):
            continue
        url = urljoin(summary_url, href)
        if url in seen:
            continue
        seen.add(url)
        district = re.sub(r"\s+District$", "", label).strip()
        districts.append(DistrictMeta(district=district, district_url=url))
        if limit and len(districts) >= limit:
            break

    return districts


def parse_key_numbers_from_text(text: str, meta: DistrictMeta) -> DistrictMeta:
    # Use broad regex because VEC line breaks move around in raw text.
    patterns = {
        "enrolment": r"Total enrolment(?:\s+as at close of rolls)?:\s*([\d,]+)",
        "formal_votes": r"Formal votes:\s*([\d,]+)",
        "informal_votes": r"Informal votes:\s*([\d,]+)",
        "total_votes": r"Total votes:\s*([\d,]+)\s*\(([-\d.]+)%",
        "majority": r"Votes required to constitute an absolute majority:\s*([\d,]+)",
    }
    for attr, pat in patterns.items():
        m = re.search(pat, text, flags=re.I)
        if not m:
            continue
        if attr == "total_votes":
            meta.total_votes = clean_int(m.group(1))
            meta.turnout_pct = clean_float(m.group(2))
        else:
            setattr(meta, attr, clean_int(m.group(1)))
    return meta


def parse_result_page(session: requests.Session, meta: DistrictMeta) -> Tuple[DistrictMeta, Dict[str, str]]:
    html = fetch(session, meta.district_url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    compact = clean_text(text)

    # Elected member block.
    elected_table = soup.find("table", attrs={"title": re.compile(r"Elected member", re.I)})
    if elected_table:
        member_span = elected_table.find(class_=re.compile(r"bold-text", re.I))
        party_span = elected_table.find(class_=re.compile(r"italic", re.I))
        if member_span:
            meta.elected_member = clean_text(member_span.get_text(" "))
        if party_span:
            meta.elected_party = clean_text(party_span.get_text(" "))
    if not meta.elected_member:
        m = re.search(r"Elected member\s+(.+?)\s+(Australian Labor Party - Victorian Branch|Australian Greens|Liberal|The Nationals|Independent|Family First Victoria|Animal Justice Party|Victorian Socialists|Fiona Patten's Reason Party|Freedom Party of Victoria)", compact)
        if m:
            meta.elected_member = clean_text(m.group(1))
            meta.elected_party = clean_text(m.group(2))

    meta = parse_key_numbers_from_text(compact, meta)

    # Find distribution URL from district page.
    preferred_links = []
    fallback_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = clean_text(a.get_text(" ")).lower()
        url = urljoin(meta.district_url, href)
        if "distribution" in url.lower() or "distribution" in label or label in {"distributions", "view indicative distributions"}:
            if "results-distribution" in url.lower():
                preferred_links.append(url)
            else:
                fallback_links.append(url)
    if preferred_links:
        meta.distribution_url = preferred_links[0]
    elif fallback_links:
        if HISTORICAL_RESULTS_BASE in meta.district_url:
            meta.distribution_url = fallback_links[0]
        else:
            indicative_links = get_indicative_distribution_links(session)
            meta.distribution_url = indicative_links.get(meta.district, fallback_links[0])
    else:
        if HISTORICAL_RESULTS_BASE not in meta.district_url:
            # URL pattern is consistent for normal 2022 districts.
            slug = meta.district_url.rstrip("/").split("/")[-1].replace("-district-results", "")
            meta.distribution_url = f"{meta.district_url.rstrip('/')}/{slug}-results-distribution"

    party_map = extract_party_map_from_result_tables(html)
    return meta, party_map


def extract_party_map_from_result_tables(html: str) -> Dict[str, str]:
    party_map: Dict[str, str] = {}
    try:
        tables = read_html_tables(html)
    except ValueError:
        return party_map

    for df in tables:
        cols = [clean_text(c) for c in df.columns]
        lower_cols = [c.lower() for c in cols]
        if not any("candidate" == c.lower() for c in cols):
            continue
        if not any("party" == c.lower() for c in cols):
            continue
        if not any("pref" in c.lower() or "votes" in c.lower() for c in cols):
            continue
        df = df.copy()
        df.columns = cols
        if "Candidate" not in df.columns or "Party" not in df.columns:
            # case-insensitive fallback
            cand_col = next((c for c in df.columns if c.lower() == "candidate"), None)
            party_col = next((c for c in df.columns if c.lower() == "party"), None)
        else:
            cand_col, party_col = "Candidate", "Party"
        if not cand_col or not party_col:
            continue
        for _, row in df.iterrows():
            cand = clean_text(row.get(cand_col, ""))
            party = clean_text(row.get(party_col, "")) or "Independent"
            if cand and cand.lower() != "nan":
                party_map[cand] = party
    return party_map


def find_distribution_table(html: str) -> pd.DataFrame:
    tables = read_html_tables(html)
    for df in tables:
        full = " ".join(clean_text(x) for x in df.astype(str).values.ravel())
        if "Total first preference votes" in full and ("Transfer of" in full or "FINAL TOTAL" in full):
            return df
    raise ValueError("Could not find distribution table")


def find_distribution_table_tag(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        title = clean_text(table.get("title", ""))
        full = clean_text(table.get_text(" "))
        if "Distribution of preference votes" in title:
            return table
        if "Total first preference votes" in full and ("Transfer of" in full or "FINAL TOTAL" in full):
            return table
    raise ValueError("Could not find distribution table")


def normalise_distribution_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # flatten multi-index column headers if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [clean_text(" ".join(map(str, c))) for c in df.columns]
    else:
        df.columns = [clean_text(c) for c in df.columns]

    # Some pages may parse the first row as data instead of header. Detect and fix if needed.
    joined_cols = " ".join(df.columns)
    if "Total first preference" in joined_cols or "Transfer of" in joined_cols:
        # Read_html probably mis-read the table. Leave as-is, caller will fail loudly.
        return df

    # Remove empty duplicate columns.
    keep = []
    seen = {}
    for c in df.columns:
        base = clean_text(c)
        if not base or base.lower().startswith("unnamed"):
            base = "row_label" if not keep else f"blank_{len(keep)}"
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        keep.append(base)
    df.columns = keep
    return df


def parse_transfer_label(label: str) -> Tuple[Optional[int], str]:
    # Example: Transfer of 428 ballot papers of AL-SAIMARY, Laylah (1st excluded candidate)
    m = re.search(r"Transfer of\s+[\d,]+\s+ballot[- ]papers of\s+(.+?)\s*\((\d+)(?:st|nd|rd|th) excluded candidate\)", label, flags=re.I)
    if m:
        return int(m.group(2)), clean_text(m.group(1))
    m = re.search(r"Transfer of\s+[\d,]+\s+ballot[- ]papers of\s+(.+)$", label, flags=re.I)
    if m:
        return None, clean_text(m.group(1))
    return None, ""


def make_long_row(
    meta: DistrictMeta,
    party_map: Dict[str, str],
    round_number: int,
    row_type: str,
    excluded: str,
    candidate: str,
    votes: int,
) -> dict:
    return {
        "district": meta.district,
        "district_url": meta.district_url,
        "distribution_url": meta.distribution_url,
        "elected_member": meta.elected_member,
        "elected_party": meta.elected_party,
        "enrolment": meta.enrolment,
        "formal_votes": meta.formal_votes,
        "informal_votes": meta.informal_votes,
        "total_votes": meta.total_votes,
        "turnout_pct": meta.turnout_pct,
        "majority": meta.majority,
        "round_number": round_number,
        "row_type": row_type,
        "excluded_candidate": excluded,
        "excluded_party": party_map.get(excluded, "Independent") if excluded else "",
        "candidate": candidate,
        "candidate_party": party_map.get(candidate, "Independent"),
        "votes": votes,
    }


def is_legacy_state_archive(url: str) -> bool:
    return bool(re.search(r"state(?:2006|2010)", url))


def parse_distribution_rows(meta: DistrictMeta, html: str, party_map: Dict[str, str]) -> List[dict]:
    if is_legacy_state_archive(meta.distribution_url):
        return parse_legacy_html_distribution_rows(meta, html, party_map)

    table = normalise_distribution_table(find_distribution_table(html))
    if table.empty or len(table.columns) < 3:
        raise ValueError("Distribution table is empty or malformed")

    label_col = table.columns[0]
    candidate_cols = [c for c in table.columns[1:] if clean_text(c).upper() != "TOTAL"]

    rows: List[dict] = []
    current_round = 0
    current_excluded = ""

    for _, raw in table.iterrows():
        label = clean_text(raw.get(label_col, ""))
        if not label or label.lower() == "nan":
            continue

        row_type: Optional[str] = None
        excluded = current_excluded
        round_number = current_round

        if re.search(r"Total first preference votes", label, flags=re.I):
            row_type = "first"
            round_number = 0
            excluded = ""
        elif re.search(r"^Transfer of", label, flags=re.I):
            parsed_round, parsed_excluded = parse_transfer_label(label)
            current_round = parsed_round or (current_round + 1)
            current_excluded = parsed_excluded
            row_type = "transfer"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^Progressive Total", label, flags=re.I):
            row_type = "progressive"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^FINAL TOTAL", label, flags=re.I):
            row_type = "final"
            round_number = current_round
            excluded = current_excluded
        else:
            continue

        for candidate in candidate_cols:
            candidate_clean = clean_text(candidate)
            if not candidate_clean or candidate_clean.lower().startswith("blank_"):
                continue
            votes = clean_int(raw.get(candidate))
            if votes is None:
                continue
            rows.append(make_long_row(meta, party_map, round_number, row_type, excluded, candidate_clean, votes))
    return rows


def parse_legacy_html_distribution_rows(meta: DistrictMeta, html: str, party_map: Dict[str, str]) -> List[dict]:
    table = find_distribution_table_tag(html)
    header = table.find("thead")
    header_cells = header.find_all(["th", "td"]) if header else []
    candidates = [clean_text(cell.get_text(" ")) for cell in header_cells[1:]]
    candidates = [c for c in candidates if c and c.upper() != "TOTAL"]
    if not candidates:
        raise ValueError("Could not find legacy distribution candidate headers")

    rows: List[dict] = []
    current_round = 0
    current_excluded = ""

    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        label_cell = tr.find(["th", "td"])
        if not label_cell:
            continue
        label = clean_text(label_cell.get_text(" "))
        if not label:
            continue

        row_type: Optional[str] = None
        excluded = current_excluded
        round_number = current_round

        if re.search(r"Total first preference votes", label, flags=re.I):
            row_type = "first"
            round_number = 0
            excluded = ""
        elif re.search(r"^Transfer of", label, flags=re.I):
            parsed_round, parsed_excluded = parse_transfer_label(label)
            current_round = parsed_round or (current_round + 1)
            current_excluded = parsed_excluded
            row_type = "transfer"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^Progressive Total", label, flags=re.I):
            row_type = "progressive"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^FINAL TOTAL", label, flags=re.I):
            row_type = "final"
            round_number = current_round
            excluded = current_excluded
        else:
            continue

        candidate_index = 0
        candidate_values: List[Tuple[str, int]] = []
        total_value: Optional[int] = None
        for cell in tr.find_all(["td"]):
            value = clean_int(cell.get_text(" "))

            if value is None:
                # The 2010 VEC pages use large colspan values as visual blanks
                # for candidates already excluded. Treat any blank span as one
                # skipped candidate slot.
                candidate_index += 1
                continue

            if candidate_index >= len(candidates):
                if total_value is None:
                    total_value = value
                continue
            candidate_values.append((candidates[candidate_index], value))
            candidate_index += 1

        if row_type == "first" and total_value is not None:
            meta.formal_votes = total_value
        for candidate, value in candidate_values:
            rows.append(make_long_row(meta, party_map, round_number, row_type, excluded, candidate, value))

    return rows


def parse_excel_distribution_rows(meta: DistrictMeta, content: bytes, party_map: Dict[str, str]) -> List[dict]:
    table = pd.read_excel(BytesIO(content), header=None)
    if table.empty or len(table.columns) < 3:
        raise ValueError("Excel distribution sheet is empty or malformed")

    header_index = None
    for idx, raw in table.iterrows():
        if "Candidates Names" in clean_text(raw.iloc[0]):
            header_index = idx
            break
    if header_index is None:
        raise ValueError("Could not find Excel candidate header row")

    candidate_cols: List[Tuple[int, str]] = []
    total_col: Optional[int] = None
    for col in table.columns[1:]:
        value = clean_text(table.iat[header_index, col])
        if not value or value.lower() == "nan":
            continue
        if value.upper() == "TOTAL":
            total_col = col
            continue
        candidate_cols.append((col, value))

    if not candidate_cols:
        raise ValueError("Could not find Excel candidate columns")

    rows: List[dict] = []
    current_round = 0
    current_excluded = ""

    for _, raw in table.iloc[header_index + 1:].iterrows():
        label = clean_text(raw.iloc[0])
        if not label or label.lower() == "nan":
            continue

        row_type: Optional[str] = None
        excluded = current_excluded
        round_number = current_round

        if re.search(r"Total first preference votes", label, flags=re.I):
            row_type = "first"
            round_number = 0
            excluded = ""
        elif re.search(r"^Transfer of", label, flags=re.I):
            parsed_round, parsed_excluded = parse_transfer_label(label)
            current_round = parsed_round or (current_round + 1)
            current_excluded = parsed_excluded
            row_type = "transfer"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^Progressive Total", label, flags=re.I):
            row_type = "progressive"
            round_number = current_round
            excluded = current_excluded
        elif re.search(r"^FINAL TOTAL", label, flags=re.I):
            row_type = "final"
            round_number = current_round
            excluded = current_excluded
        else:
            continue

        if total_col is not None and row_type == "first":
            excel_formal_votes = clean_int(raw.iloc[total_col])
            if excel_formal_votes is not None:
                meta.formal_votes = excel_formal_votes

        for col, candidate in candidate_cols:
            votes = clean_int(raw.iloc[col])
            if votes is None:
                continue
            rows.append(make_long_row(meta, party_map, round_number, row_type, excluded, candidate, votes))

    return rows


def parse_historical_result_rows(meta: DistrictMeta, html: str, party_map: Dict[str, str]) -> List[dict]:
    if is_legacy_state_archive(meta.district_url):
        return parse_legacy_historical_result_rows(meta, html, party_map)

    rows: List[dict] = []
    tables = read_html_tables(html)

    for df in tables:
        cols = [clean_text(c) for c in df.columns]
        df = df.copy()
        df.columns = cols

        cand_col = next((c for c in cols if c.lower() == "candidate"), None)
        party_col = next((c for c in cols if c.lower() == "party"), None)
        first_col = next((c for c in cols if "1st pref votes" in c.lower()), None)
        final_col = next((c for c in cols if "votes after distribution" in c.lower() or "preferred votes" in c.lower()), None)

        if cand_col and party_col and first_col:
            for _, row in df.iterrows():
                candidate = clean_text(row.get(cand_col, ""))
                if not candidate or candidate.lower() == "nan":
                    continue
                party_map[candidate] = clean_text(row.get(party_col, "")) or "Independent"
                votes = clean_int(row.get(first_col))
                if votes is not None:
                    rows.append(make_long_row(meta, party_map, 0, "first", "", candidate, votes))
            continue

        if cand_col and party_col and final_col:
            for _, row in df.iterrows():
                candidate = clean_text(row.get(cand_col, ""))
                if not candidate or candidate.lower() == "nan":
                    continue
                party_map[candidate] = clean_text(row.get(party_col, "")) or party_map.get(candidate, "Independent")
                votes = clean_int(row.get(final_col))
                if votes is not None:
                    rows.append(make_long_row(meta, party_map, 1, "final", "", candidate, votes))

    return rows


def first_integer_cell(cells: List[str]) -> Optional[int]:
    for cell in cells:
        if "%" in cell:
            continue
        value = clean_int(cell)
        if value is not None:
            return value
    return None


def party_from_cells(cells: List[str]) -> str:
    if not cells:
        return "Independent"
    party = cells[0]
    if not party or "%" in party or clean_int(party) is not None:
        return "Independent"
    return party


def parse_legacy_historical_result_rows(meta: DistrictMeta, html: str, party_map: Dict[str, str]) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[dict] = []

    for table in soup.find_all("table"):
        title = clean_text(table.get("title", ""))
        if title == "First preference votes":
            row_type = "first"
            round_number = 0
        elif title == "Two candidate preferred vote":
            row_type = "final"
            round_number = 1
        else:
            continue

        for tr in table.find_all("tr"):
            cells = [clean_text(cell.get_text(" ")) for cell in tr.find_all("td")]
            if len(cells) < 2:
                continue
            candidate = cells[0]
            if not candidate or "voting centre" in candidate.lower():
                continue
            party = party_from_cells(cells[1:])
            value = first_integer_cell(cells[2:] if party != "Independent" else cells[1:])
            if value is None:
                continue
            party_map[candidate] = party
            rows.append(make_long_row(meta, party_map, round_number, row_type, "", candidate, value))

    first_total = sum(r["votes"] for r in rows if r["row_type"] == "first")
    if first_total:
        meta.formal_votes = first_total
        for row in rows:
            row["formal_votes"] = first_total

    return rows


def make_summary(long_rows: List[dict]) -> List[dict]:
    by_district: Dict[str, List[dict]] = {}
    for r in long_rows:
        by_district.setdefault(r["district"], []).append(r)

    summaries = []
    for district, rows in by_district.items():
        first_rows = [r for r in rows if r["row_type"] == "first"]
        final_rows = [r for r in rows if r["row_type"] == "final"]
        if not first_rows or not final_rows:
            continue
        primary_leader = max(first_rows, key=lambda r: r["votes"])
        ordered_final = sorted(final_rows, key=lambda r: r["votes"], reverse=True)
        winner = ordered_final[0]
        runner = ordered_final[1] if len(ordered_final) > 1 else None
        winner_first = next((r for r in first_rows if r["candidate"] == winner["candidate"]), None)
        m = rows[0]
        summaries.append({
            "district": district,
            "district_url": m["district_url"],
            "distribution_url": m["distribution_url"],
            "elected_member": m["elected_member"],
            "elected_party": m["elected_party"],
            "enrolment": m["enrolment"],
            "formal_votes": m["formal_votes"],
            "informal_votes": m["informal_votes"],
            "total_votes": m["total_votes"],
            "turnout_pct": m["turnout_pct"],
            "majority": m["majority"],
            "primary_leader": primary_leader["candidate"],
            "primary_leader_party": primary_leader["candidate_party"],
            "primary_leader_votes": primary_leader["votes"],
            "winner": winner["candidate"],
            "winner_party": winner["candidate_party"],
            "winner_final_votes": winner["votes"],
            "runner_up": runner["candidate"] if runner else "",
            "runner_up_party": runner["candidate_party"] if runner else "",
            "runner_up_final_votes": runner["votes"] if runner else None,
            "final_margin": winner["votes"] - runner["votes"] if runner else None,
            "preference_changed_result": primary_leader["candidate"] != winner["candidate"],
            "winner_transfer_gain": winner["votes"] - (winner_first["votes"] if winner_first else 0),
        })
    return summaries


def write_csv(path: Path, rows: List[dict], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2022, help="Election year to scrape, for example 2022 or 2018")
    parser.add_argument("--out", default="data", help="Output directory")
    parser.add_argument("--limit", type=int, default=None, help="Limit districts for testing")
    parser.add_argument("--sleep", type=float, default=0.25, help="Delay between requests")
    parser.add_argument("--keep-going", action="store_true", help="Continue if a district fails")
    args = parser.parse_args()

    out_dir = Path(args.out)
    session = make_session()
    districts = discover_districts(session, year=args.year, limit=args.limit)
    if not districts:
        print("No districts discovered", file=sys.stderr)
        return 1

    all_rows: List[dict] = []
    errors: List[dict] = []

    for i, meta in enumerate(districts, start=1):
        try:
            print(f"[{i}/{len(districts)}] {meta.district}")
            meta, party_map = parse_result_page(session, meta)
            if not meta.distribution_url and HISTORICAL_RESULTS_BASE in meta.district_url:
                result_html = fetch(session, meta.district_url, sleep=args.sleep)
                rows = parse_historical_result_rows(meta, result_html, party_map)
            elif re.search(r"\.xlsx?$", meta.distribution_url, flags=re.I):
                dist_content = fetch_bytes(session, meta.distribution_url, sleep=args.sleep)
                rows = parse_excel_distribution_rows(meta, dist_content, party_map)
            else:
                dist_html = fetch(session, meta.distribution_url, sleep=args.sleep)
                rows = parse_distribution_rows(meta, dist_html, party_map)
            if not rows:
                raise ValueError("No distribution rows parsed")
            all_rows.extend(rows)
        except Exception as e:
            err = {"district": meta.district, "district_url": meta.district_url, "distribution_url": meta.distribution_url, "error": repr(e)}
            errors.append(err)
            print(f"  ERROR: {err['error']}", file=sys.stderr)
            if not args.keep_going:
                raise

    summary_rows = make_summary(all_rows)
    write_csv(out_dir / f"vic_{args.year}_preferences_long.csv", all_rows, EXPECTED_LONG_COLUMNS)
    write_csv(out_dir / f"vic_{args.year}_district_summary.csv", summary_rows, EXPECTED_SUMMARY_COLUMNS)
    error_path = out_dir / f"vic_{args.year}_scrape_errors.csv"
    if errors:
        write_csv(error_path, errors, ["district", "district_url", "distribution_url", "error"])
    else:
        error_path.unlink(missing_ok=True)
        (out_dir / "scrape_errors.csv").unlink(missing_ok=True)

    print(f"\nWrote {len(all_rows):,} long rows")
    print(f"Wrote {len(summary_rows):,} district summaries")
    if errors:
        print(f"Had {len(errors):,} errors; see {error_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
