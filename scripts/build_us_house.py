#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import requests
from pypdf import PdfReader
from shapely.geometry import mapping, shape


RESULTS_PAGE = "https://clerk.house.gov/Members/ViewElectionInformation"
EXPECTED_SEATS = 435
YEARS = (2024, 2022, 2020, 2018, 2016)

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
]

# 2020 apportionment, used from the 2022 election.
APPORTIONMENT_2020 = {
    "Alabama": 7, "Alaska": 1, "Arizona": 9, "Arkansas": 4, "California": 52,
    "Colorado": 8, "Connecticut": 5, "Delaware": 1, "Florida": 28, "Georgia": 14,
    "Hawaii": 2, "Idaho": 2, "Illinois": 17, "Indiana": 9, "Iowa": 4,
    "Kansas": 4, "Kentucky": 6, "Louisiana": 6, "Maine": 2, "Maryland": 8,
    "Massachusetts": 9, "Michigan": 13, "Minnesota": 8, "Mississippi": 4,
    "Missouri": 8, "Montana": 2, "Nebraska": 3, "Nevada": 4, "New Hampshire": 2,
    "New Jersey": 12, "New Mexico": 3, "New York": 26, "North Carolina": 14,
    "North Dakota": 1, "Ohio": 15, "Oklahoma": 5, "Oregon": 6, "Pennsylvania": 17,
    "Rhode Island": 2, "South Carolina": 7, "South Dakota": 1, "Tennessee": 9,
    "Texas": 38, "Utah": 4, "Vermont": 1, "Virginia": 11, "Washington": 10,
    "West Virginia": 2, "Wisconsin": 8, "Wyoming": 1,
}

# 2010 apportionment, used for the 2016, 2018, and 2020 elections.
APPORTIONMENT_2010 = {
    **APPORTIONMENT_2020,
    "California": 53, "Colorado": 7, "Florida": 27, "Illinois": 18,
    "Michigan": 14, "Montana": 1, "New York": 27, "North Carolina": 13,
    "Ohio": 16, "Oregon": 5, "Pennsylvania": 18, "Texas": 36,
    "West Virginia": 3,
}

# Kept as the current apportionment alias for existing validator imports.
STATE_SEATS = APPORTIONMENT_2020

