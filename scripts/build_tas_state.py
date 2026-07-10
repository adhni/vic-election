#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests


UA = "Mozilla/5.0 (compatible; australian-election-preference-explorer/0.1; +https://github.com/)"

MEMBERS_TO_ELECT = 7

ELECTIONS = {
    2025: {
        "base": "https://www.tec.tas.gov.au/house-of-assembly/elections-2025/results",
        "filename": "{year} House of Assembly - Division of {division} - Export Count {count}.xlsx",
        "boundaries_source": Path("data/federal_2025_au_division_boundaries.geojson"),
        "divisions": {
            "Bass": {"slug": "bass", "count": 90, "enrolment": 80566},
            "Braddon": {"slug": "braddon", "count": 92, "enrolment": 84566},
            "Clark": {"slug": "clark", "count": 47, "enrolment": 74385},
            "Franklin": {"slug": "franklin", "count": 86, "enrolment": 83928},
            "Lyons": {"slug": "lyons", "count": 88, "enrolment": 89460},
        },
    },
    2024: {
        "base": "https://www.tec.tas.gov.au/house-of-assembly/elections-2024/results",
        "filename": "{year} House of Assembly - Division of {division} - Export {count}.xlsx",
        "boundaries_source": Path("data/federal_2025_au_division_boundaries.geojson"),
        "divisions": {
            "Bass": {"slug": "bass", "count": 80, "enrolment": 80126},
            "Braddon": {"slug": "braddon", "count": 85, "enrolment": 83875},
            "Clark": {"slug": "clark", "count": 45, "enrolment": 74236},
            "Franklin": {"slug": "franklin", "count": 58, "enrolment": 82238},
            "Lyons": {"slug": "lyons", "count": 72, "enrolment": 87722},
        },
    },
}

LONG_FIELDS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "elected_members",
    "members_to_elect",
    "quota",
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
    "candidate_status",
    "candidate_elected",
    "candidate_elected_order",
    "votes",
]

