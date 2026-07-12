#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import zipfile
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from build_nsw_state import LONG_FIELDS, SUMMARY_FIELDS, write_csv


UA = "Mozilla/5.0 (compatible; australian-election-preference-explorer/0.1; +https://github.com/)"

ELECTIONS = {
    2018: {
        "result_page": "https://ecsa.sa.gov.au/html/results/2018/House_of_Assembly.html",
        "district_url_template": "https://ecsa.sa.gov.au/html/results/2018/{district}.html",
        "boundaries_url": "https://lsa4.geohub.sa.gov.au/server/rest/services/LSA/LocationSAViewerV34/MapServer/225/query?where=1%3D1&outFields=electorate&returnGeometry=true&outSR=4326&f=geojson",
        "expected_districts": 47,
        "source_format": "html",
        "districts": "Adelaide Badcoe Black Bragg Chaffey Cheltenham Colton Croydon Davenport Dunstan Elder Elizabeth Enfield Finniss Flinders Florey Frome Gibson Giles Hammond Hartley Heysen Hurtle_Vale Kaurna Kavel King Lee Light MacKillop Mawson Morialta Morphett Mount_Gambier Narungga Newland Playford Port_Adelaide Ramsay Reynell Schubert Stuart Taylor Torrens Unley Waite West_Torrens Wright".split(),
    },
    2022: {
        "result_page": "https://www.ecsa.sa.gov.au/elections/past-state-election-results",
        "first_preferences_url": "https://www.ecsa.sa.gov.au/component/edocman/244-2022se-house-of-assembly-first-preference-results-by-district-and-polling-place/download?Itemid=0",
        "distribution_url": "https://www.ecsa.sa.gov.au/component/edocman/244-2022se-ha-final-distribution/download?Itemid=0",
        "boundaries_url": "https://www.dptiapps.com.au/dataportal/StateElectorates2022_geojson.zip",
        "expected_districts": 47,
        "source_format": "csv",
    },
}

