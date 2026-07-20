#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from shapely.geometry import mapping, shape


ELECTIONS = {
    2025: {"boundary_id": "d_7ddf956dfc1c59080bf95bba1c58a5d2", "divisions": 33, "statements": 32, "mps": 97, "results_page": "finalresults2025.html"},
    2020: {"boundary_id": "d_6077aa5ab73d447b32f451ea224221b6", "divisions": 31, "statements": 31, "mps": 93, "results_page": "finalresults2020.html"},
    2015: {"boundary_id": "d_1dea85025d48bc75ed566eb2696b7e0f", "divisions": 29, "statements": 29, "mps": 89, "results_page": "elections_past_parliamentary2015.html"},
}
UA = "Mozilla/5.0 (compatible; election-preference-explorer/0.1; +https://github.com/)"

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_members",
    "elected_party", "members_to_elect", "enrolment", "formal_votes", "informal_votes",
    "total_votes", "turnout_pct", "majority", "round_number", "row_type",
    "excluded_candidate", "excluded_party", "candidate", "candidate_members", "candidate_party", "votes",
    "electorate_type", "contest_status",
]


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def normalise_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()


def parse_results(path: Path, expected_divisions: int) -> list[dict[str, object]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    contests = []
    for heading in soup.find_all("h3"):
        district = heading.get_text(" ", strip=True).title()
        electors_text = heading.find_next("b").get_text(" ", strip=True)
        enrolment_match = re.search(r"([\d,]+)", electors_text)
        if not enrolment_match:
            raise SystemExit(f"{district}: could not parse electors")
        teams = []
        for row in heading.find_next("table").find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) != 3:
                continue
            members = list(cells[0].stripped_strings)
            party = cells[1].get_text(" ", strip=True)
            party = "Independent" if party == "-" else party
            vote_text = cells[2].get_text(" ", strip=True)
            uncontested = "uncontested" in vote_text.lower()
            vote_match = re.search(r"[\d,]+", vote_text)
            votes = int(vote_match.group().replace(",", "")) if vote_match and not uncontested else 0
            teams.append({
                "members": members,
                "party": party,
                "votes": votes,
                "winner": "resultBold" in (row.get("class") or []) or uncontested,
            })
        winners = [team for team in teams if team["winner"]]
        if len(winners) != 1:
            raise SystemExit(f"{district}: expected one winning team, found {len(winners)}")
        contests.append({
            "district": district,
            "enrolment": int(enrolment_match.group(1).replace(",", "")),
            "teams": teams,
            "uncontested": len(teams) == 1 and teams[0]["winner"],
        })
    if len(contests) != expected_divisions:
        raise SystemExit(f"Expected {expected_divisions} electoral divisions, found {len(contests)}")
    return contests


def statement_links(gazette_path: Path, gazette_url: str, expected_statements: int) -> list[str]:
    soup = BeautifulSoup(gazette_path.read_text(encoding="utf-8"), "html.parser")
    links = []
    for anchor in soup.find_all("a", href=True):
        if "Statement of Poll for the Electoral Division" in anchor.get_text(" ", strip=True):
            links.append(urljoin(gazette_url, anchor["href"]))
    if len(links) != expected_statements:
        raise SystemExit(f"Expected {expected_statements} contested-division statements, found {len(links)}")
    return links


def extract_number(text: str, label: str, pattern: str) -> int:
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        raise SystemExit(f"Could not parse {label} from Statement of Poll")
    return int(match.group(1).replace(",", ""))


def parse_statement(path: Path) -> tuple[str, dict[str, int]]:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    # Older Gazette PDFs split some capital letters during text extraction
    # (for example, "PAYOH" becomes "P A YOH"). Their official filenames
    # preserve the electoral-division names without that PDF kerning artefact.
    name_match = re.search(r"Electoral Division of (.+?)\.pdf", path.name, re.I)
    if not name_match:
        name_match = re.search(r"ELECTORAL DIVISION OF\s+([^\n]+)", text, re.I)
    if not name_match:
        raise SystemExit(f"{path}: could not parse electoral division")
    district = re.sub(r"\s+", " ", name_match.group(1)).strip().title()
    return district, {
        "enrolment": extract_number(text, "electors", r"electors.*?used at the Poll\s+([\d,]+)"),
        "total_votes": extract_number(
            text, "votes cast",
            r"(?:a\.\s*Number of votes cast\d*|T\s*otal Number of Ballot Papers found in the ballot boxes)\s+([\d,]+)",
        ),
        "informal_votes": extract_number(
            text, "rejected ballots",
            r"Number of (?:\*?Rejected Ballot Papers|rejected ballot papers and postal ballot papers)\s+([\d,]+)",
        ),
    }


def team_label(team: dict[str, object]) -> str:
    members = team["members"]
    return str(members[0]) if len(members) == 1 else f"{team['party']} team"