SUMMARY_FIELDS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "elected_members",
    "members_to_elect",
    "quota",
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


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_int(value: object) -> int:
    text = clean_text(value)
    if not text:
        return 0
    match = re.search(r"-?\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else 0


def normalize_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def surname_key(value: str) -> str:
    text = clean_text(value)
    if "," in text:
        return normalize_key(text.split(",", 1)[0])
    parts = text.rsplit(" ", 1)
    return normalize_key(parts[0] if len(parts) == 2 else text)


def name_words(value: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", clean_text(value).upper())


def surname_word_prefixes(value: str) -> list[str]:
    surname = clean_text(value).split(",", 1)[0]
    words = name_words(surname)
    return ["".join(words[:count]) for count in range(len(words), 0, -1)]


def surname_initial_key(value: str) -> str:
    text = clean_text(value)
    if "," in text:
        surname, given = [part.strip() for part in text.split(",", 1)]
        return normalize_key(f"{surname}{given[:1]}")
    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        surname, given = parts
        return normalize_key(f"{surname}{given[:1]}")
    return normalize_key(text)


def format_candidate_name(value: str) -> str:
    text = clean_text(value)
    if "," in text:
        surname, given = [part.strip() for part in text.split(",", 1)]
        return f"{surname.upper()}, {given}".strip()
    parts = text.rsplit(" ", 1)
    if len(parts) == 2:
        surname, given = parts
        return f"{surname.upper()}, {given}".strip()
    return text.upper()


def cell_value(value: object) -> object:
    return clean_text(value) if isinstance(value, str) else value


def clean_row(row: dict[str, object]) -> dict[str, object]:
    return {key: cell_value(value) for key, value in row.items()}


def party_from_group(value: str) -> str:
    label = clean_text(value)
    upper = label.upper()
    if upper in {"ALP", "LABOR"}:
        return "Australian Labor Party"
    if upper in {"LIB", "LIBERAL"}:
        return "Liberal Party"
    if upper in {"NAT", "NATIONAL", "NATIONALS"}:
        return "The Nationals"
    if upper == "JLN":
        return "Jacqui Lambie Network"
    if upper == "SFF" or "SHOOTERS" in upper:
        return "Shooters, Fishers, Farmers TAS"
    if "GREEN" in upper:
        return "Tasmanian Greens"
    if "UNGROUPED" in upper or upper.startswith("GROUP"):
        return "Independent"
    return label or "Independent"


def workbook_url(year: int, config: dict[str, object], division: str, meta: dict[str, int | str]) -> str:
    filename = str(config["filename"]).format(year=year, division=division, count=meta["count"])
    return f"{config['base']}/{meta['slug']}/pdf/{quote(filename)}"


def download(session: requests.Session, url: str, path: Path, refresh: bool = False) -> None:
    if path.exists() and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    time.sleep(0.1)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)


def result_rows(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        name = clean_text(row.iloc[1] if len(row) > 1 else "")
        if not name or name in {"Total", "Quota", "Results as at"} or name.startswith(("Exhausted", "Loss")):
            continue
        votes = clean_int(row.iloc[2] if len(row) > 2 else "")
        status = clean_text(row.iloc[5] if len(row) > 5 else "")
        if status.lower() == "status" or name.lower().startswith("results count"):
            continue
        if not status and not votes:
            continue
        rows.append(clean_row({
            "candidate": format_candidate_name(name),
            "votes": votes,
            "status": status,
        }))
    return rows


def elected_order(df: pd.DataFrame) -> list[str]:
    elected: list[str] = []
    for _, row in df.iterrows():
        name = clean_text(row.iloc[1] if len(row) > 1 else "")
        count = clean_text(row.iloc[2] if len(row) > 2 else "")
        if not name or name.startswith("(") or name == "Elected":
            continue
        if count and count.lower() != "count1":
            elected.append(format_candidate_name(name))
    return elected[:MEMBERS_TO_ELECT]


def parse_division(
    path: Path,
    year: int,
    config: dict[str, object],
    division: str,
    meta: dict[str, int | str],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    result_df = pd.read_excel(path, sheet_name="ElectionResultLGScreen", header=None)
    status_df = pd.read_excel(path, sheet_name="ElectionResultScreen", header=None)
    scrutiny_df = pd.read_excel(path, sheet_name="ScrutinyScreen", header=None)

    final_candidates = result_rows(result_df)
    name_by_surname_initial = {
        surname_initial_key(str(candidate["candidate"])): str(candidate["candidate"])
        for candidate in final_candidates
    }
    name_by_surname_prefix: dict[str, str] = {}
    surname_prefix_counts: dict[str, int] = {}
    surname_groups: dict[str, list[str]] = {}
    for candidate in final_candidates:
        name = str(candidate["candidate"])
        surname_groups.setdefault(surname_key(name), []).append(name)
        for prefix in surname_word_prefixes(name):
            surname_prefix_counts[prefix] = surname_prefix_counts.get(prefix, 0) + 1
            name_by_surname_prefix[prefix] = name
    name_by_unique_surname = {
        key: names[0]
        for key, names in surname_groups.items()
        if len(names) == 1
    }
    name_by_unique_surname_prefix = {
        key: name
        for key, name in name_by_surname_prefix.items()
        if surname_prefix_counts[key] == 1
    }

    party_by_candidate: dict[str, str] = {}
    first_votes: dict[str, int] = {}
    current_party = ""
    for col in range(3, scrutiny_df.shape[1]):
        header = clean_text(scrutiny_df.iat[7, col])
        if "Ballot Papers" in header or header.startswith("Votes "):
            break
        if not header or "Totals" in header:
            continue
        party_header = clean_text(scrutiny_df.iat[6, col])
        if party_header:
            current_party = party_from_group(party_header)
        candidate = (
            name_by_unique_surname.get(surname_key(header))
            or name_by_unique_surname_prefix.get(surname_key(header))
            or name_by_surname_initial.get(surname_initial_key(header))
            or format_candidate_name(header)
        )
        party_by_candidate[candidate] = current_party or "Independent"
        first_votes[candidate] = clean_int(scrutiny_df.iat[9, col])

    formal_votes = clean_int(scrutiny_df.iat[3, 1])
    informal_votes = clean_int(scrutiny_df.iat[4, 1])
    quota = clean_int(result_df[result_df.iloc[:, 1].map(clean_text) == "Quota"].iloc[0, 2])
    total_votes = formal_votes + informal_votes
    enrolment = int(meta["enrolment"])
    turnout_pct = round(total_votes / enrolment * 100, 2) if enrolment else ""

    elected = elected_order(status_df)
    elected_set = set(elected)
    order_by_candidate = {name: index + 1 for index, name in enumerate(elected)}

    final_votes = {str(row["candidate"]): int(row["votes"]) for row in final_candidates}
    status_by_candidate = {str(row["candidate"]): str(row["status"]) for row in final_candidates}

    non_elected_final = [votes for candidate, votes in final_votes.items() if candidate not in elected_set]
    elected_final = [final_votes.get(candidate, 0) for candidate in elected]
    final_seat_gap = max(0, min(elected_final or [0]) - max(non_elected_final or [0]))
    primary_leader = max(first_votes.items(), key=lambda item: item[1])
    final_leader = max(final_votes.items(), key=lambda item: item[1])
    final_runner_up = sorted(final_votes.items(), key=lambda item: item[1], reverse=True)[1]

    district_url = f"{config['base']}/{meta['slug']}/index.html"
    distribution_url = workbook_url(year, config, division, meta)
    elected_members = "; ".join(elected)
    elected_parties = "; ".join(party_by_candidate.get(candidate, "Independent") for candidate in elected)

    base = {
        "district": division,
        "district_url": district_url,
        "distribution_url": distribution_url,
        "elected_member": elected_members,
        "elected_party": elected_parties,
        "elected_members": elected_members,
        "members_to_elect": MEMBERS_TO_ELECT,
        "quota": quota,
        "enrolment": enrolment,
        "formal_votes": formal_votes,
        "informal_votes": informal_votes,
        "total_votes": total_votes,
        "turnout_pct": turnout_pct,
        "majority": final_seat_gap,
    }

    long_rows: list[dict[str, object]] = []
    for candidate, votes in sorted(first_votes.items(), key=lambda item: (-item[1], item[0])):
        long_rows.append(clean_row({
            **base,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": candidate,
            "candidate_party": party_by_candidate.get(candidate, "Independent"),
            "candidate_status": status_by_candidate.get(candidate, ""),
            "candidate_elected": str(candidate in elected_set),
            "candidate_elected_order": order_by_candidate.get(candidate, ""),
            "votes": votes,
        }))

    for candidate, votes in sorted(final_votes.items(), key=lambda item: (-item[1], item[0])):
        long_rows.append(clean_row({
            **base,
            "round_number": int(meta["count"]),
            "row_type": "final",
            "excluded_candidate": "",
            "excluded_party": "",
            "candidate": candidate,
            "candidate_party": party_by_candidate.get(candidate, "Independent"),
            "candidate_status": status_by_candidate.get(candidate, ""),
            "candidate_elected": str(candidate in elected_set),
            "candidate_elected_order": order_by_candidate.get(candidate, ""),
            "votes": votes,
        }))

    elected_from_outside_top = any(
        candidate not in {name for name, _ in sorted(first_votes.items(), key=lambda item: item[1], reverse=True)[:MEMBERS_TO_ELECT]}
        for candidate in elected
    )
    summary = clean_row({
        **base,
        "primary_leader": primary_leader[0],
        "primary_leader_party": party_by_candidate.get(primary_leader[0], "Independent"),
        "primary_leader_votes": primary_leader[1],
        "winner": final_leader[0],
        "winner_party": party_by_candidate.get(final_leader[0], "Independent"),
        "winner_final_votes": final_leader[1],
        "runner_up": final_runner_up[0],
        "runner_up_party": party_by_candidate.get(final_runner_up[0], "Independent"),
        "runner_up_final_votes": final_runner_up[1],
        "final_margin": final_seat_gap,
        "preference_changed_result": str(elected_from_outside_top),
        "winner_transfer_gain": final_leader[1] - first_votes.get(final_leader[0], 0),
    })
    return long_rows, summary


def write_boundaries(source_path: Path, out_path: Path, divisions: set[str], year: int) -> None:
    with source_path.open(encoding="utf-8") as f:
        geojson = json.load(f)
    features = [
        feature
        for feature in geojson.get("features", [])
        if feature.get("properties", {}).get("district") in divisions
    ]
    if len(features) != len(divisions):
        found = {feature.get("properties", {}).get("district") for feature in features}
        raise SystemExit(f"Tasmania boundary mismatch: {sorted(divisions - found)}")
    out = {
        "type": "FeatureCollection",
        "name": f"tas_{year}_house_of_assembly_divisions",
        "features": features,
    }
    out_path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=sorted(ELECTIONS), default=2025)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--boundaries-source", type=Path)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)

    config = ELECTIONS[args.year]
    divisions = config["divisions"]
    raw_dir = args.raw_dir or Path(f"tmp/tas_{args.year}")
    boundaries_source = args.boundaries_source or config["boundaries_source"]

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for division, meta in divisions.items():
        url = workbook_url(args.year, config, division, meta)
        path = raw_dir / f"{division.lower()}_count_{meta['count']}.xlsx"
        download(session, url, path, refresh=args.refresh)
        division_rows, summary = parse_division(path, args.year, config, division, meta)
        long_rows.extend(division_rows)
        summary_rows.append(summary)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    pref_path = args.out_dir / f"tas_{args.year}_preferences_long.csv"
    summary_path = args.out_dir / f"tas_{args.year}_district_summary.csv"
    boundary_path = args.out_dir / f"tas_{args.year}_district_boundaries.geojson"

    with pref_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LONG_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(long_rows)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)
    write_boundaries(boundaries_source, boundary_path, set(divisions), args.year)

    print(f"Wrote {pref_path} ({len(long_rows)} rows)")
    print(f"Wrote {summary_path} ({len(summary_rows)} rows)")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
