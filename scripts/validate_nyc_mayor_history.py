#!/usr/bin/env python3
"""Check shipped 2017 and 2021 totals, fusion lines and historical map coverage."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    2021: {"Eric Adams": 753801, "Curtis Sliwa": 312385, "Catherine Rojas": 27982,
        "William Pepitone": 12575, "Quanda Francis": 3792, "Stacey Prussman": 3189,
        "Raja Michael Flores": 2387, "Fernando Mateo": 1870, "Skiboky Stora": 264, "Write-ins": 7013},
    2017: {"Bill de Blasio": 760112, "Nicole Malliotakis": 316948, "Sal Albanese": 24484,
        "Akeem Browder": 16536, "Michael Tolkin": 11309, "Bo Dietl": 11163, "Aaron Commey": 2770, "Write-ins": 5343},
}
BALLOTS = {2021: 1149172, 2017: 1166314}
COUNTS = {2021: 5697, 2017: 5720}
FUSION_LINES = {
    2021: {"Curtis A. Sliwa (Republican)": 302680, "Curtis A. Sliwa (Independent)": 9705},
    2017: {"Bill de Blasio (Democratic)": 713634, "Bill de Blasio (Working Families)": 46478,
        "Nicole Malliotakis (Republican)": 274424, "Nicole Malliotakis (Conservative)": 37197,
        "Nicole Malliotakis (Stop de Blasio)": 5327},
}


def validate():
    for year in (2021, 2017):
        meta = json.loads((ROOT / f"data/nyc_{year}_mayor_metadata.json").read_text())
        assert meta["raw_ed_count"] == 5901
        assert meta["candidate_totals"] == EXPECTED[year]
        assert meta["total_ballots"] == BALLOTS[year]
        assert meta["boundary_commit"] == "325cee637986542918fde0ff156cb2fd685229b8"
        assert meta["combined_ed_count"] == (176 if year == 2021 else 142)
        for level, count in (("ed", COUNTS[year]), ("assembly", 65), ("borough", 5)):
            stem = ROOT / f"data/nyc_{year}_mayor_{level}"
            groups = defaultdict(list)
            totals, lines = Counter(), Counter()
            for row in csv.DictReader(Path(str(stem) + "_fpp.csv").open(encoding="utf-8")):
                groups[row["district"]].append(row)
                totals[row["candidate"]] += int(row["votes"])
                ballot_lines = json.loads(row["ballot_lines"])
                assert sum(ballot_lines.values()) == int(row["votes"])
                lines.update(ballot_lines)
                assert row["candidate_party"] == row["candidate"] and row["row_type"] == "first"
            assert dict(totals) == EXPECTED[year] and len(groups) == count
            assert all(lines[name] == votes for name, votes in FUSION_LINES[year].items())
            ballots = 0
            ties = zero = 0
            for entries in groups.values():
                assert len(entries) == len(EXPECTED[year])
                first = entries[0]
                formal = sum(int(r["votes"]) for r in entries)
                assert formal == int(first["formal_votes"])
                assert formal + int(first["informal_votes"]) == int(first["total_votes"])
                assert first["enrolment"] == first["turnout_pct"] == ""
                ballots += int(first["total_votes"])
                named = sorted((int(r["votes"]), r["candidate"]) for r in entries if r["candidate"] != "Write-ins")
                assert int(first["majority"]) == named[-1][0] - named[-2][0]
                if not formal:
                    zero += 1
                    assert first["contest_status"] == "no-votes" and not first["elected_member"]
                    if int(first["total_votes"]):
                        assert "zero ballots" not in first["result_note"]
                elif named[-1][0] == named[-2][0]:
                    ties += 1
                    assert first["contest_status"] == "tied-local" and not first["elected_member"]
                else:
                    assert first["contest_status"] == "official" and first["elected_member"] == named[-1][1]
                if first["combined_from"] and level == "ed":
                    assert "Joint BOE reporting area" in first["result_note"]
                if level == "borough":
                    assert first["electorate_type"] == "New York City"
            assert ballots == BALLOTS[year]
            coverage = meta["geographies"][level]
            assert coverage["zero_vote_areas"] == zero and coverage["tied_areas"] == ties
            assert count + len(coverage["unmapped_zero_vote_areas"]) == coverage["source_reporting_areas"]
            features = json.loads(Path(str(stem) + "_boundaries.geojson").read_text())["features"]
            assert len(features) == count and {f["properties"]["district"] for f in features} == set(groups)
            for feature in features:
                geometry = shape(feature["geometry"])
                assert geometry.is_valid and not geometry.is_empty
                west, south, east, north = geometry.bounds
                assert -74.3 < west <= east < -73.6 and 40.4 < south <= north < 41
            if year == 2017 and level == "ed":
                corrected = groups["Manhattan · AD 76 ED 067"]
                line = next(r for r in corrected if r["candidate"] == "Nicole Malliotakis")
                assert json.loads(line["ballot_lines"])["Nicole Malliotakis (Republican)"] == 101
                no_mayoral_vote = groups["Brooklyn · AD 46 ED 037"][0]
                assert no_mayoral_vote["total_votes"] == "1" and no_mayoral_vote["formal_votes"] == "0"
                assert meta["source_corrections"][0]["ed"] == 76067
            print(f"PASS {year} {level}: {count} areas; exact certified totals and fusion lines; {ties} ties, {zero} zero-vote areas")


if __name__ == "__main__":
    validate()
