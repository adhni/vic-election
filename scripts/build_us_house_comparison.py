#!/usr/bin/env python3
"""Build/check a conservative 2022–2024 comparison using fixed 2024 ACS data."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path

from build_us_house_analysis import read_csv, summarize_result, formatted

ROOT = Path(__file__).resolve().parents[1]
STEM = 'us_house_2022_2024_comparison'
CHANGED_STATES = {'Alabama', 'Georgia', 'Louisiana', 'New York', 'North Carolina'}
BOUNDARY_SOURCE = 'https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2024/geography-changes.html'


def build_rows(root=ROOT):
    years = {}
    for year in (2022, 2024):
        grouped = defaultdict(list)
        for row in read_csv(root / f'data/us_{year}_house_fpp.csv'):
            grouped[row['constituency_code']].append(row)
        years[year] = grouped
    demographics = read_csv(root / 'data/us_2024_house_analysis.csv')
    codes = {row['constituency_code'] for row in demographics}
    if len(codes) != 435 or any(set(years[year]) != codes for year in years):
        raise ValueError('Expected the same 435 district identifiers in both elections and demographics')
    output = []
    for demo in demographics:
        code, state = demo['constituency_code'], demo['state']
        contests = {year: summarize_result(years[year][code]) for year in years}
        if any(years[year][code][0]['electorate_type'] != state for year in years):
            raise ValueError(f'State identity mismatch: {code}')
        reasons = []
        stable = state not in CHANGED_STATES
        if not stable:
            reasons.append('state_plan_changed_not_individually_verified')
        # The compact sources can mix first and decisive RCV counts across years.
        if state in {'Alaska', 'Maine'}:
            reasons.append('ranked_choice_count_basis_not_standardized')
        for year, result in contests.items():
            if result['two_party_analysis_eligible'] != 'true':
                reasons.append(f'{year}:{result["two_party_exclusion_reason"]}')
        eligible = not reasons
        multiple = any(result['multiple_major_party_candidates'] == 'true' for result in contests.values())
        row = {'constituency_code': code, 'district': demo['district'], 'state': state,
               'demographic_year': '2024', 'boundary_unchanged_verified': str(stable).lower(),
               'comparison_eligible': str(eligible).lower(),
               'comparison_sensitivity_eligible': str(eligible and not multiple).lower(),
               'comparison_exclusion_reason': ';'.join(reasons)}
        for year, result in contests.items():
            for field in ('elected_party', 'democratic_votes', 'republican_votes', 'two_party_analysis_eligible',
                          'multiple_major_party_candidates', 'democratic_two_party_share_pct'):
                row[f'{field}_{year}'] = result[field]
        # Winner changes use official elected parties, independently of share eligibility.
        winner_comparable = stable and all(result['elected_party'] and result['contest_status'] in {'official', 'uncontested'}
                                           for result in contests.values())
        row['seat_flipped'] = str(contests[2022]['elected_party'] != contests[2024]['elected_party']).lower() if winner_comparable else ''
        # Delta is withheld when boundaries or contest/count bases are not comparable.
        row['democratic_share_change_pp'] = formatted(float(contests[2024]['democratic_two_party_share_pct'])
                                                     - float(contests[2022]['democratic_two_party_share_pct'])) if eligible else ''
        output.append(row)
    return output


def artifacts(root=ROOT):
    rows = build_rows(root)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode()
    inputs = [f'data/us_{year}_house_fpp.csv' for year in (2022, 2024)] + ['data/us_2024_house_analysis.csv']
    metadata = {
        'election_years': [2022, 2024], 'demographic_year': 2024,
        'boundary_source': BOUNDARY_SOURCE,
        'boundary_source_section': 'Release of 119th Congressional Districts',
        'boundary_evidence': 'Census identifies five states with new 2024 plans and confirms all other states had no congressional boundary changes from the 2022 cycle.',
        'excluded_changed_plan_states': sorted(CHANGED_STATES),
        'boundary_policy': 'Exclude every district in a changed-plan state conservatively; no claim that each excluded district changed.',
        'ranked_choice_policy': 'Exclude Alaska and Maine; candidate-count bases have not been standardized across years.',
        'sample_policy': 'Both named major parties and positive reported votes in both years; sensitivity also excludes multiple major-party candidates in either year.',
        'seat_flip_definition': 'Different official elected parties in 2022 and 2024 on verified unchanged boundaries; blank where winner comparison is unavailable. Independent of swing eligibility; general-election snapshots, not intervening by-elections.',
        'change_definition': '2024 two-party share minus 2022 two-party share in percentage points; Republican change is the negative of Democratic change.',
        'interpretation': 'Fixed 2024 ACS snapshot, equal-weight districts. Does not measure demographic change, individual voting behavior, or causation. Midterm/presidential turnout and candidate differences can affect changes.',
        'districts': len(rows),
        'verified_unchanged_districts': sum(row['boundary_unchanged_verified'] == 'true' for row in rows),
        'matched_baseline_districts': sum(row['comparison_eligible'] == 'true' for row in rows),
        'matched_sensitivity_districts': sum(row['comparison_sensitivity_eligible'] == 'true' for row in rows),
        'input_sha256': {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in inputs},
        'output_sha256': hashlib.sha256(content).hexdigest(),
    }
    return content, (json.dumps(metadata, indent=2) + '\n').encode(), metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Recompute and validate committed artifacts without writing')
    args = parser.parse_args()
    content, metadata, summary = artifacts()
    for suffix, body in (('.csv', content), ('_metadata.json', metadata)):
        path = ROOT / 'data' / (STEM + suffix)
        if args.check:
            if path.read_bytes() != body:
                raise SystemExit(f'Stale or invalid comparison artifact: {path}')
        else:
            path.write_bytes(body)
    print(f"{'Validated' if args.check else 'Built'} {summary['districts']} districts; {summary['matched_baseline_districts']} matched baseline, {summary['matched_sensitivity_districts']} sensitivity")


if __name__ == '__main__':
    main()
