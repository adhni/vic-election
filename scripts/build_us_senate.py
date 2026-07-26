#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import pyreadr
import requests


YEARS = (2024, 2022, 2020, 2018, 2016)
MIT_SOURCE_PAGE = "https://electionlab.mit.edu/data"
FEC_SOURCE_PAGE = (
    "https://www.fec.gov/introduction-campaign-finance/"
    "election-results-and-voting-information/"
)
OPEN_ELECTIONS_SOURCE_PAGE = "https://openelections.net/"

SOURCES = {
    "senate_2016": (
        "https://raw.githubusercontent.com/MEDSL/elections/"
        "53297d9f7f6d6602b8fdc80f03f14f9153ac4458/data/senate_precincts_2016.rda",
        "532c48fd3df86c30327bcee7caa2080fa4fd138c5d0e059d87a1e1cb36300ec9",
        "senate_2016.rda",
    ),
    "senate_2018": (
        "https://raw.githubusercontent.com/MEDSL/2018-elections-official/"
        "42055b11dcd5477bc125cdec5a18fbcc60fb6bed/SENATE/SENATE_precinct_general.zip",
        "b07d7852578d3c94bc06931f6d31fd64324fd4877ae1f641fd1af634de639b75",
        "senate_2018.zip",
    ),
    "senate_2024_county": (
        "https://raw.githubusercontent.com/MEDSL/2024-elections-official/"
        "df531089c78e6d0098db1a6bfb3849a066a06995/2024-senate-county.csv",
        "6bb49fe67db5a7dcf30862fab81effc0fcfa456cb41326dd5fa9cd9fb8c60b81",
        "senate_2024_county.csv",
    ),
    "senate_2024_state": (
        "https://raw.githubusercontent.com/MEDSL/2024-elections-official/"
        "df531089c78e6d0098db1a6bfb3849a066a06995/2024-senate-state.csv",
        "e50fbfc62a095b9fe0d5178b7c09176b5cb8b7d320e08dd31e54987b9e3fcd76",
        "senate_2024_state.csv",
    ),
    "fec_2016": (
        "https://www.fec.gov/documents/1890/federalelections2016.xlsx",
        "b4a1d1383602bc388cfbdf1fbea2476476d32e0b44b44236d3a3910fa9782eb6",
        "federalelections2016.xlsx",
    ),
    "fec_2018": (
        "https://www.fec.gov/documents/2706/federalelections2018.xlsx",
        "f2c42311862b4927df2ca5908c5f9c8f8da6221a8db88fd00434a22ec1e0e303",
        "federalelections2018.xlsx",
    ),
    "fec_2020": (
        "https://www.fec.gov/documents/4228/federalelections2020.xlsx",
        "5073b6d2c76c86c941508dfb1a11cc497e8529b0068c5132aceb0f385c19352e",
        "federalelections2020.xlsx",
    ),
    "fec_2022": (
        "https://www.fec.gov/documents/5676/federalelections2022.xlsx",
        "cdb258ea23803e50d752bcea19faa39b3c201eb960094bcb556c3a38c2350897",
        "federalelections2022.xlsx",
    ),
    "indiana_2018": (
        "https://raw.githubusercontent.com/openelections/openelections-data-in/"
        "5151d136ccab66646458a519f25dcf00f05c5e56/2018/20181106__in__general__county.csv",
        "3c389b670a780727225bea4dfb5203dc29023b297128f0663e9a22bf3c5a1df7",
        "indiana_2018_county.csv",
    ),
    "connecticut_2022": (
        "https://raw.githubusercontent.com/openelections/openelections-data-ct/"
        "f948d0a1ce36871de4a1d696612ab2a268fd0758/2022/20221108__ct__general__precinct.csv",
        "fb46ac8e6664585b2e4eeaa0a66574b2cf2448fa46f7a17594942127fb9f5155",
        "connecticut_2022_precinct.csv",
    ),
    "louisiana_2016_runoff": (
        "https://raw.githubusercontent.com/openelections/openelections-data-la/"
        "dd8cf041685b466f0d32fab0ba1c3421f4fec2a5/"
        "2016/20161210__la__general__runoff__county.csv",
        "2130f015bbff40d528e1d55b791422f2ec3c053056a46103968bbb752e255fae",
        "louisiana_2016_runoff.csv",
    ),
    "georgia_2020_runoff": (
        "https://raw.githubusercontent.com/openelections/openelections-data-ga/"
        "aac678a4447af014942b2546775c2185a0bb30e4/2021/20210105__ga__runoff.csv",
        "973d2b34946f397ca036790436ae9eb346bc35ff47c552cb71de6a5a4b04aec7",
        "georgia_2020_regular_runoff.csv",
    ),
    "georgia_2022_runoff": (
        "https://raw.githubusercontent.com/openelections/openelections-data-ga/"
        "aac678a4447af014942b2546775c2185a0bb30e4/"
        "2022/20221206__ga__general_runoff__precinct.csv",
        "956f46dbae2bc5bc2728be691e04e99121cec72fccdd4bf2f39eb016c949c129",
        "georgia_2022_runoff.csv",
    ),
}

