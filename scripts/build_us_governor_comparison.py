#!/usr/bin/env python3
"""Governor swing against each state's preceding regular election. Bismillah."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from build_us_president_demographics import ROOT, read_csv, csv_bytes, json_bytes
from build_us_house_analysis import formatted

DATA=ROOT/'data'
TWO_YEAR_STATES={'New Hampshire','Vermont'}
YEARS=(2016,2018,2020,2022,2024,2026)
COMPARISON_YEARS=YEARS[1:]


def baseline_year(state, election_year=2026):
    return election_year-(2 if state in TWO_YEAR_STATES else 4)


def inputs(year,scope):
    grouped=defaultdict(list)
    for row in read_csv(DATA/f'us_{year}_governor_{scope}_fpp.csv'):
        code=row['constituency_code'].removeprefix(f'US-GOVERNOR-{scope.upper()}-')
        if scope=='county' and code in {'02','AK'}:code='AK'
        grouped[code].append(row)
    return grouped


def summarize(rows):
    parties=Counter();counts=Counter()
    for row in rows:
        if row.get('candidate_grouped')=='true':continue
        parties[row['candidate_party']]+=int(row['votes'])
        counts[row['candidate_party']]+=1
    if sum(int(r['votes']) for r in rows)!=int(rows[0]['formal_votes']):raise ValueError('Source vote accounting mismatch')
    leader=max((r for r in rows if r.get('candidate_grouped')!='true'),key=lambda r:int(r['votes']))
    return {'d':parties['Democratic'],'r':parties['Republican'],
        'both':min(parties['Democratic'],parties['Republican'])>0 and min(counts['Democratic'],counts['Republican'])>0,
        'multiple':max(counts['Democratic'],counts['Republican'])>1,
        'called':rows[0]['contest_status']!='provisional-uncalled',
        'unresolved':rows[0]['contest_status']=='provisional-local-unresolved',
        'special':rows[0].get('election_kind')=='special',
        'party':rows[0]['elected_party'] or leader['candidate_party']}


def build_scope(scope, election_year=2026):
    sources={year:inputs(year,scope) for year in YEARS}
    demo_prefix='US-COUNTY-' if scope=='county' else 'US-STATE-'
    demos={r['constituency_code'].removeprefix(demo_prefix):r for r in read_csv(DATA/f'us_2024_{scope}_demographics.csv')}
    output=[]
    for code,current in sorted(sources[election_year].items()):
        example=current[0]
        state=example['district'] if scope=='state' else example['electorate_type']
        previous_year=baseline_year(state,election_year)
        previous=sources.get(previous_year,{}).get(code)
        before,after=summarize(previous) if previous else None,summarize(current)
        reasons=[]
        if previous_year not in sources:reasons.append('previous_election_data_unavailable')
        elif not previous:reasons.append('previous_reporting_area_missing')
        if state=='Alaska' and election_year>=2022:reasons.append('ranked_choice_count_basis_not_standardized')
        if scope=='county' and state=='Alaska':reasons.append('alaska_statewide_not_county')
        if scope=='county' and state=='Connecticut':reasons.append('connecticut_counties_to_planning_regions')
        for year,result in ((previous_year,before),(election_year,after)):
            if not result:continue
            if result['special']:reasons.append(f'{year}:special_election')
            if not result['called']:reasons.append(f'{year}:race_not_called')
            if result['unresolved']:reasons.append(f'{year}:local_leader_unresolved')
            if not result['both']:reasons.append(f'{year}:named_democratic_republican_votes_unavailable')
        eligible=not reasons
        demographic=demos.get(code)
        row={'constituency_code':example['constituency_code'],'district':example['district'],'state':state,
            'baseline_year':previous_year,'election_year':election_year,'years_between_elections':election_year-previous_year,
            'demographic_constituency_code':demographic['constituency_code'] if demographic else '',
            'demographic_year':2024,'boundary_unchanged_verified':'true' if scope=='state' else '',
            'reporting_area_matched':str(bool(previous and not(scope=='county' and state in {'Alaska','Connecticut'}))).lower(),
            'comparison_eligible':str(eligible).lower(),
            'comparison_sensitivity_eligible':str(eligible and not(before['multiple'] or after['multiple'])).lower(),
            'comparison_exclusion_reason':';'.join(reasons)}
        for year in sorted({election_year-4,election_year-2,election_year}):
            raw=current if year==election_year else previous if year==previous_year else None
            summary=after if year==election_year else before if year==previous_year else None
            row[f'constituency_code_{year}']=raw[0]['constituency_code'] if raw else ''
            row[f'district_{year}']=raw[0]['district'] if raw else ''
            row[f'elected_party_{year}']=summary['party'] if summary and summary['called'] and not summary['unresolved'] else ''
            row[f'democratic_votes_{year}']=summary['d'] if summary else ''
            row[f'republican_votes_{year}']=summary['r'] if summary else ''
            row[f'democratic_two_party_share_pct_{year}']=formatted(100*summary['d']/(summary['d']+summary['r'])) if summary and summary['both'] else ''
        known=before and before['called'] and after['called'] and not(before['special'] or after['special'] or before['unresolved'] or after['unresolved'])
        row['seat_flipped']=str(before['party']!=after['party']).lower() if known and (scope=='state' or eligible) else ''
        row['democratic_share_change_pp']=formatted(100*after['d']/(after['d']+after['r'])-100*before['d']/(before['d']+before['r'])) if eligible else ''
        output.append(row)
    return output


def artifacts():
    outputs={};summary={}
    for election_year in COMPARISON_YEARS:
        summary[str(election_year)]={}
        for scope in ('state','county'):
            rows=build_scope(scope,election_year)
            outputs[f'us_governor_{scope}_{election_year}_previous_comparison.csv']=csv_bytes(rows)
            summary[str(election_year)][scope]={'rows':len(rows),'eligible':sum(r['comparison_eligible']=='true' for r in rows),
                'stricter':sum(r['comparison_sensitivity_eligible']=='true' for r in rows),
                'baseline_areas':dict(sorted(Counter(str(r['baseline_year']) for r in rows).items()))}
    files=[f'us_{year}_governor_{scope}_fpp.csv' for year in YEARS for scope in ('state','county')]
    files.extend(f'us_2024_{scope}_demographics.csv' for scope in ('state','county'))
    outputs['us_governor_comparison_metadata.json']=json_bytes({'election_years':COMPARISON_YEARS,'summary':summary,
        'baseline_policy':'Previous regular election: two years earlier for New Hampshire/Vermont; four years earlier for other participating states. Results start in 2016; earlier baselines are unavailable. No annualisation, special-election substitution or fallback to a non-preceding election.',
        'eligibility':'Positive named D/R votes in both years, known local leader and matching reporting identifier. Do not reassign independent or grouped Other votes. Exclude Alaska count bases; county scope also excludes its statewide placeholder and incompatible Connecticut county/planning-region geography. Maine governors use plurality; Maine is not excluded as a ranked-choice state.',
        'flip_policy':'State flags compare the elected party at each preceding regular election; county flags compare eligible local leaders. Uncalled, unresolved and special contests receive no flip flag. 2026 calls are provisional.',
        'demographics':'Fixed 2024 ACS one-year state and five-year county snapshot, not demographic change or causation. County identifiers are matched, not individually boundary-audited.',
        'source_credit':'Call the Map, CC BY 4.0, including civicAPI feeds; 2026-11-15T18:19:21Z snapshot. Earlier results retain their MIT/state-office compilation provenance.',
        'term_source':'https://www.nga.org/governors/powers-and-authority/',
        'input_sha256':{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in files},
        'output_sha256':{name:hashlib.sha256(body).hexdigest() for name,body in outputs.items()}})
    return outputs,summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs,summary=artifacts()
    for name,body in outputs.items():
        if args.check:
            if (DATA/name).read_bytes()!=body:raise ValueError(f'Stale artifact: {name}')
        else:(DATA/name).write_bytes(body)
    print(('Validated' if args.check else 'Built')+' Governor previous-election swing: '+json.dumps(summary))

if __name__=='__main__':main()
