#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd
import pyreadr
import requests
from pypdf import PdfReader


YEARS = (2024, 2022, 2020, 2018, 2016)
MIT_SOURCE_PAGE = "https://electionlab.mit.edu/data"
GITHUB_COMMITS = {
    2024: "df531089c78e6d0098db1a6bfb3849a066a06995",
    2022: "01d954bc3590476ca56eb16fcb7c50224967b665",
    2018: "42055b11dcd5477bc125cdec5a18fbcc60fb6bed",
    2016: "53297d9f7f6d6602b8fdc80f03f14f9153ac4458",
}
STATES_BY_YEAR = {
    2024: ("DE", "IN", "MO", "MT", "NH", "NC", "ND", "UT", "VT", "WA", "WV"),
    2022: (
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "FL", "GA", "HI", "ID", "IL",
        "IA", "KS", "ME", "MD", "MA", "MI", "MN", "NE", "NV", "NH", "NM", "NY",
        "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "VT", "WI", "WY",
    ),
    2020: ("DE", "IN", "MO", "MT", "NH", "NC", "ND", "UT", "VT", "WA", "WV"),
    2018: (
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "FL", "GA", "HI", "ID", "IL",
        "IA", "KS", "ME", "MD", "MA", "MI", "MN", "NE", "NV", "NH", "NM", "NY",
        "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "VT", "WI", "WY",
    ),
    2016: ("DE", "IN", "MO", "MT", "NH", "NC", "ND", "OR", "UT", "VT", "WA", "WV"),
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
COMBINED_SOURCES = {
    2018: (
        "https://raw.githubusercontent.com/MEDSL/2018-elections-official/"
        f"{GITHUB_COMMITS[2018]}/STATE/STATE_precinct_general.zip",
        "a9c2a201b3efaf1a0c8a62249f65b5aed3ce1ca5bcbcb4aa6a8a3e2702f6c626",
        "state_2018.zip",
    ),
    2016: (
        "https://raw.githubusercontent.com/MEDSL/elections/"
        f"{GITHUB_COMMITS[2016]}/data/state_precincts_2016.rda",
        "638d2dc3087b53df041a32baaa9e0411c42c82fdbfd9732d0fc9979870a87772",
        "state_2016.rda",
    ),
}
DATAVERSE_2020 = {
    "DE": (6100418, "2020-de-precinct-general.tab", "e1f1292aa2286c0fc3522a03f18a1151"),
    "IN": (13582892, "2020_in_precinct_general.tab", "ef260a79c4b38baf9cf3bc6f6dbac54e"),
    "MO": (6100413, "2020-mo-precinct-general.tab", "51365ba76c2309d250b50d9802c68450"),
    "MT": (6100404, "2020-mt-precinct-general.tab", "97970993a2e4eb71712d8decd024582d"),
    "NH": (6100419, "2020-nh-precinct-general.tab", "93fbb95393674e0d63c8e1337958ae04"),
    "NC": (6100444, "2020-nc-precinct-general.csv", "2ec3395a08eb3c992b486fc1b27d196e"),
    "ND": (6100438, "2020-nd-precinct-general.tab", "4ab6055d1bbb479dec9aab4e3b06c341"),
    "UT": (6100430, "2020-ut-precinct-general.tab", "77bcc7c10f855365d95fe90eddd729fd"),
    "VT": (6100442, "2020-vt-precinct-general.tab", "de617254c3c34fc35a3157835e16ff93"),
    "WA": (6100434, "2020-wa-precinct-general.tab", "71536313e0b0de4515d8123816c3034d"),
    "WV": (6100431, "2020-wv-precinct-general.tab", "4492997b11ecf59d31518c756918993e"),
}
TENNESSEE_2022 = (
    "https://sos-prod.tnsosgovfiles.com/s3fs-public/document/20221108GovbyCounty.pdf",
    "1542b43a6844390f9912fb6977fe1cce11e6b67a2866ed400210eb8a12e72d25",
    "tn_2022_governor_county.pdf",
)
FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)
NON_CANDIDATES = {
    "", "ABSENTEE / MILITARY", "AFFIDAVIT", "BALLOTS CAST", "BLANK",
    "BLANK BALLOTS", "BLANK VOTES", "BLANK/VOID", "BLANKS", "CAST VOTES",
    "ELIGIBLE", "FEDERAL", "FEDERAL BALLOTS", "INVALID VOTES",
    "MANUALLY COUNTED EMERGENCY", "NAN", "NO VOTE", "OVERVOTE", "OVERVOTES",
    "OVER VOTES", "PUBLIC COUNTER", "REGISTERED VOTERS", "SPECIAL VOTES",
    "STATE BALLOTS", "STATE VOTES", "TIMES BLANK VOTED", "TOTAL",
    "TOTAL VOTES", "TOTAL VOTES CAST", "UNDERVOTE", "UNDERVOTES",
    "UNDER VOTES", "VOID", "VOIDS", "VOTES CAST",
}
CODE_MERGES = {
    "29380": "29095", "2938000": "29095", "36122": "36123",
    "46102": "46113", "51515": "51019",
}
PARTY_OVERRIDES = {
    (2022, "MN", "TIMWALZ"): "Democratic",
    (2022, "NM", "MICHELLELUJANGRISHAM"): "Democratic",
    (2016, "ND", "DOUGBURGUMBRENTSANFORD"): "Republican",
}
CANDIDATE_ALIASES = {
    (2016, "IN", "BELLTATGENHORST"): "REXBELL",
    (2016, "IN", "GREGGHALE"): "JOHNGREGG",
    (2016, "IN", "HOLCOMBCROUCH"): "ERICHOLCOMB",
    (2016, "IN", "JOHNRGREGG"): "JOHNGREGG",
    (2016, "UT", "GRAYHERBERT"): "GARYHERBERT",
    (2016, "UT", "HERBERT"): "GARYHERBERT",
}
NAME_OVERRIDES = {
    (2020, "MT", "GREGGIANYES"): "Greg Gianforte",
}


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
    session: requests.Session, file_id: int, path: Path, refresh: bool,
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
        raise SystemExit(f"Dataverse {file_id}: no signed download URL: {payload}") from exc
    download(session, signed_url, path, True)


