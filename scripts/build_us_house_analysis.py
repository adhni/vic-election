#!/usr/bin/env python3
"""Join 2024 House results and ACS indicators; produce an exploratory district report.

Reads only local, prepared files. Uses Python's standard library and preserves
source vote totals, demographic missing values and margins of error.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STEM = "us_2024_house_analysis"
DEMO_STEM = "us_2024_house_demographics"
ELECTION_KEY = "us-house-2024"
PARTY_GROUPS = {
    "Democratic": "democratic", "Write-in (Democratic)": "democratic",
    "Republican": "republican", "Write-in (Republican)": "republican",
}
FIRST_METRICS = (
    "bachelors_plus_pct", "median_household_income", "poverty_pct",
    "median_age", "age_65_plus_pct", "homeownership_pct",
    "white_non_hispanic_pct", "black_non_hispanic_pct",
    "asian_non_hispanic_pct", "hispanic_pct",
)
RESULT_FIELDS = (
    "election_key", "election_year", "elected_member", "elected_party", "contest_status",
    "candidate_count", "democratic_named_candidate_count", "republican_named_candidate_count",
    "democratic_votes", "republican_votes", "other_votes",
    "democratic_write_in_votes", "republican_write_in_votes",
    "total_candidate_votes", "source_total_votes", "source_informal_votes", "votes_reported",
    "democratic_vote_share_pct", "republican_vote_share_pct", "other_vote_share_pct",
    "democratic_two_party_share_pct", "democratic_two_party_margin_pp",
    "candidate_margin_votes", "candidate_margin_pct",
    "two_party_analysis_eligible", "two_party_exclusion_reason",
    "multiple_major_party_candidates", "ranked_choice_state",
    "demographic_missing_metric_count", "demographic_missing_metrics",
)
CORRELATION_FIELDS = (
    "sample", "metric", "label", "n", "pearson_r", "spearman_rho", "within_state_pearson_r",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def formatted(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}".rstrip("0").rstrip(".")


def named_count(rows: list[dict], party: str) -> int:
    return sum(row["candidate_party"] == party for row in rows)


def summarize_result(rows: list[dict]) -> dict:
    """Aggregate every candidate once, including explicitly party-labelled write-ins."""
    if not rows:
        raise ValueError("Cannot summarize an empty contest")
    metadata_fields = ("district", "constituency_code", "electorate_type", "elected_member",
                       "elected_party", "contest_status", "formal_votes", "total_votes", "informal_votes")
    for field in metadata_fields:
        if len({row[field] for row in rows}) != 1:
            raise ValueError(f"Inconsistent contest metadata: {rows[0]['district']} {field}")
    if len({row["candidate"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate candidate: {rows[0]['district']}")
    votes = Counter()
    write_ins = Counter()
    for row in rows:
        if row["row_type"] != "first" or row["round_number"] != "0":
            raise ValueError("Expected compact, round-zero source candidate totals")
        count = int(row["votes"])
        if count < 0:
            raise ValueError("Negative candidate votes")
        group = PARTY_GROUPS.get(row["candidate_party"], "other")
        votes[group] += count
        if row["candidate_party"].startswith("Write-in ("):
            write_ins[group] += count
    first = rows[0]
    total = sum(votes.values())
    if total != int(first["formal_votes"]) or total + int(first["informal_votes"]) != int(first["total_votes"]):
        raise ValueError(f"Source ballot accounting failed: {first['district']}")
    democratic_count = named_count(rows, "Democratic")
    republican_count = named_count(rows, "Republican")
    reasons = []
    if total == 0:
        reasons.append("candidate_vote_totals_unavailable")
    if first["contest_status"] != "official":
        reasons.append(first["contest_status"])
    if not democratic_count:
        reasons.append("no_named_democratic_candidate")
    if not republican_count:
        reasons.append("no_named_republican_candidate")
    if democratic_count and not votes["democratic"]:
        reasons.append("no_positive_democratic_votes")
    if republican_count and not votes["republican"]:
        reasons.append("no_positive_republican_votes")
    eligible = not reasons
    two_party_total = votes["democratic"] + votes["republican"]
    two_party_share = votes["democratic"] / two_party_total * 100 if eligible else None
    ranked = sorted((int(row["votes"]) for row in rows), reverse=True)
    margin = ranked[0] - ranked[1] if total > 0 and len(ranked) >= 2 else None
    result = {
        "election_key": ELECTION_KEY, "election_year": 2024,
        "elected_member": first["elected_member"], "elected_party": first["elected_party"],
        "contest_status": first["contest_status"], "candidate_count": len(rows),
        "democratic_named_candidate_count": democratic_count,
        "republican_named_candidate_count": republican_count,
        "democratic_write_in_votes": write_ins["democratic"],
        "republican_write_in_votes": write_ins["republican"],
        "total_candidate_votes": total, "source_total_votes": int(first["total_votes"]),
        "source_informal_votes": int(first["informal_votes"]), "votes_reported": str(total > 0).lower(),
        "democratic_two_party_share_pct": formatted(two_party_share),
        "democratic_two_party_margin_pp": formatted(2 * two_party_share - 100) if eligible else "",
        "candidate_margin_votes": "" if margin is None else margin,
        "candidate_margin_pct": formatted(margin / total * 100) if margin is not None else "",
        "two_party_analysis_eligible": str(eligible).lower(),
        "two_party_exclusion_reason": ";".join(reasons),
        "multiple_major_party_candidates": str(democratic_count > 1 or republican_count > 1).lower(),
        "ranked_choice_state": str(first["electorate_type"] in {"Alaska", "Maine"}).lower(),
    }
    for group in ("democratic", "republican", "other"):
        result[f"{group}_votes"] = votes[group]
        result[f"{group}_vote_share_pct"] = formatted(votes[group] / total * 100) if total else ""
    return result


def joined_rows(results: list[dict], demographics: list[dict], metrics: dict) -> list[dict]:
    grouped = defaultdict(list)
    for row in results:
        grouped[row["constituency_code"]].append(row)
    demographic_rows = {row["constituency_code"]: row for row in demographics}
    if len(demographic_rows) != len(demographics):
        raise ValueError("Duplicate demographic district code")
    if grouped.keys() != demographic_rows.keys():
        raise ValueError(f"Results / demographics mismatch: {sorted(grouped.keys() ^ demographic_rows.keys())}")
    output = []
    for code, candidates in sorted(grouped.items()):
        demo = demographic_rows[code]
        if (demo["district"], demo["state"]) != (candidates[0]["district"], candidates[0]["electorate_type"]):
            raise ValueError(f"District identity mismatch: {code}")
        if (demo["acs_year"], demo["congress"], demo["census_geo_id"]) != ("2024", "119", f"5001900US{code}"):
            raise ValueError(f"Incorrect demographic vintage: {code}")
        missing = [metric for metric in metrics if demo[metric] == ""]
        output.append({**demo, **summarize_result(candidates),
                       "demographic_missing_metric_count": len(missing), "demographic_missing_metrics": ";".join(missing)})
    return output


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("Correlation vectors differ in length")
    if len(x) < 3:
        return None
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    dx, dy = [value - mx for value in x], [value - my for value in y]
    denominator = math.sqrt(math.fsum(value * value for value in dx) * math.fsum(value * value for value in dy))
    if denominator == 0:
        return None
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(dx, dy)) / denominator))


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        for index in order[start:end]:
            ranks[index] = (start + 1 + end) / 2
        start = end
    return ranks


def sample_rows(rows: list[dict], sample: str) -> list[dict]:
    eligible = [row for row in rows if row["two_party_analysis_eligible"] == "true"]
    if sample == "both_major_parties":
        return eligible
    if sample == "single_matchup_excluding_ranked_choice_states":
        return [row for row in eligible if row["multiple_major_party_candidates"] == "false" and row["ranked_choice_state"] == "false"]
    raise ValueError(f"Unknown analysis sample: {sample}")


def correlations(rows: list[dict], definitions: dict) -> list[dict]:
    output = []
    for sample in ("both_major_parties", "single_matchup_excluding_ranked_choice_states"):
        selected = sample_rows(rows, sample)
        for metric in FIRST_METRICS:
            complete = [row for row in selected if row[metric] != ""]
            x = [float(row[metric]) for row in complete]
            y = [float(row["democratic_two_party_share_pct"]) for row in complete]
            groups = defaultdict(list)
            for index, row in enumerate(complete):
                groups[row["state"]].append(index)
            state_x, state_y = [0.0] * len(x), [0.0] * len(y)
            for indices in groups.values():
                mean_x = math.fsum(x[i] for i in indices) / len(indices)
                mean_y = math.fsum(y[i] for i in indices) / len(indices)
                for index in indices:
                    state_x[index], state_y[index] = x[index] - mean_x, y[index] - mean_y
            output.append({"sample": sample, "metric": metric, "label": definitions[metric]["label"], "n": len(x),
                           "pearson_r": formatted(pearson(x, y)),
                           "spearman_rho": formatted(pearson(average_ranks(x), average_ranks(y))),
                           "within_state_pearson_r": formatted(pearson(state_x, state_y))})
    return output


def education_residuals(rows: list[dict]) -> list[dict]:
    selected = [row for row in sample_rows(rows, "both_major_parties") if row["bachelors_plus_pct"] != ""]
    x = [float(row["bachelors_plus_pct"]) for row in selected]
    y = [float(row["democratic_two_party_share_pct"]) for row in selected]
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    slope = math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / math.fsum((a - mx) ** 2 for a in x)
    return sorted([{"district": row["district"], "bachelors_plus_pct": a, "democratic_two_party_share_pct": b,
                    "education_fit_residual_pp": b - (my + slope * (a - mx))}
                   for row, a, b in zip(selected, x, y)], key=lambda row: (-abs(row["education_fit_residual_pp"]), row["district"]))[:5]


def write_csv(path: Path, fields: list | tuple, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def file_info(path: Path) -> dict:
    payload = path.read_bytes()
    return {"file": path.name, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def write_report(path: Path, rows: list[dict], correlation_rows: list[dict], metrics: dict) -> None:
    baseline = sample_rows(rows, "both_major_parties")
    sensitivity = sample_rows(rows, "single_matchup_excluding_ranked_choice_states")
    sensitivity_by_metric = {row["metric"]: row for row in correlation_rows if row["sample"] != "both_major_parties"}
    lines = [
        "# U.S. House 2024: first demographic correlations", "",
        "Bismillah, this is a descriptive district-level exploration of the joined local datasets.",
        "No causal or individual-voter conclusions are drawn.", "",
        f"The join retains all **{len(rows)} districts** and all **{len(metrics)} demographic indicators with their MOEs**.",
        f"The baseline uses **{len(baseline)} districts** with named Democratic and Republican candidates, positive party vote totals, and official results.",
        f"The other **{len(rows) - len(baseline)} districts** remain in the joined CSV with exclusion reasons and blank two-party shares.",
        "Both-party vote totals include explicitly party-labelled write-ins; unclassified write-ins remain Other.", "",
        "## First relationships", "",
        "Outcome: Democratic two-party vote share, 100 × D / (D + R). Positive correlations mean higher values occur in districts with higher Democratic shares; negative correlations mean lower shares.",
        "These ten indicators were selected before computing correlations to cover education, income, poverty, age, housing and racial/ethnic composition.", "",
        "| Indicator | n | Pearson r | Spearman ρ | Within-state r | Sensitivity r |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in correlation_rows:
        if row["sample"] != "both_major_parties":
            continue
        values = [f"{float(row[key]):.3f}" if row[key] else "—" for key in ("pearson_r", "spearman_rho", "within_state_pearson_r")]
        sensitivity_r = sensitivity_by_metric[row["metric"]]["pearson_r"]
        lines.append(f"| {row['label']} | {row['n']} | {' | '.join(values)} | {float(sensitivity_r):.3f} |")
    lines.extend([
        "", "Every district has equal weight. Spearman uses average ranks for ties.",
        "Within-state r demeans both variables within state before correlating them; it removes differences in state averages, not other demographic or candidate effects.",
        f"Sensitivity r uses **{len(sensitivity)} districts**, excluding Alaska/Maine and races with multiple named candidates of a major party. It is a robustness comparison, not a correction for every difference in election rules.",
        "The machine-readable correlation CSV contains both sample definitions and their sample sizes.", "",
        "## Districts furthest from the education-only line", "",
        "These are the five largest absolute residuals from a simple least-squares line fitted to bachelor's-degree share and Democratic two-party vote share in the baseline sample.",
        "A positive residual means a higher Democratic share than that descriptive line; these are not forecasts, anomalies in the source, or estimates of a candidate effect.", "",
        "| District | Bachelor's degree or higher (%) | Democratic two-party share (%) | Residual (pp) |",
        "| --- | ---: | ---: | ---: |",
    ])
    for row in education_residuals(rows):
        lines.append(f"| {row['district']} | {row['bachelors_plus_pct']:.2f} | {row['democratic_two_party_share_pct']:.2f} | {row['education_fit_residual_pp']:+.2f} |")
    lines.extend([
        "", "## Limits", "",
        "- Demographics describe residents/households and each indicator's documented universe, not the people who voted. Group-level associations do not establish individual voting behavior or causation.",
        "- Correlations use point estimates. ACS margins of error are retained but are not propagated into correlation uncertainty. No p-values, causal models or significance claims are produced.",
        "- The sample excludes missing-party and same-party contests and is not representative of every district. Candidate effects, incumbency, turnout composition, district boundaries and other demographics can affect the relationships.",
        "- Source candidate totals are retained as published in the existing repo. Ranked-choice transfer rounds are not reconstructed. Multiple same-party candidates are aggregated into party totals; candidate winning margin is a different measure from D–R party margin.",
        "- Florida 20th and Oklahoma 3rd have no reported candidate vote totals in the source. Their recorded zeros are preserved and flagged; all vote-share and candidate-margin fields are blank.",
        "- Two language indicators have five source gaps. The ten first-pass indicators above have complete coverage in the baseline sample.",
        "", "## Explore in the app", "",
        "Serve the repo locally and open `app/?year=us-house-2024&view=demographics`.",
        "The Demographics view links the district scatterplot to the election map and full results. Choose among all 42 indicators and either district sample; inspect the selected district's 90% estimate uncertainty on demand.",
        "The view shows Pearson, Spearman and within-state correlations for the chosen measure. It loads data only when opened, preserves missing values, and supports keyboard/touch selection and shareable URLs. Map filters do not change the election-wide analysis sample.",
        "", "## Files and reproduction", "",
        "- `data/us_2024_house_analysis.csv`: 435 joined district rows with result totals, eligibility flags, 42 indicators and their MOEs.",
        "- `data/us_2024_house_analysis_metadata.json`: input/output hashes, result-field definitions, demographic dictionary and sample definitions.",
        "- `data/us_2024_house_analysis_correlations.csv`: Pearson, Spearman and within-state correlations for both samples.",
        "", "```bash", "python3 scripts/build_us_house_analysis.py", "python3 scripts/validate_us_house_analysis.py",
        "python3 scripts/test_us_house_analysis.py", "```", "",
        "See [demographic source documentation](us_house_2024_demographics.md) for official Census sources, boundary vintage, uncertainty methods and missingness.", "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build(data: Path, out: Path, report: Path) -> None:
    results_path, demographics_path = data / "us_2024_house_fpp.csv", data / f"{DEMO_STEM}.csv"
    dictionary_path = data / f"{DEMO_STEM}_metadata.json"
    dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
    for name, info in dictionary["outputs"].items():
        if file_info(data / name)["sha256"] != info["sha256"]:
            raise ValueError(f"Demographic input checksum mismatch: {name}")
    demographics = read_csv(demographics_path)
    rows = joined_rows(read_csv(results_path), demographics, dictionary["metrics"])
    if len(rows) != 435:
        raise ValueError(f"Expected 435 joined districts; found {len(rows)}")
    out.mkdir(parents=True, exist_ok=True)
    joined_path = out / f"{STEM}.csv"
    correlation_path = out / f"{STEM}_correlations.csv"
    write_csv(joined_path, [*demographics[0], *RESULT_FIELDS], rows)
    correlation_rows = correlations(rows, dictionary["metrics"])
    write_csv(correlation_path, CORRELATION_FIELDS, correlation_rows)
    write_report(report, rows, correlation_rows, dictionary["metrics"])
    metadata = {
        "version": 1, "election_key": ELECTION_KEY, "election_year": 2024, "acs_year": 2024, "congress": 119,
        "district_count": len(rows), "join_key": "constituency_code; four-digit string; state FIPS + district, 00 for at-large",
        "inputs": [file_info(path) for path in (results_path, demographics_path, dictionary_path)],
        "outputs": [file_info(path) for path in (joined_path, correlation_path)], "report": file_info(report),
        "demographic_metrics": dictionary["metrics"],
        "vote_groups": {"democratic": [party for party, group in PARTY_GROUPS.items() if group == "democratic"],
                        "republican": [party for party, group in PARTY_GROUPS.items() if group == "republican"],
                        "other": "Every other source candidate_party value; no inferred affiliation"},
        "result_fields": {
            "candidate_count": "All source candidate rows, including generic / named write-ins; candidates are already consolidated across fusion ballot lines by the election builder.",
            "democratic_named_candidate_count": "Rows labelled exactly Democratic; separately labelled write-ins do not count as named-party nominees.",
            "republican_named_candidate_count": "Rows labelled exactly Republican; separately labelled write-ins do not count as named-party nominees.",
            "democratic_votes": "Sum of Democratic and Write-in (Democratic) candidate totals.",
            "republican_votes": "Sum of Republican and Write-in (Republican) candidate totals.",
            "other_votes": "All remaining candidate votes, including unclassified write-ins.",
            "democratic_write_in_votes": "Subset of democratic_votes explicitly labelled Write-in (Democratic).",
            "republican_write_in_votes": "Subset of republican_votes explicitly labelled Write-in (Republican).",
            "total_candidate_votes": "D + R + Other; reconciles to source formal_votes; zero can mean no reported poll in an unopposed seat.",
            "source_total_votes": "Source total_votes, including informal votes; not the denominator of candidate vote shares.",
            "source_informal_votes": "Source informal_votes, retained without reinterpreting them as candidate votes.",
            "votes_reported": "true when total_candidate_votes > 0; false for source contests with no reported candidate totals.",
            "democratic_vote_share_pct": "100 * democratic_votes / total_candidate_votes; blank for zero total.",
            "republican_vote_share_pct": "100 * republican_votes / total_candidate_votes; blank for zero total.",
            "other_vote_share_pct": "100 * other_votes / total_candidate_votes; blank for zero total.",
            "democratic_two_party_share_pct": "100 * D / (D + R), only when two_party_analysis_eligible is true; otherwise blank.",
            "democratic_two_party_margin_pp": "100 * (D - R) / (D + R), only for eligible contests; signed percentage points.",
            "candidate_margin_votes": "Highest minus second-highest source candidate total, irrespective of party; blank for one-candidate or zero-total contests.",
            "candidate_margin_pct": "100 * candidate_margin_votes / total_candidate_votes; not the D–R party margin or an RCV reconstruction.",
            "two_party_analysis_eligible": "Official result, at least one named D and one named R, positive D/R vote totals, and reported candidate totals.",
            "two_party_exclusion_reason": "Semicolon-separated source-status, missing-candidate or unavailable-vote reasons; blank for eligible contests.",
            "multiple_major_party_candidates": "More than one named Democratic or Republican candidate, regardless of eligibility.",
            "ranked_choice_state": "Source state is Alaska or Maine, whose House voting-system exception is documented in the explorer definition; source published totals remain unchanged.",
            "demographic_missing_metric_count": "Count of blank demographic indicators, excluding MOE fields.",
            "demographic_missing_metrics": "Semicolon-separated names of blank demographic indicators; no imputation.",
            "election_key": ELECTION_KEY, "election_year": "2024", "elected_member": "Source elected_member",
            "elected_party": "Source elected_party", "contest_status": "Source contest_status",
        },
        "samples": {name: {"n": len(sample_rows(rows, name)),
                            "definition": "two_party_analysis_eligible=true" if name == "both_major_parties"
                            else "Eligible; no multiple named major-party candidates; exclude Alaska and Maine"}
                    for name in ("both_major_parties", "single_matchup_excluding_ranked_choice_states")},
        "exploratory_metrics": list(FIRST_METRICS),
        "correlation_method": "Equal-weight districts; pairwise complete cases; Pearson on values; Spearman on average ranks; within-state Pearson on state-demeaned values. n counts districts. No significance claims or measurement-error adjustment.",
        "interpretation": "District associations, not causal effects or individual voting behavior. No turnout is inferred. Candidate totals retain the source count basis.",
    }
    (out / f"{STEM}_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} districts: {metadata['samples']['both_major_parties']['n']} eligible; {metadata['samples']['single_matchup_excluding_ranked_choice_states']['n']} sensitivity sample; {len(correlation_rows)} correlations")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    parser.add_argument("--report", type=Path, default=ROOT / "docs" / "us_house_2024_analysis.md")
    args = parser.parse_args()
    build(args.data, args.out, args.report)


if __name__ == "__main__":
    main()