DATAVERSE_SOURCES = {
    "senate_2020": (
        6100391,
        "fd965d2b168d21070c996dc214912b1335a1bb52106aeb8c82621f247631c482",
        "senate_2020.csv",
    ),
    "senate_2022": (
        7412054,
        "41ee6e40fc5ac3e79d9df795d8fafdfd3c2dc3dfccc80ab4e9fdc29f39311cf6",
        "senate_2022.tab",
    ),
}

STATE_INFO = {
    "01": ("AL", "Alabama"), "02": ("AK", "Alaska"), "04": ("AZ", "Arizona"),
    "05": ("AR", "Arkansas"), "06": ("CA", "California"), "08": ("CO", "Colorado"),
    "09": ("CT", "Connecticut"), "10": ("DE", "Delaware"), "12": ("FL", "Florida"),
    "13": ("GA", "Georgia"), "15": ("HI", "Hawaii"), "16": ("ID", "Idaho"),
    "17": ("IL", "Illinois"), "18": ("IN", "Indiana"), "19": ("IA", "Iowa"),
    "20": ("KS", "Kansas"), "21": ("KY", "Kentucky"), "22": ("LA", "Louisiana"),
    "23": ("ME", "Maine"), "24": ("MD", "Maryland"), "25": ("MA", "Massachusetts"),
    "26": ("MI", "Michigan"), "27": ("MN", "Minnesota"), "28": ("MS", "Mississippi"),
    "29": ("MO", "Missouri"), "30": ("MT", "Montana"), "31": ("NE", "Nebraska"),
    "32": ("NV", "Nevada"), "33": ("NH", "New Hampshire"), "34": ("NJ", "New Jersey"),
    "35": ("NM", "New Mexico"), "36": ("NY", "New York"),
    "37": ("NC", "North Carolina"), "38": ("ND", "North Dakota"), "39": ("OH", "Ohio"),
    "40": ("OK", "Oklahoma"), "41": ("OR", "Oregon"), "42": ("PA", "Pennsylvania"),
    "44": ("RI", "Rhode Island"), "45": ("SC", "South Carolina"),
    "46": ("SD", "South Dakota"), "47": ("TN", "Tennessee"), "48": ("TX", "Texas"),
    "49": ("UT", "Utah"), "50": ("VT", "Vermont"), "51": ("VA", "Virginia"),
    "53": ("WA", "Washington"), "54": ("WV", "West Virginia"),
    "55": ("WI", "Wisconsin"), "56": ("WY", "Wyoming"),
}
STATE_BY_ABBR = {abbr: (fips, name) for fips, (abbr, name) in STATE_INFO.items()}

EXPECTED_STATES = {2016: 34, 2018: 33, 2020: 33, 2022: 34, 2024: 33}
EXPECTED_RECONCILIATION_SHA256 = {
    # Filled after the first checksum-pinned build; any later source or parser drift must fail.
    2024: "24f77a3a3c5b1328a3c42c1ac27d763b5a0e40284ed4c2ec3c3e667e790206a4",
    2022: "6cffeb59eb60a6bb13e81bb337674969786bcdc0e93a43e80a9316b6defeddca",
    2020: "d0acc36e2a60fa5d0b2718c451eb55b795569d0af3c8378764045bd3bc593210",
    2018: "cea60dfed8b1ee83e759ceb4b8b8782ff8c9edb7387f32b5cf38dc33f390ef26",
    2016: "98178e2f7e825d2547a37f29cf9e0172ac28536e8ce14720a8f71b0b9cd0d972",
}

FEC_SHEETS = {
    2016: "2016 US Senate Results by State",
    2018: "2018 US Senate Results by State",
    2020: "12. US Senate Results by State",
    2022: "7. US Senate Results by State",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)

NON_CANDIDATES = {
    "", "BLANK", "BLANKS", "NO VOTE", "OVERVOTE", "OVERVOTES", "OVER VOTES",
    "UNDERVOTE", "UNDERVOTES", "UNDER VOTES", "FEDERAL BALLOTS", "PUBLIC COUNTER",
    "TOTAL", "TOTAL VOTES", "VOTES CAST",
}
CODE_MERGES = {
    "29380": "29095",
    "2938000": "29095",
    "36122": "36123",
    "51515": "51019",
    "46102": "46113",
}
SUFFIXES = {"JR", "SR", "II", "III", "IV"}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and path.stat().st_size and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=300, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)


