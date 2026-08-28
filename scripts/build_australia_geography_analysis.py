#!/usr/bin/env python3
"""Build compact electorate-level metrics for the Australian geography views."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPLORER_HTML = ROOT / "app" / "index.html"
OUTPUT_PATH = ROOT / "data" / "australia_geography_analysis.json"

BLOCS = ("Labor", "Coalition", "Greens", "Independent", "Other")
AUSTRALIAN_JURISDICTIONS = {
    "Australia",
    "Victoria",
    "New South Wales",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Northern Territory",
}

# These pairs use the same legal electoral boundaries. All other election
# series remain available in the history chart but are explicitly flagged as
# involving boundary changes.
COMPARISON_KEYS = {
    "2010": "2006",
    "2018": "2014",
    "nsw-2019": "nsw-2015",
    "qld-2024": "qld-2020",
    "federal-2010-vic": "federal-2007-vic",
}

BOUNDARY_GROUPS = {
    "2006": "vic-state-2001",
    "2010": "vic-state-2001",
    "2014": "vic-state-2012",
    "2018": "vic-state-2012",
    "nsw-2015": "nsw-state-2013",
    "nsw-2019": "nsw-state-2013",
    "qld-2020": "qld-state-2017",
    "qld-2024": "qld-state-2017",
    "federal-2007-vic": "federal-vic-2007",
    "federal-2010-vic": "federal-vic-2007",
}


def load_election_definitions() -> list[dict[str, object]]:
    html = EXPLORER_HTML.read_text(encoding="utf-8")
    match = re.search(r"const electionDefinitions = (\[.*?\]);", html, flags=re.S)
    if not match:
        raise SystemExit(f"Could not find electionDefinitions in {EXPLORER_HTML}")
    return json.loads(match.group(1))


def is_supported(election: dict[str, object]) -> bool:
    return (
        election.get("jurisdiction") in AUSTRALIAN_JURISDICTIONS
        and election.get("type") in {"state", "federal"}
        and election.get("system") not in {"hare-clark", "senate-stv"}
        and not election.get("localElection")
        and str(election.get("csv", "")).endswith("_preferences_long.csv")
    )


def party_bloc(raw: str) -> str:
    """Return the common Australian bloc used by the browser visualisations."""
    party = " ".join((raw or "Independent").strip().lower().split())
    upper = party.upper()

    # Democratic Labour and liberal-democratic/libertarian parties are not the
    # Australian Labor Party or the Liberal/National Coalition.
    if "democratic labo" in party or upper in {"DLP", "LABOUR DLP"}:
        return "Other"
    if "liberal democrat" in party or "libertarian" in party or upper == "LDP":
        return "Other"

    if upper in {"ALP", "A.L.P.", "CL"} or "australian labor party" in party or party in {"labor", "country labor party"}:
        return "Labor"
    if (
        upper in {"GNS", "GREENS"}
        or party in {"greens", "australian greens", "tasmanian greens", "queensland greens", "qld greens", "nt greens"}
        or party.startswith("the greens")
    ):
        return "Greens"
    if upper in {"IND", "INDEPENDENT"} or "independent" in party:
        return "Independent"
    if (
        upper in {"LP", "LIBERAL", "NP", "NATIONALS", "LNP", "LN", "NT CLP"}
        or party in {"liberal", "liberal party", "national party", "nationals", "the nationals"}
        or "liberal party of australia" in party
        or "liberal national party" in party
        or "country liberal" in party
        or "national party of australia" in party
    ):
        return "Coalition"
    return "Other"


def number(value: str, cast=float):
    value = (value or "").strip()
    return cast(float(value)) if value else None


def build_election(election: dict[str, object]) -> dict[str, object]:
    csv_path = ROOT / str(election["csv"])
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    first_rows = [row for row in rows if row.get("row_type") == "first"]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in first_rows:
        grouped[row["district"]].append(row)

    areas: dict[str, object] = {}
    for district in sorted(grouped):
        district_rows = grouped[district]
        metadata = district_rows[0]
        formal = number(metadata.get("formal_votes", ""), int) or 0
        totals = {bloc: 0 for bloc in BLOCS}
        for row in district_rows:
            totals[party_bloc(row.get("candidate_party", ""))] += number(row.get("votes", ""), int) or 0
        source_gap = formal - sum(totals.values())
        if source_gap < 0 or (formal and source_gap / formal > 0.005):
            raise SystemExit(
                f"{election['key']} {district}: first preferences {sum(totals.values())} != formal votes {formal}"
            )

        informal = number(metadata.get("informal_votes", ""), int)
        total_votes = number(metadata.get("total_votes", ""), int)
        areas[district] = {
            "formal": formal,
            "turnout": number(metadata.get("turnout_pct", "")),
            "informal": round((informal / total_votes) * 100, 3) if informal is not None and total_votes else None,
            "sourceGap": source_gap,
            "blocs": {
                bloc: round((votes / formal) * 100, 3) if formal else 0
                for bloc, votes in totals.items()
            },
        }

    key = str(election["key"])
    return {
        "label": election["label"],
        "jurisdiction": election["jurisdiction"],
        "level": election["type"],
        "year": election["year"],
        "boundaryGroup": BOUNDARY_GROUPS.get(key, key),
        "comparisonKey": COMPARISON_KEYS.get(key),
        "areas": areas,
    }


def build_payload() -> dict[str, object]:
    elections = {
        str(election["key"]): build_election(election)
        for election in load_election_definitions()
        if is_supported(election)
    }
    return {
        "version": 1,
        "blocs": list(BLOCS),
        "method": "Electorate-level first-preference shares. Same-boundary swing pairs are explicitly configured.",
        "elections": elections,
    }


def main() -> None:
    payload = build_payload()
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    elections = payload["elections"]
    area_count = sum(len(election["areas"]) for election in elections.values())
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} ({len(elections)} elections, {area_count} electorate records)")


if __name__ == "__main__":
    main()
