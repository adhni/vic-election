#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

from build_nsw_state import LONG_FIELDS, SUMMARY_FIELDS, clean_text, write_csv


RESULTS_BASE = "https://results.elections.qld.gov.au"
DATA_BASE = "https://resultsdata.elections.qld.gov.au"
BOUNDARY_SERVICE_URL = (
    "https://spatial-gis.information.qld.gov.au/arcgis/rest/services/"
    "Boundaries/AdminBoundariesFramework/MapServer/139"
)
BOUNDARY_DATASET_URL = "https://www.data.qld.gov.au/dataset/state-electoral-boundaries-2017-queensland"
UA = "Mozilla/5.0 (compatible; vic-election-preference-explorer/0.1; +https://github.com/)"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    return session


def fetch_json(session: requests.Session, url: str, path: Path, refresh: bool = False) -> dict:
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for attempt in range(5):
        response = session.get(url, timeout=120)
        if response.status_code < 400:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response.text, encoding="utf-8")
            return response.json()
        last_error = requests.HTTPError(
            f"{response.status_code} for {url}: {response.text[:200]}",
            response=response,
        )
        if response.status_code not in {403, 429, 500, 502, 503, 504} or attempt == 4:
            raise last_error
        time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise SystemExit(f"Failed to fetch Queensland JSON from {url}")


def normalize_party(value: object) -> str:
    party = clean_text(value)
    return party or "Independent"


def ballot_party_map(electorate: dict) -> dict[str, str]:
    return {
        clean_text(candidate.get("ballotName")): normalize_party(candidate.get("party"))
        for candidate in electorate.get("candidates", [])
        if clean_text(candidate.get("ballotName"))
    }


def candidate_row(candidate: dict, party_by_ballot: dict[str, str]) -> tuple[str, str, int]:
    ballot_name = clean_text(candidate.get("ballotName") or candidate.get("candidateName"))
    party = normalize_party(candidate.get("party")) if clean_text(candidate.get("party")) else party_by_ballot.get(ballot_name, "Independent")
    count = int(candidate.get("count") or candidate.get("preferences") or candidate.get("runningTotal") or 0)
    return ballot_name, party, count


def turnout_pct(enrolment: int | None, total_votes: int | None) -> float | str:
    if not enrolment or not total_votes:
        return ""
    return round(total_votes / enrolment * 100, 2)


