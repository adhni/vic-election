#!/usr/bin/env python3
"""Compare regular Senate seats six years apart at state and county scope. Bismillah."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from build_us_president_demographics import ROOT, read_csv, csv_bytes, json_bytes
from build_us_house_analysis import formatted

DATA=ROOT/'data'
PERIODS=((2016,2022),(2018,2024),(2020,2026))


def inputs(year,scope):
    grouped=defaultdict(list)
    for row in read_csv(DATA/f'us_{year}_senate_{scope}_fpp.csv'):
        code=row['constituency_code'].split(f'US-SENATE-{scope.upper()}-')[-1]
        if scope=='county' and code in {'02','AK'}:code='AK'
        grouped[code].append(row)
    return grouped


def summarize(rows):
    parties=Counter()
    counts=Counter()
    for row in rows:
        if row.get('candidate_grouped')=='true':continue
        parties[row['candidate_party']]+=int(row['votes'])
        counts[row['candidate_party']]+=1
    if sum(int(r['votes']) for r in rows)!=int(rows[0]['formal_votes']):raise ValueError('Vote accounting mismatch')
    leader=max((r for r in rows if r.get('candidate_grouped')!='true'),key=lambda r:int(r['votes']))
    return {'d':parties['Democratic'],'r':parties['Republican'],
        'both':min(parties['Democratic'],parties['Republican'])>0 and min(counts['Democratic'],counts['Republican'])>0,
        'multiple':max(counts['Democratic'],counts['Republican'])>1,
        'called':rows[0]['contest_status']!='provisional-uncalled',
        'party':rows[0]['elected_party'] if rows[0]['elected_party'] else leader['candidate_party'],
        'special':rows[0].get('election_kind')=='special'}


def build_period(start,end,scope):
    before,after=inputs(start,scope),inputs(end,scope)
    demo=read_csv(DATA/f'us_2024_{scope}_demographics.csv')
    demo_prefix='US-COUNTY-' if scope=='county' else 'US-STATE-'
    demos={r['constituency_code'].removeprefix(demo_prefix):r for r in demo}
    state_names={r['constituency_code'].removeprefix('US-STATE-'):r['district'] for r in read_csv(DATA/'us_2024_state_demographics.csv')}
    output=[]
    for code in sorted(set(before)|set(after)):
        a,b=before.get(code),after.get(code)
        example=(b or a)[0]
        state=state_names[code] if scope=='state' else example['electorate_type']
        left,right=summarize(a) if a else None,summarize(b) if b else None
        reasons=[]
        if any(s and s['special'] for s in (left,right)):reasons.append('special_election_not_same_regular_cycle')
        if not a or not b:reasons.append('regular_seat_or_reporting_area_missing_in_one_year')
        if state in {'Alaska','Maine'}:reasons.append('ranked_choice_count_basis_not_standardized')
        if scope=='county' and state=='Connecticut':reasons.append('connecticut_demographic_geography_incompatible')
        if scope=='county' and code=='AK':reasons.append('alaska_statewide_not_county')
        for year,result in ((start,left),(end,right)):
            if not result:continue
            if not result['called']:reasons.append(f'{year}:race_not_called')
            if not result['both']:reasons.append(f'{year}:named_democratic_republican_votes_unavailable')
        eligible=not reasons
        demographic=demos.get(code)
        row={'constituency_code':example['constituency_code'],'district':example['district'],'state':state,
            'demographic_constituency_code':demographic['constituency_code'] if demographic and not(scope=='county' and state=='Connecticut') else '',
            'demographic_year':2024,'senate_class':{2016:3,2018:1,2020:2}[start],
            'boundary_unchanged_verified':'true' if scope=='state' else '',
            'reporting_area_matched':str(bool(a and b and not(scope=='county' and state in {'Alaska','Connecticut'}))).lower(),
            'comparison_eligible':str(eligible).lower(),
            'comparison_sensitivity_eligible':str(eligible and not(left['multiple'] or right['multiple'])).lower(),
            'comparison_exclusion_reason':';'.join(reasons)}
        for year,source,summary in ((start,a,left),(end,b,right)):
            row[f'constituency_code_{year}']=source[0]['constituency_code'] if source else ''
            row[f'district_{year}']=source[0]['district'] if source else ''
            row[f'elected_party_{year}']=summary['party'] if summary and summary['called'] else ''
            row[f'democratic_votes_{year}']=summary['d'] if summary else ''
            row[f'republican_votes_{year}']=summary['r'] if summary else ''
            row[f'democratic_two_party_share_pct_{year}']=formatted(100*summary['d']/(summary['d']+summary['r'])) if summary and summary['both'] else ''
        row['seat_flipped']=str(left['party']!=right['party']).lower() if a and b and left['called'] and right['called'] and not(left['special'] or right['special']) and (scope=='state' or eligible) else ''
        row['democratic_share_change_pp']=formatted(100*right['d']/(right['d']+right['r'])-100*left['d']/(left['d']+left['r'])) if eligible else ''
        output.append(row)
    return output


def artifacts():
    outputs={};summary={}
    for start,end in PERIODS:
        for scope in ('state','county'):
            rows=build_period(start,end,scope)
            name=f'us_senate_{scope}_{start}_{end}_comparison.csv'
            outputs[name]=csv_bytes(rows)
            summary[f'{start}-{end}-{scope}']={'rows':len(rows),'eligible':sum(r['comparison_eligible']=='true' for r in rows),'stricter':sum(r['comparison_sensitivity_eligible']=='true' for r in rows)}
    files=[f'us_{year}_senate_{scope}_fpp.csv' for year in {y for period in PERIODS for y in period} for scope in ('state','county')]
    files.extend(f'us_2024_{scope}_demographics.csv' for scope in ('state','county'))
    metadata={'periods':PERIODS,'summary':summary,
        'policy':'Regular seats only, paired six years apart by Senate class. Florida/Ohio 2026 specials are excluded. Positive named D/R votes required in both years; grouped Other is never allocated to a party. Exclude Alaska/Maine count bases and incompatible Connecticut county demographics. County matches are reporting-identifier matches, not individual boundary audits. County flip flags describe local party leaders, not Senate seats.',
        'demographics':'Fixed 2024 ACS state one-year/county five-year snapshot, not demographic change or causation. Earlier populations can differ.',
        'provisional_2026':'Call the Map / civicAPI snapshot 2026-11-14T15:01:38Z, CC BY 4.0. Uncalled Alaska excluded. County source residuals retained without imputation; see us_2026_senate_metadata.json.',
        'class_sources':[f'https://www.senate.gov/senators/Class_{roman}.htm' for roman in ('I','II','III')],
        'input_sha256':{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in sorted(files)},
        'output_sha256':{name:hashlib.sha256(body).hexdigest() for name,body in outputs.items()}}
    outputs['us_senate_comparison_metadata.json']=json_bytes(metadata)
    return outputs,summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs,summary=artifacts()
    for name,body in outputs.items():
        if args.check:
            if (DATA/name).read_bytes()!=body:raise ValueError(f'Stale comparison: {name}')
        else:(DATA/name).write_bytes(body)
    print(('Validated' if args.check else 'Built')+' Senate six-year comparisons: '+json.dumps(summary))

if __name__=='__main__':main()