ELECTIONS = {
    2024: {
        "congress": 119,
        "seats": APPORTIONMENT_2020,
        "results_url": "https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf",
        "results_sha256": None,
        "boundary_url": "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_5m.zip",
        "boundary_sha256": None,
        "boundary_filename": "cb_2024_us_cd119_5m.zip",
        "expected_candidates": 1_241,
        "expected_winners": {"Republican": 220, "Democratic": 215},
    },
    2022: {
        "congress": 118,
        "seats": APPORTIONMENT_2020,
        "results_url": "https://clerk.house.gov/member_info/electionInfo/2022/statistics2022.pdf",
        "results_sha256": "ef9b8cefcc44bebbdc4928bf346b50e00a72dd3bb54a71ed93ec60d4ebf47690",
        "boundary_url": "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_cd118_20m.zip",
        "boundary_sha256": "510081c2b9087b8663fc532dd7a2925c18f66e3c87e35cba05ef8379629e1b2e",
        "boundary_filename": "cb_2022_us_cd118_20m.zip",
        "expected_candidates": 1_238,
        "expected_winners": {"Republican": 222, "Democratic": 213},
    },
    2020: {
        "congress": 117,
        "seats": APPORTIONMENT_2010,
        "results_url": "https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf",
        "results_sha256": "666b2a1f673f263087c141c4d44b0dce47cbddc8f4df27fbc8b415cf05842b76",
        # Census did not publish a national 117th file. All states except North
        # Carolina retained their 116th boundaries; NC is replaced below.
        "boundary_url": "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_cd116_20m.zip",
        "boundary_sha256": "17c5e10b1ad8130cea74972e882a4da8653d52f09c08aef24d3e58f850baab67",
        "boundary_filename": "cb_2020_us_cd116_20m.zip",
        "nc_boundary_url": (
            "https://raw.githubusercontent.com/JeffreyBLewis/congressional-district-boundaries/"
            "e6698d87f963f97f948357a6fc03e2e64795e0de/"
            "GeoJson/North%20Carolina_117_to_117.geojson"
        ),
        "nc_boundary_sha256": "622c4af899f2e77c8603377a15fa10422753b2a278d79d36fab0d9d8eaf916bd",
        "expected_candidates": 1_307,
        "expected_winners": {"Democratic": 222, "Republican": 213},
    },
    2018: {
        "congress": 116,
        "seats": APPORTIONMENT_2010,
        "results_url": "https://clerk.house.gov/member_info/electionInfo/2018/statistics2018.pdf",
        "results_sha256": "35ef9bc223d89cbd3ce4c544a88e93523394060d400001d365612c97f9348c53",
        "boundary_url": "https://www2.census.gov/geo/tiger/GENZ2018/shp/cb_2018_us_cd116_20m.zip",
        "boundary_sha256": "0ff70125fe422e974ba359f744e206d05256778e964b378452b47920c729ef60",
        "boundary_filename": "cb_2018_us_cd116_20m.zip",
        "expected_candidates": 1_296,
        "expected_winners": {"Democratic": 235, "Republican": 199, "Other": 1},
    },
    2016: {
        "congress": 115,
        "seats": APPORTIONMENT_2010,
        "results_url": "https://clerk.house.gov/member_info/electionInfo/2016/statistics2016.pdf",
        "results_sha256": "6d2eba0e60e3f32153a5ba9c369a42a04616ccc73b5b3bca927ea6a11cade3a3",
        "boundary_url": "https://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_us_cd115_20m.zip",
        "boundary_sha256": "275e6a63ef8313c6d2e487388f1b61c8cccccc64c3e4cb0b209c3f154d426400",
        "boundary_filename": "cb_2016_us_cd115_20m.zip",
        "expected_candidates": 1_288,
        "expected_winners": {"Republican": 241, "Democratic": 194},
    },
}

STATE_FIPS = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut", "10": "Delaware",
    "12": "Florida", "13": "Georgia", "15": "Hawaii", "16": "Idaho",
    "17": "Illinois", "18": "Indiana", "19": "Iowa", "20": "Kansas",
    "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland",
    "25": "Massachusetts", "26": "Michigan", "27": "Minnesota", "28": "Mississippi",
    "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada",
    "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico", "36": "New York",
    "37": "North Carolina", "38": "North Dakota", "39": "Ohio", "40": "Oklahoma",
    "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
    "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas",
    "49": "Utah", "50": "Vermont", "51": "Virginia", "53": "Washington",
    "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming",
}

