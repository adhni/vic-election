#!/usr/bin/env python3
"""Independent state demographic accounting and presidential share/flip checks."""
import csv
import hashlib
import json
import unittest
from pathlib import Path

from build_us_president_demographics import ROOT, PREFIX, YEARS, PERIODS, comparison_artifacts


def read(name):
    with (ROOT / 'data' / name).open() as handle:
        return list(csv.DictReader(handle))


class PresidentialDemographicTests(unittest.TestCase):
    def test_geography_sources_and_demographic_arithmetic(self):
        metadata = json.loads((ROOT / 'data' / (PREFIX + '_metadata.json')).read_text())
        self.assertEqual(metadata['area_count'], 51)
        self.assertEqual(metadata['metric_count'], 42)
        for name, info in metadata['outputs'].items():
            body = (ROOT / 'data' / name).read_bytes()
            self.assertEqual(len(body), info['bytes'])
            self.assertEqual(hashlib.sha256(body).hexdigest(), info['sha256'])
        raw = {r['constituency_code']: r for r in read(PREFIX + '_acs.csv')}
        derived = read(PREFIX + '.csv')
        self.assertEqual(len(raw), 51)
        self.assertEqual({r['district'] for r in derived}, {r['district'] for r in read('us_2024_president_state_fpp.csv')})
        for row in derived:
            source = raw[row['constituency_code']]
            self.assertRegex(row['census_geo_id'], r'^0400000US\d{2}$')
            self.assertEqual(row['acs_year'], '2024')
            population = int(source['B01001_001E'])
            self.assertEqual(population, int(source['B03002_001E']))
            self.assertEqual(population, int(source['B05002_001E']))
            self.assertEqual(int(source['B01001_002E']) + int(source['B01001_026E']), population)
            for metric, definition in metadata['metrics'].items():
                nums = [float(source[v]) for v in definition['numerator']]
                dens = [float(source[v]) for v in definition['denominator']]
                available = all(v >= 0 for v in nums + dens) and (not dens or sum(dens) > 0)
                self.assertEqual(bool(row[metric]), available)
                if available:
                    expected = sum(nums) * 100 / sum(dens) if dens else sum(nums)
                    self.assertAlmostEqual(float(row[metric]), expected, places=5)
                    self.assertTrue(not row[metric + '_moe'] or float(row[metric + '_moe']) >= 0)
        flags = read(PREFIX + '_flags.csv')
        self.assertEqual({(r['constituency_code'], r['variable']) for r in flags}, {(code, v) for code, r in raw.items() for v in metadata['variables'] if not r[v] or float(r[v]) < 0})
        for source in metadata['sources']:
            self.assertTrue(source['url'].startswith(('https://www2.census.gov/', 'https://api.census.gov/')))
            cache = ROOT / 'tmp/us_house_demographics' / source['filename']
            if cache.exists():
                self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(), source['sha256'])

    def test_cached_national_extract_matches_every_state_cell(self):
        metadata = json.loads((ROOT / 'data' / (PREFIX + '_metadata.json')).read_text())
        raw = {r['census_geo_id']: r for r in read(PREFIX + '_acs.csv')}
        for source in metadata['sources']:
            if not source['filename'].endswith('.dat'):
                continue
            cache = ROOT / 'tmp/us_house_demographics' / source['filename']
            if not cache.exists():
                continue  # CI checks committed hashes and arithmetic without downloading national files.
            table = source['filename'].split('-')[-1].split('.')[0].upper()
            found = set()
            with cache.open(newline='', encoding='utf-8-sig') as handle:
                for row in csv.DictReader(handle, delimiter='|'):
                    if row['GEO_ID'] not in raw:
                        continue
                    found.add(row['GEO_ID'])
                    for variable, definition in metadata['variables'].items():
                        if definition['table'] == table:
                            self.assertEqual(raw[row['GEO_ID']][variable], row[f'{table}_{variable[-1]}{variable[-4:-1]}'])
            self.assertEqual(found, raw.keys())

    def test_every_state_election_share_and_flip(self):
        expected_flips = {
            (2008, 2012): {'Indiana', 'North Carolina'},
            (2012, 2016): {'Florida', 'Iowa', 'Michigan', 'Ohio', 'Pennsylvania', 'Wisconsin'},
            (2016, 2020): {'Arizona', 'Georgia', 'Michigan', 'Pennsylvania', 'Wisconsin'},
            (2020, 2024): {'Arizona', 'Georgia', 'Michigan', 'Nevada', 'Pennsylvania', 'Wisconsin'},
        }
        sources = {}
        for year in YEARS:
            grouped = {}
            for row in read(f'us_{year}_president_state_fpp.csv'):
                grouped.setdefault(row['constituency_code'], {})[row['candidate_party']] = int(row['votes'])
            sources[year] = grouped
        for start, end in PERIODS:
            rows = read(f'us_president_{start}_{end}_comparison.csv')
            self.assertEqual(len(rows), 51)
            self.assertEqual({r['district'] for r in rows if r['seat_flipped'] == 'true'}, expected_flips[start, end])
            for row in rows:
                shares = {}
                for year in (start, end):
                    totals = sources[year][row['constituency_code']]
                    shares[year] = 100 * totals['Democratic'] / (totals['Democratic'] + totals['Republican'])
                    self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']), shares[year], places=5)
                    self.assertEqual(row[f'elected_party_{year}'], max(totals, key=totals.get))
                self.assertAlmostEqual(float(row['democratic_share_change_pp']), shares[end] - shares[start], places=5)
                self.assertEqual(row['comparison_eligible'], 'true')
            self.assertTrue({'Alaska', 'Maine', 'District of Columbia'} <= {r['district'] for r in rows})
        for name, expected in comparison_artifacts().items():
            self.assertEqual((ROOT / 'data' / name).read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
