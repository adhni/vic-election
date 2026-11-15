#!/usr/bin/env python3
"""Verify district matching logic and the committed boundary audit evidence."""
import csv
import hashlib
import json
from pathlib import Path
import unittest

from build_us_house_boundary_audit import compare_blocks

ROOT = Path(__file__).resolve().parents[1]


class BoundaryAuditTests(unittest.TestCase):
    def test_exact_match_can_have_a_different_district_number(self):
        rows = compare_blocks({'01': {'a', 'b'}, '02': {'c', 'd'}}, {'07': {'c', 'd'}, '08': {'a', 'b'}})
        self.assertEqual([(r['number'], r['previous_number'], r['boundary_unchanged_verified']) for r in rows],
                         [('07', '02', 'true'), ('08', '01', 'true')])

    def test_similar_is_not_identical_even_with_equal_block_counts(self):
        rows = compare_blocks({'01': {'a', 'b', 'c'}}, {'01': {'a', 'b', 'd'}})
        row = rows[0]
        self.assertEqual(row['boundary_unchanged_verified'], 'false')
        self.assertEqual((row['added_block_count'], row['removed_block_count']), (1, 1))
        self.assertNotEqual(row['previous_block_sha256'], row['current_block_sha256'])
        large = {str(i) for i in range(10000)}
        almost = compare_blocks({'01': large}, {'01': large | {'new'}})[0]
        self.assertGreater(float(almost['block_overlap_pct']), 99.9)
        self.assertEqual(almost['boundary_unchanged_verified'], 'false')

    def test_committed_audit_coverage_hash_and_accounting(self):
        path = ROOT / 'data/us_house_2020_2022_boundary_audit.csv'
        metadata = json.loads((ROOT / 'data/us_house_2020_2022_boundary_audit_metadata.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), metadata['output_sha256'])
        with path.open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 435)
        self.assertEqual(len({r['constituency_code'] for r in rows}), 435)
        same = [r for r in rows if r['boundary_unchanged_verified'] == 'true']
        self.assertEqual(len(same), metadata['verified_unchanged_districts'])
        self.assertEqual({r['constituency_code'] for r in same}, {'0200', '1000', '3800', '4600', '5000', '5600'})
        for row in rows:
            if row['audit_method'] == 'census_2020_block_membership':
                old, current, shared, added, removed = (int(row[k]) for k in
                    ('previous_block_count', 'current_block_count', 'shared_block_count', 'added_block_count', 'removed_block_count'))
                self.assertEqual(old, shared + removed)
                self.assertEqual(current, shared + added)
                self.assertAlmostEqual(float(row['block_overlap_pct']), 100 * shared / (shared + added + removed), places=6)
                self.assertEqual(row['boundary_unchanged_verified'] == 'true', added == 0 and removed == 0)
                self.assertEqual(row['previous_block_sha256'] == row['current_block_sha256'], added == 0 and removed == 0)
            else:
                self.assertTrue(row['constituency_code'].startswith('37'))
                self.assertLess(float(row['polygon_overlap_pct']), 95)
                self.assertEqual(row['boundary_unchanged_verified'], 'false')
        by_code = {r['constituency_code']: r for r in rows}
        self.assertEqual(by_code['1502']['added_block_count'], '45')
        self.assertEqual(by_code['5507']['added_block_count'], '214')
        self.assertEqual(by_code['5507']['removed_block_count'], '3')


if __name__ == '__main__':
    unittest.main()