FUSION_LINES = {
    "Connecticut": {"Working Families", "Independent"},
    "New York": {
        "Blue Lives Matter", "Common Sense", "Common Sense Suffolk", "Conservative",
        "Constitution", "Independence", "Libertarian", "Medical Freedom", "Moderate",
        "Parent", "Reform", "Save America Movement", "Save Our City",
        "Serve America Movement", "Stop Iran Deal", "Upstate Jobs", "Women’s Equality",
        "Working Families",
    },
    "South Carolina": {"Green", "Working Families"},
    "Virginia": {"Independent"},
}
INVALID_LINES = {
    "Blank", "Blanks", "Blank Votes", "Exhausted Ballot", "Exhausted Ballots",
    "Over Votes", "Overvotes", "Spoiled Votes", "Under Votes", "Void",
}
WRITE_IN_LINES = {
    "All Others", "Miscellaneous", "Other Write-ins", "Others", "Scatter",
    "Scattering", "Write-in", "Write-in (Miscellaneous)", "Write-in (No Party)",
    "Write-in (Other)", "Write-Ins", "Write-ins",
}
PARTY_NAMES = {
    "Democrat": "Democratic",
    "Democratic-Farmer-Labor": "Democratic",
    "Democratic-Nonpartisan League": "Democratic",
    "Republican/Tax Revolt": "Republican",
}
PDF_FOOTNOTE_VOTE_FIXES = {
    # The 2016 Clerk PDF text layer joins Louisiana runoff footnote markers
    # 2 and 3 to the leading edge of these general-election vote totals.
    (2016, "Louisiana", 3, 277_671): 77_671,
    (2016, "Louisiana", 3, 260_762): 60_762,
    (2016, "Louisiana", 4, 387_370): 87_370,
    (2016, "Louisiana", 4, 346_579): 46_579,
    (2016, "Ohio", 8, 187_794): 87_794,
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def require_sha256(path: Path, expected: str | None) -> None:
    if not expected:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def district_name(state: str, number: int) -> str:
    if number == 0:
        return f"{state} at-large"
    suffix = "th" if 10 < number % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{state} {number}{suffix}"


def unwrap_antimeridian_coordinates(coordinates):
    """Keep Aleutian rings contiguous in the app's simple longitude projection."""
    if coordinates and isinstance(coordinates[0], (int, float)):
        longitude, latitude, *rest = coordinates
        return (longitude - 360 if longitude > 0 else longitude, latitude, *rest)
    return tuple(unwrap_antimeridian_coordinates(part) for part in coordinates)


def parse_recap_totals(
    reader: PdfReader,
    state_seats: dict[str, int],
) -> dict[tuple[str, int], int]:
    state_lookup = {state.upper(): state for state in state_seats}
    district_line = re.compile(r"^\s*(?:(\d+)(?:st|d|th) district|At large).*?([\d,]+)\s*$", re.I)
    state = ""
    totals: dict[tuple[str, int], list[int]] = defaultdict(list)
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw in text.splitlines():
            line = raw.strip().replace("\xa0", " ")
            heading = line.replace("—Continued", "").replace("-Continued", "").strip()
            if heading in state_lookup:
                state = state_lookup[heading]
                continue
            match = district_line.match(line)
            if match and state:
                totals[(state, int(match.group(1) or 0))].append(int(match.group(2).replace(",", "")))
    # Wide recapitulation tables sometimes wrap into two column groups. The final
    # district total is always the largest last-column figure for that district.
    return {key: max(values) for key, values in totals.items()}


def parse_results(
    path: Path,
    year: int = 2024,
    config: dict[str, object] | None = None,
) -> dict[tuple[str, int], dict[str, object]]:
    config = config or ELECTIONS[year]
    state_seats = config["seats"]
    if not isinstance(state_seats, dict):
        raise SystemExit(f"{year}: invalid state apportionment configuration")
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(path)
    official_totals = parse_recap_totals(reader, state_seats)
    state_lookup = {state.upper(): state for state in state_seats}
    value_line = re.compile(r"^(.*?)(?:\.{5,})\s*([\d,]+)\s*$")
    uncontested_line = re.compile(r"^(.*?)(?:\.{5,})\s*\(1\)\s*$")
    numbered = re.compile(r"^(\d+)\.\s*(.*)$")

    candidates: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    invalid_votes: Counter[tuple[str, int]] = Counter()
    ranked_choice_totals: dict[tuple[str, int], int] = {}
    state = ""
    district: int | None = None
    in_house = False

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except KeyError:
            continue
        for raw in text.splitlines():
            line = raw.strip().replace("\xa0", " ")
            heading = line.replace("—Continued", "").replace("-Continued", "").strip()
            if heading in state_lookup:
                state = state_lookup[heading]
                district = 0 if state_seats[state] == 1 else None
                in_house = False
                continue
            if line.startswith("FOR UNITED STATES REPRESENTATIVE"):
                in_house = True
                continue
            if in_house and (
                line.startswith("Recapitulation")
                or (line.startswith("FOR UNITED STATES ") and "REPRESENTATIVE" not in line)
            ):
                in_house = False
                continue
            if not in_house:
                continue

            match = value_line.match(line)
            uncontested = False
            if not match:
                match = uncontested_line.match(line)
                uncontested = bool(match)
            if not match:
                continue
            descriptor = match.group(1).strip()
            votes = 0 if uncontested else int(match.group(2).replace(",", ""))
            district_match = numbered.match(descriptor)
            if district_match:
                district = int(district_match.group(1))
                descriptor = district_match.group(2).strip()
            if district is None:
                raise SystemExit(f"PDF page {page_number}: candidate appeared before a district number")
            key = (state, district)

            if descriptor == "Continuing Ballots":
                # Maine 2 repeats the sum of the two continuing candidates as a
                # separate subtotal; counting it again would double the vote.
                continue
            if year == 2022 and key == ("Maine", 2) and descriptor == "Exhausted Ballot":
                # This is the number of ballots entering Maine's second RCV
                # round, not an invalid-vote category. The Clerk recap adds it
                # as a column subtotal alongside the decisive-round totals.
                ranked_choice_totals[key] = votes
                continue
            if descriptor in FUSION_LINES.get(state, set()):
                if not candidates[key]:
                    raise SystemExit(f"PDF page {page_number}: fusion line appeared before a candidate")
                candidates[key][-1]["votes"] = int(candidates[key][-1]["votes"]) + votes
                continue
            if descriptor in INVALID_LINES:
                invalid_votes[key] += votes
                continue
            if "," in descriptor:
                name, party = (part.strip() for part in descriptor.rsplit(",", 1))
            elif descriptor in WRITE_IN_LINES:
                name, party = descriptor, "Write-in"
            else:
                raise SystemExit(f"PDF page {page_number}: unrecognised House result line {descriptor!r}")
            if year == 2022 and key == ("Maine", 2) and votes > 1_000_000:
                # PDF extraction joins the superscript round-two footnote marker
                # to each finalist's six-digit vote total.
                votes = int(str(votes)[1:])
            votes = PDF_FOOTNOTE_VOTE_FIXES.get((year, state, district, votes), votes)
            candidates[key].append({"name": name, "party": PARTY_NAMES.get(party, party), "votes": votes})

    expected_keys = {
        (state, 0 if seats == 1 else number)
        for state, seats in state_seats.items()
        for number in ([0] if seats == 1 else range(1, seats + 1))
    }
    if year == 2018 and ("North Carolina", 9) not in candidates:
        # The Clerk publication omits this voided contest because no result was
        # certified. Preserve the State Board's apparent totals while clearly
        # marking that the election produced no winner.
        candidates[("North Carolina", 9)] = [
            {"name": "Mark Harris", "party": "Republican", "votes": 139_246},
            {"name": "Dan McCready", "party": "Democratic", "votes": 138_341},
            {"name": "Jeff Scott", "party": "Libertarian", "votes": 5_130},
        ]
    if set(candidates) != expected_keys:
        missing = sorted(expected_keys - set(candidates))
        extra = sorted(set(candidates) - expected_keys)
        raise SystemExit(
            f"Expected {EXPECTED_SEATS} House districts, found {len(candidates)}; "
            f"missing={missing}, extra={extra}"
        )

    seats: dict[tuple[str, int], dict[str, object]] = {}
    for key in sorted(candidates):
        state, number = key
        result = candidates[key]
        if year == 2022 and key == ("Maine", 2):
            all_lines = {str(candidate["name"]): int(candidate["votes"]) for candidate in result}
            round_total = ranked_choice_totals.get(key, 0)
            if (
                official_totals.get(key)
                != sum(all_lines.values()) + round_total
                or round_total <= 0
            ):
                raise SystemExit("Maine 2nd: ranked-choice subtotals did not reconcile")
            # Publish the decisive round. The Clerk separately lists eliminated
            # first-round lines, which cannot be mixed into a round-two tally.
            result = sorted(result, key=lambda candidate: -int(candidate["votes"]))[:2]
        names = Counter(str(candidate["name"]) for candidate in result)
        for candidate in result:
            if names[str(candidate["name"])] > 1:
                candidate["name"] = f"{candidate['name']} ({candidate['party']})"
        result.sort(key=lambda candidate: (-int(candidate["votes"]), str(candidate["name"])))
        formal = sum(int(candidate["votes"]) for candidate in result)
        if year == 2022 and key == ("Maine", 2):
            total = ranked_choice_totals[key]
            informal = total - formal
        else:
            informal = invalid_votes[key]
            total = formal + informal
        official_total = official_totals.get(key, 0)
        if year == 2024 and key == ("Maine", 2):
            if official_total != formal * 2 + informal:
                raise SystemExit("Maine 2nd: continuing-ballot subtotal did not reconcile")
        elif year == 2022 and key == ("Maine", 2):
            if total <= formal:
                raise SystemExit("Maine 2nd: decisive-round ballot total is invalid")
        elif year == 2020 and key == ("Louisiana", 5):
            # The Clerk recap's PDF text layer drops 200,000 from the Republican
            # subtotal and total; the individual official candidate lines sum
            # to 435,090.
            if total != 435_090 or official_total != 235_090:
                raise SystemExit("Louisiana 5th: known Clerk recap text-layer correction changed")
        elif year == 2018 and key == ("North Carolina", 9):
            if total != 282_717 or official_total:
                raise SystemExit("North Carolina 9th: voided-result fixture changed")
        elif official_total != total:
            raise SystemExit(f"{district_name(*key)}: parsed {total:,} votes but recap reports {official_total:,}")
        winner = result[0]
        if year == 2018 and key == ("North Carolina", 9):
            winner = {"name": "No certified winner", "party": "Other"}
            contest_status = "void"
        else:
            contest_status = "uncontested" if len(result) == 1 else "official"
        seats[key] = {
            "district": district_name(state, number), "state": state,
            "winner": winner["name"], "party": winner["party"], "candidates": result,
            "formal": formal, "informal": informal, "total": total,
            "contest_status": contest_status,
            "source_url": (
                "https://dl.ncsbe.gov/State_Board_Meeting_Docs/"
                "Congressional_District_9_Portal/Order_03132019.pdf"
                if year == 2018 and key == ("North Carolina", 9)
                else RESULTS_PAGE
            ),
        }

    candidate_count = sum(len(seat["candidates"]) for seat in seats.values())
    expected_candidates = config["expected_candidates"]
    if expected_candidates is not None and candidate_count != expected_candidates:
        raise SystemExit("Unexpected candidate-row count after parsing Clerk publication")
    winners = Counter(str(seat["party"]) for seat in seats.values())
    if winners != Counter(config["expected_winners"]):
        raise SystemExit(f"Unexpected House result: {winners}")
    return seats


def build_boundaries(
    path: Path,
    seats: dict[tuple[str, int], dict[str, object]],
    year: int = 2024,
    config: dict[str, object] | None = None,
    nc_path: Path | None = None,
) -> tuple[dict[str, object], dict[tuple[str, int], str]]:
    config = config or ELECTIONS[year]
    congress = int(config["congress"])
    source = gpd.read_file(f"zip://{path.resolve()}").to_crs(epsg=4326)
    source = source[source["STATEFP"].isin(STATE_FIPS)]
    if year == 2020:
        source = source[source["STATEFP"] != "37"]
        if nc_path is None:
            raise SystemExit("2020: North Carolina 117th Congress boundary source is required")
        nc_source = gpd.read_file(nc_path).to_crs(epsg=4326)
        if len(nc_source) != 13:
            raise SystemExit(f"2020: expected 13 North Carolina districts, found {len(nc_source)}")
    else:
        nc_source = None

    boundary_column = f"CD{congress}FP"
    if boundary_column not in source.columns:
        # The 2020 national base is the 116th Congress because Census did not
        # issue a national 117th boundary file.
        boundary_column = "CD116FP"

    records: list[tuple[str, int, object, str]] = []
    for _, row in source.sort_values("GEOID").iterrows():
        state = STATE_FIPS[str(row["STATEFP"])]
        number = int(row[boundary_column])
        records.append((state, number, row.geometry, str(row["GEOID"])))
    if nc_source is not None:
        for _, row in nc_source.sort_values("district").iterrows():
            number = int(row["district"])
            records.append(("North Carolina", number, row.geometry, f"37{number:02d}"))

    features = []
    codes: dict[tuple[str, int], str] = {}
    for state, number, raw_geometry, code in sorted(records):
        key = (state, number)
        if key not in seats:
            raise SystemExit(f"Census boundary has no matching result: {key}")
        geometry = raw_geometry.simplify(0.01, preserve_topology=True)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{district_name(*key)}: invalid simplified Census geometry")
        display_geometry = mapping(geometry)
        if state == "Alaska":
            display_geometry["coordinates"] = unwrap_antimeridian_coordinates(display_geometry["coordinates"])
            unwrapped = shape(display_geometry)
            if unwrapped.is_empty or not unwrapped.is_valid:
                raise SystemExit("Alaska at-large: invalid antimeridian-unwrapped geometry")
        codes[key] = code
        features.append({
            "type": "Feature",
            "properties": {
                "district": seats[key]["district"], "constituency_code": code,
                "electorate_type": state,
            },
            "geometry": display_geometry,
        })
    if len(features) != EXPECTED_SEATS or set(codes) != set(seats):
        raise SystemExit(f"Expected {EXPECTED_SEATS} matching Census districts, found {len(features)}")
    return {
        "type": "FeatureCollection",
        "name": f"us_{year}_{congress}th_congressional_districts",
        "features": features,
    }, codes


def build_rows(seats: dict[tuple[str, int], dict[str, object]], codes: dict[tuple[str, int], str]) -> list[dict[str, object]]:
    rows = []
    for key, seat in sorted(seats.items(), key=lambda item: str(item[1]["district"])):
        base = {
            "district": seat["district"], "district_url": seat.get("source_url", RESULTS_PAGE),
            "distribution_url": seat.get("source_url", RESULTS_PAGE), "elected_member": seat["winner"],
            "elected_party": seat["party"], "enrolment": 0, "formal_votes": seat["formal"],
            "informal_votes": seat["informal"], "total_votes": seat["total"],
            "turnout_pct": 0, "majority": int(seat["formal"]) // 2 + 1 if seat["formal"] else 0,
            "electorate_type": seat["state"], "constituency_code": codes[key],
            "contest_status": seat["contest_status"],
        }
        rows.extend({
            **base, "round_number": 0, "row_type": "first", "excluded_candidate": "",
            "excluded_party": "", "candidate": candidate["name"],
            "candidate_party": candidate["party"], "votes": candidate["votes"],
        } for candidate in seat["candidates"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build official U.S. House election data")
    parser.add_argument("--years", nargs="+", type=int, choices=YEARS, default=[2024])
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/us_house"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; election-preference-explorer/0.1)"})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for year in args.years:
        config = ELECTIONS[year]
        year_raw = args.raw_dir / str(year)
        results_path = year_raw / f"statistics{year}.pdf"
        boundaries_path = year_raw / str(config["boundary_filename"])
        download(session, str(config["results_url"]), results_path, args.refresh)
        download(session, str(config["boundary_url"]), boundaries_path, args.refresh)
        require_sha256(results_path, config["results_sha256"])
        require_sha256(boundaries_path, config["boundary_sha256"])

        nc_path = None
        if "nc_boundary_url" in config:
            nc_path = year_raw / "north_carolina_117th.geojson"
            download(session, str(config["nc_boundary_url"]), nc_path, args.refresh)
            require_sha256(nc_path, config["nc_boundary_sha256"])

        seats = parse_results(results_path, year, config)
        boundaries, codes = build_boundaries(boundaries_path, seats, year, config, nc_path)
        rows = build_rows(seats, codes)
        csv_path = args.out_dir / f"us_{year}_house_fpp.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        boundary_path = args.out_dir / f"us_{year}_congressional_boundaries.geojson"
        boundary_path.write_text(
            json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"Wrote {csv_path} ({len(rows):,} rows, {EXPECTED_SEATS} districts)")
        print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
