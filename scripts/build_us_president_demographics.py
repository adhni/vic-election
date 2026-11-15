#!/usr/bin/env python3
"""Prepare 2024 ACS state demographics and all available presidential comparisons.

Bismillah. Public Census bulk inputs are shared with the House extract; election
inputs are the repository's official statewide FEC compilations. No API key.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import re

import build_us_house_demographics as acs

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2008, 2012, 2016, 2020, 2024)
PERIODS = tuple(zip(YEARS, YEARS[1:]))
PREFIX = 'us_2024_state_demographics'


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def csv_bytes(rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def election_rows(root=ROOT):
    results = {}
    for year in YEARS:
        grouped = {}
        for row in read_csv(root / f'data/us_{year}_president_state_fpp.csv'):
            grouped.setdefault(row['constituency_code'], []).append(row)
        if len(grouped) != 51:
            raise ValueError(f'{year}: expected 50 states and DC')
        output = {}
        for code, rows in grouped.items():
            parties = {r['candidate_party']: int(r['votes']) for r in rows}
            if len(rows) != 3 or set(parties) != {'Democratic', 'Republican', 'Other'} or any(r['contest_status'] != 'official' for r in rows):
                raise ValueError(f'{year} {code}: invalid official statewide result')
            if sum(parties.values()) != int(rows[0]['formal_votes']) or min(parties.values()) < 0 or min(parties['Democratic'], parties['Republican']) <= 0:
                raise ValueError(f'{year} {code}: invalid vote accounting')
            leader = max(parties, key=parties.get)
            if rows[0]['elected_party'] != leader or leader == 'Other':
                raise ValueError(f'{year} {code}: popular-vote leader mismatch')
            output[code] = {'district': rows[0]['district'], 'elected_party': leader,
                            'democratic_votes': parties['Democratic'], 'republican_votes': parties['Republican'],
                            'democratic_two_party_share_pct': acs.csv_number(100.0 * parties['Democratic'] / (parties['Democratic'] + parties['Republican']))}
        results[year] = output
    if any(set(rows) != set(results[2024]) for rows in results.values()):
        raise ValueError('State identifiers differ between elections')
    return results


def comparison_rows(results, start, end):
    rows = []
    for code in sorted(results[end]):
        row = {'constituency_code': code, 'district': results[end][code]['district'],
               'state': results[end][code]['district'], 'demographic_year': '2024',
               'boundary_unchanged_verified': 'true', 'comparison_eligible': 'true',
               'comparison_sensitivity_eligible': 'true', 'comparison_exclusion_reason': ''}
        for year in (start, end):
            result = results[year][code]
            if result['district'] != row['district']:
                raise ValueError(f'State name mismatch {year} {code}')
            row.update({f'{key}_{year}': result[key] for key in ('elected_party', 'democratic_votes', 'republican_votes', 'democratic_two_party_share_pct')})
        row['seat_flipped'] = str(results[start][code]['elected_party'] != results[end][code]['elected_party']).lower()
        row['democratic_share_change_pp'] = acs.csv_number(float(results[end][code]['democratic_two_party_share_pct']) - float(results[start][code]['democratic_two_party_share_pct']))
        rows.append(row)
    return rows


def comparison_artifacts(root=ROOT):
    results = election_rows(root)
    output = {}
    for start, end in PERIODS:
        name = f'us_president_{start}_{end}_comparison'
        rows = comparison_rows(results, start, end)
        body = csv_bytes(rows)
        inputs = [f'data/us_{year}_president_state_fpp.csv' for year in (start, end)] + [f'data/{PREFIX}.csv']
        metadata = {'election_years': [start, end], 'geography': '50 states and District of Columbia',
                    'demographic_year': 2024, 'demographic_dataset': '2024 ACS 1-year estimates, fixed in every comparison',
                    'areas': 51, 'comparable_areas': 51, 'flipped_states': sum(r['seat_flipped'] == 'true' for r in rows),
                    'vote_source': 'https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/',
                    'change_definition': f'{end} D / (D + R) share minus {start} share, in percentage points. Republican change negates Democratic change.',
                    'flip_definition': 'Change in statewide popular-vote leading party; not electoral-vote allocation, congressional-district electors, or the national presidency. seat_flipped is the shared chart field name.',
                    'sample_policy': 'All 50 states and DC; published official statewide totals, both major parties positive. No House district or county geography joins. Alaska and Maine retained.',
                    'interpretation': 'Equal-weight state/DC associations, not vote-weighted national results. Fixed 2024 characteristics, measured after earlier elections; not demographic change or individual voting behavior. No within-state correlation: each point is a whole state/DC.',
                    'input_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in inputs},
                    'output_sha256': hashlib.sha256(body).hexdigest()}
        output[name + '.csv'] = body
        output[name + '_metadata.json'] = json_bytes(metadata)
    return output


def demographic_artifacts(cache):
    results = election_rows()
    fips_by_name = {row['state']: row['constituency_code'][:2] for row in read_csv(ROOT / 'data/us_2024_house_demographics.csv')}
    fips_by_name['District of Columbia'] = '11'
    districts = {fips_by_name[row['district']]: {'constituency_code': code, 'district': row['district'], 'state': row['district']} for code, row in results[2024].items()}
    previous_pattern = acs.CD_PATTERN
    acs.CD_PATTERN = re.compile(r'0400000US(\d{2})\Z')
    try:
        raw, variables, sources, coverage = acs.load_sources(cache, districts)
    finally:
        acs.CD_PATTERN = previous_pattern
    metrics = acs.metric_definitions()
    acs.add_industry_metrics(metrics, variables)
    for definition in metrics.values():
        definition['source_universes'] = sorted({variables[v]['universe'] for v in definition['numerator'] + definition['denominator']})
        definition['formula'] = '100 * sum(numerator) / sum(denominator)' if definition['denominator'] else 'sum(numerator)'
    derived, raw_rows, flags = [], [], []
    for fips, identity in sorted(districts.items()):
        identity = {**identity, 'census_geo_id': f'0400000US{fips}', 'acs_year': '2024'}
        row = dict(identity)
        for name, definition in metrics.items():
            estimate, moe = acs.metric_value(raw[fips], definition)
            row[name], row[name + '_moe'] = acs.csv_number(estimate), acs.csv_number(moe)
        derived.append(row)
        raw_rows.append({**identity, **raw[fips]})
        for variable, value in sorted(raw[fips].items()):
            if acs.number(value) is None:
                flags.append({'constituency_code': identity['constituency_code'], 'variable': variable, 'source_value': value})
    output = {PREFIX + '.csv': csv_bytes(derived), PREFIX + '_acs.csv': csv_bytes(raw_rows)}
    # Controlled MOE sentinels ensure at least one flag; keep an explicit header if empty.
    output[PREFIX + '_flags.csv'] = csv_bytes(flags) if flags else b'constituency_code,variable,source_value\n'
    metadata = {'version': 1, 'dataset': '2024 ACS 1-year estimates', 'geography': 'state', 'area_count': 51,
                'scope': '50 states plus District of Columbia; no territories', 'metric_count': len(metrics),
                'join_key': 'State name -> two-digit Census state FIPS; election US-STATE- postal codes retained',
                'moe_confidence': 0.90, 'moe_method': 'Published MOEs; derived sums use root-sum-of-squares and percentages use ACS subset-proportion approximation with ratio fallback. Controlled MOE sentinel contributes zero sampling error.',
                'missing_values': 'Negative estimates and unavailable source tokens become blank derived values; raw tokens retained. No imputation.',
                'interpretation': 'Fixed 2024 resident/household characteristics, not demographics of actual voters or demographic change since 2008.',
                'sources': sources, 'table_coverage': coverage, 'variables': variables, 'metrics': metrics,
                'outputs': {name: {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} for name, body in output.items()}}
    output[PREFIX + '_metadata.json'] = json_bytes(metadata)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=acs.CACHE)
    parser.add_argument('--download', action='store_true', help='Download missing public ACS sources')
    parser.add_argument('--check', action='store_true', help='Verify committed comparisons; also demographics when sources are cached')
    args = parser.parse_args()
    if args.download:
        args.cache.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda spec: acs.fetch_source(spec, args.cache), acs.source_specs()))
    if not args.check or all((args.cache / name).exists() for name, _ in acs.source_specs()):
        for name, body in demographic_artifacts(args.cache).items():
            path = ROOT / 'data' / name
            if args.check:
                if path.read_bytes() != body:
                    raise SystemExit(f'Stale state demographic artifact: {path}')
            else:
                path.write_bytes(body)
    for name, body in comparison_artifacts().items():
        path = ROOT / 'data' / name
        if args.check:
            if path.read_bytes() != body:
                raise SystemExit(f'Stale presidential comparison: {path}')
        else:
            path.write_bytes(body)
    print(f"{'Validated' if args.check else 'Built'} state demographics and 4 presidential comparisons: 2008–2024, 51 states/DC each")


if __name__ == '__main__':
    main()