PARTIES = {
    "ALP": "Australian Labor Party",
    "LIB": "Liberal Party",
    "GRN": "The Greens",
    "NP": "The Nationals",
    "NAT": "The Nationals",
    "AJP": "Animal Justice Party",
    "AFP": "Australian Family Party",
    "RCH": "Real Change SA",
    "IND": "Independent",
    "SA-BEST": "SA-Best",
    "SAB": "SA-Best",
    "UAP": "United Australia Party",
    "ON": "Pauline Hanson's One Nation",
    "ONP": "Pauline Hanson's One Nation",
    "PHON": "Pauline Hanson's One Nation",
    "FFP": "Family First Party",
    "LDP": "Liberal Democratic Party",
    "AC": "Australian Conservatives",
    "DIG": "Dignity Party",
    "DPA": "Danig Party of Australia",
    "SPGN": "Stop Population Growth Now",
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip().strip("\ufeff")


def clean_int(value: object) -> int:
    text = clean_text(value)
    if not text:
        return 0
    match = re.search(r"-?\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else 0


def normalize_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def title_district(value: object) -> str:
    text = clean_text(value).title()
    return text.replace("Mackillop", "MacKillop")


def party_name(code: object) -> str:
    text = clean_text(code).strip("()")
    return PARTIES.get(text.upper(), text or "Independent")


def format_candidate(header: object) -> tuple[str, str]:
    text = clean_text(header)
    match = re.match(r"(.+?)\s+\(([^)]+)\)$", text)
    candidate = match.group(1) if match else text
    party = party_name(match.group(2) if match else "")
    return candidate, party


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


def zip_member(zip_path: Path, suffix: str) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        matches = [name for name in zf.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise SystemExit(f"{zip_path}: expected one member ending {suffix!r}, found {len(matches)}")
    return matches[0]


def read_csv_from_zip(zip_path: Path, suffix: str) -> pd.DataFrame:
    member = zip_member(zip_path, suffix)
    with zipfile.ZipFile(zip_path) as zf:
        text = zf.read(member).decode("utf-8-sig")
    return pd.read_csv(StringIO(text), header=None, dtype=str, keep_default_na=False)


def parse_first_preferences(first_zip: Path, district: str) -> tuple[dict[str, object], list[dict[str, object]], dict[str, str]]:
    df = read_csv_from_zip(first_zip, f"CSV/{district}.csv")
    polling_row = next(
        index
        for index, row in df.iterrows()
        if clean_text(row.iloc[0]) in {"Polling Place", "Polling Location"}
    )
    header_row = polling_row - 1
    total_row = df[df.iloc[:, 0].map(clean_text) == "District Total"].iloc[0]
    enrolment = 0
    for _, row in df.iterrows():
        values = [clean_text(value) for value in row.tolist()]
        if "No. enrolled" in values:
            start = values.index("No. enrolled") + 1
            enrolment = next((clean_int(value) for value in values[start:] if clean_int(value)), 0)
            break

    meta = {
        "enrolment": enrolment,
        "formal_votes": clean_int(total_row.iloc[-5]),
        "informal_votes": clean_int(total_row.iloc[-3]),
        "total_votes": clean_int(total_row.iloc[-1]),
    }
    meta["turnout_pct"] = round(meta["total_votes"] / meta["enrolment"] * 100, 2) if meta["enrolment"] else ""
    meta["majority"] = meta["formal_votes"] // 2 + 1 if meta["formal_votes"] else ""

    first_rows: list[dict[str, object]] = []
    party_by_candidate: dict[str, str] = {}
    col = 1
    while col < len(df.columns):
        header = clean_text(df.iat[header_row, col])
        if not header or header == "Formal Votes":
            break
        candidate, party = format_candidate(header)
        votes = clean_int(total_row.iloc[col])
        first_rows.append({"candidate": candidate, "candidate_party": party, "votes": votes})
        party_by_candidate[candidate] = party
        col += 2
    first_rows.sort(key=lambda row: (-int(row["votes"]), str(row["candidate"])))
    return meta, first_rows, party_by_candidate


def read_distribution_csv(distribution_zip: Path, district: str) -> pd.DataFrame:
    district_key = normalize_key(district)
    with zipfile.ZipFile(distribution_zip) as zf:
        matches = []
        for name in zf.namelist():
            if not name.endswith(".csv") or "Final distribution csv/" not in name:
                continue
            stem = Path(name).stem
            match = re.match(r"2022SE\s+(.+?)\s*final distribution", stem, flags=re.I)
            if not match:
                continue
            if normalize_key(match.group(1)) == district_key:
                matches.append(name)
        if len(matches) != 1:
            raise SystemExit(f"{distribution_zip}: expected one distribution CSV for {district}, found {len(matches)}")
        text = zf.read(matches[0]).decode("utf-8-sig")
    return pd.read_csv(StringIO(text), header=None, dtype=str, keep_default_na=False)


def candidate_lookup(first_rows: list[dict[str, object]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in first_rows:
        candidate = str(row["candidate"])
        surname = candidate.split(",", 1)[0]
        lookup[normalize_key(surname)] = candidate
    return lookup


def parse_distribution(
    distribution_zip: Path,
    district: str,
    first_rows: list[dict[str, object]],
    party_by_candidate: dict[str, str],
) -> tuple[list[dict[str, object]], dict[str, int], str]:
    df = read_distribution_csv(distribution_zip, district)
    affiliation_row = df[df.iloc[:, 1].map(clean_text) == "Votes transferred"].index[0]
    header_row = affiliation_row - 1
    lookup = candidate_lookup(first_rows)

    col_candidates: dict[int, str] = {}
    for col in range(2, len(df.columns) - 1):
        header = clean_text(df.iat[header_row, col])
        if not header or header.upper() == "TOTAL FORMAL VOTES":
            continue
        candidate = lookup.get(normalize_key(header))
        if not candidate:
            candidate = header.title()
        party_by_candidate.setdefault(candidate, party_name(df.iat[affiliation_row, col]))
        col_candidates[col] = candidate

    rows: list[dict[str, object]] = []
    final_votes: dict[str, int] = {}
    elected_candidate = ""
    last_transfer_round = 0
    pending_round = 0
    pending_excluded = ""
    pending_excluded_party = ""

    for index in range(affiliation_row + 1, len(df)):
        label = clean_text(df.iat[index, 0])
        if not label:
            continue
        if label.endswith("preference votes"):
            continue
        if "excluded candidate" in label:
            pending_round = clean_int(label)
            last_transfer_round = max(last_transfer_round, pending_round)
            excluded_label = re.sub(r"^\d+(?:st|nd|rd|th)\s+excluded candidate\s+", "", label, flags=re.I)
            pending_excluded = lookup.get(normalize_key(excluded_label), excluded_label.title())
            pending_excluded_party = party_by_candidate.get(pending_excluded, "Independent")
            for col, candidate in col_candidates.items():
                value = clean_text(df.iat[index, col])
                votes = clean_int(value)
                if value and value.lower() != "excluded" and votes >= 0:
                    rows.append({
                        "round_number": pending_round,
                        "row_type": "transfer",
                        "excluded_candidate": pending_excluded,
                        "excluded_party": pending_excluded_party,
                        "candidate": candidate,
                        "candidate_party": party_by_candidate.get(candidate, "Independent"),
                        "votes": votes,
                    })
        elif label == "Progressive Total":
            for col, candidate in col_candidates.items():
                value = clean_text(df.iat[index, col])
                if value and value.lower() != "excluded":
                    rows.append({
                        "round_number": pending_round,
                        "row_type": "progressive",
                        "excluded_candidate": pending_excluded,
                        "excluded_party": pending_excluded_party,
                        "candidate": candidate,
                        "candidate_party": party_by_candidate.get(candidate, "Independent"),
                        "votes": clean_int(value),
                    })
        elif label == "FINAL DISTRICT TOTALS":
            for col, candidate in col_candidates.items():
                value = clean_text(df.iat[index, col])
                if value and value.lower() != "excluded":
                    final_votes[candidate] = clean_int(value)
        elif label == "ELECTION RESULT":
            for col, candidate in col_candidates.items():
                if clean_text(df.iat[index, col]).upper() == "ELECTED":
                    elected_candidate = candidate

    if not final_votes:
        raise SystemExit(f"{district}: missing final distribution totals")
    if not elected_candidate:
        elected_candidate = max(final_votes.items(), key=lambda item: item[1])[0]
    for candidate, votes in sorted(final_votes.items(), key=lambda item: (-item[1], item[0])):
        rows.append({
            "round_number": max(last_transfer_round, 1),
            "row_type": "final",
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": candidate,
            "candidate_party": party_by_candidate.get(candidate, "Independent"),
            "votes": votes,
        })
    return rows, final_votes, elected_candidate


def build_district_rows(
    config: dict[str, object],
    first_zip: Path,
    distribution_zip: Path,
    district: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    meta_values, first_rows, party_by_candidate = parse_first_preferences(first_zip, district)
    distribution_rows, final_votes, elected_member = parse_distribution(distribution_zip, district, first_rows, party_by_candidate)

    final_sorted = sorted(final_votes.items(), key=lambda item: item[1], reverse=True)
    winner = elected_member
    runner_up = next(candidate for candidate, _ in final_sorted if candidate != winner)
    winner_final_votes = final_votes[winner]
    runner_up_final_votes = final_votes[runner_up]
    primary_leader = first_rows[0]
    winner_first_votes = next((int(row["votes"]) for row in first_rows if row["candidate"] == winner), 0)

    base = {
        "district": district,
        "district_url": str(config["result_page"]),
        "distribution_url": str(config["distribution_url"]),
        "elected_member": winner,
        "elected_party": party_by_candidate.get(winner, "Independent"),
        **meta_values,
    }

    long_rows: list[dict[str, object]] = []
    for row in first_rows:
        long_rows.append({
            **base,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })
    for row in distribution_rows:
        long_rows.append({**base, **row})

    summary = {
        **base,
        "primary_leader": primary_leader["candidate"],
        "primary_leader_party": primary_leader["candidate_party"],
        "primary_leader_votes": primary_leader["votes"],
        "winner": winner,
        "winner_party": party_by_candidate.get(winner, "Independent"),
        "winner_final_votes": winner_final_votes,
        "runner_up": runner_up,
        "runner_up_party": party_by_candidate.get(runner_up, "Independent"),
        "runner_up_final_votes": runner_up_final_votes,
        "final_margin": abs(winner_final_votes - runner_up_final_votes),
        "preference_changed_result": str(primary_leader["candidate"] != winner),
        "winner_transfer_gain": winner_final_votes - winner_first_votes,
    }
    return long_rows, summary


def write_boundaries(boundary_zip: Path, out_path: Path, districts: set[str]) -> None:
    with zipfile.ZipFile(boundary_zip) as zf:
        member = next(name for name in zf.namelist() if name.endswith("GDA2020.geojson"))
        geojson = json.loads(zf.read(member))
    district_by_key = {normalize_key(district): district for district in districts}
    features = []
    for feature in geojson.get("features", []):
        source_name = clean_text(feature.get("properties", {}).get("electorate"))
        district = district_by_key.get(normalize_key(source_name), title_district(source_name))
        if district not in districts:
            continue
        feature["properties"] = {
            "district": district,
            "source_electorate": source_name,
        }
        features.append(feature)
    if len(features) != len(districts):
        found = {feature["properties"]["district"] for feature in features}
        raise SystemExit(f"SA boundary mismatch: {sorted(districts - found)}")
    out_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": "sa_2022_state_electoral_districts",
        "features": features,
    }, separators=(",", ":")), encoding="utf-8")


def table_after_heading(soup: BeautifulSoup, heading: str):
    node = next((tag for tag in soup.find_all("h3") if clean_text(tag.get_text()) == heading), None)
    if node is None:
        raise SystemExit(f"Missing {heading!r} table")
    return node.find_next("table")


def parse_2018_district(config: dict[str, object], district: str, html_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
    text = clean_text(soup.get_text(" "))
    enrolment_match = re.search(r"([\d,]+)\s+ELECTORS ENROLLED", text, flags=re.I)
    enrolment = clean_int(enrolment_match.group(1)) if enrolment_match else 0

    first_table = table_after_heading(soup, "First Preference Votes")
    first_rows: list[dict[str, object]] = []
    party_by_candidate: dict[str, str] = {}
    for tr in first_table.select("tbody tr"):
        cells = [clean_text(td.get_text(" ")) for td in tr.find_all("td", recursive=False)]
        if len(cells) < 5:
            continue
        candidate = cells[0]
        party = party_name(cells[1])
        votes = clean_int(cells[-1])
        first_rows.append({"candidate": candidate, "candidate_party": party, "votes": votes})
        party_by_candidate[candidate] = party
    first_rows.sort(key=lambda row: (-int(row["votes"]), str(row["candidate"])))

    footers = first_table.select("tfoot tr")
    totals = {}
    for tr in footers:
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        label = clean_text(cells[0].get_text(" ")).rstrip(":")
        # Some archived ECSA pages wrap individual digits in span tags. Joining
        # fragments without a separator preserves values such as 1,216 and
        # 22,696 instead of parsing them as 12 and 22.
        totals[label] = clean_int(cells[-1].get_text("", strip=True))
    formal_votes = totals.get("Total Formal", sum(int(row["votes"]) for row in first_rows))
    informal_votes = totals.get("Total Informal", 0)
    total_votes = totals.get("Total Ballot Papers", formal_votes + informal_votes)
    if total_votes != formal_votes + informal_votes:
        raise SystemExit(
            f"{district}: total ballot papers {total_votes} != "
            f"formal {formal_votes} + informal {informal_votes}"
        )

    final_table = table_after_heading(soup, "Two Candidate Preferred")
    final_votes: dict[str, int] = {}
    for tr in final_table.select("tbody tr"):
        cells = [clean_text(td.get_text(" ")) for td in tr.find_all("td", recursive=False)]
        if len(cells) < 5:
            continue
        candidate = cells[0]
        party_by_candidate.setdefault(candidate, party_name(cells[1]))
        final_votes[candidate] = clean_int(cells[-1])
    if len(final_votes) != 2:
        raise SystemExit(f"{district}: expected two final candidates, found {len(final_votes)}")

    final_sorted = sorted(final_votes.items(), key=lambda item: (-item[1], item[0]))
    winner, winner_final_votes = final_sorted[0]
    runner_up, runner_up_final_votes = final_sorted[1]
    primary_leader = first_rows[0]
    winner_first_votes = next(int(row["votes"]) for row in first_rows if row["candidate"] == winner)
    district_url = str(config["district_url_template"]).format(district=district.replace(" ", "_"))
    base = {
        "district": district,
        "district_url": district_url,
        "distribution_url": district_url,
        "elected_member": winner,
        "elected_party": party_by_candidate[winner],
        "enrolment": enrolment,
        "formal_votes": formal_votes,
        "informal_votes": informal_votes,
        "total_votes": total_votes,
        "turnout_pct": round(total_votes / enrolment * 100, 2) if enrolment else "",
        "majority": formal_votes // 2 + 1,
    }
    long_rows = [
        {**base, "round_number": 0, "row_type": "first", "excluded_candidate": "", "excluded_party": "", **row}
        for row in first_rows
    ]
    long_rows.extend({
        **base,
        "round_number": 1,
        "row_type": "final",
        "excluded_candidate": "",
        "excluded_party": "",
        "candidate": candidate,
        "candidate_party": party_by_candidate[candidate],
        "votes": votes,
    } for candidate, votes in final_sorted)
    summary = {
        **base,
        "primary_leader": primary_leader["candidate"],
        "primary_leader_party": primary_leader["candidate_party"],
        "primary_leader_votes": primary_leader["votes"],
        "winner": winner,
        "winner_party": party_by_candidate[winner],
        "winner_final_votes": winner_final_votes,
        "runner_up": runner_up,
        "runner_up_party": party_by_candidate[runner_up],
        "runner_up_final_votes": runner_up_final_votes,
        "final_margin": winner_final_votes - runner_up_final_votes,
        "preference_changed_result": str(primary_leader["candidate"] != winner),
        "winner_transfer_gain": winner_final_votes - winner_first_votes,
    }
    return long_rows, summary


def write_2018_boundaries(source_path: Path, out_path: Path, districts: set[str]) -> None:
    geojson = json.loads(source_path.read_text(encoding="utf-8"))
    district_by_key = {normalize_key(district): district for district in districts}
    features = []
    for feature in geojson.get("features", []):
        source_name = clean_text(feature.get("properties", {}).get("electorate"))
        district = district_by_key.get(normalize_key(source_name))
        if not district:
            continue
        feature["properties"] = {"district": district, "source_electorate": source_name}
        features.append(feature)
    if len(features) != len(districts):
        found = {feature["properties"]["district"] for feature in features}
        raise SystemExit(f"SA 2018 boundary mismatch: {sorted(districts - found)}")
    out_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": "sa_2018_state_electoral_districts",
        "features": features,
    }, separators=(",", ":")), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=sorted(ELECTIONS), default=2022)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    config = ELECTIONS[args.year]
    raw_dir = args.raw_dir or Path(f"tmp/sa_{args.year}")
    session = make_session()

    if config["source_format"] == "html":
        summary_path = raw_dir / "House_of_Assembly.html"
        download(session, str(config["result_page"]), summary_path, refresh=args.refresh)
        soup = BeautifulSoup(summary_path.read_text(encoding="utf-8"), "lxml")
        districts = sorted(str(district).replace("_", " ") for district in config["districts"])
        boundary_source = raw_dir / "boundaries.geojson"
        download(session, str(config["boundaries_url"]), boundary_source, refresh=args.refresh)
    else:
        first_zip = raw_dir / "first_preferences.zip"
        distribution_zip = raw_dir / "final_distribution.zip"
        boundary_zip = raw_dir / "boundaries_geojson.zip"
        download(session, str(config["first_preferences_url"]), first_zip, refresh=args.refresh)
        download(session, str(config["distribution_url"]), distribution_zip, refresh=args.refresh)
        download(session, str(config["boundaries_url"]), boundary_zip, refresh=args.refresh)
        with zipfile.ZipFile(first_zip) as zf:
            districts = sorted(
                Path(name).stem
                for name in zf.namelist()
                if "/CSV/" in name and name.endswith(".csv")
            )
    expected = int(config["expected_districts"])
    if len(districts) != expected:
        raise SystemExit(f"Expected {expected} South Australian districts, found {len(districts)}")

    long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for district in districts:
        if config["source_format"] == "html":
            district_slug = district.replace(" ", "_")
            district_path = raw_dir / "districts" / f"{district_slug}.html"
            district_url = str(config["district_url_template"]).format(district=district_slug)
            download(session, district_url, district_path, refresh=args.refresh)
            district_rows, summary = parse_2018_district(config, district, district_path)
        else:
            district_rows, summary = build_district_rows(config, first_zip, distribution_zip, district)
        long_rows.extend(district_rows)
        summary_rows.append(summary)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pref_path = args.out_dir / f"sa_{args.year}_preferences_long.csv"
    summary_path = args.out_dir / f"sa_{args.year}_district_summary.csv"
    boundary_path = args.out_dir / f"sa_{args.year}_district_boundaries.geojson"

    write_csv(pref_path, long_rows, LONG_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    if config["source_format"] == "html":
        write_2018_boundaries(boundary_source, boundary_path, set(districts))
    else:
        write_boundaries(boundary_zip, boundary_path, set(districts))

    print(f"Wrote {pref_path} ({len(long_rows)} rows)")
    print(f"Wrote {summary_path} ({len(summary_rows)} rows)")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
