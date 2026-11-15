#!/usr/bin/env python3
"""Audit comparison eligibility and arithmetic directly against candidate sources."""
import csv
from collections import defaultdict
import unittest
from build_us_house_comparison import ROOT, build_rows, CHANGED_STATES


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_rows()
        cls.sources = {}
        for year in (2022, 2024):
            grouped = defaultdict(list)
            with (ROOT / f'data/us_{year}_house_fpp.csv').open() as handle:
                for row in csv.DictReader(handle):
                    grouped[row['constituency_code']].append(row)
            cls.sources[year] = grouped

    def test_geography_and_exclusions(self):
        self.assertEqual(len(self.rows), 435)
        self.assertEqual(len({r['constituency_code'] for r in self.rows}), 435)
        self.assertEqual(sum(r['comparison_eligible'] == 'true' for r in self.rows), 312)
        for row in self.rows:
            stable = row['state'] not in CHANGED_STATES
            self.assertEqual(row['boundary_unchanged_verified'], str(stable).lower())
            if not stable or row['state'] in {'Alaska', 'Maine'}:
                self.assertEqual(row['comparison_eligible'], 'false')
                self.assertEqual(row['democratic_share_change_pp'], '')

    def test_flips_use_elected_parties_and_verified_boundaries(self):
        for row in self.rows:
            parties = {year: self.sources[year][row['constituency_code']][0]['elected_party'] for year in (2022, 2024)}
            statuses = [self.sources[year][row['constituency_code']][0]['contest_status'] for year in (2022, 2024)]
            for year in parties:
                self.assertEqual(row[f'elected_party_{year}'], parties[year])
            valid = row['state'] not in CHANGED_STATES and all(parties.values()) and all(status in {'official', 'uncontested'} for status in statuses)
            self.assertEqual(row['seat_flipped'], str(parties[2022] != parties[2024]).lower() if valid else '')
        by_name = {row['district']: row for row in self.rows}
        self.assertEqual(by_name['California 13th']['seat_flipped'], 'true')
        self.assertEqual(by_name['Colorado 8th']['seat_flipped'], 'true')
        self.assertEqual(by_name['Montana 2nd']['seat_flipped'], 'false')  # big swing, same winning party
        self.assertEqual(by_name['Alaska at-large']['seat_flipped'], 'true')  # known winners, excluded vote-count comparison
        self.assertEqual(by_name['New York 19th']['seat_flipped'], '')  # changed plan

    def test_independent_vote_arithmetic_and_common_sample(self):
        for row in self.rows:
            shares = {}
            expected = row['state'] not in CHANGED_STATES | {'Alaska', 'Maine'}
            for year in (2022, 2024):
                source = self.sources[year][row['constituency_code']]
                totals = {party: sum(int(r['votes']) for r in source if r['candidate_party'] in {party, f'Write-in ({party})'})
                          for party in ('Democratic', 'Republican')}
                valid = (source[0]['contest_status'] == 'official'
                         and all(any(r['candidate_party'] == party for r in source) and totals[party] > 0 for party in totals))
                expected = expected and valid
                self.assertEqual(int(row[f'democratic_votes_{year}']), totals['Democratic'])
                self.assertEqual(int(row[f'republican_votes_{year}']), totals['Republican'])
                if valid:
                    shares[year] = 100 * totals['Democratic'] / sum(totals.values())
                    self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']), shares[year], places=5)
                else:
                    self.assertEqual(row[f'democratic_two_party_share_pct_{year}'], '')
            self.assertEqual(row['comparison_eligible'], str(expected).lower())
            if expected:
                self.assertAlmostEqual(float(row['democratic_share_change_pp']), shares[2024] - shares[2022], places=5)
                # Republican shares complement Democratic shares; changes negate.
                self.assertAlmostEqual(-float(row['democratic_share_change_pp']), (100 - shares[2024]) - (100 - shares[2022]), places=5)
                single = all(row[f'multiple_major_party_candidates_{year}'] == 'false' for year in (2022, 2024))
                self.assertEqual(row['comparison_sensitivity_eligible'], str(single).lower())
            else:
                self.assertEqual(row['democratic_share_change_pp'], '')


if __name__ == '__main__':
    unittest.main()
