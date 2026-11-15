#!/usr/bin/env python3
"""Build/check conservative House comparisons using fixed 2024 ACS data."""
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
UNCHANGED_2020_STATES = {'Alaska', 'Delaware', 'North Dakota', 'South Dakota', 'Vermont', 'Wyoming'}
BOUNDARY_2020_SOURCE = 'https://www.census.gov/programs-surveys/geography/guidance/geo-areas/congressional-dist.html'
BOUNDARY_SOURCE = 'https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2024/geography-changes.html'


def build_rows(root=ROOT, period='2022-2024'):
    start, end = (2020, 2022) if period == '2020-2022' else (2022, 2024)
    years = {}
    for year in (start, end):
        grouped = defaultdict(list)
        for row in read_csv(root / f'data/us_{year}_house_fpp.csv'):
            grouped[row['constituency_code']].append(row)
        years[year] = grouped
    demographics = read_csv(root / 'data/us_2024_house_analysis.csv')
    codes = {row['constituency_code'] for row in demographics}
    if len(codes) != 435 or set(years[end]) != codes or (start == 2022 and set(years[start]) != codes):
        raise ValueError('Expected the same 435 district identifiers in both elections and demographics')
    output = []
    for demo in demographics:
        code, state = demo['constituency_code'], demo['state']
        contests = {year: summarize_result(years[year][code]) if code in years[year] else {
            'elected_party': '', 'contest_status': 'missing_previous_district', 'democratic_votes': '', 'republican_votes': '',
            'two_party_analysis_eligible': 'false', 'two_party_exclusion_reason': 'missing_previous_district',
            'multiple_major_party_candidates': 'false', 'democratic_two_party_share_pct': '',
        } for year in years}
        if any(years[year][code][0]['electorate_type'] != state for year in years if code in years[year]):
            raise ValueError(f'State identity mismatch: {code}')
        reasons = []
        stable = state in UNCHANGED_2020_STATES if start == 2020 else state not in CHANGED_STATES
        if stable and code not in years[start]:
            raise ValueError(f'Unchanged district missing from previous election: {code}')
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
        row['seat_flipped'] = str(contests[start]['elected_party'] != contests[end]['elected_party']).lower() if winner_comparable else ''
        # Delta is withheld when boundaries or contest/count bases are not comparable.
        row['democratic_share_change_pp'] = formatted(float(contests[end]['democratic_two_party_share_pct'])
                                                     - float(contests[start]['democratic_two_party_share_pct'])) if eligible else ''
        output.append(row)
    return output


def artifacts(root=ROOT, period='2022-2024'):
    rows = build_rows(root, period)
    start, end = (2020, 2022) if period == '2020-2022' else (2022, 2024)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode()
    inputs = [f'data/us_{year}_house_fpp.csv' for year in (start, end)] + ['data/us_2024_house_analysis.csv']
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
    if start == 2020:
        metadata.update({
            'election_years': [start, end], 'boundary_source': BOUNDARY_2020_SOURCE,
            'boundary_source_section': 'What are Congressional Districts?',
            'boundary_evidence': 'Census identifies six single-member states as the exceptions to new 2022 plans: Alaska, Delaware, North Dakota, South Dakota, Vermont, Wyoming.',
            'excluded_changed_plan_states': sorted({row['state'] for row in rows} - UNCHANGED_2020_STATES),
            'boundary_policy': 'Conservatively include only the six verified unchanged at-large states. All other districts remain unverified and excluded; no reconstructed votes.',
            'seat_flip_definition': 'Different official elected parties in 2020 and 2022 on verified unchanged boundaries; blank where unavailable. General-election snapshots, not intervening by-elections.',
            'change_definition': '2022 two-party share minus 2020 two-party share in percentage points; Republican change is the negative of Democratic change.',
            'sample_note': 'Only Delaware, Vermont and Wyoming pass all contest and count-basis checks. This tiny sample does not describe national patterns.',
        })
    return content, (json.dumps(metadata, indent=2) + '\n').encode(), metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--period', choices=('2022-2024', '2020-2022'), default='2022-2024')
    parser.add_argument('--check', action='store_true', help='Recompute and validate committed artifacts without writing')
    args = parser.parse_args()
    content, metadata, summary = artifacts(period=args.period)
    stem = STEM if args.period == "2022-2024" else "us_house_2020_2022_comparison"
    for suffix, body in (('.csv', content), ('_metadata.json', metadata)):
        path = ROOT / 'data' / (stem + suffix)
        if args.check:
            if path.read_bytes() != body:
                raise SystemExit(f'Stale or invalid comparison artifact: {path}')
        else:
            path.write_bytes(body)
    print(f"{'Validated' if args.check else 'Built'} {summary['districts']} districts; {summary['matched_baseline_districts']} matched baseline, {summary['matched_sensitivity_districts']} sensitivity")


if __name__ == '__main__':
    main()
