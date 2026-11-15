#!/usr/bin/env python3
"""Verify six-year Senate identity, named votes and exclusions independently."""
import csv
import json
import unittest
from collections import defaultdict
from pathlib import Path
from build_us_senate_comparison import artifacts

DATA=Path(__file__).resolve().parents[1]/'data'
PERIODS=((2016,2022),(2018,2024),(2020,2026))
def read(name):
    with (DATA/name).open() as handle:return list(csv.DictReader(handle))
def source(year,scope):
    grouped=defaultdict(list)
    for row in read(f'us_{year}_senate_{scope}_fpp.csv'):
        grouped[row['constituency_code']].append(row)
    return grouped

class SenateComparisonTests(unittest.TestCase):
    def test_deterministic_artifacts(self):
        outputs,_=artifacts()
        for name,body in outputs.items():self.assertEqual((DATA/name).read_bytes(),body,name)

    def test_six_year_class_and_regular_identity(self):
        for start,end in PERIODS:
            rows=read(f'us_senate_state_{start}_{end}_comparison.csv')
            self.assertEqual(end-start,6)
            matched=[r for r in rows if r[f'constituency_code_{start}'] and r[f'constituency_code_{end}']]
            self.assertEqual(len(matched),34 if start==2016 else 33)
            for row in matched:
                self.assertEqual(row[f'constituency_code_{start}'],row[f'constituency_code_{end}'])
                self.assertEqual(row['senate_class'],str({2016:3,2018:1,2020:2}[start]))
            for row in rows:
                if end==2026 and row['state'] in {'Florida','Ohio'}:
                    self.assertEqual(row['comparison_eligible'],'false')
                    self.assertIn('special_election',row['comparison_exclusion_reason'])
                    self.assertEqual(row['democratic_share_change_pp'],'')
                    self.assertEqual(row['seat_flipped'],'')

    def test_all_party_counts_shares_and_flips(self):
        for start,end in PERIODS:
            for scope in ('state','county'):
                sources={year:source(year,scope) for year in (start,end)}
                for row in read(f'us_senate_{scope}_{start}_{end}_comparison.csv'):
                    shares=[]
                    leaders=[]
                    for year in (start,end):
                        code=row[f'constituency_code_{year}']
                        if not code:continue
                        candidates=sources[year][code]
                        votes={party:sum(int(r['votes']) for r in candidates if r['candidate_party']==party and r.get('candidate_grouped')!='true') for party in ('Democratic','Republican')}
                        self.assertEqual(int(row[f'democratic_votes_{year}']),votes['Democratic'])
                        self.assertEqual(int(row[f'republican_votes_{year}']),votes['Republican'])
                        if min(votes.values())>0:
                            share=100*votes['Democratic']/sum(votes.values())
                            self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']),share,places=5)
                            shares.append(share)
                        if candidates[0]['contest_status']=='provisional-uncalled':
                            self.assertEqual(row[f'elected_party_{year}'],'')
                            self.assertEqual(row['comparison_eligible'],'false')
                        else:
                            named=[r for r in candidates if r.get('candidate_grouped')!='true']
                            leaders.append(candidates[0]['elected_party'] or max(named,key=lambda r:int(r['votes']))['candidate_party'])
                    if row['comparison_eligible']=='true':
                        self.assertEqual(len(shares),2)
                        self.assertAlmostEqual(float(row['democratic_share_change_pp']),shares[1]-shares[0],places=5)
                        self.assertNotIn(row['state'],{'Alaska','Maine'})
                        self.assertEqual(row['seat_flipped'],str(leaders[0]!=leaders[1]).lower())
                    else:self.assertEqual(row['democratic_share_change_pp'],'')

    def test_reporting_and_independent_exclusions(self):
        for start,end in PERIODS:
            for row in read(f'us_senate_county_{start}_{end}_comparison.csv'):
                if row['state'] in {'Alaska','Connecticut','Maine'}:
                    self.assertEqual(row['comparison_eligible'],'false')
                if row['state']=='Connecticut':self.assertEqual(row['demographic_constituency_code'],'')
                if not row[f'constituency_code_{start}'] or not row[f'constituency_code_{end}']:
                    self.assertEqual(row['comparison_eligible'],'false')
        rows=read('us_senate_county_2020_2026_comparison.csv')
        for row in rows:
            if row['state'] in {'Idaho','Montana','Nebraska','South Dakota'} and row['constituency_code_2026']:
                self.assertEqual(row['comparison_eligible'],'false')
                self.assertEqual(row['democratic_votes_2026'],'0')
        # Georgia's 2020 baseline is the regular Ossoff seat, not Warnock's special.
        state=next(r for r in read('us_senate_state_2020_2026_comparison.csv') if r['state']=='Georgia')
        self.assertEqual(state['elected_party_2020'],'Democratic')
        self.assertEqual(state['seat_flipped'],'false')
        rows=source(2020,'state')['US-SENATE-STATE-GA']
        self.assertTrue(any('Ossoff' in r['candidate'] for r in rows))
        self.assertFalse(any('Warnock' in r['candidate'] for r in rows))

    def test_expected_sample_sizes(self):
        metadata=json.loads((DATA/'us_senate_comparison_metadata.json').read_text())
        expected={'2016-2022-state':30,'2018-2024-state':28,'2020-2026-state':27,
                  '2016-2022-county':1895,'2018-2024-county':1630,'2020-2026-county':1933}
        self.assertEqual({key:value['eligible'] for key,value in metadata['summary'].items()},expected)

if __name__=='__main__':unittest.main()
