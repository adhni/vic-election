#!/usr/bin/env python3
"""Cluster 50 states by five presidential Democratic two-party vote shares."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import sklearn
from scipy.cluster.hierarchy import linkage
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_samples, silhouette_score

ROOT = Path(__file__).resolve().parents[1]
YEARS = [2008, 2012, 2016, 2020, 2024]
PALETTE = ["#7851a9", "#c57928", "#288b87", "#4267b2", "#bd4c71", "#6b7f30", "#8c564b"]


def load_features(root: Path = ROOT):
    returns, hashes = {}, {}
    for year in YEARS:
        path = root / f"data/us_{year}_president_state_fpp.csv"
        hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        states = defaultdict(lambda: defaultdict(int))
        for row in csv.DictReader(path.open(encoding="utf-8-sig", newline="")):
            if row["district"] == "District of Columbia" or row["row_type"] != "first":
                continue
            assert row["contest_status"] == "official"
            if row["candidate_party"] in {"Democratic", "Republican"}:
                states[row["district"]][row["candidate_party"]] += int(row["votes"])
        assert len(states) == 50
        assert all(v["Democratic"] > 0 and v["Republican"] > 0 for v in states.values())
        returns[year] = states
    names = sorted(returns[YEARS[0]])
    assert all(set(returns[y]) == set(names) for y in YEARS)
    x = np.array([[100 * returns[y][s]["Democratic"] /
                   (returns[y][s]["Democratic"] + returns[y][s]["Republican"])
                   for y in YEARS] for s in names], dtype=float)
    return names, x, returns, hashes


def fit(x, k):
    labels = AgglomerativeClustering(n_clusters=k, metric="euclidean", linkage="ward").fit_predict(x)
    # IDs are display ranks by mean Democratic share, never partisan labels.
    ordered = sorted(set(labels), key=lambda label: (float(x[labels == label].mean()), tuple(np.where(labels == label)[0])))
    relabel = {old: new + 1 for new, old in enumerate(ordered)}
    return np.array([relabel[label] for label in labels])


def rounded(value):
    return round(float(value), 8)


def build_models(names, x, member_key="states"):
    models = {}
    for k in [2, 3, 4, 5, 7]:
        labels = fit(x, k)
        scores = silhouette_samples(x, labels, metric="euclidean")
        omissions, agreement = [], []
        for column, year in enumerate(YEARS):
            alternative = fit(np.delete(x, column, axis=1), k)
            omissions.append({"omitted_year": year, "adjusted_rand": rounded(adjusted_rand_score(labels, alternative))})
            values = []
            for i in range(len(names)):
                original_peers = set(np.flatnonzero(labels == labels[i])) - {i}
                alternative_peers = set(np.flatnonzero(alternative == alternative[i])) - {i}
                union = original_peers | alternative_peers
                values.append(len(original_peers & alternative_peers) / len(union) if union else 1.0)
            agreement.append(values)
        peer_stability = np.mean(agreement, axis=0)
        groups = []
        for group in range(1, k + 1):
            indexes = np.flatnonzero(labels == group)
            centroid = x[indexes].mean(axis=0)
            groups.append({"id": group, "color": PALETTE[group - 1], "size": len(indexes),
                           member_key: [names[i] for i in indexes],
                           "centroid": [rounded(v) for v in centroid],
                           "mean_democratic_share": rounded(centroid.mean()),
                           "change_2008_2024_pp": rounded(centroid[-1] - centroid[0]),
                           "mean_silhouette": rounded(scores[indexes].mean())})
        models[str(k)] = {"k": k, "silhouette": rounded(silhouette_score(x, labels, metric="euclidean")),
            "mean_adjusted_rand": rounded(np.mean([item["adjusted_rand"] for item in omissions])),
            "min_adjusted_rand": min(item["adjusted_rand"] for item in omissions),
            "leave_one_election_out": omissions, "groups": groups,
            "assignments": {name: {"group": int(labels[i]), "silhouette": rounded(scores[i]),
                                   "peer_stability": rounded(peer_stability[i])} for i, name in enumerate(names)}}
    return models


def build(root: Path = ROOT):
    names, x, returns, hashes = load_features(root)
    models = build_models(names, x)
    result = {
        "method": "Ward agglomerative hierarchical clustering", "distance": "Euclidean",
        "feature": "Democratic share of Democratic + Republican presidential votes, percent",
        "years": YEARS, "state_count": 50, "default_k": 4, "candidate_k": [2, 3, 4, 5, 7],
        "weighting": "Each state and each election have equal weight. No population weighting or per-state standardization.",
        "excluded": ["District of Columbia", "Third-party votes", "Provisional 2026 results"],
        "stability_method": "Refit after omitting each election. Adjusted Rand measures whole-partition agreement; per-state peer stability is mean Jaccard overlap of co-clustered states across the five refits.",
        "source_sha256": hashes, "software": {"scikit_learn": sklearn.__version__, "numpy": np.__version__},
        "states": {s: {"democratic_share": [rounded(v) for v in x[i]],
                       "votes": {str(y): {"democratic": returns[y][s]["Democratic"], "republican": returns[y][s]["Republican"]} for y in YEARS}}
                   for i, s in enumerate(names)},
        "models": models, "ward_leaf_order": names,
        "ward_linkage": [[rounded(v) for v in row] for row in linkage(x, method="ward", metric="euclidean")],
    }
    path = root / "data/us_state_presidential_clusters.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    csv_path = root / "data/us_state_presidential_clusters.csv"
    fields = ["state", "k", "group", *[f"democratic_two_party_share_{y}" for y in YEARS], "silhouette", "peer_stability"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for k, model in models.items():
            for name, assignment in model["assignments"].items():
                writer.writerow({"state": name, "k": k, **assignment,
                    **{f"democratic_two_party_share_{y}": result["states"][name]["democratic_share"][i] for i, y in enumerate(YEARS)}})
    for k, model in models.items():
        print(f"k={k}: silhouette={model['silhouette']:.3f}, leave-one-election-out ARI={model['mean_adjusted_rand']:.3f}; group sizes={[g['size'] for g in model['groups']]}")
    return result


if __name__ == "__main__":
    build()
