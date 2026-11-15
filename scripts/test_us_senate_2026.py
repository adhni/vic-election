#!/usr/bin/env python3
"""Independent accounting and scope checks for the frozen 2026 Senate snapshot."""
import csv
import json
import unittest
from collections import defaultdict
from pathlib import Path
from build_us_senate_2026 import check, PARTIES, REGULAR_STATES

DATA = Path(__file__).resolve().parents[1]/'data'
def read(name):
    with (DATA/name).open() as handle:
        return list(csv.DictReader(handle))
def grouped(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[row[key]].append(row)
    return result

class Senate2026Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = grouped(read('us_2026_senate_source.csv'),'state')
        cls.county_source = read('us_2026_senate_county_source.csv')
        cls.states = grouped(read('us_2026_senate_state_fpp.csv'),'race_id')
        cls.counties = grouped(read('us_2026_senate_county_fpp.csv'),'constituency_code')
        cls.meta = json.loads((DATA/'us_2026_senate_metadata.json').read_text())

    def test_rebuild_and_boundary_joins(self):
        check()
        for scope, groups in [('state',self.states),('county',self.counties)]:
            geometry = json.loads((DATA/f'us_senate_2026_{scope}_boundaries.geojson').read_text())
            by_code = {r[0]['constituency_code']:r[0]['district'] for r in groups.values()}
            shapes = {f['properties']['constituency_code']:f['properties']['district'] for f in geometry['features']}
            self.assertEqual(shapes,by_code)
            self.assertEqual(len(geometry['features']),len(groups))
        self.assertEqual(len(self.states),35)
        self.assertEqual(len(self.counties),2443)

    def test_regular_and_special_seat_identity(self):
        self.assertEqual(set(self.source),REGULAR_STATES | {'FL','OH'})
        self.assertEqual(len(REGULAR_STATES),33)
        for state in self.source:
            for row in self.states['SEN-'+state]:
                self.assertEqual(row['election_kind'],'special' if state in {'FL','OH'} else 'regular')
                self.assertEqual(row['senate_class'],'3' if state in {'FL','OH'} else '2')
        self.assertIn('not a certified',self.meta['source_credit'])
        self.assertIn('100-seat',self.meta['scope_policy'])

    def test_each_state_candidate_and_explicit_call(self):
        calls = 0
        for state, original in self.source.items():
            result = self.states['SEN-'+state]
            source_candidates = {r['candidate']:(PARTIES[r['party']],int(r['votes'])) for r in original}
            result_candidates = {r['candidate']:(r['candidate_party'],int(r['votes'])) for r in result}
            self.assertEqual(source_candidates,result_candidates)
            total = sum(v[1] for v in result_candidates.values())
            self.assertTrue(all(int(r['formal_votes'])==total for r in result))
            winner = next((r for r in original if r['outcome']=='won'),None)
            calls += bool(winner)
            for row in result:
                self.assertEqual(row['elected_member'],winner['candidate'] if winner else '')
                self.assertEqual(row['elected_party'],PARTIES[winner['party']] if winner else '')
                self.assertEqual(row['contest_status'],'provisional' if winner else 'provisional-uncalled')
                self.assertIn('not certified',row['result_note'])
        self.assertEqual(calls,34)
        self.assertEqual(self.meta['summary']['uncalled_states'],['AK'])

    def test_every_county_source_vote_and_party(self):
        for source in self.county_source:
            if source['state']=='AK':continue
            rows = self.counties['US-SENATE-COUNTY-'+source['fips']]
            candidates = {r['candidate']:r for r in rows}
            for suffix in ('a','b'):
                row = candidates[source['candidate_'+suffix]]
                self.assertEqual(row['candidate_party'],PARTIES[source['party_'+suffix]])
                self.assertEqual(int(row['votes']),int(source['votes_'+suffix]))
            other = int(source['votes_other'])
            self.assertEqual(int(candidates.get('Other candidates (combined)',{}).get('votes',0)),other)
            self.assertEqual(sum(int(r['votes']) for r in rows),int(source['total_votes']))
            self.assertEqual(int(rows[0]['majority']),abs(int(source['votes_a'])-int(source['votes_b'])))
            self.assertTrue(all(r['candidate_grouped']==str(r['candidate']=='Other candidates (combined)').lower() for r in rows))
            self.assertTrue(all(r['elected_member']==r['elected_party']=='' for r in rows))
            self.assertTrue(all(r['contest_status']=='provisional-local' for r in rows))
            self.assertTrue(all('not elected senators' in r['result_note'] for r in rows))

    def test_independents_and_state_county_residual(self):
        for state in ('ID','MT','NE','SD'):
            county = next(r for r in self.county_source if r['state']==state)
            result = self.counties['US-SENATE-COUNTY-'+county['fips']]
            candidate = next(r for r in result if r['candidate']==county['candidate_a'])
            self.assertEqual(candidate['candidate_party'],'Independent')
        differences = {s:r['unallocated_to_counties'] for s,r in self.meta['summary']['reconciliation'].items() if r['unallocated_to_counties']}
        self.assertEqual(differences,{'AK':200,'RI':778})
        ri = [rows for code,rows in self.counties.items() if code.startswith('US-SENATE-COUNTY-44')]
        self.assertEqual(sum(int(rows[0]['formal_votes']) for rows in ri),359628)
        self.assertTrue(all('778 additional statewide votes' in rows[0]['result_note'] for rows in ri))
        self.assertEqual(int(self.states['SEN-RI'][0]['formal_votes']),360406)

    def test_alaska_uses_statewide_counts_not_fake_counties(self):
        fallback = self.counties['US-SENATE-COUNTY-AK']
        statewide = self.states['SEN-AK']
        self.assertEqual({r['candidate']:r['votes'] for r in fallback},{r['candidate']:r['votes'] for r in statewide})
        self.assertTrue(all(r['contest_status']=='provisional-uncalled' for r in fallback))
        self.assertIn('statewide fallback',fallback[0]['district'])
        self.assertIn('not county/borough',fallback[0]['result_note'])
        self.assertFalse(any(code.startswith('US-SENATE-COUNTY-029') for code in self.counties))
        self.assertEqual(sum(r['state']=='AK' for r in self.county_source),40)

if __name__=='__main__':unittest.main()
