#!/usr/bin/env python3
"""Audit the 2024 House demographic join and its exploratory statistics."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean, pstdev

from build_us_house_analysis import CORRELATION_FIELDS, DEMO_STEM, FIRST_METRICS, RESULT_FIELDS, ROOT, STEM


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def close(actual: str, expected: float, context: str) -> None:
    require(actual != "" and math.isfinite(float(actual)) and abs(float(actual) - expected) <= 0.000001, f"Numeric mismatch: {context}: {actual} != {expected}")


def ranks(values: list[float]) -> list[float]:
    # Independent rank construction for the small exploratory samples.
    distinct = sorted(set(values))
    counts = Counter(values)
    lookup, before = {}, 0
    for value in distinct:
        lookup[value] = before + (counts[value] + 1) / 2
        before += counts[value]
    return [lookup[value] for value in values]


def correlation(x: list[float], y: list[float]) -> float:
    # An independent calculation using standard-library population standard
    # deviations, including on Python 3.9 (before statistics.correlation).
    covariance = fmean(a * b for a, b in zip(x, y)) - fmean(x) * fmean(y)
    return covariance / (pstdev(x) * pstdev(y))


def validate(data: Path, report: Path) -> None:
    metadata = json.loads((data / f"{STEM}_metadata.json").read_text())
    require((metadata["version"], metadata["election_year"], metadata["acs_year"], metadata["congress"]) == (1, 2024, 2024, 119), "Incorrect analysis vintage")
    for source in metadata["inputs"]:
        payload = (data / source["file"]).read_bytes()
        require(hashlib.sha256(payload).hexdigest() == source["sha256"] and len(payload) == source["bytes"], f"Input checksum mismatch: {source['file']}")
    for output in [*metadata["outputs"], metadata["report"]]:
        path = report if output is metadata["report"] else data / output["file"]
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == output["sha256"] and len(payload) == output["bytes"], f"Output checksum mismatch: {path}")

    demographic_rows = read_csv(data / f"{DEMO_STEM}.csv")
    demographics = {row["constituency_code"]: row for row in demographic_rows}
    results = defaultdict(list)
    for row in read_csv(data / "us_2024_house_fpp.csv"):
        results[row["constituency_code"]].append(row)
    rows = read_csv(data / f"{STEM}.csv")
    joined = {row["constituency_code"]: row for row in rows}
    require(len(rows) == len(joined) == len(demographics) == len(results) == metadata["district_count"] == 435, "Join cardinality is not exactly one row per 435 districts")
    require(joined.keys() == demographics.keys() == results.keys(), "Join lost or added districts")
    boundary = json.loads((data / "us_2024_congressional_boundaries.geojson").read_text())
    require({feature["properties"]["constituency_code"] for feature in boundary["features"]} == joined.keys(), "Boundary join mismatch")
    expected_fields = [*demographic_rows[0], *RESULT_FIELDS]
    require(len(expected_fields) == len(set(expected_fields)) and list(rows[0]) == expected_fields, "Unexpected joined schema")
    dictionary = json.loads((data / f"{DEMO_STEM}_metadata.json").read_text())
    require(metadata["demographic_metrics"] == dictionary["metrics"], "Demographic dictionary changed in join")
    require(set(metadata["result_fields"]) == set(RESULT_FIELDS), "Incomplete result-field dictionary")

    eligible, sensitivity, not_reported = [], [], []
    for code, row in joined.items():
        source, demo = results[code], demographics[code]
        first = source[0]
        require(all(row[field] == value for field, value in demo.items()), f"Demographics / MOEs were altered: {code}")
        for field in ("elected_member", "elected_party", "contest_status"):
            require(row[field] == first[field], f"Source result metadata changed: {code} {field}")
        require(row["election_key"] == "us-house-2024" and row["election_year"] == "2024", f"Wrong election: {code}")
        require((row["district"], row["state"]) == (first["district"], first["electorate_type"]), f"Wrong result identity: {code}")
        d = sum(int(candidate["votes"]) for candidate in source if candidate["candidate_party"] in {"Democratic", "Write-in (Democratic)"})
        r = sum(int(candidate["votes"]) for candidate in source if candidate["candidate_party"] in {"Republican", "Write-in (Republican)"})
        total = sum(int(candidate["votes"]) for candidate in source)
        other = total - d - r
        require([int(row[key]) for key in ("democratic_votes", "republican_votes", "other_votes", "total_candidate_votes")] == [d, r, other, total], f"Party accounting mismatch: {code}")
        require(total == int(first["formal_votes"]), f"Source formal total mismatch: {code}")
        require(row["source_total_votes"] == first["total_votes"] and row["source_informal_votes"] == first["informal_votes"], f"Ballot metadata changed: {code}")
        require(total + int(row["source_informal_votes"]) == int(row["source_total_votes"]), f"Ballot accounting mismatch: {code}")
        require(int(row["candidate_count"]) == len(source), f"Candidate count mismatch: {code}")
        nd = sum(candidate["candidate_party"] == "Democratic" for candidate in source)
        nr = sum(candidate["candidate_party"] == "Republican" for candidate in source)
        require([int(row[key]) for key in ("democratic_named_candidate_count", "republican_named_candidate_count")] == [nd, nr], f"Named candidate count mismatch: {code}")
        for party, group in (("Democratic", "democratic"), ("Republican", "republican")):
            count = sum(int(candidate["votes"]) for candidate in source if candidate["candidate_party"] == f"Write-in ({party})")
            require(int(row[f"{group}_write_in_votes"]) == count, f"Write-in tally mismatch: {code}")
        expected_eligible = nd > 0 and nr > 0 and d > 0 and r > 0 and total > 0 and first["contest_status"] == "official"
        require(row["two_party_analysis_eligible"] == str(expected_eligible).lower(), f"Incorrect analysis eligibility: {code}")
        require(bool(row["two_party_exclusion_reason"]) != expected_eligible, f"Missing or spurious exclusion reason: {code}")
        if expected_eligible:
            eligible.append(row)
            close(row["democratic_two_party_share_pct"], 100 * d / (d + r), f"{code} two-party share")
            close(row["democratic_two_party_margin_pp"], 100 * (d - r) / (d + r), f"{code} signed margin")
        else:
            require(row["democratic_two_party_share_pct"] == row["democratic_two_party_margin_pp"] == "", f"Ineligible race has two-party shares: {code}")
        multiple = nd > 1 or nr > 1
        ranked_choice_state = row["state"] in {"Alaska", "Maine"}
        require(row["multiple_major_party_candidates"] == str(multiple).lower() and row["ranked_choice_state"] == str(ranked_choice_state).lower(), f"Special-contest flags mismatch: {code}")
        if expected_eligible and not multiple and not ranked_choice_state:
            sensitivity.append(row)
        require(row["votes_reported"] == str(total > 0).lower(), f"Incorrect unavailable-votes flag: {code}")
        for group, votes in (("democratic", d), ("republican", r), ("other", other)):
            if total:
                close(row[f"{group}_vote_share_pct"], votes / total * 100, f"{code} {group} share")
            else:
                require(row[f"{group}_vote_share_pct"] == "", f"Zero-total seat has a vote share: {code}")
        if total and len(source) > 1:
            candidate_votes = sorted((int(candidate["votes"]) for candidate in source), reverse=True)
            margin = candidate_votes[0] - candidate_votes[1]
            require(int(row["candidate_margin_votes"]) == margin, f"Candidate margin mismatch: {code}")
            close(row["candidate_margin_pct"], margin / total * 100, f"{code} candidate margin")
        else:
            require(row["candidate_margin_votes"] == row["candidate_margin_pct"] == "", f"Unavailable candidate margin populated: {code}")
        if not total:
            not_reported.append(code)
        missing = [metric for metric in dictionary["metrics"] if row[metric] == ""]
        require(int(row["demographic_missing_metric_count"]) == len(missing) and row["demographic_missing_metrics"].split(";") == (missing or [""]), f"Incorrect demographic missingness: {code}")
    require(len(eligible) == 397 and len(sensitivity) == 389, "Analysis samples changed unexpectedly")
    require(set(not_reported) == {"1220", "4003"}, "Unavailable source-vote districts changed")
    require(Counter(row["elected_party"] for row in rows) == {"Democratic": 215, "Republican": 220}, "Winner totals changed")
    # Party-labelled write-ins are included without changing the source candidate rows.
    require(joined["0402"]["democratic_write_in_votes"] == "22" and joined["0801"]["democratic_write_in_votes"] == "88", "Known party-labelled write-in totals changed")

    samples = {"both_major_parties": eligible, "single_matchup_excluding_ranked_choice_states": sensitivity}
    stats = read_csv(data / f"{STEM}_correlations.csv")
    require(len(stats) == 20 and list(stats[0]) == list(CORRELATION_FIELDS), "Unexpected correlation schema")
    require(set(metadata["exploratory_metrics"]) == set(FIRST_METRICS), "Exploratory metrics changed")
    require({(row["sample"], row["metric"]) for row in stats} == {(sample, metric) for sample in samples for metric in FIRST_METRICS}, "Missing or duplicate correlations")
    for name, selected in samples.items():
        require(metadata["samples"][name]["n"] == len(selected), f"Sample manifest mismatch: {name}")
    for statistic in stats:
        metric = statistic["metric"]
        selected = [row for row in samples[statistic["sample"]] if row[metric] != ""]
        x = [float(row[metric]) for row in selected]
        y = [float(row["democratic_two_party_share_pct"]) for row in selected]
        require(int(statistic["n"]) == len(selected), "Wrong correlation sample size")
        close(statistic["pearson_r"], correlation(x, y), f"{metric} Pearson")
        close(statistic["spearman_rho"], correlation(ranks(x), ranks(y)), f"{metric} Spearman")
        states = defaultdict(list)
        for index, row in enumerate(selected):
            states[row["state"]].append(index)
        x_state, y_state = list(x), list(y)
        for indices in states.values():
            mx, my = sum(x[i] for i in indices) / len(indices), sum(y[i] for i in indices) / len(indices)
            for index in indices:
                x_state[index], y_state[index] = x[index] - mx, y[index] - my
        close(statistic["within_state_pearson_r"], correlation(x_state, y_state), f"{metric} within-state Pearson")
    print("US House analysis passed: 435 exact demographic joins; 397 eligible / 389 sensitivity districts; 20 independently verified correlation rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "us_house_2024_analysis.md")
    args = parser.parse_args()
    validate(args.data, args.report)


if __name__ == "__main__":
    main()
