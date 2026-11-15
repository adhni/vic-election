#!/usr/bin/env python3
"""Audit county ACS extracts, derived metrics, reporting aliases and source votes."""
import csv
import hashlib
import io
import json
import unittest
from pathlib import Path

from build_us_president_county_demographics import ROOT, CACHE, PREFIX, YEARS, PERIODS, TABLES, canonical, build_comparisons
from build_us_president_demographics import read_csv


class CountyDemographicTests(unittest.TestCase):
    def test_demographic_geography_arithmetic_and_hashes(self):
        meta = json.loads((ROOT / 'data' / (PREFIX + '_metadata.json')).read_bytes())
        derived = read_csv(ROOT / 'data' / (PREFIX + '.csv'))
        raw = {r['constituency_code']: r for r in read_csv(ROOT / 'data' / (PREFIX + '_acs.csv'))}
        self.assertEqual(len(derived), 3114)
        self.assertEqual(meta['metric_count'], 42)
        self.assertEqual({r['constituency_code'] for r in derived}, {r['constituency_code'] for r in read_csv(ROOT / 'data/us_2024_president_county_fpp.csv')})
        for filename, info in meta['outputs'].items():
            payload = (ROOT / 'data' / filename).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), info['sha256'])
            self.assertEqual(len(payload), info['bytes'])
        for row in derived:
            source = raw[row['constituency_code']]
            if row['constituency_code'] == 'US-COUNTY-02':
                self.assertEqual(row['census_geo_id'], '')
                self.assertTrue(all(row[m] == '' for m in meta['metrics']))
                continue
            self.assertEqual(row['census_geo_id'], '0500000US' + row['constituency_code'].split('-')[-1])
            self.assertEqual(int(source['B01001_001E']), int(source['B03002_001E']))
            for name, definition in meta['metrics'].items():
                nums = [float(source[v]) for v in definition['numerator']]
                dens = [float(source[v]) for v in definition['denominator']]
                valid = min(nums + dens) >= 0 and (not dens or sum(dens) > 0)
                self.assertEqual(bool(row[name]), valid)
                if valid:
                    expected = sum(nums) * 100 / sum(dens) if dens else sum(nums)
                    self.assertAlmostEqual(float(row[name]), expected, places=5)
                    self.assertTrue(not row[name + '_moe'] or float(row[name + '_moe']) >= 0)
        self.assertIn('Worked from home', meta['variables']['B08301_021E']['label'])
        flags = read_csv(ROOT / 'data' / (PREFIX + '_flags.csv'))
        self.assertEqual({(r['constituency_code'], r['variable']) for r in flags}, {(code, v) for code, r in raw.items() for v in meta['variables'] if not r[v] or float(r[v]) < 0})

    def test_official_prefix_extracts(self):
        meta = json.loads((ROOT / 'data' / (PREFIX + '_metadata.json')).read_bytes())
        raw = {r['census_geo_id']: r for r in read_csv(ROOT / 'data' / (PREFIX + '_acs.csv')) if r['census_geo_id']}
        for source in meta['sources']:
            self.assertTrue(source['url'].startswith(('https://www2.census.gov/', 'https://api.census.gov/')))
            path = CACHE / source['filename']
            if not path.exists():
                continue
            payload = path.read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), source['sha256'])
            if not path.suffix == '.dat':
                continue
            self.assertTrue(source['content_range'].startswith('bytes 0-'))
            table = path.stem.split('-')[-1].upper()
            rows = csv.DictReader(io.StringIO(payload.rsplit(b'\n', 1)[0].decode()), delimiter='|')
            found = set()
            for row in rows:
                if row['GEO_ID'] not in raw: continue
                found.add(row['GEO_ID'])
                for variable, definition in meta['variables'].items():
                    if definition['table'] == table:
                        self.assertEqual(raw[row['GEO_ID']][variable], row[f'{table}_{variable[-1]}{variable[-4:-1]}'])
            self.assertEqual(found, raw.keys())

    def test_reporting_aliases_exclusions_and_independent_vote_arithmetic(self):
        sources = {}
        for year in YEARS:
            grouped = {}
            for row in read_csv(ROOT / f'data/us_{year}_president_county_fpp.csv'):
                grouped.setdefault(row['constituency_code'], {})[row['candidate_party']] = int(row['votes'])
            sources[year] = grouped
        for start, end in PERIODS:
            rows = read_csv(ROOT / f'data/us_president_county_{start}_{end}_comparison.csv')
            self.assertEqual(sum(r['comparison_eligible'] == 'true' for r in rows), 3104)
            for row in rows:
                excluded = row['state'] in {'Alaska', 'Connecticut'}
                self.assertEqual(row['comparison_eligible'], str(not excluded).lower())
                shares = {}
                for year in (start, end):
                    code = row[f'constituency_code_{year}']
                    if not code:
                        self.assertEqual(row[f'democratic_votes_{year}'], '')
                        continue
                    votes = sources[year][code]
                    self.assertEqual(int(row[f'democratic_votes_{year}']), votes['Democratic'])
                    self.assertEqual(int(row[f'republican_votes_{year}']), votes['Republican'])
                    shares[year] = 100 * votes['Democratic'] / (votes['Democratic'] + votes['Republican'])
                    self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']), shares[year], places=5)
                if excluded:
                    self.assertEqual(row['democratic_share_change_pp'], '')
                    self.assertEqual(row['seat_flipped'], '')
                else:
                    self.assertAlmostEqual(float(row['democratic_share_change_pp']), shares[end] - shares[start], places=5)
                    self.assertEqual(row['seat_flipped'], str(row[f'elected_party_{start}'] != row[f'elected_party_{end}']).lower())
            renamed = next(r for r in rows if r['demographic_constituency_code'] == 'US-COUNTY-46102')
            self.assertEqual(renamed['comparison_eligible'], 'true')
            self.assertEqual(canonical(renamed[f'constituency_code_{start}']), 'US-COUNTY-46102')
        for filename, body in build_comparisons().items():
            self.assertEqual((ROOT / 'data' / filename).read_bytes(), body)


if __name__ == '__main__': unittest.main()
