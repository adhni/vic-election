#!/usr/bin/env python3
"""Build certified NYC mayoral 2025 general returns and election-year maps.

Python dependencies: requests, shapely. The first boundary conversion also
requires Rscript with sf; --boundaries accepts a previously converted GeoJSON.
Raw downloads and conversion output stay in the ignored tmp/nyc directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PAGE = "https://www.vote.nyc/page/election-results-summary-2025"
RESULTS_BASE = "https://www.vote.nyc/sites/default/files/pdf/election_results/2025/20251104General%20Election/"
ED_URL = RESULTS_BASE + "00000100000Citywide%20Mayor%20Citywide%20EDLevel.csv"
RECAP_URL = RESULTS_BASE + "00000100000Citywide%20Mayor%20Citywide%20Recap.csv"
# Pinned mirror of NYC Planning's August 2025 (25C) shoreline-clipped release.
# The live NYC Open Data layer now describes a later election's geography.
BOUNDARY_COMMIT = "8b0b6bf6997bb3c0253517cca58828b4be27b44f"
BOUNDARY_URL = f"https://raw.githubusercontent.com/kjhealy/nycmaps/{BOUNDARY_COMMIT}/data/nyc_election_precincts_sf.rda"
SHA256 = {
    "general_ed.csv": "a39b09ce5f83a026541a234e01ee024cd968edb26338cff1cc6a8196e96219ba",
    "general_recap.csv": "7ce20521454792cc79c3ef84ddc276f9a254f7e4a03b8f59509291c62798545e",
    "nyc_election_precincts_sf.rda": "f988fde566fb9cc553cafd9fc19503b0da212fa408f016fdbf2418d47334a080",
}
BOROUGHS = {"New York": "Manhattan", "Bronx": "Bronx", "Kings": "Brooklyn", "Queens": "Queens", "Richmond": "Staten Island"}
CANDIDATES = {
    "Zohran Kwame Mamdani": "Zohran Mamdani", "Andrew M. Cuomo": "Andrew Cuomo",
    "Curtis A. Sliwa": "Curtis Sliwa", "Irene Estrada": "Irene Estrada",
    "Eric L. Adams": "Eric Adams", "Joseph Hernandez": "Joseph Hernandez",
    "Jim Walden": "Jim Walden", "Scattered": "Write-ins",
}
BALLOT_UNITS = {"Public Counter", "Manually Counted Emergency", "Absentee / Military", "Affidavit"}
EXPECTED = {"Zohran Mamdani": 1114184, "Andrew Cuomo": 906614, "Curtis Sliwa": 153749,
            "Eric Adams": 6897, "Irene Estrada": 2856, "Jim Walden": 2319,
            "Joseph Hernandez": 1379, "Write-ins": 6206}
FIELDS = ["district", "district_url", "distribution_url", "elected_member", "elected_party",
          "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
          "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
          "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
          "result_note", "candidate_grouped", "ballot_lines", "assembly_district", "election_district",
          "combined_from"]


def number(value: str) -> int:
    return int(value.replace(",", ""))


def download(url: str, path: Path, refresh: bool = False, expected_sha256: str | None = None) -> None:
    if refresh or not path.exists():
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != (expected_sha256 or SHA256[path.name]):
        raise ValueError(f"Source changed: {path.name} ({digest}); review before rebuilding")


def load_returns(path: Path, candidate_names: dict[str, str] = CANDIDATES) -> dict[int, dict]:
    areas: dict[int, dict] = {}
    for raw in csv.reader(path.open(encoding="utf-8-sig", newline="")):
        # BOE's CSV repeats the eleven field labels before every data record.
        if len(raw) == 11 and raw[:3] == ["AD", "ED", "County"]:
            continue
        if len(raw) == 22 and raw[:3] == ["AD", "ED", "County"]:
            raw = raw[11:]
        if len(raw) != 11:
            raise ValueError("Unexpected BOE ED CSV schema")
        ad, ed, county, status, event, party, office, district, vote_for, unit, tally = raw
        assert office == "Mayor" and district == "NYC" and vote_for == "1"
        code = int(ad) * 1000 + int(ed)
        area = areas.setdefault(code, {"county": county, "status": status, "ballots": 0,
                                      "votes": Counter(), "lines": defaultdict(Counter)})
        assert area["county"] == county and area["status"] == status
        votes = number(tally)
        if unit in BALLOT_UNITS:
            area["ballots"] += votes
        else:
            candidate = candidate_names[unit.split(" (")[0]]
            area["votes"][candidate] += votes
            area["lines"][candidate][unit] += votes
    return areas


def verify_recap(areas: dict[int, dict], recap: Path, candidate_names: dict[str, str] = CANDIDATES,
                 totals: dict[str, int] = EXPECTED, ballots: int = 2218647) -> None:
    expected = defaultdict(Counter)
    expected_ballots = Counter()
    for row in csv.reader(recap.open(encoding="utf-8-sig", newline="")):
        scope, unit, tally = row[3:6]
        key = "citywide" if scope == "Total for Mayor (Citywide)" else scope.removesuffix(" County")
        if unit in BALLOT_UNITS:
            expected_ballots[key] += number(tally)
            continue
        if unit.endswith("(Write-In)"):
            candidate = "Write-ins"
        else:
            candidate = candidate_names[unit.split(" (")[0]]
        expected[key][candidate] += number(tally)
    actual = defaultdict(Counter)
    actual_ballots = Counter()
    for area in areas.values():
        actual[area["county"]].update(area["votes"])
        actual["citywide"].update(area["votes"])
        actual_ballots[area["county"]] += area["ballots"]
        actual_ballots["citywide"] += area["ballots"]
    assert dict(actual["citywide"]) == totals
    assert actual == expected, "ED totals must match certified borough and citywide recaps"
    assert actual_ballots == expected_ballots, "Ballots must match certified borough and citywide recaps"
    assert sum(a["ballots"] for a in areas.values()) == ballots
    assert sum(actual["citywide"].values()) == sum(totals.values())


def ed_name(code: int, county: str) -> str:
    return f"{BOROUGHS[county]} · AD {code // 1000:02d} ED {code % 1000:03d}"


def aggregate(areas: dict[int, dict], level: str) -> dict[str, dict]:
    output = {}
    for code, area in sorted(areas.items()):
        if area["status"] != "IN-PLAY":
            assert not area["ballots"] and not sum(area["votes"].values())
            continue
        borough = BOROUGHS[area["county"]]
        name = (ed_name(code, area["county"]) if level == "ed" else
                f"Assembly District {code // 1000:02d}" if level == "assembly" else borough)
        target = output.setdefault(name, {"votes": Counter(), "lines": defaultdict(Counter),
                                         "ballots": 0, "boroughs": set(), "codes": []})
        target["votes"].update(area["votes"])
        for candidate, lines in area["lines"].items():
            target["lines"][candidate].update(lines)
        target["ballots"] += area["ballots"]
        target["boroughs"].add(borough)
        target["codes"].append(code)
    return output


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def build(areas: dict[int, dict], boundary_path: Path, out: Path, config: dict | None = None) -> dict:
    config = {"year": 2025, "election_date": "2025-11-04", "certified_date": "2025-12-02",
              "results_page": RESULTS_PAGE, "results_ed_url": ED_URL, "recap_url": RECAP_URL,
              "source_sha256": SHA256, "boundary_release": "25C (August 2025)",
              "boundary_producer": "NYC Department of City Planning",
              "boundary_mirror_url": BOUNDARY_URL, "boundary_commit": BOUNDARY_COMMIT,
              "candidate_totals": EXPECTED, "valid_votes": 2194204, "total_ballots": 2218647,
              "unrecorded": 24443, "boundary_count": 4264,
              "boundary_source_note": "NYC Planning 25C via pinned nycmaps mirror; BOE combined reporting areas dissolved",
              **(config or {})}
    expected = config["candidate_totals"]
    source = json.loads(boundary_path.read_text())
    assert len(source["features"]) == config["boundary_count"]
    geometries = {int(f["properties"]["elect_dist"]): shape(f["geometry"]) for f in source["features"]}
    assert len(geometries) == config["boundary_count"] and set(geometries) <= set(areas)
    combined = defaultdict(list)
    for code, area in areas.items():
        if area["status"] == "IN-PLAY":
            continue
        match = re.fullmatch(r"COMBINED INTO (\d+)/(\d+)", area["status"])
        assert match, area["status"]
        ed, ad = map(int, match.groups())
        target = ad * 1000 + ed
        assert areas[target]["status"] == "IN-PLAY"
        combined[target].append(code)
    # Draw joint reporting areas once, using their component ED polygons.
    reporting_shapes = {}
    for code, area in areas.items():
        if area["status"] != "IN-PLAY":
            continue
        parts = [geometries[c] for c in [code, *combined[code]] if c in geometries]
        if parts:
            reporting_shapes[code] = unary_union(parts)
        else:
            assert not sum(area["votes"].values()), f"Unmapped votes: {code}"
    metadata = {key: value for key, value in config.items() if key not in {"boundary_count", "boundary_source_note"}}
    metadata.update({"raw_ed_count": len(areas), "combined_ed_count": sum(len(v) for v in combined.values()),
                     "boundary_feature_count": len(geometries),
                     "combined_ed_without_polygon": sorted(c for codes in combined.values() for c in codes if c not in geometries),
                     "geographies": {}})
    anomalies = {code: sum(area["votes"].values()) - area["ballots"] for code, area in areas.items()
                 if sum(area["votes"].values()) > area["ballots"]}
    assert anomalies == config.get("known_ballot_anomalies", {}), anomalies
    if anomalies:
        metadata["ballot_count_anomalies"] = [{"ed": code, "ballots": areas[code]["ballots"],
            "candidate_votes": sum(areas[code]["votes"].values())} for code in anomalies]
    for level in ("ed", "assembly", "borough"):
        groups = aggregate(areas, level)
        unmapped_zero = [name for name, g in groups.items() if not any(c in reporting_shapes for c in g["codes"])]
        assert all(not groups[name]["ballots"] and not sum(groups[name]["votes"].values()) for name in unmapped_zero)
        source_area_count = len(groups)
        # Keep non-geographic zero returns in the audit metadata, not false polygons.
        groups = {name: g for name, g in groups.items() if name not in unmapped_zero}
        features = []
        rows = []
        for name, area in groups.items():
            formal = sum(area["votes"].values())
            assert area["ballots"] >= formal or (level == "ed" and area["codes"][0] in anomalies)
            ranked = sorted(((c, v) for c, v in area["votes"].items() if c != "Write-ins"), key=lambda item: (-item[1], item[0]))
            tied = formal > 0 and ranked[0][1] == ranked[1][1]
            status = "no-votes" if not formal else "tied-local" if tied else "official"
            winner = ranked[0][0] if status == "official" else ""
            from_codes = sorted(c for code in area["codes"] for c in combined[code])
            note = ""
            if from_codes and level == "ed":
                note = "Joint BOE reporting area; includes " + ", ".join(f"AD {c // 1000:02d} ED {c % 1000:03d}" for c in from_codes) + ". Component votes are not separately available."
                if config["year"] != 2025 and any(c not in geometries for c in from_codes):
                    note += " Some component polygons are unavailable in the historical map; the available reporting-ED polygon is shown."
            if not formal:
                note += (" " if note else "") + (f"BOE reports {area['ballots']} ballot(s), with no recorded mayoral vote."
                        if area["ballots"] else "BOE reports zero ballots and zero mayoral votes for this election district.")
            if area["ballots"] < formal:
                note += (" " if note else "") + f"BOE source discrepancy: {formal} recorded mayoral votes against {area['ballots']} ballots. Original counts are preserved; the negative accounting balance is not an unrecorded-vote count."
            base = {"district": name, "district_url": config["results_page"], "distribution_url": config["results_ed_url"],
                    "elected_member": winner, "elected_party": winner, "enrolment": "",
                    "formal_votes": formal, "informal_votes": area["ballots"] - formal,
                    "total_votes": area["ballots"], "turnout_pct": "",
                    "majority": ranked[0][1] - ranked[1][1],
                    "electorate_type": "New York City" if level == "borough" else " / ".join(sorted(area["boroughs"])),
                    "constituency_code": str(area["codes"][0]) if level == "ed" else name,
                    "contest_status": status, "result_note": note,
                    "combined_from": ";".join(map(str, from_codes)),
                    "assembly_district": area["codes"][0] // 1000 if level != "borough" else "",
                    "election_district": area["codes"][0] % 1000 if level == "ed" else ""}
            for candidate in expected:
                rows.append({**base, "round_number": 0, "row_type": "first", "candidate": candidate,
                             "candidate_party": candidate, "votes": area["votes"][candidate],
                             "candidate_grouped": "true" if candidate == "Write-ins" else "false",
                             "ballot_lines": json.dumps(dict(area["lines"][candidate]), separators=(",", ":"))})
            parts = [reporting_shapes[c] for c in area["codes"] if c in reporting_shapes]
            if parts:
                simplified = unary_union(parts).simplify(0.000015, preserve_topology=True)
                geometry = mapping(simplified)
                geometry["coordinates"] = rounded(geometry["coordinates"])
                if not shape(geometry).is_valid:
                    geometry = mapping(simplified)
                assert shape(geometry).is_valid
                features.append({"type": "Feature", "properties": {"district": name}, "geometry": geometry})
            else:
                assert not formal
        stem = f"nyc_{config['year']}_mayor_{level}"
        with (out / f"{stem}_fpp.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        (out / f"{stem}_boundaries.geojson").write_text(json.dumps({"type": "FeatureCollection",
            "source": config["boundary_source_note"],
            "features": features}, ensure_ascii=False, separators=(",", ":")) + "\n")
        metadata["geographies"][level] = {"areas": len(groups), "mapped_areas": len(features),
            "source_reporting_areas": source_area_count,
            "zero_vote_areas": sum(not sum(g["votes"].values()) for g in groups.values()),
            "tied_areas": len({r["district"] for r in rows if r["contest_status"] == "tied-local"}),
            "unmapped_zero_vote_areas": unmapped_zero}
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "tmp/nyc")
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    parser.add_argument("--boundaries", type=Path, help="Converted NYC Planning 25C GeoJSON (elect_dist field)")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    for url, filename in [(ED_URL, "general_ed.csv"), (RECAP_URL, "general_recap.csv"),
                          (BOUNDARY_URL, "nyc_election_precincts_sf.rda")]:
        download(url, args.cache / filename, args.refresh)
    boundary_path = args.boundaries or args.cache / "ed_25c.geojson"
    if not args.boundaries and (args.refresh or not boundary_path.exists()):
        subprocess.run(["Rscript", "-e", 'args <- commandArgs(TRUE); load(args[1]); sf::st_write(sf::st_transform(nyc_election_precincts_sf, 4326), args[2], quiet=TRUE, delete_dsn=TRUE)',
                        str(args.cache / "nyc_election_precincts_sf.rda"), str(boundary_path)], check=True)
    areas = load_returns(args.cache / "general_ed.csv")
    verify_recap(areas, args.cache / "general_recap.csv")
    metadata = build(areas, boundary_path, args.out)
    (args.out / "nyc_2025_mayor_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(metadata["geographies"], indent=2))


if __name__ == "__main__":
    main()