def build_rows(
    contests: list[dict[str, object]], polls: dict[str, dict[str, int]],
    results_url: str, gazette_url: str,
) -> list[dict[str, object]]:
    output = []
    for contest in contests:
        district = str(contest["district"])
        teams = list(contest["teams"])
        winner = next(team for team in teams if team["winner"])
        members_to_elect = len(winner["members"])
        formal = sum(int(team["votes"]) for team in teams)
        if contest["uncontested"]:
            poll = {"enrolment": int(contest["enrolment"]), "total_votes": 0, "informal_votes": 0}
        else:
            poll = polls.get(normalise_name(district))
            if not poll:
                raise SystemExit(f"{district}: missing Statement of Poll")
            if poll["enrolment"] != contest["enrolment"]:
                raise SystemExit(f"{district}: electors disagree between official sources")
            if poll["total_votes"] != formal + poll["informal_votes"]:
                raise SystemExit(f"{district}: valid and rejected votes do not equal votes cast")
        sorted_teams = sorted(teams, key=lambda team: (-int(team["votes"]), team_label(team)))
        if not contest["uncontested"] and sorted_teams[0] is not winner:
            raise SystemExit(f"{district}: marked winner does not have the most votes")
        base = {
            "district": district,
            "district_url": results_url,
            "distribution_url": gazette_url,
            "elected_member": team_label(winner),
            "elected_members": ";".join(winner["members"]),
            "elected_party": winner["party"],
            "members_to_elect": members_to_elect,
            "enrolment": poll["enrolment"],
            "formal_votes": formal,
            "informal_votes": poll["informal_votes"],
            "total_votes": poll["total_votes"],
            "turnout_pct": round(poll["total_votes"] / poll["enrolment"] * 100, 2) if poll["enrolment"] else 0,
            "majority": formal // 2 + 1 if formal else 0,
            "electorate_type": "GRC" if members_to_elect > 1 else "SMC",
            "contest_status": "uncontested" if contest["uncontested"] else "official",
        }
        output.extend({
            **base, "round_number": 0, "row_type": "first",
            "excluded_candidate": "", "excluded_party": "", "candidate": team_label(team),
            "candidate_members": ";".join(team["members"]),
            "candidate_party": team["party"], "votes": team["votes"],
        } for team in sorted_teams)
    return output


def boundary_download(session: requests.Session, dataset_id: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    api_url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
    response = session.get(api_url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    url = payload.get("data", {}).get("url")
    if not url:
        raise SystemExit("data.gov.sg did not return a boundary download URL")
    download(session, url, path, True)


def build_boundaries(source: dict[str, object], contests: list[dict[str, object]], year: int) -> dict[str, object]:
    names = {normalise_name(str(contest["district"])): str(contest["district"]) for contest in contests}
    features = []
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        raw_name = str(properties.get("ED_DESC") or properties.get("ED_DESC_FU") or "").strip()
        district = names.get(normalise_name(raw_name))
        if not district:
            raise SystemExit(f"Boundary has no matching result: {raw_name}")
        geometry = mapping(shape(feature["geometry"]).simplify(0.00005, preserve_topology=True))
        contest = next(contest for contest in contests if contest["district"] == district)
        member_count = len(next(team for team in contest["teams"] if team["winner"])["members"])
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "electorate_type": "GRC" if member_count > 1 else "SMC",
            },
            "geometry": geometry,
        })
    if len(features) != len(contests) or {feature["properties"]["district"] for feature in features} != set(names.values()):
        raise SystemExit(f"Expected {len(contests)} unique boundaries matching all electoral divisions")
    return {"type": "FeatureCollection", "name": f"singapore_{year}_electoral_divisions", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Singapore General Election data")
    parser.add_argument("--year", type=int, choices=sorted(ELECTIONS), default=2025)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    config = ELECTIONS[args.year]
    raw_dir = args.raw_dir or Path(f"tmp/singapore_{args.year}")
    results_url = f"https://www.eld.gov.sg/{config['results_page']}"
    gazette_url = f"https://www.eld.gov.sg/gazette_{args.year}.html"

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    results_path = raw_dir / "final-results.html"
    gazette_path = raw_dir / "gazette.html"
    boundaries_path = raw_dir / "boundaries.geojson"
    download(session, results_url, results_path, args.refresh)
    download(session, gazette_url, gazette_path, args.refresh)
    boundary_download(session, config["boundary_id"], boundaries_path, args.refresh)

    polls = {}
    for url in statement_links(gazette_path, gazette_url, config["statements"]):
        pdf_path = raw_dir / "statements" / url.rsplit("/", 1)[-1]
        download(session, url, pdf_path, args.refresh)
        district, values = parse_statement(pdf_path)
        polls[normalise_name(district)] = values
    if len(polls) != config["statements"]:
        raise SystemExit(f"Expected {config['statements']} parsed Statements of Poll, found {len(polls)}")

    contests = parse_results(results_path, config["divisions"])
    rows = build_rows(contests, polls, results_url, gazette_url)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / f"singapore_{args.year}_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    boundaries = build_boundaries(json.loads(boundaries_path.read_text(encoding="utf-8")), contests, args.year)
    output_boundaries = args.out_dir / f"singapore_{args.year}_electoral_boundaries.geojson"
    output_boundaries.write_text(json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    elected = Counter()
    for contest in contests:
        winner = next(team for team in contest["teams"] if team["winner"])
        elected[str(winner["party"])] += len(winner["members"])
    print(f"Wrote {csv_path} ({len(rows)} rows, {config['divisions']} electoral divisions, {config['mps']} elected MPs)")
    print(f"Wrote {output_boundaries} ({len(boundaries['features'])} features); elected parties {dict(elected)}")


if __name__ == "__main__":
    main()
