#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

from build_nsw_state import LONG_FIELDS, SUMMARY_FIELDS, write_csv


UA = "Mozilla/5.0 (compatible; australian-election-preference-explorer/0.1; +https://github.com/)"
DISTRICTS = [
    "Arafura", "Araluen", "Arnhem", "Barkly", "Blain", "Braitling", "Brennan", "Casuarina",
    "Daly", "Drysdale", "Fannie Bay", "Fong Lim", "Goyder", "Gwoja", "Johnston", "Karama",
    "Katherine", "Mulka", "Namatjira", "Nelson", "Nightcliff", "Port Darwin", "Sanderson",
    "Spillett", "Wanguri",
]
ELECTIONS = {
    2024: {
        "base_url": "https://ntec.nt.gov.au/elections/past-elections/legislative-assembly/2024-territory-election/results",
        "boundary_url": "https://geo.abs.gov.au/arcgis/rest/services/ASGS2024/SED/FeatureServer/0/query?where=state_code_2021%3D%277%27&outFields=sed_code_2024%2Csed_name_2024%2Cstate_code_2021&returnGeometry=true&outSR=4326&f=geojson",
        "boundary_name_field": "sed_name_2024",
    },
    2020: {
        "base_url": "https://ntec.nt.gov.au/elections/past-elections/legislative-assembly/2020-territory-election/results",
        "boundary_url": "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SED/FeatureServer/0/query?where=state_code_2021%3D%277%27&outFields=sed_code_2021%2Csed_name_2021%2Cstate_code_2021&returnGeometry=true&outSR=4326&f=geojson",
        "boundary_name_field": "sed_name_2021",
    },
}
PARTIES = {
    "AJP": "Animal Justice Party",
    "ALP": "Australian Labor Party NT Branch",
    "BFFCPW": "Ban Fracking Fix Crime Protect Water",
    "CLP": "Country Liberal Party of the Northern Territory",
    "FP": "Federation Party Northern Territory",
    "GRN": "NT Greens",
    "IND": "Independent",
    "TA": "Territory Alliance",
}


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_int(value: object) -> int:
    text = clean_text(value)
    match = re.search(r"-?\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else 0


def normalize_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def party_name(code: str) -> str:
    return PARTIES.get(code.upper(), code or "Independent")


def slug(district: str) -> str:
    return district.lower().replace(" ", "-")


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    return session


def download(session: requests.Session, url: str, path: Path, refresh: bool = False) -> None:
    if path.exists() and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            time.sleep(0.25 * (attempt + 1))
            response = session.get(url, timeout=60)
            response.raise_for_status()
            path.write_bytes(response.content)
            return
        except requests.RequestException as exc:
            last_error = exc
    raise SystemExit(f"Failed to download {url} after 4 attempts: {last_error}")


def parse_pipe_summary(section: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    candidates: list[dict[str, object]] = []
    totals: dict[str, int] = {}
    for line in section.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [clean_text(cell) for cell in line.strip().strip("|").split("|")]
        party_code = cells[1] if len(cells) > 1 else ""
        if (
            len(cells) >= 5
            and cells[0] not in {"Candidate", "---"}
            and (party_code.upper() in PARTIES or party_code.lower() == "ind")
        ):
            candidates.append({
                "candidate": cells[0],
                "party": party_name("IND" if party_code.lower() == "ind" else party_code.upper()),
                "primary": clean_int(cells[2]),
                "tcp": clean_int(cells[3]),
            })
        if len(cells) >= 2 and cells[0] in {"Formal", "Informal", "Total counted", "Enrolment"}:
            totals[cells[0]] = clean_int(cells[1])
    return candidates, totals


def parse_flat_summary(section: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    candidates: list[dict[str, object]] = []
    totals: dict[str, int] = {}
    party_codes = "|".join(sorted([*PARTIES, "Ind"], key=len, reverse=True))
    candidate_pattern = re.compile(
        rf"^(.+?)\s+({party_codes})\s+([\d,]+)(?:\s+([\d,]+)\s+\d+(?:\.\d+)?%)?$",
        flags=re.I,
    )
    for raw_line in section.splitlines():
        line = clean_text(raw_line)
        match = candidate_pattern.match(line)
        if match:
            candidate, code, primary, tcp = match.groups()
            candidates.append({
                "candidate": candidate,
                "party": party_name("IND" if code.lower() == "ind" else code.upper()),
                "primary": clean_int(primary),
                "tcp": clean_int(tcp),
            })
            continue
        total_match = re.match(r"^(Formal|Informal|Total counted)\s+([\d,]+)", line)
        if total_match:
            totals[total_match.group(1)] = clean_int(total_match.group(2))
    return candidates, totals


def parse_final_progressive(markdown: str) -> dict[str, int]:
    distribution_match = re.search(
        r"### Distribution of preferences(.*?)### Electorate summary",
        markdown,
        flags=re.S,
    )
    if not distribution_match:
        return {}

    header: list[str] = []
    final_progressive: list[str] = []
    for line in distribution_match.group(1).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [clean_text(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[:2] == ["Count", "Comments"]:
            header = cells
        elif len(cells) >= 6 and cells[1] == "Progressive":
            final_progressive = cells

    if not header or len(final_progressive) != len(header):
        return {}
    candidate_names = [re.sub(r"\s+\([^)]*\)$", "", value) for value in header[2:-2]]
    return {
        normalize_key(candidate): clean_int(value)
        for candidate, value in zip(candidate_names, final_progressive[2:-2])
    }


def parse_district(path: Path, district: str, source_url: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    markdown = path.read_text(encoding="utf-8")
    summary_match = re.search(r"### Electorate summary(.*?)### First preferences by voting centre", markdown, flags=re.S)
    if not summary_match:
        raise SystemExit(f"{district}: missing electorate summary")
    section = summary_match.group(1)
    if "| Candidate | Party | Primary" in section:
        candidates, totals = parse_pipe_summary(section)
    else:
        candidates, totals = parse_flat_summary(section)
    if len(candidates) < 2:
        raise SystemExit(f"{district}: expected at least two candidates, found {len(candidates)}")

    enrolment_match = re.search(r"Enrolment:?\s*([\d,]+)", section)
    enrolment = totals.get("Enrolment")
    if not enrolment and enrolment_match:
        enrolment = clean_int(enrolment_match.group(1))
    if not enrolment:
        raise SystemExit(f"{district}: missing enrolment")
    formal_votes = totals.get("Formal", sum(int(row["primary"]) for row in candidates))
    informal_votes = totals.get("Informal", 0)
    total_votes = totals.get("Total counted", formal_votes + informal_votes)
    if formal_votes != sum(int(row["primary"]) for row in candidates):
        raise SystemExit(f"{district}: primary votes do not equal formal votes")
    if total_votes != formal_votes + informal_votes:
        raise SystemExit(f"{district}: total votes do not equal formal plus informal")

    tcp_rows = [row for row in candidates if int(row["tcp"])]
    if len(tcp_rows) >= 2:
        final_rows = tcp_rows
        for row in final_rows:
            row["final"] = int(row["tcp"])
        if sum(int(row["final"]) for row in final_rows) != formal_votes:
            final_progressive = parse_final_progressive(markdown)
            if not final_progressive:
                raise SystemExit(f"{district}: mismatched TCP total and missing final progressive distribution")
            for row in candidates:
                row["final"] = final_progressive.get(normalize_key(row["candidate"]), 0)
            final_rows = [row for row in candidates if int(row["final"])]
    else:
        final_rows = candidates
        for row in final_rows:
            row["final"] = int(row["primary"])
    if len(final_rows) < 2 or sum(int(row["final"]) for row in final_rows) != formal_votes:
        raise SystemExit(f"{district}: final votes do not equal formal votes")
    final_rows = sorted(final_rows, key=lambda row: (-int(row["final"]), str(row["candidate"])))
    winner = final_rows[0]
    runner_up = final_rows[1]
    winner_final = int(winner["final"])
    runner_up_final = int(runner_up["final"])
    first_sorted = sorted(candidates, key=lambda row: (-int(row["primary"]), str(row["candidate"])))
    primary_leader = first_sorted[0]
    base = {
        "district": district,
        "district_url": source_url,
        "distribution_url": source_url,
        "elected_member": winner["candidate"],
        "elected_party": winner["party"],
        "enrolment": enrolment,
        "formal_votes": formal_votes,
        "informal_votes": informal_votes,
        "total_votes": total_votes,
        "turnout_pct": round(total_votes / enrolment * 100, 2),
        "majority": formal_votes // 2 + 1,
    }
    long_rows = [{
        **base,
        "round_number": 0,
        "row_type": "first",
        "excluded_candidate": "",
        "excluded_party": "",
        "candidate": row["candidate"],
        "candidate_party": row["party"],
        "votes": row["primary"],
    } for row in first_sorted]
    long_rows.extend({
        **base,
        "round_number": 1,
        "row_type": "final",
        "excluded_candidate": "",
        "excluded_party": "",
        "candidate": row["candidate"],
        "candidate_party": row["party"],
        "votes": row["final"],
    } for row in final_rows)
    winner_first = next(int(row["primary"]) for row in candidates if row["candidate"] == winner["candidate"])
    summary = {
        **base,
        "primary_leader": primary_leader["candidate"],
        "primary_leader_party": primary_leader["party"],
        "primary_leader_votes": primary_leader["primary"],
        "winner": winner["candidate"],
        "winner_party": winner["party"],
        "winner_final_votes": winner_final,
        "runner_up": runner_up["candidate"],
        "runner_up_party": runner_up["party"],
        "runner_up_final_votes": runner_up_final,
        "final_margin": winner_final - runner_up_final,
        "preference_changed_result": str(primary_leader["candidate"] != winner["candidate"]),
        "winner_transfer_gain": winner_final - winner_first,
    }
    return long_rows, summary


def write_boundaries(source_path: Path, out_path: Path, year: int) -> None:
    config = ELECTIONS[year]
    geojson = json.loads(source_path.read_text(encoding="utf-8"))
    district_by_key = {normalize_key(district): district for district in DISTRICTS}
    features = []
    for feature in geojson.get("features", []):
        source_name = clean_text(feature.get("properties", {}).get(config["boundary_name_field"]))
        source_name = re.sub(r"\s+\([^)]*\)$", "", source_name)
        district = district_by_key.get(normalize_key(source_name))
        if not district:
            continue
        feature["properties"] = {"district": district, "source_district": source_name}
        features.append(feature)
    found = {feature["properties"]["district"] for feature in features}
    if found != set(DISTRICTS) or len(features) != len(DISTRICTS):
        raise SystemExit(f"NT {year} boundary mismatch: {sorted(found ^ set(DISTRICTS))}")
    out_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "name": f"nt_{year}_legislative_assembly_divisions",
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
    raw_dir = args.raw_dir or Path(f"tmp/nt_{year}")
    session = make_session()
    long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for district in DISTRICTS:
        source_url = f"{config['base_url']}/{slug(district)}"
        mirror_url = f"https://r.jina.ai/{source_url}"
        path = raw_dir / "districts" / f"{slug(district)}.md"
        download(session, mirror_url, path, args.refresh)
        district_rows, summary = parse_district(path, district, source_url)
        long_rows.extend(district_rows)
        summary_rows.append(summary)

    boundary_source = raw_dir / "boundaries_source.geojson"
    download(session, config["boundary_url"], boundary_source, args.refresh)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    preferences_out = args.out_dir / f"nt_{year}_preferences_long.csv"
    summary_out = args.out_dir / f"nt_{year}_district_summary.csv"
    boundaries_out = args.out_dir / f"nt_{year}_district_boundaries.geojson"
    write_csv(preferences_out, long_rows, LONG_FIELDS)
    write_csv(summary_out, summary_rows, SUMMARY_FIELDS)
    write_boundaries(boundary_source, boundaries_out, year)
    print(f"Wrote {preferences_out} ({len(long_rows)} rows)")
    print(f"Wrote {summary_out} ({len(summary_rows)} rows)")
    print(f"Wrote {boundaries_out}")


if __name__ == "__main__":
    main()
