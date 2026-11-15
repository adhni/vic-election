#!/usr/bin/env python3
"""Audit provisional House results and comparison eligibility against source rows."""
import csv
import json
import unittest
from collections import defaultdict
from pathlib import Path
from build_us_house_2026 import CHANGED_STATES, PARTIES, check

ROOT = Path(__file__).resolve().parents[1]
def rows(name):
    with (ROOT/'data'/name).open() as handle:
        return list(csv.DictReader(handle))

class House2026Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = defaultdict(list)
        for row in rows('us_2026_house_source.csv'): cls.source[row['race_id']].append(row)
        cls.results = defaultdict(list)
        for row in rows('us_2026_house_fpp.csv'): cls.results[row['constituency_code']].append(row)
        cls.comparison = rows('us_house_2024_2026_comparison.csv')

    def test_artifacts_and_coverage(self):
        check()
        self.assertEqual(len(self.source), 435)
        self.assertEqual(len(self.results), 435)
        geo = json.loads((ROOT/'data/us_2026_congressional_boundaries.geojson').read_text())
        self.assertEqual({f['properties']['constituency_code'] for f in geo['features']}, set(self.results))
        self.assertTrue(all(f['geometry']['type'] in {'Polygon','MultiPolygon'} for f in geo['features']))

    def test_source_accounting_and_winner_calls(self):
        source_by_page = {r[0]['page_url']:r for r in self.source.values()}
        called = 0
        for candidates in self.results.values():
            original = source_by_page[candidates[0]['district_url']]
            self.assertEqual({r['candidate']:int(r['votes']) for r in candidates}, {r['candidate']:int(r['votes'] or 0) for r in original})
            self.assertEqual(sum(int(r['votes']) for r in candidates), int(original[0]['total_votes'] or 0))
            winner = next((r for r in original if r['outcome']=='won'), None)
            called += bool(winner)
            for row in candidates:
                self.assertEqual(row['elected_member'], winner['candidate'] if winner else '')
                self.assertEqual(row['elected_party'], PARTIES[winner['party']] if winner else '')
                self.assertEqual(row['contest_status'], 'provisional' if winner else 'provisional-uncalled')
                self.assertIn('not certified', row['result_note'])
                self.assertIn('CC BY 4.0', row['result_note'])
        self.assertEqual(called, 421)

    def test_uncalled_have_no_winner_flip_or_swing(self):
        uncalled = [r for r in self.comparison if r['result_called_2026']=='false']
        self.assertEqual(len(uncalled), 14)
        for row in uncalled:
            self.assertEqual(row['elected_party_2026'], '')
            self.assertEqual(row['seat_flipped'], '')
            self.assertEqual(row['democratic_share_change_pp'], '')
            self.assertEqual(row['comparison_eligible'], 'false')
            self.assertIn('race_not_called', row['comparison_exclusion_reason'])

    def test_geography_policy_and_missouri(self):
        for row in self.comparison:
            stable = row['state'] not in CHANGED_STATES
            self.assertEqual(row['boundary_unchanged_verified'], str(stable).lower())
            if not stable:
                self.assertEqual(row['comparison_eligible'], 'false')
                self.assertEqual(row['seat_flipped'], '')
                self.assertEqual(row['democratic_share_change_pp'], '')
        self.assertTrue(all(r['boundary_unchanged_verified']=='true' for r in self.comparison if r['state']=='Missouri'))
        self.assertEqual(sum(r['boundary_unchanged_verified']=='true' for r in self.comparison), 262)

    def test_eligible_shares_and_flips(self):
        eligible = [r for r in self.comparison if r['comparison_eligible']=='true']
        self.assertEqual(len(eligible), 236)
        for row in eligible:
            self.assertNotIn(row['state'], CHANGED_STATES | {'Alaska','Maine'})
            self.assertEqual(row['result_called_2026'], 'true')
            shares=[]
            for year in (2024,2026):
                d, r = (int(row[f'{party}_votes_{year}']) for party in ('democratic','republican'))
                self.assertGreater(min(d,r), 0)
                shares.append(100*d/(d+r))
                self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']), shares[-1], places=5)
            self.assertAlmostEqual(float(row['democratic_share_change_pp']), shares[1]-shares[0], places=5)
            self.assertEqual(row['seat_flipped'], str(row['elected_party_2024']!=row['elected_party_2026']).lower())

    def test_unreported_votes_are_explicit(self):
        row = next(r[0] for r in self.results.values() if r[0]['district']=='Florida 10th')
        self.assertEqual(row['formal_votes'], '0')
        self.assertIn('not reported', row['result_note'])
        self.assertIn('structural placeholders', row['result_note'])
        comparison = next(r for r in self.comparison if r['district']=='Florida 10th')
        self.assertEqual(comparison['comparison_eligible'], 'false')

if __name__=='__main__': unittest.main()
