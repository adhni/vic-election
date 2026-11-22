#!/usr/bin/env python3
"""Build comparable county voting histories from existing compiled returns."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import sklearn
from scipy.cluster.hierarchy import linkage

from build_us_state_clusters import YEARS, build_models, rounded

ROOT = Path(__file__).resolve().parents[1]


def canonical(code):
    # Same identifier harmonization used by the county demographics builder.
    return "US-COUNTY-46102" if code == "US-COUNTY-46113" else code


def load_features(root=ROOT):
    returns, hashes, excluded = {}, {}, {}
    for year in YEARS:
        path = root / f"data/us_{year}_president_county_fpp.csv"
        hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        areas = {}
        for row in csv.DictReader(path.open(encoding="utf-8-sig", newline="")):
            if row["row_type"] != "first":
                continue
            code = canonical(row["constituency_code"])
            region = row["electorate_type"]
            if region in {"Alaska", "Connecticut", "District of Columbia"}:
                excluded[row["district"]] = region
                continue
            assert row["contest_status"] == "compiled", (year, code)
            area = areas.setdefault(code, {"district": row["district"], "state": region, "votes": {}, "formal": int(row["formal_votes"])})
            assert row["candidate_party"] not in area["votes"], (year, code)
            area["votes"][row["candidate_party"]] = int(row["votes"])
            assert int(row["formal_votes"]) == area["formal"] >= 0
        for code, area in areas.items():
            assert set(area["votes"]) == {"Democratic", "Republican", "Other"}, (year, code)
            assert area["votes"]["Democratic"] > 0 and area["votes"]["Republican"] > 0
            assert area["votes"]["Other"] >= 0
            assert sum(area["votes"].values()) == area["formal"], (year, code)
        returns[year] = areas
    codes = set(returns[YEARS[0]])
    assert len(codes) == 3103
    assert all(set(returns[y]) == codes for y in YEARS), "Inconsistent county coverage"
    # Latest names and boundaries; join by identifier, not spelling.
    names = sorted(returns[2024][code]["district"] for code in codes)
    by_name = {area["district"]: code for code, area in returns[2024].items()}
    assert len(by_name) == len(codes)
    x = np.array([[100 * returns[y][by_name[name]]["votes"]["Democratic"] /
        (returns[y][by_name[name]]["votes"]["Democratic"] + returns[y][by_name[name]]["votes"]["Republican"])
        for y in YEARS] for name in names], dtype=float)
    boundary = root / "data/us_president_2024_county_boundaries.geojson"
    hashes[str(boundary.relative_to(root))] = hashlib.sha256(boundary.read_bytes()).hexdigest()
    geo = json.loads(boundary.read_text())
    mapped = {canonical(f["properties"]["constituency_code"]): f["properties"]["district"] for f in geo["features"]}
    assert all(mapped[code] == returns[2024][code]["district"] for code in codes)
    return names, x, returns, by_name, hashes, excluded


def build(root=ROOT):
    names, x, returns, by_name, hashes, excluded = load_features(root)
    models = build_models(names, x, "counties")
    result = {
        "method": "Ward agglomerative hierarchical clustering", "distance": "Euclidean",
        "feature": "Democratic share of Democratic + Republican presidential votes, percent",
        "years": YEARS, "county_count": len(names), "state_count": 48,
        "default_k": 4, "candidate_k": [2, 3, 4, 5, 7],
        "weighting": "Each county reporting area and election have equal weight. No population weighting or per-county standardization.",
        "coverage_note": "3,103 comparable counties and county equivalents across 48 states. Connecticut is excluded because reporting areas changed. Alaska has statewide totals only. DC is excluded. Existing source combinations of Bedford city/county and Kansas City/Jackson are retained.",
        "excluded_reporting_areas": excluded,
        "identifier_policy": "Shannon County 46113 is joined to Oglala Lakota County 46102. All places use 2024 names and boundaries; joins use identifiers, not name spelling.",
        "source_status": "Compiled county returns, not independently certified by this analysis.",
        "stability_method": "Refit omitting each election; adjusted Rand agreement and mean Jaccard overlap of peers.",
        "source_sha256": hashes, "software": {"scikit_learn": sklearn.__version__, "numpy": np.__version__},
        "counties": {name: {
            "constituency_code": by_name[name], "state": returns[2024][by_name[name]]["state"],
            "democratic_share": [rounded(v) for v in x[i]],
            "votes": {str(y): {"democratic": returns[y][by_name[name]]["votes"]["Democratic"],
                                "republican": returns[y][by_name[name]]["votes"]["Republican"]} for y in YEARS}
        } for i, name in enumerate(names)},
        "models": models, "ward_leaf_order": names,
        "ward_linkage": [[rounded(v) for v in row] for row in linkage(x, method="ward", metric="euclidean")]
    }
    (root / "data/us_county_presidential_clusters.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    with (root / "data/us_county_presidential_clusters.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["county", "state", "constituency_code", "k", "group", *[f"democratic_two_party_share_{y}" for y in YEARS], "silhouette", "peer_stability"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for k, model in models.items():
            for name, assignment in model["assignments"].items():
                record = result["counties"][name]
                writer.writerow({"county": name, "state": record["state"], "constituency_code": record["constituency_code"],
                    "k": k, **assignment, **{f"democratic_two_party_share_{y}": record["democratic_share"][i] for i, y in enumerate(YEARS)}})
    for k, model in models.items():
        print(f"k={k}: separation={model['silhouette']:.3f}, stability={model['mean_adjusted_rand']:.3f}, sizes={[g['size'] for g in model['groups']]}", flush=True)
    return result


if __name__ == "__main__":
    build()