def download_dataverse(
    session: requests.Session,
    file_id: int,
    path: Path,
    refresh: bool,
) -> None:
    if path.exists() and path.stat().st_size and not refresh:
        return
    response = session.post(
        f"https://dataverse.harvard.edu/api/access/datafile/{file_id}",
        json={
            "guestbookResponse": {
                "name": "Vic Election Preference Explorer",
                "email": "election-explorer@example.com",
                "institution": "Open-source election explorer",
                "position": "Data builder",
                "answers": [],
            }
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        signed_url = payload["data"]["signedUrl"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"Dataverse {file_id}: could not obtain download URL: {payload}") from exc
    download(session, signed_url, path, True)


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def number(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip().replace(",", "").replace("[", "").replace("]", "")
    if not text or text.lower() == "nan":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def normalized(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def name_tokens(value: object) -> tuple[str, ...]:
    tokens = re.findall(r"[A-Z0-9]+", str(value).upper())
    return tuple(sorted(token for token in tokens if token not in SUFFIXES))


def title_name(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return ""
    if text.upper() in {"[WRITE-IN]", "WRITEIN", "WRITE-IN", "SCATTERING"}:
        return "Write-ins"
    return text.title().replace("Mc", "Mc").replace(" Ii", " II").replace(" Iii", " III")


def canonical_party(detailed: object, simplified: object = "") -> str:
    detail = str(detailed).strip().upper()
    simple = str(simplified).strip().upper()
    value = simple or detail
    if (
        "DEMOCRAT" in value
        or value in {"D", "D*", "DFL"}
        or value.startswith(("D/", "DEM/"))
    ):
        return "Democratic"
    if "REPUBLICAN" in value or value in {"R", "R*"} or value.startswith("R/"):
        return "Republican"
    if "LIBERTARIAN" in value or value == "LIB":
        return "Libertarian"
    if "GREEN" in value or value in {"GRE", "GRN"}:
        return "Green"
    if "INDEPENDENT" in detail or detail in {"IND", "I", "NONPARTISAN", "NOPTY"}:
        return "Independent"
    return "Other"


def regular_district(year: int, state: str, value: object) -> bool:
    district = str(value).strip().upper()
    if year == 2016:
        return district == "S"
    if year == 2018 and state in {"MN", "MS"}:
        return district == "S-FULL TERM"
    if year == 2020 and state == "AZ":
        return False
    if year == 2020 and state == "GA":
        return district == "S-FULL TERM"
    if year == 2022 and state in {"CA", "OK"}:
        return district == "S-FULL TERM"
    return district == "S"


def fec_name(row: pd.Series) -> str:
    first_value = row.get("CANDIDATE NAME (First)", "")
    last_value = row.get("CANDIDATE NAME (Last)", "")
    first = "" if pd.isna(first_value) else str(first_value).strip()
    last = "" if pd.isna(last_value) else str(last_value).strip()
    return title_name(f"{first} {last}".strip())


def parse_fec_candidates(year: int, path: Path) -> dict[str, dict[str, dict[str, object]]]:
    frame = pd.read_excel(path, sheet_name=FEC_SHEETS[year])
    district_column = "D" if year == 2016 else "DISTRICT"
    fec_column = "FEC ID#" if year in {2016, 2018} else "FEC ID"
    combined_column = next(
        column for column in frame.columns if str(column).startswith("COMBINED GE PARTY TOTALS")
    )
    runoff_column = next(
        (column for column in frame.columns if str(column).startswith("GE RUNOFF ELECTION VOTES")),
        None,
    )
    official: dict[str, dict[str, dict[str, object]]] = {}
    for state in sorted(STATE_BY_ABBR):
        rows = frame[
            (frame["STATE ABBREVIATION"].astype(str).str.strip() == state)
            & frame[district_column].map(lambda value: regular_district(year, state, value))
        ].copy()
        if rows.empty:
            continue
        candidates: dict[str, dict[str, object]] = {}
        for _, row in rows.iterrows():
            name = fec_name(row)
            if not name or str(row.get("CANDIDATE NAME", "")).strip() in {"Party Votes:", "Total State Votes:"}:
                continue
            combined = 0
            if year == 2022 and state == "AK":
                votes = number(row.get("3RD ROUND RCV VOTES"))
            elif (year, state) in {(2016, "LA"), (2020, "GA"), (2022, "GA")}:
                votes = number(row.get(runoff_column))
            else:
                combined = number(row.get(combined_column))
                votes = combined or number(row.get("GENERAL VOTES "))
            if not votes:
                continue
            fec_id = str(row.get(fec_column, "")).strip()
            key = fec_id if fec_id and fec_id.lower() != "nan" else normalized(name)
            item = candidates.setdefault(
                key,
                {
                    "id": key,
                    "name": name,
                    "last": normalized(row.get("CANDIDATE NAME (Last)", "")),
                    "tokens": name_tokens(name),
                    "party": canonical_party(row.get("PARTY", "")),
                    "votes": 0,
                    "winner": False,
                },
            )
            party = canonical_party(row.get("PARTY", ""))
            if party in {"Democratic", "Republican"}:
                item["party"] = party
            if combined:
                item["votes"] = max(int(item["votes"]), votes)
            else:
                item["votes"] = int(item["votes"]) + votes
            item["winner"] = bool(item["winner"]) or str(row.get("GE WINNER INDICATOR", "")).strip() == "W"
        if candidates:
            official[state] = candidates
    expected = EXPECTED_STATES[year]
    if len(official) != expected:
        raise SystemExit(f"FEC {year}: expected {expected} regular Senate states, found {len(official)}")
    return official


def parse_2024_official(path: Path) -> dict[str, dict[str, dict[str, object]]]:
    frame = pd.read_csv(path, dtype={"state_fips": str})
    frame = frame[
        (frame["office"] == "US SENATE")
        & (frame["stage"] == "GEN")
        & (~frame["special"].astype(bool))
        & (frame["mode"] == "TOTAL")
        & frame["candidate"].map(candidate_is_valid)
    ]
    official: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for _, row in frame.iterrows():
        name = title_name(row["candidate"])
        key = normalized(name)
        party = canonical_party(row.get("party_detailed", ""), row.get("party_simplified", ""))
        item = official[str(row["state_po"])].setdefault(
            key,
            {
                "id": key,
                "name": name,
                "last": normalized(name.split()[-1]),
                "tokens": name_tokens(name),
                "party": party,
                "votes": 0,
                "winner": False,
            },
        )
        item["votes"] = int(item["votes"]) + number(row["votes"])
        if party in {"Democratic", "Republican"}:
            item["party"] = party
    for candidates in official.values():
        winner = max(candidates.values(), key=lambda item: int(item["votes"]))
        winner["winner"] = True
    if len(official) != EXPECTED_STATES[2024]:
        raise SystemExit(f"MIT 2024 state file: expected 33 regular states, found {len(official)}")
    return dict(official)


def county_code(value: object, state: str) -> str:
    if value is None or pd.isna(value) or not str(value).strip():
        return "02" if state == "AK" else ""
    code = str(number(value))
    if len(code) > 5 and not code[5:].strip("0"):
        code = code[:5]
    code = CODE_MERGES.get(code, code.zfill(5))
    if len(code) == 5 and code.endswith("000"):
        return ""
    return code


def candidate_is_valid(value: object) -> bool:
    name = re.sub(r"\s+", " ", str(value).strip().upper())
    return name not in NON_CANDIDATES


def regular_source_rows(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (frame["office"].astype(str).str.upper() == "US SENATE")
        & (frame["stage"].astype(str).str.upper() == "GEN")
        & (~frame["special"].astype(str).str.upper().isin({"TRUE", "1"}))
    ].copy()


def aggregate_mit_frame(
    frame: pd.DataFrame,
    year: int,
    key_column: str | None = None,
) -> dict[str, dict[str, object]]:
    rows = regular_source_rows(frame)
    state_column = "state_po" if "state_po" in rows else "state_postal"
    party_detail = "party_detailed" if "party_detailed" in rows else "party"
    party_simple = "party_simplified" if "party_simplified" in rows else None
    vote_column = "candidatevotes" if "candidatevotes" in rows else "votes"
    rows = rows[rows["candidate"].map(candidate_is_valid)].copy()
    rows["_state"] = rows[state_column].astype(str).str.strip().str.upper()
    rows = rows[rows["_state"].isin(STATE_BY_ABBR)]
    rows["_code"] = [
        county_code(value, state)
        for value, state in zip(rows["county_fips"], rows["_state"])
    ]
    rows = rows[rows["_code"] != ""]
    rows["_candidate_key"] = (
        rows[key_column].map(normalized)
        if key_column
        else rows["candidate"].map(normalized)
    )
    rows["_candidate_key"] = rows["_candidate_key"].where(
        ~rows["candidate"].astype(str).str.upper().isin({"[WRITE-IN]", "WRITEIN", "WRITE-IN", "SCATTERING"}),
        "WRITEINS",
    )
    rows["_candidate_name"] = rows["candidate"].map(title_name)
    rows["_party"] = [
        canonical_party(detail, simple if party_simple else "")
        for detail, simple in zip(
            rows[party_detail],
            rows[party_simple] if party_simple else [""] * len(rows),
        )
    ]
    rows["_votes"] = rows[vote_column].map(number)
    rows["_is_total"] = rows["mode"].astype(str).str.upper() == "TOTAL"
    if "precinct" in rows:
        rows["_reporting"] = rows["precinct"].fillna("").astype(str)
    else:
        rows["_reporting"] = "__county__"

    grouping = ["_state", "_code", "_reporting", "_candidate_key"]
    rows["_total_votes"] = rows["_votes"].where(rows["_is_total"], 0)
    rows["_component_votes"] = rows["_votes"].where(~rows["_is_total"], 0)
    reporting = rows.groupby(grouping, dropna=False).agg(
        total_votes=("_total_votes", "sum"),
        component_votes=("_component_votes", "sum"),
        has_total=("_is_total", "max"),
    ).reset_index()
    if year <= 2020:
        # In these MEDSL releases, TOTAL is one reporting mode used alongside
        # mode-specific rows in other precincts; the rows are additive.
        reporting["votes"] = reporting["total_votes"] + reporting["component_votes"]
    else:
        reporting["votes"] = reporting["total_votes"].where(
            reporting["has_total"], reporting["component_votes"]
        )
    county = reporting.groupby(
        ["_state", "_code", "_candidate_key"], dropna=False
    )["votes"].sum()

    variants = rows.groupby(
        ["_state", "_candidate_key", "_candidate_name", "_party"], dropna=False
    )["_votes"].sum()
    preferred: dict[tuple[str, str], tuple[str, str]] = {}
    for (state, key, name, party), votes in variants.items():
        current = preferred.get((state, key))
        candidate = (str(name), str(party), int(votes))
        if current is None or candidate[2] > current[2]:
            preferred[(state, key)] = candidate

    areas: dict[str, dict[str, object]] = {}
    for (state, code, key), votes in county.items():
        if not votes:
            continue
        name, party, _ = preferred[(state, key)]
        area = areas.setdefault(code, {"code": code, "state_abbr": state, "candidates": {}})
        item = area["candidates"].setdefault(
            key, {"id": key, "name": name, "party": party, "votes": 0}
        )
        item["votes"] = int(item["votes"]) + int(votes)
    return areas


def read_2018(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        member = archive.namelist()[0]
        with archive.open(member) as handle:
            return pd.read_csv(handle, low_memory=False)


def read_2016(path: Path, cache_path: Path) -> pd.DataFrame:
    if cache_path.exists():
        return pd.read_csv(cache_path, low_memory=False)
    frame = next(iter(pyreadr.read_r(str(path)).values()))
    needed = [
        "stage", "special", "state_postal", "county_fips", "precinct", "candidate",
        "candidate_normalized", "office", "party", "mode", "votes",
    ]
    return frame[needed].copy()


def merge_areas(
    target: dict[str, dict[str, object]],
    source: dict[str, dict[str, object]],
) -> None:
    for code, area in source.items():
        output = target.setdefault(
            code,
            {"code": code, "state_abbr": area["state_abbr"], "candidates": {}},
        )
        for key, candidate in area["candidates"].items():
            if key not in output["candidates"]:
                output["candidates"][key] = dict(candidate)
            else:
                item = output["candidates"][key]
                item["votes"] = int(item["votes"]) + int(candidate["votes"])


def aggregate_2020(path: Path) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    for chunk in pd.read_csv(path, chunksize=200_000, low_memory=False):
        selected = regular_source_rows(chunk)
        if selected.empty:
            continue
        merge_areas(areas, aggregate_mit_frame(selected, 2020))
    return areas


def boundary_sources(output_dir: Path, year: int) -> list[dict[str, object]]:
    if year <= 2018:
        names = ["us_president_2008_2016_county_boundaries.geojson"]
    elif year == 2020:
        names = ["us_president_2020_county_boundaries.geojson"]
    else:
        names = ["us_president_2024_county_boundaries.geojson"]
        names.append("us_president_2008_2016_county_boundaries.geojson")
    return [json.loads((output_dir / name).read_text(encoding="utf-8")) for name in names]


def boundary_lookup(output_dir: Path, year: int) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for source in boundary_sources(output_dir, year):
        for feature in source["features"]:
            code = str(feature["properties"]["constituency_code"]).removeprefix("US-COUNTY-")
            canonical_code = CODE_MERGES.get(code, code)
            if year >= 2022 and code.startswith("09") and len(code) == 5 and int(code[2:]) < 100:
                lookup[canonical_code] = feature
            else:
                lookup.setdefault(canonical_code, feature)
    states = json.loads(
        (output_dir / "us_president_state_boundaries.geojson").read_text(encoding="utf-8")
    )
    for feature in states["features"]:
        state = str(feature["properties"]["constituency_code"]).removeprefix("US-STATE-")
        if state in STATE_BY_ABBR:
            fips, name = STATE_BY_ABBR[state]
            fallback = json.loads(json.dumps(feature))
            fallback["properties"]["district"] = f"{name} statewide"
            lookup.setdefault(fips, fallback)
    return lookup


def name_code_lookup(boundaries: dict[str, dict[str, object]], state: str) -> dict[str, str]:
    state_name = STATE_BY_ABBR[state][1]
    result = {}
    for code, feature in boundaries.items():
        district = str(feature["properties"]["district"])
        if not district.endswith(f", {state_name}"):
            continue
        local = district.rsplit(",", 1)[0]
        local = re.sub(
            r"\s+(COUNTY|PARISH|CITY|BOROUGH|CENSUS AREA|MUNICIPALITY)$",
            "",
            local,
            flags=re.IGNORECASE,
        )
        result[normalized(local)] = code
    return result


def rows_to_areas(
    rows: list[dict[str, object]],
    state: str,
    name_to_code: dict[str, str],
) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    for row in rows:
        local = normalized(row["county"])
        if local not in name_to_code:
            raise SystemExit(f"{state}: boundary code missing for {row['county']}")
        code = name_to_code[local]
        key = normalized(row["candidate"])
        area = areas.setdefault(code, {"code": code, "state_abbr": state, "candidates": {}})
        item = area["candidates"].setdefault(
            key,
            {
                "id": key,
                "name": title_name(row["candidate"]),
                "party": canonical_party(row.get("party", "")),
                "votes": 0,
            },
        )
        item["votes"] = int(item["votes"]) + number(row["votes"])
    return areas


def parse_louisiana_runoff(
    path: Path,
    boundaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    frame = pd.read_csv(path)
    frame = frame[(frame["office"] == "U.S. Senate") & (frame["county"] != "Total Votes")]
    rows = [
        {
            "county": row["county"],
            "candidate": row["candidate"],
            "party": row["party"],
            "votes": row["votes"],
        }
        for _, row in frame.iterrows()
    ]
    return rows_to_areas(rows, "LA", name_code_lookup(boundaries, "LA"))


def parse_georgia_runoff(
    path: Path,
    year: int,
    boundaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    frame = pd.read_csv(path)
    frame = frame[frame["office"] == "U.S. Senate"]
    vote_columns = [
        "election_day_votes", "advanced_votes", "absentee_by_mail_votes", "provisional_votes"
    ]
    frame["votes"] = frame[vote_columns].fillna(0).sum(axis=1).astype(int)
    grouped = frame.groupby(["county", "candidate", "party"], as_index=False)["votes"].sum()
    rows = grouped.to_dict("records")
    return rows_to_areas(rows, "GA", name_code_lookup(boundaries, "GA"))


def parse_indiana(
    path: Path,
    boundaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    frame = pd.read_csv(path)
    frame = frame[frame["office"] == "U.S. Senate"]
    rows = frame.rename(columns={"county": "county"}).to_dict("records")
    return rows_to_areas(rows, "IN", name_code_lookup(boundaries, "IN"))


def parse_connecticut(
    path: Path,
    town_to_code: dict[str, str],
    boundaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    frame = pd.read_csv(path)
    frame = frame[frame["office"] == "U.S. Senate"].copy()
    missing = sorted(set(frame["town"].map(normalized)) - set(town_to_code))
    if missing:
        raise SystemExit(f"Connecticut 2022: towns missing historical county mapping: {missing}")
    areas: dict[str, dict[str, object]] = {}
    for _, row in frame.iterrows():
        code = town_to_code[normalized(row["town"])]
        if code not in boundaries:
            raise SystemExit(f"Connecticut 2022: boundary missing historical county {code}")
        key = normalized(row["candidate"])
        area = areas.setdefault(code, {"code": code, "state_abbr": "CT", "candidates": {}})
        item = area["candidates"].setdefault(
            key,
            {
                "id": key,
                "name": title_name(row["candidate"]),
                "party": canonical_party(row["party"]),
                "votes": 0,
            },
        )
        item["votes"] = int(item["votes"]) + number(row["votes"])
    return areas


def connecticut_town_codes(frame_2018: pd.DataFrame) -> dict[str, str]:
    mapping_rows = frame_2018[frame_2018["state_po"] == "CT"][
        ["jurisdiction_name", "county_fips"]
    ].dropna().drop_duplicates()
    return {
        normalized(row["jurisdiction_name"]): county_code(row["county_fips"], "CT")
        for _, row in mapping_rows.iterrows()
    }


def official_match(
    raw: dict[str, object],
    official: dict[str, dict[str, object]],
) -> str | None:
    raw_tokens = set(name_tokens(raw["name"]))
    raw_key = normalized(raw["id"])
    raw_last = normalized(str(raw["name"]).split()[-1])
    matches = []
    for key, candidate in official.items():
        candidate_tokens = set(candidate["tokens"])
        score = 0
        if raw_key == "WRITEINS" and normalized(candidate["name"]) == "SCATTERED":
            score = 110
        elif raw_tokens == candidate_tokens:
            score = 100
        elif raw_tokens and (raw_tokens.issubset(candidate_tokens) or candidate_tokens.issubset(raw_tokens)):
            score = 80
        elif raw_key and raw_key == candidate["last"]:
            score = 70
        elif candidate["last"] and candidate["last"] in raw_key:
            score = 50
        elif (
            raw_last
            and candidate["last"]
            and raw_tokens.intersection(candidate_tokens)
            and SequenceMatcher(None, raw_last, str(candidate["last"])).ratio() >= 0.8
        ):
            score = 60
        if score:
            matches.append((score, key))
    matches.sort(reverse=True)
    if not matches or (len(matches) > 1 and matches[0][0] == matches[1][0]):
        return None
    return matches[0][1]


def canonicalize_candidates(
    year: int,
    areas: dict[str, dict[str, object]],
    official: dict[str, dict[str, dict[str, object]]],
) -> None:
    for area in areas.values():
        state = str(area["state_abbr"])
        replacements: dict[str, dict[str, object]] = {}
        for raw in area["candidates"].values():
            match = official_match(raw, official[state])
            if match:
                source = official[state][match]
                key = str(source["id"])
                name = str(source["name"])
                party = str(source["party"])
            else:
                key = str(raw["id"])
                name = str(raw["name"])
                party = str(raw["party"])
            if year == 2022 and state == "AK":
                party = "Republican" if normalized(name) in {"LISAMURKOWSKI", "KELLYCTSHIBAKA", "BUZZAKELLEY"} else "Democratic"
            item = replacements.setdefault(
                key, {"id": key, "name": name, "party": party, "votes": 0}
            )
            item["votes"] = int(item["votes"]) + int(raw["votes"])
        area["candidates"] = replacements


def replace_state(
    areas: dict[str, dict[str, object]],
    state: str,
    replacement: dict[str, dict[str, object]],
) -> None:
    for code in [code for code, area in areas.items() if area["state_abbr"] == state]:
        del areas[code]
    overlap = set(areas).intersection(replacement)
    if overlap:
        raise SystemExit(f"{state}: replacement codes collide with other states: {sorted(overlap)}")
    areas.update(replacement)


def override_statewide_final(
    areas: dict[str, dict[str, object]],
    state: str,
    official: dict[str, dict[str, dict[str, object]]],
) -> None:
    candidates = {
        key: {
            "id": key,
            "name": item["name"],
            "party": item["party"],
            "votes": item["votes"],
        }
        for key, item in official[state].items()
        if item["votes"]
    }
    fips = STATE_BY_ABBR[state][0]
    replace_state(
        areas,
        state,
        {fips: {"code": fips, "state_abbr": state, "candidates": candidates}},
    )


def state_areas(county_areas: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {}
    for area in county_areas.values():
        state = str(area["state_abbr"])
        target = states.setdefault(state, {"code": state, "state_abbr": state, "candidates": {}})
        for key, candidate in area["candidates"].items():
            item = target["candidates"].setdefault(
                key,
                {
                    "id": key,
                    "name": candidate["name"],
                    "party": candidate["party"],
                    "votes": 0,
                },
            )
            item["votes"] = int(item["votes"]) + int(candidate["votes"])
    return states


def official_state_areas(
    official: dict[str, dict[str, dict[str, object]]],
) -> dict[str, dict[str, object]]:
    return {
        state: {
            "code": state,
            "state_abbr": state,
            "candidates": {
                key: {
                    "id": key,
                    "name": candidate["name"],
                    "party": candidate["party"],
                    "votes": candidate["votes"],
                }
                for key, candidate in candidates.items()
            },
        }
        for state, candidates in official.items()
    }


def validate_reconciliation(
    year: int,
    states: dict[str, dict[str, object]],
    official: dict[str, dict[str, dict[str, object]]],
) -> None:
    report = {}
    for state in sorted(official):
        generated = states[state]["candidates"]
        deltas = {
            key: int(candidate["votes"]) - int(generated.get(key, {}).get("votes", 0))
            for key, candidate in sorted(official[state].items())
        }
        unmatched = sum(
            int(candidate["votes"])
            for key, candidate in generated.items()
            if key not in official[state]
        )
        if unmatched:
            deltas["_unmatched_generated"] = -unmatched
        report[state] = deltas
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    expected = EXPECTED_RECONCILIATION_SHA256.get(year)
    if not expected:
        changed = {
            state: {key: delta for key, delta in values.items() if delta}
            for state, values in report.items()
            if any(values.values())
        }
        raise SystemExit(f"{year}: lock reconciliation digest {digest}; differences: {changed}")
    if digest != expected:
        changed = {
            state: {key: delta for key, delta in values.items() if delta}
            for state, values in report.items()
            if any(values.values())
        }
        raise SystemExit(
            f"{year}: official reconciliation changed to {digest}; expected {expected}: {changed}"
        )


def prepare_boundaries(
    output_dir: Path,
    year: int,
    areas: dict[str, dict[str, object]],
) -> dict[str, object]:
    lookup = boundary_lookup(output_dir, year)
    features = []
    for code, area in sorted(areas.items()):
        if code not in lookup:
            raise SystemExit(f"{year}: county boundary missing result code {code}")
        feature = json.loads(json.dumps(lookup[code]))
        state = STATE_BY_ABBR[str(area["state_abbr"])][1]
        district = str(feature["properties"]["district"])
        feature["properties"] = {
            "district": district,
            "constituency_code": f"US-SENATE-COUNTY-{code}",
            "electorate_type": state,
        }
        area["district"] = district
        features.append(feature)
    return {
        "type": "FeatureCollection",
        "name": f"us_senate_{year}_counties",
        "features": features,
    }


def prepare_state_boundaries(
    output_dir: Path,
    year: int,
    areas: dict[str, dict[str, object]],
) -> dict[str, object]:
    source = json.loads(
        (output_dir / "us_president_state_boundaries.geojson").read_text(encoding="utf-8")
    )
    wanted = set(areas)
    features = []
    for raw in source["features"]:
        state = str(raw["properties"]["constituency_code"]).removeprefix("US-STATE-")
        if state not in wanted:
            continue
        feature = json.loads(json.dumps(raw))
        feature["properties"] = {
            "district": STATE_BY_ABBR[state][1],
            "constituency_code": f"US-SENATE-STATE-{state}",
            "electorate_type": "United States",
        }
        areas[state]["district"] = STATE_BY_ABBR[state][1]
        features.append(feature)
    if len(features) != len(wanted):
        raise SystemExit(f"{year}: state boundary/result join is incomplete")
    return {
        "type": "FeatureCollection",
        "name": f"us_senate_{year}_states",
        "features": features,
    }


def build_rows(
    year: int,
    areas: dict[str, dict[str, object]],
    geography: str,
) -> list[dict[str, object]]:
    rows = []
    for area in sorted(
        areas.values(),
        key=lambda item: (STATE_BY_ABBR[str(item["state_abbr"])][1], str(item["district"])),
    ):
        candidates = sorted(
            (candidate for candidate in area["candidates"].values() if int(candidate["votes"]) > 0),
            key=lambda item: (-int(item["votes"]), str(item["name"])),
        )
        if len(candidates) < 2:
            raise SystemExit(f"{year} {area['district']}: fewer than two Senate candidates")
        total = sum(int(candidate["votes"]) for candidate in candidates)
        majority = int(candidates[0]["votes"]) - int(candidates[1]["votes"])
        state = str(area["state_abbr"])
        audit_source = (
            "the MIT Election Lab state compilation"
            if year == 2024
            else "the official FEC state compilation"
        )
        note = (
            "Candidate totals are aggregated from checksum-pinned MIT Election Lab returns and "
            f"audited against {audit_source}. Concurrent special elections are excluded."
        )
        if (year, state) in {(2016, "LA"), (2020, "GA"), (2022, "GA")}:
            note += " This state uses the decisive regular-seat runoff."
        if year == 2018 and state == "IN":
            note += " Indiana is filled from state-sourced OpenElections county returns."
        if year == 2022 and state == "CT":
            note += " Connecticut towns are aggregated to the eight election-time counties."
        if year == 2022 and state == "AK":
            note += " Alaska is a statewide fallback showing the final ranked-choice round."
        if year == 2022 and state == "VT":
            note += " Vermont is a statewide fallback because the source has no county codes."
        source_url = MIT_SOURCE_PAGE
        if state in {"LA", "GA"} and (year, state) in {
            (2016, "LA"), (2020, "GA"), (2022, "GA")
        }:
            source_url = OPEN_ELECTIONS_SOURCE_PAGE
        base = {
            "district": area["district"],
            "district_url": source_url,
            "distribution_url": FEC_SOURCE_PAGE if year <= 2022 else MIT_SOURCE_PAGE,
            "elected_member": candidates[0]["name"],
            "elected_party": candidates[0]["party"],
            "enrolment": 0,
            "formal_votes": total,
            "informal_votes": 0,
            "total_votes": total,
            "turnout_pct": 0,
            "majority": majority,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": (
                STATE_BY_ABBR[state][1] if geography == "county" else "United States"
            ),
            "constituency_code": (
                f"US-SENATE-COUNTY-{area['code']}"
                if geography == "county"
                else f"US-SENATE-STATE-{area['code']}"
            ),
            "contest_status": "official" if geography == "state" else "compiled",
            "result_note": note,
        }
        for candidate in candidates:
            rows.append({
                **base,
                "candidate": candidate["name"],
                "candidate_party": candidate["party"],
                "votes": candidate["votes"],
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_geojson(path: Path, data: dict[str, object]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build regular U.S. Senate county and state maps, 2016-2024"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/us_senate"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"
    paths = {}
    for key, (url, checksum, filename) in SOURCES.items():
        path = args.raw_dir / filename
        download(session, url, path, args.refresh)
        require_sha256(path, checksum)
        paths[key] = path
    for key, (file_id, checksum, filename) in DATAVERSE_SOURCES.items():
        path = args.raw_dir / filename
        download_dataverse(session, file_id, path, args.refresh)
        require_sha256(path, checksum)
        paths[key] = path

    official = {
        year: parse_fec_candidates(year, paths[f"fec_{year}"])
        for year in (2016, 2018, 2020, 2022)
    }
    official[2024] = parse_2024_official(paths["senate_2024_state"])

    for year in YEARS:
        if year == 2016:
            frame = read_2016(
                paths["senate_2016"],
                args.raw_dir / "senate_2016_filtered.csv",
            )
            areas = aggregate_mit_frame(frame, year, "candidate_normalized")
        elif year == 2018:
            frame = read_2018(paths["senate_2018"])
            areas = aggregate_mit_frame(frame, year)
        elif year == 2020:
            frame = None
            areas = aggregate_2020(paths["senate_2020"])
        elif year == 2022:
            frame_2018 = read_2018(paths["senate_2018"])
            town_to_code = connecticut_town_codes(frame_2018)
            del frame_2018
            gc.collect()
            frame = pd.read_csv(paths["senate_2022"], sep="\t", low_memory=False)
            areas = aggregate_mit_frame(frame, year)
        else:
            frame = pd.read_csv(paths["senate_2024_county"], low_memory=False)
            areas = aggregate_mit_frame(frame, year)
        del frame
        gc.collect()

        boundaries = boundary_lookup(args.output_dir, year)
        if year == 2016:
            replace_state(
                areas,
                "LA",
                parse_louisiana_runoff(paths["louisiana_2016_runoff"], boundaries),
            )
        elif year == 2018:
            replace_state(
                areas,
                "IN",
                parse_indiana(paths["indiana_2018"], boundaries),
            )
        elif year == 2020:
            replace_state(
                areas,
                "GA",
                parse_georgia_runoff(paths["georgia_2020_runoff"], year, boundaries),
            )
        elif year == 2022:
            replace_state(
                areas,
                "CT",
                parse_connecticut(paths["connecticut_2022"], town_to_code, boundaries),
            )
            replace_state(
                areas,
                "GA",
                parse_georgia_runoff(paths["georgia_2022_runoff"], year, boundaries),
            )
            override_statewide_final(areas, "AK", official[year])
            override_statewide_final(areas, "VT", official[year])

        canonicalize_candidates(year, areas, official[year])
        county_states = state_areas(areas)
        if len(county_states) != EXPECTED_STATES[year]:
            raise SystemExit(
                f"{year}: expected {EXPECTED_STATES[year]} regular Senate states, found {len(county_states)}"
            )
        validate_reconciliation(year, county_states, official[year])
        states = official_state_areas(official[year])

        county_boundaries = prepare_boundaries(args.output_dir, year, areas)
        state_boundaries = prepare_state_boundaries(args.output_dir, year, states)
        write_geojson(
            args.output_dir / f"us_senate_{year}_county_boundaries.geojson",
            county_boundaries,
        )
        write_geojson(
            args.output_dir / f"us_senate_{year}_state_boundaries.geojson",
            state_boundaries,
        )
        write_csv(
            args.output_dir / f"us_{year}_senate_county_fpp.csv",
            build_rows(year, areas, "county"),
        )
        write_csv(
            args.output_dir / f"us_{year}_senate_state_fpp.csv",
            build_rows(year, states, "state"),
        )
        winners = Counter(
            max(area["candidates"].values(), key=lambda item: int(item["votes"]))["party"]
            for area in states.values()
        )
        print(
            f"{year}: {len(areas):,} county/reporting areas, {len(states)} regular races; "
            + ", ".join(f"{party} {count}" for party, count in winners.most_common())
        )
        del areas, county_states, states, boundaries
        gc.collect()


if __name__ == "__main__":
    main()
