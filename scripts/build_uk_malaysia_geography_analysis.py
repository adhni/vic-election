#!/usr/bin/env python3
"""Build constituency-level political-geography metrics for the UK and Malaysia."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "uk_malaysia_geography_analysis.json"

ELECTIONS = {
    "uk-2024": {
        "label": "United Kingdom General 2024",
        "jurisdiction": "United Kingdom",
        "level": "national",
        "year": 2024,
        "csv": "data/uk_2024_fpp.csv",
        "boundaries": "data/uk_2024_constituency_boundaries.geojson",
        "boundaryGroup": "uk-westminster-2024",
    },
    "uk-2019": {
        "label": "United Kingdom General 2019",
        "jurisdiction": "United Kingdom",
        "level": "national",
        "year": 2019,
        "csv": "data/uk_2019_fpp.csv",
        "boundaries": "data/uk_2019_constituency_boundaries.geojson",
        "boundaryGroup": "uk-westminster-2010",
        "comparisonKey": "uk-2017",
    },
    "uk-2017": {
        "label": "United Kingdom General 2017",
        "jurisdiction": "United Kingdom",
        "level": "national",
        "year": 2017,
        "csv": "data/uk_2017_fpp.csv",
        "boundaries": "data/uk_2017_constituency_boundaries.geojson",
        "boundaryGroup": "uk-westminster-2010",
    },
    "malaysia-2022": {
        "label": "Malaysia General 2022 (GE15)",
        "jurisdiction": "Malaysia",
        "level": "national",
        "year": 2022,
        "csv": "data/malaysia_2022_fpp.csv",
        "boundaries": "data/malaysia_2022_parliamentary_boundaries.geojson",
        "boundaryGroup": "malaysia-ge15-mixed-delimitation",
    },
    "malaysia-2018": {
        "label": "Malaysia General 2018 (GE14)",
        "jurisdiction": "Malaysia",
        "level": "national",
        "year": 2018,
        "csv": "data/malaysia_2018_fpp.csv",
        "boundaries": "data/malaysia_2018_parliamentary_boundaries.geojson",
        "boundaryGroup": "malaysia-ge14-mixed-delimitation",
    },
    "malaysia-2013": {
        "label": "Malaysia General 2013 (GE13)",
        "jurisdiction": "Malaysia",
        "level": "national",
        "year": 2013,
        "csv": "data/malaysia_2013_fpp.csv",
        "boundaries": "data/malaysia_2013_parliamentary_boundaries.geojson",
        "boundaryGroup": "malaysia-ge13-mixed-delimitation",
    },
}

UK_BLOCS = (
    "Labour",
    "Conservative",
    "Liberal Democrats",
    "Reform / UKIP",
    "Greens",
    "National / regional",
    "Other",
)
MALAYSIA_BLOCS = (
    "PH / PKR-DAP",
    "BN",
    "PN / PAS",
    "East Malaysian parties",
    "Independent",
    "Other",
)
BLOCS_BY_JURISDICTION = {
    "United Kingdom": UK_BLOCS,
    "Malaysia": MALAYSIA_BLOCS,
}

UK_NATIONAL_REGIONAL = {
    "Alba Party",
    "Alliance",
    "Aontú",
    "Democratic Unionist Party",
    "People Before Profit Alliance",
    "Plaid Cymru",
    "Scottish National Party",
    "Sinn Féin",
    "Social Democratic & Labour Party",
    "Traditional Unionist Voice",
    "Ulster Unionist Party",
}
MALAYSIA_EAST = {
    "ANAKNEGERI",
    "GPS",
    "GRS",
    "KDM",
    "PAP",
    "PBDS",
    "PBDSB",
    "PBK",
    "PBRS",
    "PCS",
    "PFP",
    "PSB",
    "PPRS",
    "SAPP",
    "SOLIDARITI",
    "STAR",
    "SWP",
    "WARISAN",
}


def party_bloc(jurisdiction: str, raw: str) -> str:
    party = " ".join((raw or "").strip().split())
    if jurisdiction == "United Kingdom":
        if party == "Labour":
            return "Labour"
        if party == "Conservative":
            return "Conservative"
        if party == "Liberal Democrat":
            return "Liberal Democrats"
        if party in {"Reform UK", "The Brexit Party", "UK Independence Party"}:
            return "Reform / UKIP"
        if party in {"Green Party", "Green Party Northern Ireland", "Scottish Green Party"}:
            return "Greens"
        if party in UK_NATIONAL_REGIONAL:
            return "National / regional"
        return "Other"

    upper = party.upper()
    if upper in {"PH", "PKR", "DAP", "AMANAH", "MUDA"}:
        return "PH / PKR-DAP"
    if upper == "BN":
        return "BN"
    if upper in {"PN", "PAS"}:
        return "PN / PAS"
    if upper in MALAYSIA_EAST:
        return "East Malaysian parties"
    if upper in {"BEBAS", "INDEPENDENT"}:
        return "Independent"
    return "Other"


def number(value: str, cast=float):
    value = (value or "").strip()
    return cast(float(value)) if value else None


def build_election(key: str, config: dict[str, object]) -> dict[str, object]:
    csv_path = ROOT / str(config["csv"])
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("row_type") == "first":
            grouped[row["district"]].append(row)

    blocs = BLOCS_BY_JURISDICTION[str(config["jurisdiction"])]
    areas: dict[str, object] = {}
    for district in sorted(grouped):
        district_rows = grouped[district]
        metadata = district_rows[0]
        formal = number(metadata.get("formal_votes", ""), int) or 0
        totals = {bloc: 0 for bloc in blocs}
        for row in district_rows:
            bloc = party_bloc(str(config["jurisdiction"]), row.get("candidate_party", ""))
            totals[bloc] += number(row.get("votes", ""), int) or 0
        represented = sum(totals.values())
        if represented != formal:
            raise SystemExit(f"{key} {district}: candidate votes {represented} != formal votes {formal}")

        informal = number(metadata.get("informal_votes", ""), int)
        total_votes = number(metadata.get("total_votes", ""), int)
        areas[district] = {
            "formal": formal,
            "turnout": number(metadata.get("turnout_pct", "")),
            "informal": round((informal / total_votes) * 100, 3) if informal is not None and total_votes else None,
            "blocs": {
                bloc: round((votes / formal) * 100, 3) if formal else 0
                for bloc, votes in totals.items()
            },
        }

    boundary_path = ROOT / str(config["boundaries"])
    boundary_data = json.loads(boundary_path.read_text(encoding="utf-8"))
    boundary_districts = {feature["properties"]["district"] for feature in boundary_data["features"]}
    if boundary_districts != set(areas):
        missing_results = sorted(boundary_districts - set(areas))
        missing_boundaries = sorted(set(areas) - boundary_districts)
        raise SystemExit(
            f"{key}: result/boundary mismatch; no result={missing_results[:5]}, no boundary={missing_boundaries[:5]}"
        )

    return {
        "label": config["label"],
        "jurisdiction": config["jurisdiction"],
        "level": config["level"],
        "year": config["year"],
        "boundaryGroup": config["boundaryGroup"],
        "comparisonKey": config.get("comparisonKey"),
        "blocs": list(blocs),
        "defaultBloc": blocs[0],
        "areas": areas,
    }


def build_payload() -> dict[str, object]:
    return {
        "version": 1,
        "method": "Constituency-level candidate-vote shares grouped into country-specific political blocs.",
        "elections": {key: build_election(key, config) for key, config in ELECTIONS.items()},
    }


def main() -> None:
    payload = build_payload()
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    elections = payload["elections"]
    area_count = sum(len(election["areas"]) for election in elections.values())
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} ({len(elections)} elections, {area_count} constituency records)")


if __name__ == "__main__":
    main()
