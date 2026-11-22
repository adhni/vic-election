#!/usr/bin/env python3
"""Build certified 2017/2021 NYC mayoral general elections from pinned inputs.

Only geometry is read from the historical map mirror. All candidate counts,
ballot lines, joint reporting and ballot totals come directly from NYC BOE.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from build_nyc_mayor_2025 import ROOT, build, download, load_returns, verify_recap

MIRROR_COMMIT = "325cee637986542918fde0ff156cb2fd685229b8"
MIRROR_BASE = f"https://raw.githubusercontent.com/joshgreenman1973/nyc-election-archive/{MIRROR_COMMIT}/docs/"
SOURCES = {
    2021: {
        "election_date": "2021-11-02", "certified_date": "2021-11-30",
        "report_id": "00000200000", "date_folder": "20211102General%20Election",
        "boundary_release": "21A (February 2021), archived geometry mirror",
        "candidate_names": {"Eric L. Adams": "Eric Adams", "Curtis A. Sliwa": "Curtis Sliwa",
            "Catherine Rojas": "Catherine Rojas", "William A. Pepitone": "William Pepitone",
            "Quanda S. Francis": "Quanda Francis", "Stacey H. Prussman": "Stacey Prussman",
            "Raja Michael Flores": "Raja Michael Flores", "Fernando Mateo": "Fernando Mateo",
            "Skiboky Stora": "Skiboky Stora", "Scattered": "Write-ins"},
        "candidate_totals": {"Eric Adams": 753801, "Curtis Sliwa": 312385, "Catherine Rojas": 27982,
            "William Pepitone": 12575, "Quanda Francis": 3792, "Stacey Prussman": 3189,
            "Raja Michael Flores": 2387, "Fernando Mateo": 1870, "Skiboky Stora": 264, "Write-ins": 7013},
        "total_ballots": 1149172,
        "sha256": {"2021_ed.csv": "5a1664de6e1862eb277ab795ac5b479fb2ad96eff2a257fb13af57894aa27ece",
            "2021_recap.csv": "280924eaee4c9ea829f1d83cc998c8c8d8463a0cf6b110327e8b2a9f77d641fd",
            "2021_boundaries.geojson": "2c3f9c6c64bd31e5547084a788d24ca514144b3b2ccc12d0dab52fbef490ab53",
            "2021_primary_boundaries.geojson": "69c3df7cb2418f33e9fd816fd7c53187878814bd403473768a7c9bb4cc1c9d77"},
    },
    2017: {
        "election_date": "2017-11-07", "certified_date": "2019-07-16",
        "report_id": "00001100000", "date_folder": "20171107General%20Election",
        "boundary_release": "Historical 2017 NYC Planning mirror; original release unrecorded",
        "candidate_names": {"Bill de Blasio": "Bill de Blasio", "Nicole Malliotakis": "Nicole Malliotakis",
            "Sal F. Albanese": "Sal Albanese", "Akeem Browder": "Akeem Browder",
            "Michael Tolkin": "Michael Tolkin", "Bo Dietl": "Bo Dietl", "Aaron Commey": "Aaron Commey",
            "Scattered": "Write-ins"},
        "candidate_totals": {"Bill de Blasio": 760112, "Nicole Malliotakis": 316948, "Sal Albanese": 24484,
            "Akeem Browder": 16536, "Michael Tolkin": 11309, "Bo Dietl": 11163, "Aaron Commey": 2770, "Write-ins": 5343},
        "total_ballots": 1166314,
        "sha256": {"2017_ed.csv": "5a19e0c6111ceb56f355dba60b91fac5e0723e74d39bfb5261227219821b0ae0",
            "2017_recap.csv": "ca6a2dfd04d20dc8656f1ee4275a96ee5378a0e3b3267ee01fcecd8c8970a21f",
            "2017_manhattan_ed.csv": "a87f723d9af1c2563505150b59a500048b3f3fce0dd99294eb98e76b7c6abcf0",
            "2017_kings_ed.csv": "eb8bcaaa5dc26b8f842671a20b5e8f0fbefd0872259adfbfd2b7ac1b19e1e0cd",
            "2017_boundaries.geojson": "dfb2934fbca98b730abfcc189a64bfe8dc81501327f08f433aa39d51707b9c3c"},
    },
}


def source_urls(year: int) -> dict[str, str]:
    spec = SOURCES[year]
    base = f"https://www.vote.nyc/sites/default/files/pdf/election_results/{year}/{spec['date_folder']}/{spec['report_id']}Citywide%20Mayor%20Citywide%20"
    urls = {f"{year}_ed.csv": base + "EDLevel.csv", f"{year}_recap.csv": base + "Recap.csv",
            f"{year}_boundaries.geojson": MIRROR_BASE + f"results_{year}_general_mayor.geojson"}
    if year == 2021:
        urls["2021_primary_boundaries.geojson"] = MIRROR_BASE + "results_2021.geojson"
    else:
        urls["2017_manhattan_ed.csv"] = "https://www.vote.nyc/sites/default/files/pdf/election_results/2017/20171107General%20Election/00101100000New%20York%20Mayor%20Citywide%20EDLevel.csv"
        urls["2017_kings_ed.csv"] = "https://www.vote.nyc/sites/default/files/pdf/election_results/2017/20171107General%20Election/00301100000Kings%20Mayor%20Citywide%20EDLevel.csv"
    return urls


def prepare_geometry(year: int, cache: Path) -> tuple[Path, list[int]]:
    """Strip all third-party result properties; merge only identical-vintage shapes."""
    filenames = [f"{year}_boundaries.geojson"]
    if year == 2021:
        filenames.append("2021_primary_boundaries.geojson")
    features = {}
    for filename in filenames:
        for feature in json.loads((cache / filename).read_text())["features"]:
            code = int(feature["properties"]["ed"])
            if code in features:
                assert feature["geometry"] == features[code]["geometry"]
            features[code] = {"type": "Feature", "properties": {"elect_dist": code}, "geometry": feature["geometry"]}
    repaired = []
    for code, feature in features.items():
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            valid = make_valid(geometry)
            if valid.geom_type == "GeometryCollection":
                valid = unary_union([g for g in valid.geoms if g.geom_type in {"Polygon", "MultiPolygon"}])
            assert valid.geom_type in {"Polygon", "MultiPolygon"} and valid.is_valid and not valid.is_empty
            assert abs(valid.area - geometry.area) < 0.000001, f"Material boundary repair: {code}"
            feature["geometry"] = mapping(valid)
            repaired.append(code)
    path = cache / f"{year}_geometry_only.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": list(features.values())}, separators=(",", ":")))
    return path, sorted(repaired)


def build_year(year: int, cache: Path, out: Path, refresh: bool = False) -> dict:
    spec = SOURCES[year]
    urls = source_urls(year)
    for filename, url in urls.items():
        download(url, cache / filename, refresh, spec["sha256"][filename])
    geometry, repaired = prepare_geometry(year, cache)
    areas = load_returns(cache / f"{year}_ed.csv", spec["candidate_names"])
    if year == 2017:
        # BOE's borough file includes a correction missing from its citywide ED
        # file. Replace the complete borough from that official source; do not
        # manufacture a one-vote adjustment or assign a citywide residual.
        manhattan = load_returns(cache / "2017_manhattan_ed.csv", spec["candidate_names"])
        assert set(manhattan) == {code for code, area in areas.items() if area["county"] == "New York"}
        changed = [code for code, area in manhattan.items() if area != areas[code]]
        assert changed == [76067], changed
        assert manhattan[76067]["ballots"] - areas[76067]["ballots"] == 1
        assert manhattan[76067]["votes"]["Nicole Malliotakis"] - areas[76067]["votes"]["Nicole Malliotakis"] == 1
        areas.update(manhattan)
        kings = load_returns(cache / "2017_kings_ed.csv", spec["candidate_names"])
        assert all(area == areas[code] for code, area in kings.items())
    verify_recap(areas, cache / f"{year}_recap.csv", spec["candidate_names"], spec["candidate_totals"], spec["total_ballots"])
    valid = sum(spec["candidate_totals"].values())
    config = {"year": year, "election_date": spec["election_date"], "certified_date": spec["certified_date"],
              "results_page": f"https://www.vote.nyc/page/election-results-summary-{year}",
              "results_ed_url": urls[f"{year}_ed.csv"], "recap_url": urls[f"{year}_recap.csv"],
              "source_sha256": spec["sha256"], "source_urls": urls,
              "boundary_release": spec["boundary_release"], "boundary_commit": MIRROR_COMMIT,
              "boundary_mirror_url": urls[f"{year}_boundaries.geojson"],
              "repaired_boundary_ids": repaired,
              "boundary_provenance_note": "Only archived geometry is used. The mirror omits some zero-vote and combined ED polygons. Original 2017 release is not recorded; 2021 is identified as 21A by the mirror. No claim of boundary equivalence across election years.",
              "boundary_count": len(json.loads(geometry.read_text())["features"]),
              "boundary_source_note": f"NYC Planning historical {year} geometry via pinned NYC election archive; original 2017 release unrecorded; available combined components dissolved",
              "candidate_totals": spec["candidate_totals"], "valid_votes": valid,
              "total_ballots": spec["total_ballots"], "unrecorded": spec["total_ballots"] - valid}
    if year == 2017:
        config["known_ballot_anomalies"] = {57057: 1}
        config["source_corrections"] = [{"ed": 76067, "source": urls["2017_manhattan_ed.csv"],
            "note": "Official Manhattan ED file supersedes the stale citywide ED return: +1 absentee ballot and +1 Nicole Malliotakis Republican vote. Borough and citywide certification recaps both reconcile."}]
    metadata = build(areas, geometry, out, config)
    (out / f"nyc_{year}_mayor_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(f"{year}: " + json.dumps(metadata["geographies"], ensure_ascii=False), flush=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=[2017, 2021], help="Default: both elections")
    parser.add_argument("--cache", type=Path, default=ROOT / "tmp/nyc/history")
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    for year in [args.year] if args.year else [2021, 2017]:
        build_year(year, args.cache, args.out, args.refresh)


if __name__ == "__main__":
    main()
