#!/usr/bin/env python3
"""County/reporting-area presidential demographics and comparisons, 2008–2024.

Download verified prefixes of official ACS bulk tables: counties precede tract
records. Keep complete source response prefixes and hashes for reproducibility.
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
import urllib.request

import build_us_house_demographics as acs
from build_us_president_demographics import ROOT, YEARS, PERIODS, read_csv, csv_bytes, json_bytes

CACHE = ROOT / 'tmp/us_county_demographics'
PREFIX = 'us_2024_county_demographics'
BULK = 'https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/'
METADATA = 'https://api.census.gov/data/2024/acs/acs5/groups/'
TABLES = tuple('B08301' if table == 'C08301' else table for table in acs.TABLES)
RANGE_END = 4 * 1024 * 1024 - 1


def fetch_table(table, cache):
    name = f'acsdt5y2024-{table.lower()}.dat'
    for filename, url, ranged in ((name, BULK + name, True), (table + '.json', METADATA + table + '.json', False)):
        path = cache / filename
        if path.exists():
            continue
        headers = {'User-Agent': 'ElectionExplorer-county-demographics/1.0'}
        if ranged:
            headers['Range'] = f'bytes=0-{RANGE_END}'
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
            payload = response.read(RANGE_END + 2) if ranged else response.read()
            content_range = response.headers.get('Content-Range', '')
            if ranged and (response.status != 206 or not content_range.startswith('bytes 0-') or len(payload) > RANGE_END + 1):
                raise ValueError(f'{url}: expected bounded official byte-range response')
        if ranged:
            lines = payload.rsplit(b'\n', 1)[0].decode('utf-8-sig').splitlines()
            if not lines[0].startswith('GEO_ID|') or not any(line[:3].isdigit() and int(line[:3]) > 50 for line in lines[1:]):
                raise ValueError(f'{table}: prefix does not include the complete county section')
            (cache / (name + '.source.json')).write_bytes(json_bytes({'url': url, 'content_range': content_range,
                'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}))
        elif 'variables' not in json.loads(payload):
            raise ValueError(f'{url}: missing variable metadata')
        path.write_bytes(payload)
        print(f'Downloaded {filename}: {len(payload):,} bytes', flush=True)


def canonical(code):
    return 'US-COUNTY-46102' if code == 'US-COUNTY-46113' else code


def elections():
    output = {}
    for year in YEARS:
        grouped = {}
        for row in read_csv(ROOT / f'data/us_{year}_president_county_fpp.csv'):
            grouped.setdefault(canonical(row['constituency_code']), []).append(row)
        areas = {}
        for key, rows in grouped.items():
            totals = {r['candidate_party']: int(r['votes']) for r in rows}
            if len(rows) != 3 or set(totals) != {'Democratic', 'Republican', 'Other'} or sum(totals.values()) != int(rows[0]['formal_votes']) or min(totals.values()) < 0:
                raise ValueError(f'{year} {key}: invalid county vote accounting')
            winner = max(totals, key=totals.get)
            if winner != rows[0]['elected_party']:
                raise ValueError(f'{year} {key}: leader mismatch')
            areas[key] = {**rows[0], 'democratic_votes': totals['Democratic'], 'republican_votes': totals['Republican'],
                          'share': 100.0 * totals['Democratic'] / (totals['Democratic'] + totals['Republican']) if totals['Democratic'] + totals['Republican'] else None}
        output[year] = areas
    return output


def build_demographics(cache):
    areas = elections()[2024]
    identities = {key.removeprefix('US-COUNTY-'): {'constituency_code': key, 'district': row['district'], 'state': row['electorate_type']} for key, row in areas.items()}
    # Alaska is a statewide placeholder, not a county. Keep its map row blank.
    raw = {fips: {} for fips in identities}
    variables, sources, coverage = {}, [], {}
    for table in TABLES:
        path = cache / f'acsdt5y2024-{table.lower()}.dat'
        payload = path.read_bytes()
        lines = payload.rsplit(b'\n', 1)[0].decode('utf-8-sig')
        metadata = json.loads((cache / (table + '.json')).read_bytes())['variables']
        reader = csv.DictReader(io.StringIO(lines), delimiter='|')
        columns = {}
        for column in reader.fieldnames[1:]:
            match = re.fullmatch(rf'{table}_([EM])(\d{{3}})', column)
            if not match:
                raise ValueError(f'Unexpected ACS column {column}')
            kind, line = match.groups()
            variable = f'{table}_{line}{kind}'
            definition = metadata[variable]
            variables[variable] = {'table': table, 'label': definition['label'], 'concept': definition['concept'], 'universe': definition['universe']}
            columns[column] = variable
        found = set()
        for row in reader:
            match = re.fullmatch(r'0500000US(\d{5})', row['GEO_ID'])
            if not match or match[1] not in identities:
                continue
            fips = match[1]
            if fips in found:
                raise ValueError(f'{table}: duplicate county {fips}')
            found.add(fips)
            raw[fips].update({v: row[c] for c, v in columns.items()})
        missing = identities.keys() - found
        if missing != {'02'}:
            raise ValueError(f'{table}: unexpected missing counties {sorted(missing)}')
        raw['02'].update({v: '' for v in columns.values()})
        coverage[table] = {'counties_in_source': len(found), 'unavailable_reporting_areas': ['US-COUNTY-02']}
        source = json.loads((cache / (path.name + '.source.json')).read_bytes())
        if hashlib.sha256(payload).hexdigest() != source['sha256']:
            raise ValueError(f'{table}: cached prefix checksum mismatch')
        sources.append({'filename': path.name, **source, 'scope': 'Complete county section in official table prefix; incomplete trailing row ignored'})
        meta_path = cache / (table + '.json')
        sources.append({'filename': meta_path.name, 'url': METADATA + meta_path.name, 'bytes': meta_path.stat().st_size, 'sha256': hashlib.sha256(meta_path.read_bytes()).hexdigest()})
    metrics = acs.metric_definitions()
    metrics['work_from_home_pct'].update(numerator=['B08301_021E'], denominator=['B08301_001E'])
    metrics['public_transit_commute_pct'].update(numerator=['B08301_010E'], denominator=['B08301_001E'])
    acs.add_industry_metrics(metrics, variables)
    for definition in metrics.values():
        definition['source_universes'] = sorted({variables[v]['universe'] for v in definition['numerator'] + definition['denominator']})
        definition['formula'] = '100 * sum(numerator) / sum(denominator)' if definition['denominator'] else 'sum(numerator)'
    derived, extracts, flags = [], [], []
    for fips, identity in sorted(identities.items()):
        identity = {**identity, 'census_geo_id': '' if fips == '02' else f'0500000US{fips}', 'acs_year': '2024'}
        row = dict(identity)
        for name, definition in metrics.items():
            estimate, moe = acs.metric_value(raw[fips], definition)
            row[name], row[name + '_moe'] = acs.csv_number(estimate), acs.csv_number(moe)
        derived.append(row)
        extracts.append({**identity, **raw[fips]})
        for variable, value in sorted(raw[fips].items()):
            if acs.number(value) is None:
                flags.append({'constituency_code': identity['constituency_code'], 'variable': variable, 'source_value': value})
    output = {PREFIX + '.csv': csv_bytes(derived), PREFIX + '_acs.csv': csv_bytes(extracts), PREFIX + '_flags.csv': csv_bytes(flags)}
    metadata = {'version': 1, 'dataset': '2020–2024 ACS 5-year estimates', 'geography': 'county', 'area_count': len(derived),
        'metric_count': len(metrics), 'scope': 'Current election county/reporting areas, including DC; Alaska statewide placeholder has no county estimate',
        'moe_confidence': 0.90, 'missing_values': 'Missing/negative estimate sentinels become blanks; controlled MOE sentinel contributes zero sampling error. No imputation.',
        'interpretation': 'Fixed 2020–2024 five-year resident/household estimates, not 2024-only measurements or demographics of voters. Earlier populations may differ.',
        'sources': sources, 'table_coverage': coverage, 'variables': variables, 'metrics': metrics,
        'outputs': {name: {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} for name, body in output.items()}}
    output[PREFIX + '_metadata.json'] = json_bytes(metadata)
    return output


def build_comparisons():
    years = elections()
    output = {}
    for start, end in PERIODS:
        rows = []
        for key in sorted(years[start].keys() | years[end].keys()):
            previous, current = years[start].get(key), years[end].get(key)
            identity = current or previous
            reasons = []
            if key == 'US-COUNTY-02': reasons.append('alaska_statewide_not_county')
            if key.startswith('US-COUNTY-09'): reasons.append('connecticut_changed_geography_no_matching_acs')
            if not current: reasons.append("no_matching_current_reporting_area")
            if not previous: reasons.append('no_matching_previous_reporting_area')
            if any(r and min(r['democratic_votes'], r['republican_votes']) <= 0 for r in (previous, current)):
                reasons.append('both_major_parties_need_positive_votes')
            row = {'constituency_code': identity['constituency_code'], 'district': identity['district'], 'state': identity['electorate_type'],
                'demographic_constituency_code': key, 'demographic_year': '2024', 'boundary_unchanged_verified': '', 'reporting_area_matched': str(previous is not None and current is not None).lower(),
                'comparison_eligible': str(not reasons).lower(), 'comparison_sensitivity_eligible': str(not reasons).lower(), 'comparison_exclusion_reason': ';'.join(reasons)}
            for year, result in ((start, previous), (end, current)):
                for field in ('district', 'constituency_code', 'elected_party', 'democratic_votes', 'republican_votes'):
                    row[f'{field}_{year}'] = result[field] if result else ''
                row[f'democratic_two_party_share_pct_{year}'] = acs.csv_number(result['share']) if result else ''
            row['seat_flipped'] = str(previous['elected_party'] != current['elected_party']).lower() if not reasons else ''
            row['democratic_share_change_pp'] = acs.csv_number(current['share'] - previous['share']) if not reasons else ''
            rows.append(row)
        stem = f'us_president_county_{start}_{end}_comparison'
        body = csv_bytes(rows)
        metadata = {'election_years': [start, end], 'geography': 'county/reporting area', 'areas': len(rows),
            'comparable_areas': sum(r['comparison_eligible'] == 'true' for r in rows), 'flipped_areas': sum(r['seat_flipped'] == 'true' for r in rows),
            'demographic_dataset': 'Fixed 2020–2024 ACS 5-year county estimates',
            'geography_policy': 'Match source reporting-area identifiers, harmonizing Shannon 46113 to renamed Oglala Lakota 46102. Not an individual Census block boundary audit. Historical source already combines Bedford city/county and Kansas City/Jackson reporting returns. Exclude Connecticut throughout because old counties lack matching current ACS areas; exclude Alaska statewide placeholder. No reconstructed votes or invented ACS values.',
            'flip_definition': 'Change of county/reporting-area popular-vote leader on a comparable reporting area, not electoral votes.',
            'interpretation': 'Equal-weight county/reporting areas; descriptive associations with a fixed 2020–2024 snapshot, not individual behavior or demographic change.',
            'input_sha256': {f'data/us_{year}_president_county_fpp.csv': hashlib.sha256((ROOT / f'data/us_{year}_president_county_fpp.csv').read_bytes()).hexdigest() for year in (start, end)},
            'output_sha256': hashlib.sha256(body).hexdigest()}
        output[stem + '.csv'], output[stem + '_metadata.json'] = body, json_bytes(metadata)
        print(f'{start}–{end}: {metadata["comparable_areas"]} comparable / {len(rows)} reporting areas', flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.download:
        CACHE.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda table: fetch_table(table, CACHE), TABLES))
    output = build_demographics(CACHE) if not args.check or all((CACHE / f'acsdt5y2024-{table.lower()}.dat').exists() for table in TABLES) else {}
    output.update(build_comparisons())
    for name, body in output.items():
        path = ROOT / 'data' / name
        if args.check:
            if path.read_bytes() != body: raise SystemExit(f'Stale county artifact: {path}')
        else:
            path.write_bytes(body)


if __name__ == '__main__': main()