def require_digest(path: Path, expected: str, algorithm: str = "sha256") -> None:
    digest = hashlib.new(algorithm, path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: checksum changed to {digest}; expected {expected}")


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


def title_name(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    if text.upper() in {"[WRITE-IN]", "WRITEIN", "WRITE-IN", "SCATTERING"}:
        return "Write-ins"
    return text.title().replace(" Ii", " II").replace(" Iii", " III")


def canonical_party(detailed: object, simplified: object = "") -> str:
    detail = str(detailed).strip().upper()
    value = str(simplified).strip().upper() or detail
    if (
        "DEMOCRAT" in value
        or "DEMOCRAT" in detail
        or value in {"D", "D*", "DFL"}
        or value.startswith(("D/", "DEM/"))
    ):
        return "Democratic"
    if "REPUBLICAN" in value or value in {"R", "R*", "REP"} or value.startswith("R/"):
        return "Republican"
    if "LIBERTARIAN" in value or value == "LIB":
        return "Libertarian"
    if "GREEN" in value or value in {"GRE", "GRN"}:
        return "Green"
    if "INDEPENDENT" in detail or detail in {"IND", "I", "NONPARTISAN", "NOPTY"}:
        return "Independent"
    return "Other"


def candidate_valid(value: object) -> bool:
    return re.sub(r"\s+", " ", str(value).strip().upper()) not in NON_CANDIDATES


def governor_office(value: object) -> bool:
    office = re.sub(r"\s+", " ", str(value).strip().upper())
    if office == "GOVERNOR":
        return True
    return office.startswith("GOVERNOR") and (
        "LIEUTENANT GOVERNOR" in office
        or bool(re.search(r"\bLT\.? GOVERNOR\b", office))
    )


def false_value(value: object) -> bool:
    return str(value).strip().upper() not in {"TRUE", "1"}


def governor_rows(frame: pd.DataFrame, year: int, state: str | None = None) -> pd.DataFrame:
    rows = frame[
        frame["office"].map(governor_office)
        & (frame["stage"].astype(str).str.upper() == "GEN")
        & frame["special"].map(false_value)
        & frame["candidate"].map(candidate_valid)
    ].copy()
    state_column = "state_po" if "state_po" in rows else "state_postal"
    rows["_state"] = rows[state_column].astype(str).str.strip().str.upper()
    rows = rows[rows["_state"].isin(STATES_BY_YEAR[year])]
    if state:
        rows = rows[rows["_state"] == state]
    return rows


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


def aggregate_frame(
    frame: pd.DataFrame, year: int, expected_state: str | None = None,
) -> dict[str, dict[str, object]]:
    rows = governor_rows(frame, year, expected_state)
    if rows.empty:
        return {}
    party_detail = "party_detailed" if "party_detailed" in rows else "party"
    party_simple = "party_simplified" if "party_simplified" in rows else None
    vote_column = "votes" if "votes" in rows else "candidatevotes"
    rows["_code"] = [
        county_code(value, state)
        for value, state in zip(rows["county_fips"], rows["_state"])
    ]
    rows = rows[rows["_code"] != ""]
    rows["_candidate"] = rows["candidate"].map(normalized)
    rows["_candidate"] = [
        CANDIDATE_ALIASES.get((year, state, candidate), candidate)
        for state, candidate in zip(rows["_state"], rows["_candidate"])
    ]
    writein_rows = (
        rows["writein"].astype(str).str.upper().isin({"TRUE", "1"})
        if "writein" in rows
        else pd.Series(False, index=rows.index)
    )
    rows["_candidate"] = rows["_candidate"].where(
        ~(
            writein_rows
            | rows["candidate"].astype(str).str.upper().isin(
                {"[WRITE-IN]", "WRITEIN", "WRITE-IN", "SCATTERING"}
            )
        ),
        "WRITEINS",
    )
    rows["_name"] = rows["candidate"].map(title_name)
    rows["_party"] = [
        canonical_party(detail, simple if party_simple else "")
        for detail, simple in zip(
            rows[party_detail],
            rows[party_simple] if party_simple else [""] * len(rows),
        )
    ]
    rows["_votes"] = rows[vote_column].map(number)
    rows["_is_total"] = rows["mode"].astype(str).str.upper() == "TOTAL"
    rows["_reporting"] = (
        rows["precinct"].fillna("").astype(str) if "precinct" in rows else "__county__"
    )
    grouping = ["_state", "_code", "_reporting", "_candidate"]
    rows["_total_votes"] = rows["_votes"].where(rows["_is_total"], 0)
    rows["_component_votes"] = rows["_votes"].where(~rows["_is_total"], 0)
    reporting = rows.groupby(grouping, dropna=False).agg(
        total_votes=("_total_votes", "sum"),
        component_votes=("_component_votes", "sum"),
        has_total=("_is_total", "max"),
    ).reset_index()
    reporting["votes"] = reporting["total_votes"].where(
        reporting["has_total"], reporting["component_votes"]
    )
    county = reporting.groupby(["_state", "_code", "_candidate"], dropna=False)["votes"].sum()
    variants = rows.groupby(
        ["_state", "_candidate", "_name", "_party"], dropna=False
    )["_votes"].sum()
    preferred: dict[tuple[str, str], tuple[str, str, int]] = {}
    for (state, key, name, party), votes in variants.items():
        candidate = (str(name), str(party), int(votes))
        current = preferred.get((state, key))
        if (
            current is None
            or (candidate[1] in {"Democratic", "Republican"} and current[1] not in {"Democratic", "Republican"})
            or candidate[2] > current[2]
        ):
            preferred[(state, key)] = candidate
    areas: dict[str, dict[str, object]] = {}
    for (state, code, key), votes in county.items():
        if not votes:
            continue
        name, party, _ = preferred[(state, key)]
        if key == "WRITEINS":
            name, party = "Write-ins", "Other"
        name = NAME_OVERRIDES.get((year, state, key), name)
        party = PARTY_OVERRIDES.get((year, state, key), party)
        area = areas.setdefault(
            code, {"code": code, "state_abbr": state, "candidates": {}}
        )
        item = area["candidates"].setdefault(
            key, {"id": key, "name": name, "party": party, "votes": 0}
        )
        item["votes"] = int(item["votes"]) + int(votes)
    return areas


def merge_areas(
    target: dict[str, dict[str, object]], source: dict[str, dict[str, object]],
) -> None:
    for code, area in source.items():
        output = target.setdefault(
            code, {"code": code, "state_abbr": area["state_abbr"], "candidates": {}}
        )
        for key, candidate in area["candidates"].items():
            if key not in output["candidates"]:
                output["candidates"][key] = dict(candidate)
            else:
                item = output["candidates"][key]
                item["votes"] = int(item["votes"]) + int(candidate["votes"])


def read_archive_chunks(path: Path, chunksize: int = 200_000):
    with zipfile.ZipFile(path) as archive:
        member = next(
            name for name in archive.namelist()
            if name.lower().endswith((".csv", ".tab"))
        )
        with archive.open(member) as handle:
            yield from pd.read_csv(
                handle,
                sep="\t" if member.lower().endswith(".tab") else ",",
                chunksize=chunksize,
                low_memory=False,
            )


def aggregate_archive(
    path: Path, year: int, expected_state: str | None = None,
) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    for chunk in read_archive_chunks(path):
        merge_areas(areas, aggregate_frame(chunk, year, expected_state))
    return areas


def aggregate_delimited(
    path: Path, year: int, expected_state: str,
) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    separator = "," if path.suffix.lower() == ".csv" else "\t"
    for chunk in pd.read_csv(path, sep=separator, chunksize=200_000, low_memory=False):
        merge_areas(areas, aggregate_frame(chunk, year, expected_state))
    return areas


def read_2016(path: Path, cache_path: Path) -> pd.DataFrame:
    if cache_path.exists():
        return pd.read_csv(cache_path, low_memory=False)
    frame = next(iter(pyreadr.read_r(str(path)).values()))
    needed = [
        "stage", "special", "state_postal", "county_fips", "precinct", "candidate",
        "office", "party", "mode", "votes",
    ]
    return frame[needed].copy()


def github_archive_url(year: int, state: str) -> str:
    if year == 2024:
        path = f"individual_states/{state.lower()}24.zip"
        repo = "2024-elections-official"
    else:
        path = f"individual_states/2022-{state.lower()}-local-precinct-general.zip"
        repo = "2022-elections-official"
    return (
        f"https://raw.githubusercontent.com/MEDSL/{repo}/"
        f"{GITHUB_COMMITS[year]}/{path}"
    )


def boundary_sources(output_dir: Path, year: int) -> list[dict[str, object]]:
    if year <= 2018:
        names = ["us_president_2008_2016_county_boundaries.geojson"]
    elif year == 2020:
        names = ["us_president_2020_county_boundaries.geojson"]
    else:
        names = [
            "us_president_2024_county_boundaries.geojson",
            "us_president_2008_2016_county_boundaries.geojson",
        ]
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


def county_name_lookup(
    output_dir: Path, year: int, state: str,
) -> dict[str, str]:
    state_name = STATE_BY_ABBR[state][1]
    result = {}
    for code, feature in boundary_lookup(output_dir, year).items():
        district = str(feature["properties"]["district"])
        if not district.endswith(f", {state_name}"):
            continue
        local = district.rsplit(",", 1)[0]
        local = re.sub(r"\s+COUNTY$", "", local, flags=re.IGNORECASE)
        result[normalized(local)] = code
    return result


def parse_tennessee_2022(path: Path, output_dir: Path) -> dict[str, dict[str, object]]:
    candidates = (
        ("Bill Lee", "Republican"),
        ("Jason Brantley Martin", "Democratic"),
        ("Constance M. Every", "Independent"),
        ("John Gentry", "Independent"),
        ("Basil Marceaux", "Independent"),
        ("Charles Van Morgan", "Independent"),
        ("Alfred O'Neil", "Independent"),
        ("Deborah Rouse", "Independent"),
        ("Michael E. Scantland", "Independent"),
        ("Rick Tyler", "Independent"),
    )
    name_to_code = county_name_lookup(output_dir, 2022, "TN")
    areas: dict[str, dict[str, object]] = {}
    for page in PdfReader(str(path)).pages:
        text = page.extract_text(extraction_mode="layout")
        for line in text.splitlines():
            match = re.match(
                r"^([A-Za-z][A-Za-z .'-]+?)\s{2,}"
                r"((?:[\d,]+\s+){9}[\d,]+)\s*$",
                line,
            )
            if not match or match.group(1).strip() == "STATE TOTALS":
                continue
            county = match.group(1).strip()
            code = name_to_code.get(normalized(county))
            if not code:
                raise SystemExit(f"Tennessee 2022: boundary missing county {county}")
            votes = [int(value.replace(",", "")) for value in match.group(2).split()]
            area = areas.setdefault(
                code, {"code": code, "state_abbr": "TN", "candidates": {}}
            )
            for (name, party), total in zip(candidates, votes):
                key = normalized(name)
                area["candidates"][key] = {
                    "id": key, "name": name, "party": party, "votes": total,
                }
    if len(areas) != 95:
        raise SystemExit(f"Tennessee 2022: expected 95 counties, found {len(areas)}")
    return areas


def state_areas(county_areas: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {}
    for area in county_areas.values():
        state = str(area["state_abbr"])
        target = states.setdefault(
            state, {"code": state, "state_abbr": state, "candidates": {}}
        )
        for key, candidate in area["candidates"].items():
            item = target["candidates"].setdefault(
                key, {
                    "id": key, "name": candidate["name"],
                    "party": candidate["party"], "votes": 0,
                },
            )
            item["votes"] = int(item["votes"]) + int(candidate["votes"])
    return states


def prepare_boundaries(
    output_dir: Path, year: int, areas: dict[str, dict[str, object]],
) -> dict[str, object]:
    lookup = boundary_lookup(output_dir, year)
    features = []
    for code, area in sorted(areas.items()):
        if code not in lookup:
            raise SystemExit(f"{year}: county boundary missing result code {code}")
        feature = json.loads(json.dumps(lookup[code]))
        state_name = STATE_BY_ABBR[str(area["state_abbr"])][1]
        feature["properties"] = {
            "district": str(feature["properties"]["district"]),
            "constituency_code": f"US-GOVERNOR-COUNTY-{code}",
            "electorate_type": state_name,
        }
        area["district"] = feature["properties"]["district"]
        features.append(feature)
    return {
        "type": "FeatureCollection",
        "name": f"us_governor_{year}_counties",
        "features": features,
    }


def prepare_state_boundaries(
    output_dir: Path, year: int, areas: dict[str, dict[str, object]],
) -> dict[str, object]:
    source = json.loads(
        (output_dir / "us_president_state_boundaries.geojson").read_text(encoding="utf-8")
    )
    lookup = {
        str(feature["properties"]["constituency_code"]).removeprefix("US-STATE-"): feature
        for feature in source["features"]
    }
    features = []
    for state, area in sorted(areas.items()):
        feature = json.loads(json.dumps(lookup[state]))
        state_name = STATE_BY_ABBR[state][1]
        feature["properties"] = {
            "district": state_name,
            "constituency_code": f"US-GOVERNOR-STATE-{state}",
            "electorate_type": "United States",
        }
        area["district"] = state_name
        features.append(feature)
    if len(features) != len(areas):
        raise SystemExit(f"{year}: state boundary/result join is incomplete")
    return {
        "type": "FeatureCollection",
        "name": f"us_governor_{year}_states",
        "features": features,
    }


def build_rows(
    year: int, areas: dict[str, dict[str, object]], geography: str,
) -> list[dict[str, object]]:
    rows = []
    for area in sorted(
        areas.values(),
        key=lambda item: (STATE_BY_ABBR[str(item["state_abbr"])][1], str(item["district"])),
    ):
        candidates = sorted(
            (
                candidate for candidate in area["candidates"].values()
                if int(candidate["votes"]) > 0
            ),
            key=lambda item: (-int(item["votes"]), str(item["name"])),
        )
        if len(candidates) < 2:
            raise SystemExit(f"{year} {area['district']}: fewer than two governor candidates")
        total = sum(int(candidate["votes"]) for candidate in candidates)
        state = str(area["state_abbr"])
        note = (
            "Candidate totals are aggregated from checksum- or revision-pinned MIT Election "
            "Lab precinct returns. The state view is the sum of mapped county/reporting areas."
        )
        if year == 2022 and state == "AK":
            note += " Alaska is shown as a statewide fallback for its ranked-choice contest."
        base = {
            "district": area["district"],
            "district_url": MIT_SOURCE_PAGE,
            "distribution_url": MIT_SOURCE_PAGE,
            "elected_member": candidates[0]["name"],
            "elected_party": candidates[0]["party"],
            "enrolment": 0,
            "formal_votes": total,
            "informal_votes": 0,
            "total_votes": total,
            "turnout_pct": 0,
            "majority": int(candidates[0]["votes"]) - int(candidates[1]["votes"]),
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": (
                STATE_BY_ABBR[state][1] if geography == "county" else "United States"
            ),
            "constituency_code": (
                f"US-GOVERNOR-COUNTY-{area['code']}"
                if geography == "county"
                else f"US-GOVERNOR-STATE-{area['code']}"
            ),
            "contest_status": "compiled",
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
        description="Build U.S. governor county and state views, 2016-2024"
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/us_governor"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--years", type=int, nargs="+", choices=YEARS, default=list(YEARS))
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"

    combined_paths = {}
    for year, (url, checksum, filename) in COMBINED_SOURCES.items():
        if year not in args.years:
            continue
        path = args.raw_dir / filename
        download(session, url, path, args.refresh)
        require_digest(path, checksum)
        combined_paths[year] = path

    for year in (item for item in YEARS if item in args.years):
        areas: dict[str, dict[str, object]] = {}
        if year == 2016:
            frame = read_2016(
                combined_paths[2016], args.raw_dir / "state_2016_governor.csv"
            )
            areas = aggregate_frame(frame, year)
            del frame
        elif year == 2018:
            areas = aggregate_archive(combined_paths[2018], year)
        elif year == 2020:
            for state, (file_id, filename, checksum) in DATAVERSE_2020.items():
                path = args.raw_dir / filename
                download_dataverse(session, file_id, path, args.refresh)
                require_digest(path, checksum, "md5")
                merge_areas(areas, aggregate_delimited(path, year, state))
        else:
            for state in STATES_BY_YEAR[year]:
                path = args.raw_dir / f"{state.lower()}_{year}.zip"
                download(session, github_archive_url(year, state), path, args.refresh)
                merge_areas(areas, aggregate_archive(path, year, state))
            if year == 2022 and "TN" not in {str(area["state_abbr"]) for area in areas.values()}:
                url, checksum, filename = TENNESSEE_2022
                path = args.raw_dir / filename
                download(session, url, path, args.refresh)
                require_digest(path, checksum)
                merge_areas(areas, parse_tennessee_2022(path, args.output_dir))
        gc.collect()

        states = state_areas(areas)
        expected_states = set(STATES_BY_YEAR[year])
        if set(states) != expected_states:
            raise SystemExit(
                f"{year}: governor state coverage changed; "
                f"missing {sorted(expected_states - set(states))}, "
                f"extra {sorted(set(states) - expected_states)}"
            )
        county_boundaries = prepare_boundaries(args.output_dir, year, areas)
        state_boundaries = prepare_state_boundaries(args.output_dir, year, states)
        write_geojson(
            args.output_dir / f"us_governor_{year}_county_boundaries.geojson",
            county_boundaries,
        )
        write_geojson(
            args.output_dir / f"us_governor_{year}_state_boundaries.geojson",
            state_boundaries,
        )
        write_csv(
            args.output_dir / f"us_{year}_governor_county_fpp.csv",
            build_rows(year, areas, "county"),
        )
        write_csv(
            args.output_dir / f"us_{year}_governor_state_fpp.csv",
            build_rows(year, states, "state"),
        )
        winners = Counter(
            max(area["candidates"].values(), key=lambda item: int(item["votes"]))["party"]
            for area in states.values()
        )
        print(
            f"{year}: {len(areas):,} county/reporting areas, {len(states)} races; "
            + ", ".join(f"{party} {count}" for party, count in winners.most_common())
        )
        del areas, states
        gc.collect()


if __name__ == "__main__":
    main()
