#!/usr/bin/env python3
"""Build a frozen, provisional 2026 Governor snapshot at state and county scope.

Bismillah. Candidate rows and calls retain Call the Map / civicAPI attribution.
County files publish two named candidates plus all remaining votes together;
that group is never treated as a person or as a Democratic vote total.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import urllib.request

from build_us_president_demographics import ROOT, read_csv, csv_bytes, json_bytes

CACHE = ROOT/'tmp/us_governor/2026'
DATA = ROOT/'data'
SOURCE_BASE = 'https://www.callthemap.com/results/data/2026/'
EXPECTED_STATES = set('AL AK AZ AR CA CO CT FL GA HI ID IL IA KS ME MD MA MI MN NE NV NH NM NY OH OK OR PA RI SC SD TN TX VT WI WY'.split())
PARTIES = {'D':'Democratic', 'R':'Republican', 'I':'Independent', 'L':'Libertarian', 'G':'Green', 'O':'Other'}
META = 'us_2026_governor_metadata.json'
STATE_SOURCE = 'us_2026_governor_source.csv'
COUNTY_SOURCE = 'us_2026_governor_county_source.csv'
BOUNDARY_INPUTS = ('us_president_state_boundaries.geojson', 'us_president_2024_county_boundaries.geojson')


def digest(body):
    return hashlib.sha256(body).hexdigest()


def group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


def snapshot_note(snapshot):
    return (f'Provisional snapshot published {snapshot}; not certified final results. '
            'Call the Map (CC BY 4.0), including civicAPI feeds; underlying source links retained in the source download. '
            + '2026 gubernatorial election. ')


def base_row(district, code, state, candidates, status, note, source, snapshot, winner=None, geography='state'):
    total = sum(c['votes'] for c in candidates)
    ranked = sorted((c for c in candidates if not c.get('grouped')), key=lambda c: (-c['votes'], c['name']))
    base = {
        'district':district, 'district_url':source['page_url'], 'distribution_url':SOURCE_BASE+'races.csv',
        'elected_member':winner['candidate'] if winner else '',
        'elected_party':PARTIES[winner['party']] if winner else '',
        'enrolment':0, 'formal_votes':total, 'informal_votes':0, 'total_votes':total, 'turnout_pct':0,
        'majority':ranked[0]['votes']-ranked[1]['votes'],
        'electorate_type':'United States' if geography=='state' else state,
        'constituency_code':code, 'contest_status':status, 'result_note':note,
        'race_id':source['race_id'], 'election_kind':'regular',
        'source_count_updated_utc':source['count_updated_utc'], 'snapshot_published_utc':snapshot,
        'round_number':0, 'row_type':'first', 'excluded_candidate':'', 'excluded_party':''}
    return [{**base, 'candidate':c['name'], 'candidate_party':c['party'], 'votes':c['votes'], 'candidate_grouped':str(bool(c.get('grouped'))).lower()} for c in candidates]


def prepare(raw_states, raw_counties, snapshot):
    states = group(raw_states, 'state')
    if set(states) != EXPECTED_STATES:
        raise ValueError('Expected all 36 states holding governor elections in 2026')
    state_geometry = json.loads((DATA/BOUNDARY_INPUTS[0]).read_bytes())
    state_features = {f['properties']['constituency_code'].removeprefix('US-STATE-'):f for f in state_geometry['features']}
    county_geometry = json.loads((DATA/BOUNDARY_INPUTS[1]).read_bytes())
    county_features = {f['properties']['constituency_code'].removeprefix('US-COUNTY-'):f for f in county_geometry['features']}
    state_rows, county_rows, boundaries_state, boundaries_county = [], [], [], []
    calls, reconciliation, unresolved = {}, {}, []
    grouped_counties = group(raw_counties, 'state')
    if set(grouped_counties) != set(states):
        raise ValueError('County and state race coverage differ')
    if len({(r['race_id'], r['fips']) for r in raw_counties}) != len(raw_counties):
        raise ValueError('Duplicate county result')

    for state, original in sorted(states.items()):
        race_id = 'GOV-'+state
        if any(r['office']!='Governor' or r['race_id']!=race_id or r['seats']!='1' for r in original):
            raise ValueError(f'Unexpected race identity: {state}')
        if len({r['candidate'] for r in original}) != len(original):
            raise ValueError(f'Duplicate state candidate: {state}')
        candidates = [{'name':r['candidate'], 'party':PARTIES[r['party']], 'votes':int(r['votes'])} for r in original]
        total = sum(c['votes'] for c in candidates)
        if len(candidates)<2 or min(c['votes'] for c in candidates)<0 or {int(r['total_votes']) for r in original}!={total}:
            raise ValueError(f'State accounting mismatch: {state}')
        winners = [r for r in original if r['outcome']=='won']
        if len(winners)>1 or winners and int(winners[0]['votes'])!=max(c['votes'] for c in candidates):
            raise ValueError(f'Invalid source winner call: {state}')
        winner = winners[0] if winners else None
        calls[state] = bool(winner)
        district = state_features[state]['properties']['district']
        note = snapshot_note(snapshot)
        note += 'Source-reported winner; counts may change.' if winner else 'Race not called; the current leader is not a declared winner.'
        if state == 'AK':
            note += ' Source counts are retained without reconstructing ranked-choice transfers.'
        state_status = 'provisional' if winner else 'provisional-uncalled'
        state_rows.extend(base_row(district, 'US-GOVERNOR-STATE-'+state, district, candidates, state_status, note, original[0], snapshot, winner))
        feature = json.loads(json.dumps(state_features[state]))
        feature['properties'] = {'district':district, 'constituency_code':'US-GOVERNOR-STATE-'+state, 'electorate_type':'United States'}
        boundaries_state.append(feature)
        county_source = grouped_counties[state]
        named_totals = defaultdict(int)
        county_total = 0
        for row in county_source:
            counts = [int(row[key] or 0) for key in ('votes_a','votes_b','votes_other','total_votes')]
            if row['office']!='Governor' or row['race_id']!=race_id or min(counts)<0 or sum(counts[:3])!=counts[3]:
                raise ValueError(f'County accounting mismatch: {state} {row["place"]}')
            for suffix in ('a','b'):
                match = [r for r in original if r['candidate']==row['candidate_'+suffix] and r['party']==row['party_'+suffix]]
                if len(match)!=1:
                    raise ValueError(f'County candidate identity mismatch: {state} {row["place"]}')
                named_totals[row['candidate_'+suffix]] += int(row['votes_'+suffix] or 0)
            county_total += counts[3]
        difference = total-county_total
        if difference<0:
            raise ValueError(f'County counts exceed state snapshot: {state}')
        for name, count in named_totals.items():
            statewide = next(int(r['votes']) for r in original if r['candidate']==name)
            if count>statewide or difference==0 and count!=statewide:
                raise ValueError(f'County named counts disagree with statewide snapshot: {state} {name}')
        reconciliation[state] = {'state_votes':total, 'source_county_votes':county_total, 'unallocated_to_counties':difference,
            'map_policy':'statewide_fallback' if state=='AK' else 'source_counties_without_imputation',
            'named_candidate_differences':{name:next(int(r['votes']) for r in original if r['candidate']==name)-count for name,count in named_totals.items()}}
        if state=='AK':
            if any(r['place_kind']!='house district' for r in county_source):
                raise ValueError('Alaska reporting unit changed; revisit fallback')
            name = 'Alaska (statewide fallback)'
            note += ' Alaska reports by state House district, not county/borough. This shape shows the exact statewide candidate counts, not county results.'
            county_rows.extend(base_row(name, 'US-GOVERNOR-COUNTY-AK', district, candidates, state_status, note, original[0], snapshot, winner, 'county'))
            feature = json.loads(json.dumps(feature))
            feature['properties'] = {'district':name, 'constituency_code':'US-GOVERNOR-COUNTY-AK', 'electorate_type':district}
            boundaries_county.append(feature)
            continue
        for row in county_source:
            if row['place_kind'] not in {'county','parish','planning region'} or row['fips'] not in county_features:
                raise ValueError(f'Unmatched reporting geography: {state} {row["fips"]}')
            feature = json.loads(json.dumps(county_features[row['fips']]))
            if feature['properties']['electorate_type']!=district:
                raise ValueError(f'County/state boundary mismatch: {row["fips"]}')
            name = feature['properties']['district']
            local = [{'name':row['candidate_'+suffix], 'party':PARTIES[row['party_'+suffix]], 'votes':int(row['votes_'+suffix] or 0)} for suffix in ('a','b')]
            other = int(row['votes_other'] or 0)
            ambiguous = other >= max(c['votes'] for c in local) or local[0]['votes']==local[1]['votes']
            if ambiguous:
                unresolved.append(name)
            if other:
                local.append({'name':'Other candidates (combined)', 'party':'Other', 'votes':other, 'grouped':True})
            note = snapshot_note(snapshot)
            note += ('Local vote leaders are not elected governors. Two named candidates are reported separately; all remaining candidates/write-ins are combined as Other. '
                     'Other is not a candidate or a Democratic/Republican total. Margins compare the two named candidates; the grouped Other votes are excluded from outcome ranking. ')
            if ambiguous:
                note += 'Local leader unavailable: the two named candidates are tied or grouped Other votes prevent identifying the leading individual candidate. No winner is inferred from the combined group. '
            if row['finished']:
                note += f'Source county count finished: {row["finished"]}. '
            if difference:
                note += f'The source has {difference:,} additional statewide votes not allocated to counties; no votes are distributed or imputed here. '
            code = 'US-GOVERNOR-COUNTY-'+row['fips']
            local_source = {**original[0], 'count_updated_utc':row['count_updated_utc']}
            county_rows.extend(base_row(name, code, district, local, 'provisional-local-unresolved' if ambiguous else 'provisional-local', note, local_source, snapshot, geography='county'))
            feature['properties'] = {'district':name, 'constituency_code':code, 'electorate_type':district}
            boundaries_county.append(feature)

    geo = lambda scope, features: {'type':'FeatureCollection', 'name':f'us_governor_2026_{scope}', 'features':features}
    outputs = {
        'us_2026_governor_state_fpp.csv':csv_bytes(state_rows),
        'us_2026_governor_county_fpp.csv':csv_bytes(county_rows),
        'us_governor_2026_state_boundaries.geojson':(json.dumps(geo('states',boundaries_state),separators=(',',':'))+'\n').encode(),
        'us_governor_2026_county_boundaries.geojson':(json.dumps(geo('counties',boundaries_county),separators=(',',':'))+'\n').encode()}
    summary = {'state_races':len(states), 'source_candidate_rows':len(raw_states),
        'source_reported_winners':sum(calls.values()), 'uncalled_states':sorted(state for state,called in calls.items() if not called),
        'county_map_areas':len(boundaries_county), 'actual_county_reporting_areas':len(boundaries_county)-1, 'unresolved_local_leaders':unresolved,
        'statewide_fallbacks':['AK'], 'reconciliation':reconciliation}
    return outputs, summary


def check():
    metadata = json.loads((DATA/META).read_bytes())
    for name, info in metadata['outputs'].items():
        body = (DATA/name).read_bytes()
        if digest(body)!=info['sha256'] or len(body)!=info['bytes']:
            raise ValueError(f'Artifact checksum mismatch: {name}')
    for name, sha in metadata['boundary_input_sha256'].items():
        if digest((DATA/name).read_bytes())!=sha:
            raise ValueError(f'Boundary input changed: {name}')
    outputs, summary = prepare(read_csv(DATA/STATE_SOURCE),read_csv(DATA/COUNTY_SOURCE),metadata['snapshot_published_utc'])
    for name, body in outputs.items():
        if (DATA/name).read_bytes()!=body:
            raise ValueError(f'Stale output: {name}')
    if summary != metadata['summary']:
        raise ValueError('Snapshot summary differs from committed inputs')
    print(f'Validated Governor 2026: {summary["state_races"]} races, {summary["county_map_areas"]} county/fallback areas; provisional {metadata["snapshot_published_utc"]}')


def build():
    manifest = json.loads((CACHE/'manifest.json').read_bytes())
    source_files = {}
    for name in ('races.csv','counties.csv'):
        source_files[name] = next(r for r in manifest['files'] if r['path']==name)
        if digest((CACHE/name).read_bytes())!=source_files[name]['sha256']:
            raise ValueError(f'Source checksum differs from published manifest: {name}')
    raw_states = [r for r in read_csv(CACHE/'races.csv') if r['office']=='Governor']
    raw_counties = [r for r in read_csv(CACHE/'counties.csv') if r['office']=='Governor']
    outputs, summary = prepare(raw_states,raw_counties,manifest['generated_utc'])
    outputs.update({STATE_SOURCE:csv_bytes(raw_states), COUNTY_SOURCE:csv_bytes(raw_counties)})
    metadata = {'version':1,'election_year':2026,'provisional':True, 'snapshot_published_utc':manifest['generated_utc'],
        'source_credit':'Call the Map (callthemap.com/results), CC BY 4.0; civicAPI (civicapi.org) for its feeds. Compiled provisional counts, not a certified FEC compilation.',
        'source_page':'https://www.callthemap.com/results/data', 'license':manifest['license'],
        'sources':{name:{'url':SOURCE_BASE+name,'sha256':info['sha256'],'bytes':info['bytes']} for name,info in source_files.items()},
        'manifest_sha256':digest((CACHE/'manifest.json').read_bytes()),
        'scope_sources':['https://www.nga.org/governors/elections/'],
        'scope_policy':'All 36 states holding gubernatorial elections in 2026. County view includes Connecticut planning regions and a labelled Alaska statewide fallback.',
        'county_policy':'Two named source candidates plus other votes combined. Never relabel an independent as Democratic or infer a combined Other candidate winner. Unresolved local leaders are explicitly flagged. Alaska uses exact statewide counts on a labelled statewide shape, not its 40 state House reporting districts.',
        'boundary_input_sha256':{name:digest((DATA/name).read_bytes()) for name in BOUNDARY_INPUTS},
        'summary':summary, 'outputs':{name:{'sha256':digest(body),'bytes':len(body)} for name,body in outputs.items()}}
    for name, body in outputs.items():
        (DATA/name).write_bytes(body)
    (DATA/META).write_bytes(json_bytes(metadata))
    print(f'Built provisional Governor 2026: {summary["state_races"]} races, {summary["source_reported_winners"]} reported winners, {summary["county_map_areas"]} county/fallback areas')


def download():
    CACHE.mkdir(parents=True,exist_ok=True)
    for name in ('manifest.json','races.csv','counties.csv','README.txt'):
        request = urllib.request.Request(SOURCE_BASE+name,headers={'User-Agent':'ElectionPreferenceExplorer/1.0'})
        with urllib.request.urlopen(request,timeout=120) as response:
            body = response.read()
        (CACHE/name).write_bytes(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--check',action='store_true')
    options.add_argument('--download',action='store_true',help='Fetch a fresh snapshot before building; review dates/counts afterward')
    args = parser.parse_args()
    if args.download:
        download()
    check() if args.check else build()

if __name__=='__main__':
    main()
