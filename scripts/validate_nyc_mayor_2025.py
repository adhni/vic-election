#!/usr/bin/env python3
"""Independently verify shipped NYC mayoral totals, fusion lines and map joins."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"Zohran Mamdani": 1114184, "Andrew Cuomo": 906614, "Curtis Sliwa": 153749,
            "Eric Adams": 6897, "Irene Estrada": 2856, "Jim Walden": 2319,
            "Joseph Hernandez": 1379, "Write-ins": 6206}


def validate() -> None:
    metadata = json.loads((ROOT / "data/nyc_2025_mayor_metadata.json").read_text())
    assert metadata["boundary_release"] == "25C (August 2025)"
    assert metadata["raw_ed_count"] == 4338 and metadata["combined_ed_count"] == 221
    assert len(metadata["geographies"]["ed"]["unmapped_zero_vote_areas"]) == 15
    for level, expected_count in [("ed", 4102), ("assembly", 65), ("borough", 5)]:
        prefix = ROOT / f"data/nyc_2025_mayor_{level}"
        rows = list(csv.DictReader(Path(str(prefix) + "_fpp.csv").open(encoding="utf-8")))
        groups = defaultdict(list)
        totals = Counter()
        ballot_totals = Counter()
        for row in rows:
            groups[row["district"]].append(row)
            totals[row["candidate"]] += int(row["votes"])
            assert row["candidate_party"] == row["candidate"]
            assert row["row_type"] == "first" and row["round_number"] == "0"
            lines = json.loads(row["ballot_lines"])
            assert sum(lines.values()) == int(row["votes"])
            ballot_totals.update(lines)
        assert len(groups) == expected_count
        assert dict(totals) == EXPECTED, (level, totals)
        assert ballot_totals["Zohran Kwame Mamdani (Democratic)"] == 944950
        assert ballot_totals["Zohran Kwame Mamdani (Working Families)"] == 169234
        assert ballot_totals["Curtis A. Sliwa (Republican)"] == 143305
        assert ballot_totals["Curtis A. Sliwa (Protect Animals)"] == 10444
        ballots = unrecorded = ties = zero = 0
        for district, entries in groups.items():
            assert len(entries) == 8 and len({r["candidate"] for r in entries}) == 8
            first = entries[0]
            votes = sum(int(r["votes"]) for r in entries)
            assert votes == int(first["formal_votes"])
            assert votes + int(first["informal_votes"]) == int(first["total_votes"])
            assert first["enrolment"] == first["turnout_pct"] == ""
            if level == "borough":
                assert first["electorate_type"] == "New York City"
            ballots += int(first["total_votes"])
            unrecorded += int(first["informal_votes"])
            ranked = sorted(int(r["votes"]) for r in entries if r["candidate"] != "Write-ins")
            if not votes:
                zero += 1
                assert first["contest_status"] == "no-votes" and first["elected_member"] == ""
            elif ranked[-1] == ranked[-2]:
                ties += 1
                assert first["contest_status"] == "tied-local" and first["elected_member"] == ""
            else:
                assert first["contest_status"] == "official"
                assert next(int(r["votes"]) for r in entries if r["candidate"] == first["elected_member"]) == ranked[-1]
            assert int(first["majority"]) == ranked[-1] - ranked[-2]
        assert ballots == 2218647 and unrecorded == 24443
        if level == "ed":
            assert ties == 9 and zero == 72
            combined = groups["Manhattan · AD 76 ED 059"][0]
            assert "37071" in combined["combined_from"]
            assert "Joint BOE reporting area" in combined["result_note"]
        features = json.loads(Path(str(prefix) + "_boundaries.geojson").read_text())["features"]
        assert len(features) == len(groups)
        assert {f["properties"]["district"] for f in features} == set(groups)
        for feature in features:
            geometry = shape(feature["geometry"])
            assert geometry.is_valid and not geometry.is_empty
            west, south, east, north = geometry.bounds
            assert -74.3 < west <= east < -73.6 and 40.4 < south <= north < 41
        print(f"PASS {level}: {len(groups)} areas; exact certified totals; {ties} ties, {zero} zero-vote areas")


if __name__ == "__main__":
    validate()
