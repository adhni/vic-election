#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
import requests
from pypdf import PdfReader
from shapely.geometry import mapping, shape


RESULTS_URL = "https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf"
RESULTS_PAGE = "https://clerk.house.gov/Members/ViewElectionInformation"
BOUNDARY_URL = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_5m.zip"
EXPECTED_SEATS = 435
EXPECTED_CANDIDATES = 1_241

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
]

# 2020 apportionment, used for the 119th Congress elected in 2024.
STATE_SEATS = {
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
    "New York": {"Conservative", "Common Sense Suffolk", "Working Families", "Common Sense"},
}
INVALID_LINES = {"Blank", "Blanks", "Blank Votes", "Over Votes", "Under Votes", "Void", "Exhausted Ballots"}
WRITE_IN_LINES = {"Write-in", "Other Write-ins", "All Others", "Scattering", "Miscellaneous"}
PARTY_NAMES = {
    "Democrat": "Democratic",
    "Democratic-Farmer-Labor": "Democratic",
    "Democratic-Nonpartisan League": "Democratic",
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=180)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


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


def parse_recap_totals(reader: PdfReader) -> dict[tuple[str, int], int]:
    state_lookup = {state.upper(): state for state in STATE_SEATS}
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


def parse_results(path: Path) -> dict[tuple[str, int], dict[str, object]]:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(path)
    official_totals = parse_recap_totals(reader)
    state_lookup = {state.upper(): state for state in STATE_SEATS}
    value_line = re.compile(r"^(.*?)(?:\.{5,})\s*([\d,]+)\s*$")
    uncontested_line = re.compile(r"^(.*?)(?:\.{5,})\s*\(1\)\s*$")
    numbered = re.compile(r"^(\d+)\.\s*(.*)$")

    candidates: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    invalid_votes: Counter[tuple[str, int]] = Counter()
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
                district = 0 if STATE_SEATS[state] == 1 else None
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
            candidates[key].append({"name": name, "party": PARTY_NAMES.get(party, party), "votes": votes})

    expected_keys = {
        (state, 0 if seats == 1 else number)
        for state, seats in STATE_SEATS.items()
        for number in ([0] if seats == 1 else range(1, seats + 1))
    }
    if set(candidates) != expected_keys:
        raise SystemExit(f"Expected {EXPECTED_SEATS} House districts, found {len(candidates)}")

    seats: dict[tuple[str, int], dict[str, object]] = {}
    for key in sorted(candidates):
        state, number = key
        result = candidates[key]
        names = Counter(str(candidate["name"]) for candidate in result)
        for candidate in result:
            if names[str(candidate["name"])] > 1:
                candidate["name"] = f"{candidate['name']} ({candidate['party']})"
        result.sort(key=lambda candidate: (-int(candidate["votes"]), str(candidate["name"])))
        formal = sum(int(candidate["votes"]) for candidate in result)
        informal = invalid_votes[key]
        total = formal + informal
        official_total = official_totals.get(key, 0)
        if key == ("Maine", 2):
            if official_total != formal * 2 + informal:
                raise SystemExit("Maine 2nd: continuing-ballot subtotal did not reconcile")
        elif official_total != total:
            raise SystemExit(f"{district_name(*key)}: parsed {total:,} votes but recap reports {official_total:,}")
        winner = result[0]
        contest_status = "uncontested" if len(result) == 1 else "official"
        seats[key] = {
            "district": district_name(state, number), "state": state,
            "winner": winner["name"], "party": winner["party"], "candidates": result,
            "formal": formal, "informal": informal, "total": total,
            "contest_status": contest_status,
        }

    if sum(len(seat["candidates"]) for seat in seats.values()) != EXPECTED_CANDIDATES:
        raise SystemExit("Unexpected candidate-row count after parsing Clerk publication")
    winners = Counter(str(seat["party"]) for seat in seats.values())
    if winners != Counter({"Republican": 220, "Democratic": 215}):
        raise SystemExit(f"Unexpected House result: {winners}")
    return seats


def build_boundaries(path: Path, seats: dict[tuple[str, int], dict[str, object]]) -> tuple[dict[str, object], dict[tuple[str, int], str]]:
    source = gpd.read_file(f"zip://{path.resolve()}").to_crs(epsg=4326)
    source = source[source["STATEFP"].isin(STATE_FIPS)]
    features = []
    codes: dict[tuple[str, int], str] = {}
    for _, row in source.sort_values("GEOID").iterrows():
        state = STATE_FIPS[str(row["STATEFP"])]
        number = int(row["CD119FP"])
        key = (state, number)
        if key not in seats:
            raise SystemExit(f"Census boundary has no matching result: {key}")
        geometry = row.geometry.simplify(0.005, preserve_topology=True)
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"{district_name(*key)}: invalid simplified Census geometry")
        display_geometry = mapping(geometry)
        if state == "Alaska":
            display_geometry["coordinates"] = unwrap_antimeridian_coordinates(display_geometry["coordinates"])
            unwrapped = shape(display_geometry)
            if unwrapped.is_empty or not unwrapped.is_valid:
                raise SystemExit("Alaska at-large: invalid antimeridian-unwrapped geometry")
        code = str(row["GEOID"])
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
    return {"type": "FeatureCollection", "name": "us_2024_119th_congressional_districts", "features": features}, codes


def build_rows(seats: dict[tuple[str, int], dict[str, object]], codes: dict[tuple[str, int], str]) -> list[dict[str, object]]:
    rows = []
    for key, seat in sorted(seats.items(), key=lambda item: str(item[1]["district"])):
        base = {
            "district": seat["district"], "district_url": RESULTS_PAGE,
            "distribution_url": RESULTS_PAGE, "elected_member": seat["winner"],
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
    parser = argparse.ArgumentParser(description="Build official 2024 U.S. House election data")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/us_2024"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; election-preference-explorer/0.1)"})
    results_path = args.raw_dir / "statistics2024.pdf"
    boundaries_path = args.raw_dir / "cb_2024_us_cd119_5m.zip"
    download(session, RESULTS_URL, results_path, args.refresh)
    download(session, BOUNDARY_URL, boundaries_path, args.refresh)

    seats = parse_results(results_path)
    boundaries, codes = build_boundaries(boundaries_path, seats)
    rows = build_rows(seats, codes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "us_2024_house_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    boundary_path = args.out_dir / "us_2024_congressional_boundaries.geojson"
    boundary_path.write_text(json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {csv_path} ({len(rows):,} rows, {EXPECTED_SEATS} districts)")
    print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
