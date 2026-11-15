#!/usr/bin/env python3
"""Audit provisional governor calls, county groups and reporting geography."""
import csv
import json
import unittest
from collections import defaultdict
from pathlib import Path
from build_us_governor_2026 import check, prepare, PARTIES, EXPECTED_STATES

DATA=Path(__file__).resolve().parents[1]/'data'
def read(name):
    with (DATA/name).open() as handle:return list(csv.DictReader(handle))
def grouped(rows,key):
    result=defaultdict(list)
    for row in rows:result[row[key]].append(row)
    return result

class Governor2026Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=read('us_2026_governor_source.csv')
        cls.local_source=read('us_2026_governor_county_source.csv')
        cls.states=grouped(read('us_2026_governor_state_fpp.csv'),'race_id')
        cls.counties=grouped(read('us_2026_governor_county_fpp.csv'),'constituency_code')
        cls.meta=json.loads((DATA/'us_2026_governor_metadata.json').read_text())

    def test_deterministic_artifacts_and_coverage(self):
        check()
        self.assertEqual({r['state'] for r in self.original},EXPECTED_STATES)
        self.assertEqual(len(self.states),36)
        self.assertEqual(len(self.counties),2151)
        for scope,groups in [('state',self.states),('county',self.counties)]:
            geometry=json.loads((DATA/f'us_governor_2026_{scope}_boundaries.geojson').read_text())
            shapes={f['properties']['constituency_code']:f['properties']['district'] for f in geometry['features']}
            self.assertEqual(shapes,{r[0]['constituency_code']:r[0]['district'] for r in groups.values()})
            self.assertEqual(len(geometry['features']),len(groups))

    def test_source_candidate_accounting_and_calls(self):
        original=grouped(self.original,'race_id')
        for race,candidates in original.items():
            rows=self.states[race]
            self.assertEqual({r['candidate']:(r['candidate_party'],int(r['votes'])) for r in rows},
                {r['candidate']:(PARTIES[r['party']],int(r['votes'])) for r in candidates})
            winner=next(r for r in candidates if r['outcome']=='won')
            self.assertTrue(all(r['elected_member']==winner['candidate'] and r['elected_party']==PARTIES[winner['party']] for r in rows))
            self.assertEqual(sum(int(r['votes']) for r in rows),int(candidates[0]['total_votes']))
            self.assertTrue(all(r['contest_status']=='provisional' and 'not certified' in r['result_note'] for r in rows))
        self.assertEqual(self.meta['summary']['source_reported_winners'],36)
        self.assertEqual(self.meta['snapshot_published_utc'],'2026-11-15T18:19:21Z')

    def test_every_county_vote_and_group(self):
        for source in self.local_source:
            if source['state']=='AK':continue
            rows=self.counties['US-GOVERNOR-COUNTY-'+source['fips']]
            by_name={r['candidate']:r for r in rows}
            for suffix in ('a','b'):
                row=by_name[source['candidate_'+suffix]]
                self.assertEqual(row['candidate_party'],PARTIES[source['party_'+suffix]])
                self.assertEqual(int(row['votes']),int(source['votes_'+suffix]))
                self.assertEqual(row['candidate_grouped'],'false')
            other=by_name.get('Other candidates (combined)',{})
            self.assertEqual(int(other.get('votes',0)),int(source['votes_other']))
            if other:self.assertEqual(other['candidate_grouped'],'true')
            self.assertEqual(sum(int(r['votes']) for r in rows),int(source['total_votes']))
            self.assertEqual(int(rows[0]['majority']),abs(int(source['votes_a'])-int(source['votes_b'])))
            self.assertTrue(all(r['elected_member']==r['elected_party']=='' for r in rows))
        self.assertTrue(all(r['unallocated_to_counties']==0 for r in self.meta['summary']['reconciliation'].values()))

    def test_franklin_has_no_inferred_local_winner(self):
        rows=self.counties['US-GOVERNOR-COUNTY-05047']
        self.assertTrue(all(r['contest_status']=='provisional-local-unresolved' for r in rows))
        self.assertTrue(all(r['elected_member']==r['elected_party']=='' for r in rows))
        self.assertEqual({r['candidate']:int(r['votes']) for r in rows},
            {'Fred Love':676,'Sarah Huckabee Sanders':2152,'Other candidates (combined)':2354})
        self.assertEqual(self.meta['summary']['unresolved_local_leaders'],['Franklin County, Arkansas'])
        self.assertIn('No winner is inferred',rows[0]['result_note'])

    def test_connecticut_regions_and_alaska_fallback(self):
        ct=[code for code in self.counties if code.startswith('US-GOVERNOR-COUNTY-09')]
        self.assertEqual(len(ct),9)
        self.assertTrue(all('Planning Region' in self.counties[code][0]['district'] for code in ct))
        alaska=self.counties['US-GOVERNOR-COUNTY-AK']
        self.assertIn('statewide fallback',alaska[0]['district'])
        self.assertEqual({r['candidate']:r['votes'] for r in alaska},{r['candidate']:r['votes'] for r in self.states['GOV-AK']})
        self.assertFalse(any(code.startswith('US-GOVERNOR-COUNTY-029') for code in self.counties))
        self.assertEqual(sum(r['state']=='AK' for r in self.local_source),40)

    def test_a_lead_is_not_a_winner_call(self):
        modified=[dict(r, outcome='') if r['state']=='AK' else r.copy() for r in self.original]
        outputs,summary=prepare(modified,self.local_source,self.meta['snapshot_published_utc'])
        self.assertEqual(summary['source_reported_winners'],35)
        self.assertEqual(summary['uncalled_states'],['AK'])
        rows=list(csv.DictReader(outputs['us_2026_governor_state_fpp.csv'].decode().splitlines()))
        alaska=[r for r in rows if r['race_id']=='GOV-AK']
        self.assertTrue(all(r['contest_status']=='provisional-uncalled' and r['elected_member']=='' for r in alaska))

if __name__=='__main__':unittest.main()