def build_district_rows(
    session: requests.Session,
    election_stub: str,
    electorate: dict,
    raw_dir: Path,
    refresh: bool = False,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    district = clean_text(electorate["electorateName"])
    district_stub = clean_text(electorate["stub"])
    district_url = f"{RESULTS_BASE}/{election_stub}/{district_stub}"
    distribution_url = f"{district_url}/preference"
    party_by_ballot = ballot_party_map(electorate)

    primary = fetch_json(
        session,
        f"{DATA_BASE}/{election_stub}-primary-count-district-{district_stub}.json",
        raw_dir / "districts" / f"{district_stub}_primary.json",
        refresh=refresh,
    )
    preference = fetch_json(
        session,
        f"{DATA_BASE}/{election_stub}-preference-count-district-{district_stub}.json",
        raw_dir / "districts" / f"{district_stub}_preference.json",
        refresh=refresh,
    )

    enrolment = int(electorate.get("enrolment") or 0) or None
    formal_votes = int(primary.get("formalVotes") or 0) or None
    informal_votes = int(primary.get("informalVotes") or 0) if primary.get("informalVotes") is not None else None
    total_votes = int(primary.get("totalVotes") or 0) or None
    majority = (formal_votes // 2 + 1) if formal_votes else ""

    first_rows: list[dict[str, object]] = []
    for candidate in primary.get("candidates", []):
        ballot_name, party, count = candidate_row(candidate, party_by_ballot)
        first_rows.append({
            "candidate": ballot_name,
            "candidate_party": party,
            "votes": count,
        })
    first_rows.sort(key=lambda row: (-int(row["votes"]), str(row["candidate"])))

    final_rows: list[dict[str, object]] = []
    for candidate in preference.get("candidates", []):
        ballot_name, party, count = candidate_row(candidate, party_by_ballot)
        final_rows.append({
            "candidate": ballot_name,
            "candidate_party": party,
            "votes": count,
        })
    final_rows.sort(key=lambda row: (-int(row["votes"]), str(row["candidate"])))
    if len(final_rows) < 2:
        raise SystemExit(f"{district}: expected at least 2 final rows from Queensland preference JSON")

    winner = final_rows[0]
    runner_up = final_rows[1]
    winner_first_votes = next((int(row["votes"]) for row in first_rows if row["candidate"] == winner["candidate"]), 0)

    meta = {
        "district": district,
        "district_url": district_url,
        "distribution_url": distribution_url,
        "elected_member": winner["candidate"],
        "elected_party": winner["candidate_party"],
        "enrolment": enrolment or "",
        "formal_votes": formal_votes or "",
        "informal_votes": informal_votes if informal_votes is not None else "",
        "total_votes": total_votes or "",
        "turnout_pct": turnout_pct(enrolment, total_votes),
        "majority": majority,
    }

    long_rows: list[dict[str, object]] = []
    for row in first_rows:
        long_rows.append({
            **meta,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })

    distributions = preference.get("preferenceDistributionDetails", {}).get("distributions", [])
    for distribution in distributions:
        round_number = int(distribution.get("exclusion") or 0)
        excluded_candidate = clean_text(distribution.get("excludedCandidate"))
        excluded_party = normalize_party(distribution.get("excludedCandidateParty"))
        for pref in distribution.get("preferences", []):
            ballot_name = clean_text(pref.get("ballotName"))
            party = normalize_party(pref.get("party")) if clean_text(pref.get("party")) else party_by_ballot.get(ballot_name, "Independent")
            transfer_votes = int(pref.get("preferences") or 0)
            running_total = int(pref.get("runningTotal") or 0)
            long_rows.append({
                **meta,
                "round_number": round_number,
                "row_type": "transfer",
                "excluded_candidate": excluded_candidate,
                "excluded_party": excluded_party,
                "candidate": ballot_name,
                "candidate_party": party,
                "votes": transfer_votes,
            })
            long_rows.append({
                **meta,
                "round_number": round_number,
                "row_type": "progressive",
                "excluded_candidate": excluded_candidate,
                "excluded_party": excluded_party,
                "candidate": ballot_name,
                "candidate_party": party,
                "votes": running_total,
            })

    distribution_rounds = [int(distribution.get("exclusion") or 0) for distribution in distributions]
    final_round = max(
        int(preference.get("countround") or 0),
        max(distribution_rounds, default=0),
        len(distributions),
        1,
    )
    for row in final_rows:
        long_rows.append({
            **meta,
            "round_number": final_round,
            "row_type": "final",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })

    summary_row = {
        **meta,
        "primary_leader": first_rows[0]["candidate"],
        "primary_leader_party": first_rows[0]["candidate_party"],
        "primary_leader_votes": first_rows[0]["votes"],
        "winner": winner["candidate"],
        "winner_party": winner["candidate_party"],
        "winner_final_votes": winner["votes"],
        "runner_up": runner_up["candidate"],
        "runner_up_party": runner_up["candidate_party"],
        "runner_up_final_votes": runner_up["votes"],
        "final_margin": int(winner["votes"]) - int(runner_up["votes"]),
        "preference_changed_result": str(first_rows[0]["candidate"] != winner["candidate"]),
        "winner_transfer_gain": int(winner["votes"]) - winner_first_votes,
    }
    return long_rows, summary_row


def build_boundaries(
    session: requests.Session,
    out_path: Path,
    district_names: list[str],
    refresh: bool = False,
    raw_dir: Path | None = None,
) -> None:
    cache_path = (raw_dir or Path("tmp/qld_state")) / "boundaries_geojson.json"
    if cache_path.exists() and not refresh:
        geojson = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        response = session.get(
            f"{BOUNDARY_SERVICE_URL}/query",
            params={
                "where": "1=1",
                "returnGeometry": "true",
                "outFields": "name,id",
                "outSR": "4326",
                "f": "geojson",
            },
            timeout=240,
        )
        response.raise_for_status()
        geojson = response.json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(geojson), encoding="utf-8")

    by_upper = {name.upper(): name for name in district_names}
    features = []
    seen: set[str] = set()
    for feature in geojson.get("features", []):
        raw_name = clean_text(feature.get("properties", {}).get("name")).upper()
        district = by_upper.get(raw_name)
        if not district:
            raise SystemExit(f"Queensland boundary district does not match results: {raw_name}")
        properties = {
            "district": district,
            "source": BOUNDARY_DATASET_URL,
            "service": BOUNDARY_SERVICE_URL,
        }
        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": feature["geometry"],
        })
        seen.add(district)

    missing = sorted(set(district_names) - seen)
    if missing:
        raise SystemExit(f"Missing Queensland boundary districts: {missing}")

    features.sort(key=lambda feature: feature["properties"]["district"])
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n", encoding="utf-8")


def main(
    default_raw_dir: str = "tmp/qld_2024",
    default_election_stub: str = "SGE2024",
    default_prefix: str = "qld_2024",
    default_expected_districts: int = 93,
) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path(default_raw_dir))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--election-stub", default=default_election_stub)
    parser.add_argument("--prefix", default=default_prefix)
    parser.add_argument("--expected-districts", type=int, default=default_expected_districts)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = make_session()
    electorates = fetch_json(
        session,
        f"{DATA_BASE}/{args.election_stub}-electorates.json",
        args.raw_dir / "electorates.json",
        refresh=args.refresh,
    ).get("electorates", [])
    state_electorates = [
        electorate
        for electorate in electorates
        if clean_text(electorate.get("contestType")).lower() == "state"
    ]
    if len(state_electorates) != args.expected_districts:
        raise SystemExit(
            f"Expected {args.expected_districts} Queensland state districts, found {len(state_electorates)}"
        )

    all_long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    state_electorates.sort(key=lambda electorate: clean_text(electorate["electorateName"]))
    for index, electorate in enumerate(state_electorates, start=1):
        district = clean_text(electorate["electorateName"])
        print(f"[{index:02d}/{len(state_electorates)}] {district}")
        long_rows, summary_row = build_district_rows(
            session,
            args.election_stub,
            electorate,
            args.raw_dir,
            refresh=args.refresh,
        )
        all_long_rows.extend(long_rows)
        summary_rows.append(summary_row)

    summary_rows.sort(key=lambda row: str(row["district"]))
    all_long_rows.sort(
        key=lambda row: (str(row["district"]), int(row["round_number"]), str(row["row_type"]), str(row["candidate"]))
    )

    pref_path = args.out / f"{args.prefix}_preferences_long.csv"
    summary_path = args.out / f"{args.prefix}_district_summary.csv"
    boundary_path = args.out / f"{args.prefix}_district_boundaries.geojson"
    write_csv(pref_path, all_long_rows, LONG_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    build_boundaries(
        session,
        boundary_path,
        [clean_text(electorate["electorateName"]) for electorate in state_electorates],
        refresh=args.refresh,
        raw_dir=args.raw_dir,
    )

    print(f"Wrote {pref_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
