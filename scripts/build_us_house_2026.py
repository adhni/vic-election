#!/usr/bin/env python3
"""Prepare a dated, provisional 2026 House snapshot and a safe 2024 comparison."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.parse

from build_us_house_analysis import summarize_result, formatted
from build_us_president_demographics import ROOT, read_csv, csv_bytes, json_bytes

CACHE = ROOT / 'tmp/us_house/2026'
SOURCE_BASE = 'https://www.callthemap.com/results/data/2026/'
BOUNDARY_NOTE = 'https://www.census.gov/programs-surveys/decennial-census/about/rdo/congressional-districts.120th_Congress.html'
CHANGED_STATES = {'Alabama', 'California', 'Florida', 'Louisiana', 'North Carolina', 'Ohio', 'Tennessee', 'Texas', 'Utah'}
PARTIES = {'D':'Democratic', 'R':'Republican', 'I':'Independent', 'L':'Libertarian', 'G':'Green', 'O':'Other'}
META = 'us_2026_house_metadata.json'
SOURCE = 'us_2026_house_source.csv'
RESULTS = 'us_2026_house_fpp.csv'
BOUNDARIES = 'us_2026_congressional_boundaries.geojson'
COMPARISON = 'us_house_2024_2026_comparison.csv'


def digest(body): return hashlib.sha256(body).hexdigest()


def identities():
    rows = {r['constituency_code']: {'district':r['district'], 'state':r['electorate_type']} for r in read_csv(ROOT/'data/us_2024_house_fpp.csv')}
    fips = {row['state']: code[:2] for code,row in rows.items()}
    abbreviation = {row['district']: row['constituency_code'].split('-')[-1] for row in read_csv(ROOT/'data/us_2024_president_state_fpp.csv')}
    codes = {abbreviation[state]: code for state,code in fips.items()}
    return rows, codes


def prepare_results(source, snapshot):
    identity, states = identities()
    grouped = defaultdict(list)
    for row in source:
        if row['office'] != 'House': continue
        abbr, number = row['race_id'].split('-')
        code = states[abbr] + ('00' if number == 'AL' else f'{int(number):02d}')
        if code not in identity: raise ValueError(f'Unknown House race {row["race_id"]}')
        grouped[code].append(row)
    if set(grouped) != set(identity) or len(grouped) != 435: raise ValueError('Expected all 435 voting House districts')
    output, contests = [], {}
    for code, candidates in sorted(grouped.items()):
        district, state = identity[code]['district'], identity[code]['state']
        if len({r['candidate'] for r in candidates}) != len(candidates): raise ValueError(f'Duplicate candidate: {district}')
        totals = {int(r['total_votes'] or 0) for r in candidates}
        votes = sum(int(r['votes'] or 0) for r in candidates)
        if len(totals) != 1 or votes != next(iter(totals)) or any(int(r['votes'] or 0)<0 for r in candidates): raise ValueError(f'Inconsistent source counts: {district}')
        winners = [r for r in candidates if r['outcome']=='won']
        if len(winners)>1: raise ValueError(f'Multiple reported winners: {district}')
        winner = winners[0] if winners else None
        if winner and int(winner['votes'] or 0) != max(int(r['votes'] or 0) for r in candidates): raise ValueError(f'Reported winner differs from vote leader: {district}')
        status = 'provisional' if winner else 'provisional-uncalled'
        note = f'Provisional snapshot published {snapshot}; not certified final results. Call the Map (CC BY 4.0), using {candidates[0]["source"]}. '
        note += 'Reported winner from the source.' if winner else 'Race not called in this snapshot; a vote lead is not a declared winner.'
        if not votes: note += ' Candidate vote totals were not reported; displayed zeros are structural placeholders, not a measured zero-vote contest.'
        base = {'district':district, 'district_url':candidates[0]['page_url'], 'distribution_url':SOURCE_BASE+'races.csv',
            'elected_member':winner['candidate'] if winner else '', 'elected_party':PARTIES[winner['party']] if winner else '',
            'enrolment':0, 'formal_votes':votes, 'informal_votes':0, 'total_votes':votes, 'turnout_pct':0,
            'majority':votes//2+1 if votes else 0, 'electorate_type':state, 'constituency_code':code, 'contest_status':status,
            'result_note':note, 'source_count_updated_utc':candidates[0]['count_updated_utc'], 'snapshot_published_utc':snapshot}
        rows = [{**base, 'round_number':0, 'row_type':'first', 'excluded_candidate':'', 'excluded_party':'',
                 'candidate':r['candidate'], 'candidate_party':PARTIES[r['party']], 'votes':int(r['votes'] or 0)} for r in candidates]
        output.extend(rows)
        counts = Counter(r['candidate_party'] for r in rows)
        party_votes = Counter()
        for row in rows: party_votes[row['candidate_party']] += row['votes']
        contests[code] = {**identity[code], 'elected_party':base['elected_party'], 'elected_member':base['elected_member'],
            'called':bool(winner), 'democratic_votes':party_votes['Democratic'], 'republican_votes':party_votes['Republican'],
            'named_both':bool(counts['Democratic'] and counts['Republican']),
            'multiple':counts['Democratic']>1 or counts['Republican']>1,
            'share':100*party_votes['Democratic']/(party_votes['Democratic']+party_votes['Republican']) if party_votes['Democratic']+party_votes['Republican'] else None}
    return output, contests


def prepare_comparison(contests):
    previous = defaultdict(list)
    for row in read_csv(ROOT/'data/us_2024_house_fpp.csv'): previous[row['constituency_code']].append(row)
    rows = []
    for code, result in sorted(contests.items()):
        before = summarize_result(previous[code])
        stable = result['state'] not in CHANGED_STATES
        reasons = []
        if not stable: reasons.append('state_plan_changed_not_individually_verified')
        if not result['called']: reasons.append('2026:race_not_called')
        if result['state'] in {'Alaska','Maine'}: reasons.append('ranked_choice_count_basis_not_standardized')
        if before['two_party_analysis_eligible']!='true': reasons.append('2024:'+before['two_party_exclusion_reason'])
        if not result['named_both'] or min(result['democratic_votes'],result['republican_votes'])<=0: reasons.append('2026:both_named_major_parties_need_positive_votes')
        eligible = not reasons
        row = {'constituency_code':code, 'district':result['district'], 'state':result['state'], 'demographic_year':'2024',
            'boundary_unchanged_verified':str(stable).lower(), 'comparison_eligible':str(eligible).lower(),
            'comparison_sensitivity_eligible':str(eligible and not result['multiple'] and before['multiple_major_party_candidates']=='false').lower(),
            'comparison_exclusion_reason':';'.join(reasons)}
        for field in ('elected_party','democratic_votes','republican_votes','democratic_two_party_share_pct'):
            row[field+'_2024'] = before[field]
        row.update(elected_party_2026=result['elected_party'], elected_member_2026=result['elected_member'], democratic_votes_2026=result['democratic_votes'],
            republican_votes_2026=result['republican_votes'], democratic_two_party_share_pct_2026=formatted(result['share']),
            result_called_2026=str(result['called']).lower())
        row['seat_flipped'] = str(before['elected_party']!=result['elected_party']).lower() if stable and result['called'] and before['elected_party'] else ''
        row['democratic_share_change_pp'] = formatted(result['share']-float(before['democratic_two_party_share_pct'])) if eligible else ''
        rows.append(row)
    return rows


def unwrap(coordinates):
    if coordinates and isinstance(coordinates[0],(int,float)):
        lon,lat,*rest=coordinates
        return [lon-360 if lon>0 else lon,lat,*rest]
    return [unwrap(part) for part in coordinates]


def prepare_boundaries(raw):
    from shapely.geometry import shape, mapping
    from shapely import make_valid
    identity,_ = identities()
    features=[]
    for feature in raw['features']:
        properties=feature['properties']
        if not properties['CD120'].isdigit(): continue  # ZZ = unassigned water, not a House seat.
        code=properties['GEOID']
        if code not in identity or properties['CDSESSN']!='120': raise ValueError(f'Unexpected boundary {properties}')
        geometry=shape(feature['geometry'])
        if not geometry.is_valid: geometry=make_valid(geometry)
        if geometry.is_empty or geometry.geom_type not in {'Polygon','MultiPolygon'}: raise ValueError(f'Invalid geometry {code}')
        geometry=mapping(geometry)
        if code.startswith('02'): geometry['coordinates']=unwrap(geometry['coordinates'])
        features.append({'type':'Feature','properties':{'district':identity[code]['district'],'constituency_code':code,'electorate_type':identity[code]['state']},'geometry':geometry})
    if len(features)!=435 or {f['properties']['constituency_code'] for f in features}!=identity.keys(): raise ValueError('Expected 435 boundary joins')
    return {'type':'FeatureCollection','name':'us_2026_120th_congressional_districts','features':sorted(features,key=lambda f:f['properties']['constituency_code'])}


def check():
    meta=json.loads((ROOT/'data'/META).read_bytes())
    for filename,info in meta['outputs'].items():
        payload=(ROOT/'data'/filename).read_bytes()
        if digest(payload)!=info['sha256'] or len(payload)!=info['bytes']: raise ValueError(f'Artifact checksum mismatch: {filename}')
    comparison_meta=json.loads((ROOT/'data/us_house_2024_2026_comparison_metadata.json').read_bytes())
    for name,sha in comparison_meta['input_sha256'].items():
        if digest((ROOT/name).read_bytes())!=sha: raise ValueError(f'Comparison input changed: {name}')
    raw=read_csv(ROOT/'data'/SOURCE)
    results,contests=prepare_results(raw,meta['snapshot_published_utc'])
    for filename,body in ((RESULTS,csv_bytes(results)),(COMPARISON,csv_bytes(prepare_comparison(contests)))):
        if (ROOT/'data'/filename).read_bytes()!=body: raise ValueError(f'Stale artifact {filename}')
    geometry=json.loads((ROOT/'data'/BOUNDARIES).read_bytes())
    if len(geometry['features'])!=435 or {f['properties']['constituency_code'] for f in geometry['features']}!=contests.keys(): raise ValueError('Boundary coverage mismatch')
    print(f'Validated House 2026: 435 districts; {sum(r["called"] for r in contests.values())} source-reported winners; provisional snapshot {meta["snapshot_published_utc"]}')


def build():
    manifest=json.loads((CACHE/'manifest.json').read_bytes())
    info=next(item for item in manifest['files'] if item['path']=='races.csv')
    if digest((CACHE/'races.csv').read_bytes())!=info['sha256']: raise ValueError('Source CSV does not match published manifest checksum')
    raw=[r for r in read_csv(CACHE/'races.csv') if r['office']=='House']
    snapshot=manifest['generated_utc']
    results,contests=prepare_results(raw,snapshot)
    comparisons=prepare_comparison(contests)
    geometry=prepare_boundaries(json.loads((CACHE/'districts.geojson').read_bytes()))
    output={SOURCE:csv_bytes(raw),RESULTS:csv_bytes(results),COMPARISON:csv_bytes(comparisons),
        BOUNDARIES:(json.dumps(geometry,separators=(',',':'))+'\n').encode()}
    comparison_meta={'election_years':[2024,2026], 'demographic_year':2024, 'provisional':True,'snapshot_published_utc':snapshot,
        'districts':435,'verified_unchanged_districts':sum(r['boundary_unchanged_verified']=='true' for r in comparisons),
        'matched_baseline_districts':sum(r['comparison_eligible']=='true' for r in comparisons),
        'matched_sensitivity_districts':sum(r['comparison_sensitivity_eligible']=='true' for r in comparisons),
        'boundary_source':BOUNDARY_NOTE,'excluded_changed_plan_states':sorted(CHANGED_STATES),
        'boundary_policy':'Census identifies nine states with new 2026 plans and confirms continuity for all other states. Exclude every seat in changed-plan states conservatively, including from demographic joins; no claim every excluded seat changed.',
        'result_policy':'Dated provisional reported counts, not certified final results. Require a source-reported winner, positive named D/R votes in both years; exclude AK/ME count bases. Sensitivity also excludes multiple major-party candidates in either year.',
        'flip_definition':'Different 2024 elected party and 2026 source-reported winning party on unchanged boundaries. Blank for uncalled or unverified districts; provisional, not certified flips.',
        'interpretation':'Fixed 2024 ACS snapshot on unchanged districts, equal-weight districts; not demographic change or causation. No 2024 ACS values assigned to redrawn 2026 seats.',
        'source_credit':'Call the Map, CC BY 4.0, https://www.callthemap.com/results; underlying published counts retain row-level source links.',
        'input_sha256':{p:digest((ROOT/p).read_bytes()) for p in ('data/us_2024_house_fpp.csv','data/us_2024_house_demographics.csv')},
        'output_sha256':digest(output[COMPARISON])}
    output['us_house_2024_2026_comparison_metadata.json']=json_bytes(comparison_meta)
    meta={'version':1,'election_year':2026,'congress':120,'provisional':True,'snapshot_published_utc':snapshot,
        'districts':435,'candidate_rows':len(results),'source_reported_winners':sum(r['called'] for r in contests.values()),
        'uncalled_races':sum(not r['called'] for r in contests.values()),
        'source_credit':'Call the Map, licensed CC BY 4.0. Counts compiled from published state/county results and civicAPI; not a Clerk certified compilation.',
        'source_page':'https://www.callthemap.com/results/data', 'license':manifest['license'],
        'sources':{'manifest':{'url':SOURCE_BASE+'manifest.json','sha256':digest((CACHE/'manifest.json').read_bytes())},
            'all_races':{'url':SOURCE_BASE+'races.csv','sha256':info['sha256'],'bytes':info['bytes']},
            'boundaries':{'url':(CACHE/'boundary-source-url.txt').read_text(),'sha256':digest((CACHE/'districts.geojson').read_bytes()),
                'note':'Official Census TIGERweb 120th Congress, simplified at 0.005 degrees for display. ZZ unassigned-water features omitted; Alaska antimeridian unwrapped; invalid polygon rings repaired for display.'},
            'boundary_continuity':BOUNDARY_NOTE,
            'missouri_correction':'https://www.census.gov/programs-surveys/geography/technical-documentation/user-note/120cd.html'},
        'outputs':{name:{'bytes':len(body),'sha256':digest(body)} for name,body in output.items()}}
    output[META]=json_bytes(meta)
    for name,body in output.items(): (ROOT/'data'/name).write_bytes(body)
    print(f'Built provisional House 2026: 435 seats, {meta["source_reported_winners"]} reported winners, {meta["uncalled_races"]} uncalled; {comparison_meta["matched_baseline_districts"]} comparable districts')


def download():
    """Explicitly refresh the cache; builds without this option stay frozen."""
    CACHE.mkdir(parents=True, exist_ok=True)
    query=urllib.parse.urlencode({'where':"STATE NOT IN ('11','60','66','69','72','78')",
        'outFields':'GEOID,STATE,CD120,CDSESSN,NAME','returnGeometry':'true',
        'outSR':'4326','maxAllowableOffset':'0.005','geometryPrecision':'5','f':'geojson'})
    boundary_url='https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0/query?'+query
    for name,url in [('manifest.json',SOURCE_BASE+'manifest.json'),('races.csv',SOURCE_BASE+'races.csv'),
                     ('README.txt',SOURCE_BASE+'README.txt'),('districts.geojson',boundary_url)]:
        request=urllib.request.Request(url,headers={'User-Agent':'ElectionPreferenceExplorer/1.0'})
        with urllib.request.urlopen(request,timeout=120) as response: payload=response.read()
        (CACHE/name).write_bytes(payload)
    (CACHE/'boundary-source-url.txt').write_text(boundary_url)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--check',action='store_true')
    group.add_argument('--download',action='store_true',help='Refresh source cache before rebuilding; inspect snapshot counts and labels afterward')
    args=parser.parse_args()
    if args.download: download()
    check() if args.check else build()


if __name__=='__main__': main()
