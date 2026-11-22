#!/usr/bin/env python3
"""Independently audit inputs, Ward partitions, scores, profiles and exports."""
import csv
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import cut_tree, linkage
from sklearn.metrics import adjusted_rand_score

from build_us_state_clusters import build

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / "data/us_state_presidential_clusters.json").read_text())
    names = sorted(data["states"])
    assert len(names) == 50 and "District of Columbia" not in names
    assert data["years"] == [2008, 2012, 2016, 2020, 2024]
    assert data["default_k"] == 4 and data["candidate_k"] == [2, 3, 4, 5, 7]
    assert set(data["models"]) == {"2", "3", "4", "5", "7"}
    assert data["ward_leaf_order"] == names
    expected = defaultdict(dict)
    for year in data["years"]:
        path = ROOT / f"data/us_{year}_president_state_fpp.csv"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == data["source_sha256"][str(path.relative_to(ROOT))]
        totals = defaultdict(lambda: defaultdict(int))
        for row in csv.DictReader(path.open()):
            if row["row_type"] == "first" and row["district"] in names:
                totals[row["district"]][row["candidate_party"]] += int(row["votes"])
        assert set(totals) == set(names)
        for name, values in totals.items():
            assert values["Democratic"] > 0 and values["Republican"] > 0
            assert data["states"][name]["votes"][str(year)] == {"democratic": values["Democratic"], "republican": values["Republican"]}
            expected[name][year] = 100 * values["Democratic"] / (values["Democratic"] + values["Republican"])
    x = np.array([[expected[name][year] for year in data["years"]] for name in names])
    assert np.allclose(x, [data["states"][name]["democratic_share"] for name in names], atol=1e-8)
    tree = linkage(x, method="ward")
    assert np.allclose(tree, data["ward_linkage"], atol=1e-7)
    distances = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
    for k in [2, 3, 4, 5, 7]:
        model = data["models"][str(k)]
        labels = np.array([model["assignments"][name]["group"] for name in names])
        independent = cut_tree(tree, n_clusters=k).ravel()
        assert adjusted_rand_score(labels, independent) == 1.0
        assert len(set(labels)) == k
        assert set(model["assignments"]) == set(names)
        assert sum(group["size"] for group in model["groups"]) == 50
        means = []
        for group in model["groups"]:
            selected = labels == group["id"]
            assert group["states"] == [names[i] for i in np.flatnonzero(selected)]
            centroid = x[selected].mean(axis=0)
            assert np.allclose(centroid, group["centroid"], atol=1e-8)
            assert abs(group["mean_democratic_share"] - centroid.mean()) < 1e-7
            assert abs(group["change_2008_2024_pp"] - (centroid[-1] - centroid[0])) < 1e-7
            means.append(centroid.mean())
        assert means == sorted(means)
        scores = []
        for i, name in enumerate(names):
            own = (labels == labels[i]) & (np.arange(50) != i)
            a = distances[i, own].mean() if own.any() else 0
            b = min(distances[i, labels == other].mean() for other in set(labels) if other != labels[i])
            score = (b - a) / max(a, b) if own.any() else 0
            assert abs(score - model["assignments"][name]["silhouette"]) < 1e-7
            scores.append(score)
        assert abs(np.mean(scores) - model["silhouette"]) < 1e-7
        stability = []
        peer_scores = []
        for column, year in enumerate(data["years"]):
            alternative = cut_tree(linkage(np.delete(x, column, axis=1), method="ward"), n_clusters=k).ravel()
            ari = adjusted_rand_score(labels, alternative)
            assert abs(ari - model["leave_one_election_out"][column]["adjusted_rand"]) < 1e-7
            stability.append(ari)
            peers = []
            for i in range(50):
                a = set(np.flatnonzero(labels == labels[i])) - {i}
                b = set(np.flatnonzero(alternative == alternative[i])) - {i}
                peers.append(len(a & b) / len(a | b) if a | b else 1)
            peer_scores.append(peers)
        assert abs(np.mean(stability) - model["mean_adjusted_rand"]) < 1e-7
        assert np.allclose(np.mean(peer_scores, axis=0), [model["assignments"][name]["peer_stability"] for name in names], atol=1e-8)
        print(f"PASS k={k}: independent Ward partition, silhouette, centroids and five sensitivity refits")
    rows = list(csv.DictReader((ROOT / "data/us_state_presidential_clusters.csv").open()))
    assert len(rows) == 250 and len({(r["state"], r["k"]) for r in rows}) == 250
    for row in rows:
        assert int(row["group"]) == data["models"][row["k"]]["assignments"][row["state"]]["group"]
        for i, year in enumerate(data["years"]):
            assert float(row[f"democratic_two_party_share_{year}"]) == data["states"][row["state"]]["democratic_share"][i]
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        (temporary / "data").mkdir()
        for relative in data["source_sha256"]:
            shutil.copyfile(ROOT / relative, temporary / relative)
        assert build(temporary) == data
    print("PASS exact source joins, 250 state-election observations, 250 CSV assignments and deterministic rebuild")


if __name__ == "__main__":
    main()
