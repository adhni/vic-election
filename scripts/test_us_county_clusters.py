#!/usr/bin/env python3
"""Audit county source joins and cluster outputs independently of the builder."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import cdist
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    assert data["candidate_k"] == [2, 3, 4, 5, 7] and set(data["models"]) == {"2", "3", "4", "5", "7"}
    years = [2008, 2012, 2016, 2020, 2024]
    returns = {}
    for year in years:
        areas = {}
        for row in csv.DictReader((ROOT / f"data/us_{year}_president_county_fpp.csv").open()):
            if row["row_type"] != "first" or row["electorate_type"] in {"Alaska", "Connecticut", "District of Columbia"}:
                continue
            code = row["constituency_code"].replace("US-COUNTY-46113", "US-COUNTY-46102")
            area = areas.setdefault(code, {"name": row["district"], "state": row["electorate_type"], "votes": {}, "formal": int(row["formal_votes"])})
            assert row["candidate_party"] not in area["votes"]
            area["votes"][row["candidate_party"]] = int(row["votes"])
        assert len(areas) == 3103
        for area in areas.values():
            assert sum(area["votes"].values()) == area["formal"]
        returns[year] = areas
    names = sorted(data["counties"])
    codes = [data["counties"][name]["constituency_code"] for name in names]
    assert len(set(codes)) == 3103 and all(set(codes) == set(returns[y]) for y in years)
    assert len({area["state"] for area in data["counties"].values()}) == 48
    x = []
    for name, code in zip(names, codes):
        record = data["counties"][name]
        assert name == returns[2024][code]["name"] and record["state"] == returns[2024][code]["state"]
        shares = []
        for year in years:
            votes = returns[year][code]["votes"]
            assert record["votes"][str(year)] == {"democratic": votes["Democratic"], "republican": votes["Republican"]}
            shares.append(100 * votes["Democratic"] / (votes["Democratic"] + votes["Republican"]))
        np.testing.assert_allclose(record["democratic_share"], shares, rtol=0, atol=5.1e-9)
        x.append(shares)
    x = np.array(x)
    tree = linkage(x, method="ward")
    np.testing.assert_allclose(data["ward_linkage"], tree, rtol=0, atol=5.1e-9)
    assert data["ward_leaf_order"] == names
    distances = cdist(x, x)
    alternatives = {y: linkage(np.delete(x, i, axis=1), method="ward") for i, y in enumerate(years)}
    for k in [2, 3, 4, 5, 7]:
        model = data["models"][str(k)]
        labels = np.array([model["assignments"][name]["group"] for name in names])
        assert adjusted_rand_score(labels, cut_tree(tree, n_clusters=k).ravel()) == 1
        scores = []
        for i in range(len(names)):
            peers = labels == labels[i]
            a = distances[i, peers].sum() / (peers.sum() - 1) if peers.sum() > 1 else 0
            b = min(distances[i, labels == group].mean() for group in range(1, k + 1) if group != labels[i])
            scores.append((b - a) / max(a, b) if peers.sum() > 1 else 0)
        np.testing.assert_allclose([model["assignments"][n]["silhouette"] for n in names], scores, rtol=0, atol=5.1e-9)
        assert abs(model["silhouette"] - np.mean(scores)) < 5.1e-9
        stability = []
        for item in model["leave_one_election_out"]:
            alt = cut_tree(alternatives[item["omitted_year"]], n_clusters=k).ravel()
            assert abs(item["adjusted_rand"] - adjusted_rand_score(labels, alt)) < 5.1e-9
            overlaps = []
            for i in range(len(names)):
                own = labels == labels[i]
                other = alt == alt[i]
                own[i] = other[i] = False
                overlaps.append((own & other).sum() / (own | other).sum() if (own | other).any() else 1)
            stability.append(overlaps)
        np.testing.assert_allclose([model["assignments"][n]["peer_stability"] for n in names], np.mean(stability, axis=0), rtol=0, atol=5.1e-9)
        assert abs(model["mean_adjusted_rand"] - np.mean([v["adjusted_rand"] for v in model["leave_one_election_out"]])) < 5.1e-9
        for group in model["groups"]:
            indexes = np.flatnonzero(labels == group["id"])
            assert group["counties"] == [names[i] for i in indexes] and group["size"] == len(indexes)
            centroid = x[indexes].mean(axis=0)
            np.testing.assert_allclose(group["centroid"], centroid, rtol=0, atol=5.1e-9)
            assert abs(group["mean_democratic_share"] - centroid.mean()) < 5.1e-9
        print(f"PASS k={k}: independent Ward partition, every county silhouette, centroids and five sensitivity refits", flush=True)
    for path, digest in data["source_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    geometry = json.loads((ROOT / "data/us_president_2024_county_boundaries.geojson").read_text())
    mapped = {f["properties"]["constituency_code"]: f["properties"]["district"] for f in geometry["features"]}
    assert all(mapped[code] == name for name, code in zip(names, codes))
    rows = list(csv.DictReader((ROOT / "data/us_county_presidential_clusters.csv").open()))
    assert len(rows) == 3103 * 5
    assert len({(r["county"], r["k"]) for r in rows}) == len(rows)
    for row in rows:
        assignment = data["models"][row["k"]]["assignments"][row["county"]]
        assert int(row["group"]) == assignment["group"]
        assert float(row["peer_stability"]) == assignment["peer_stability"]
        for i, year in enumerate(years):
            assert float(row[f"democratic_two_party_share_{year}"]) == data["counties"][row["county"]]["democratic_share"][i]
    print("PASS 15,515 county-election source joins, boundary coverage, source hashes and 15,515 CSV assignments", flush=True)


if __name__ == "__main__":
    main()
