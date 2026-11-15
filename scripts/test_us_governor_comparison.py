#!/usr/bin/env python3
"""Independently audit mixed two-/four-year governor baselines and arithmetic."""
import csv
import unittest
from collections import defaultdict
from pathlib import Path
from build_us_governor_comparison import artifacts

DATA=Path(__file__).resolve().parents[1]/'data'
def read(name):
    with (DATA/name).open() as handle:return list(csv.DictReader(handle))
def grouped(year,scope):
    result=defaultdict(list)
    for row in read(f'us_{year}_governor_{scope}_fpp.csv'):result[row['constituency_code']].append(row)
    return result

class GovernorComparisonTests(unittest.TestCase):
    def test_deterministic_artifacts(self):
        outputs,_=artifacts()
        for name,body in outputs.items():self.assertEqual((DATA/name).read_bytes(),body,name)

    def test_exact_previous_regular_year_per_area(self):
        for scope in ('state','county'):
            rows=read(f'us_governor_{scope}_2026_previous_comparison.csv')
            self.assertEqual(len(rows),36 if scope=='state' else 2151)
            for row in rows:
                year=2024 if row['state'] in {'New Hampshire','Vermont'} else 2022
                self.assertEqual(int(row['baseline_year']),year)
                self.assertEqual(int(row['years_between_elections']),2026-year)
                other=2022 if year==2024 else 2024
                self.assertEqual(row[f'democratic_votes_{other}'],'')
                self.assertEqual(row[f'district_{other}'],'')
            self.assertEqual(sum(r['baseline_year']=='2024' for r in rows),2 if scope=='state' else 24)

    def test_every_named_party_total_and_raw_pp_change(self):
        for scope in ('state','county'):
            source={year:grouped(year,scope) for year in (2022,2024,2026)}
            for row in read(f'us_governor_{scope}_2026_previous_comparison.csv'):
                shares=[];leaders=[];multiple=False
                for year in (int(row['baseline_year']),2026):
                    code=row[f'constituency_code_{year}']
                    if not code:continue
                    original=source[year][code]
                    named=[r for r in original if r.get('candidate_grouped')!='true']
                    totals={p:sum(int(r['votes']) for r in named if r['candidate_party']==p) for p in ('Democratic','Republican')}
                    multiple |= max(sum(r['candidate_party']==p for r in named) for p in totals)>1
                    self.assertEqual(int(row[f'democratic_votes_{year}']),totals['Democratic'])
                    self.assertEqual(int(row[f'republican_votes_{year}']),totals['Republican'])
                    if min(totals.values())>0:
                        share=100*totals['Democratic']/sum(totals.values())
                        self.assertAlmostEqual(float(row[f'democratic_two_party_share_pct_{year}']),share,places=5)
                        shares.append(share)
                    leaders.append(original[0]['elected_party'] or max(named,key=lambda r:int(r['votes']))['candidate_party'])
                if row['comparison_eligible']=='true':
                    self.assertEqual(len(shares),2)
                    self.assertAlmostEqual(float(row['democratic_share_change_pp']),shares[1]-shares[0],places=5)
                    self.assertEqual(row['seat_flipped'],str(leaders[0]!=leaders[1]).lower())
                    self.assertEqual(row['comparison_sensitivity_eligible'],str(not multiple).lower())
                else:self.assertEqual(row['democratic_share_change_pp'],'')

    def test_exclusions_and_independent_votes(self):
        counties=read('us_governor_county_2026_previous_comparison.csv')
        franklin=next(r for r in counties if r['district']=='Franklin County, Arkansas')
        self.assertEqual(franklin['comparison_eligible'],'false')
        self.assertIn('local_leader_unresolved',franklin['comparison_exclusion_reason'])
        self.assertEqual(franklin['seat_flipped'],'')
        for row in counties:
            if row['state'] in {'Alaska','Connecticut','Rhode Island'}:self.assertEqual(row['comparison_eligible'],'false')
            if row['state']=='Rhode Island':self.assertEqual(row['republican_votes_2026'],'0')
            if row['state']=='Connecticut':self.assertEqual(row['constituency_code_2022'],'')
        states=read('us_governor_state_2026_previous_comparison.csv')
        maine=next(r for r in states if r['state']=='Maine')
        self.assertEqual(maine['comparison_eligible'],'true')
        self.assertNotIn('ranked_choice',maine['comparison_exclusion_reason'])
        alaska=next(r for r in states if r['state']=='Alaska')
        self.assertEqual(alaska['comparison_eligible'],'false')
        self.assertEqual(alaska['seat_flipped'],'true') # Known elected-party flip independent of share eligibility.

    def test_sample_sizes(self):
        _,summary=artifacts()
        self.assertEqual((summary['state']['eligible'],summary['state']['stricter']),(34,33))
        self.assertEqual((summary['county']['eligible'],summary['county']['stricter']),(2109,2107))

if __name__=='__main__':unittest.main()
