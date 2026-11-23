"""Independent weighted-pattern replay and every SF precinct/round map snapshot."""
import csv
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'data/sources/sf'
D=json.loads((ROOT/'data/sf_2024_mayor_rounds.json').read_text())
A=json.loads((source/'cvr_mayor.json').read_text());official=json.loads((source/'rcv_mayor.json').read_text())
for n,s in D['source_manifest']['sources'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==s['sha256']
assert D['summary']=={'precincts':514,'rounds':14,'cvr_ballots':410105,'mapped_cvr_ballots':410102,'unmapped_cvr_ballots':3,'sov_suppressed_precincts':13,'turnout_precincts':501}
assert official['totalRounds']==14 and official['winner']=='DANIEL LURIE'
assert A['formatVersion']==1 and len(A['groups'])%3==0
assert len(A['candidates'])==len(set(A['candidates']))==15
assert all(p.count(-1)<=1 and (-1 not in p or p[-1]==-1) and len(set(p))==len(p) for p in A['patterns'])
# Construct weighted precinct patterns, using ordinary Python counters rather
# than the builder's NumPy indexed accumulation and candidate destinations.
ballots=defaultdict(list)
for p,pattern_idx,weight in zip(A['groups'][::3],A['groups'][1::3],A['groups'][2::3]):
    assert weight>0 and 0<=p<len(A['precincts']) and 0<=pattern_idx<len(A['patterns'])
    ballots[A['precincts'][p]].append((A['patterns'][pattern_idx],weight))
assert sum(weight for rows in ballots.values() for _,weight in rows)==410105
assert sum(weight for _,weight in ballots['0000'])==3
# Keep zero-record precincts in the independent check as well.
for code in A['precincts']:ballots.setdefault(code,[])
alive=set(range(15));names=D['candidates'];initial_ballots={}
for round_idx in range(1,15):
    city=Counter();per_precinct={}
    for code,weighted in ballots.items():
        tally=Counter()
        for pattern,weight in weighted:
            outcome='blanks' if not pattern else 'exhausted'
            for candidate in pattern:
                if candidate==-1:outcome='overvotes';break
                if candidate in alive:outcome=candidate;break
            tally[outcome]+=weight
        per_precinct[code]=tally;city.update(tally)
    report=official['rounds'][round_idx-1]
    assert [city[i] for i in range(15)]==[next(c['votes'] for c in report['candidates'] if c['name']==A['candidates'][i]) for i in range(15)]
    assert sum(city[i] for i in range(15))==report['continuingTotal']
    assert all(city[k]==report[k] for k in ['exhausted','overvotes','blanks'])
    ours=D['rounds'][round_idx-1]
    assert ours['active']==[names[i] for i in sorted(alive)]
    assert ours['votes']=={names[i]:city[i] for i in sorted(alive)}
    assert ours['continuing']==report['continuingTotal']
    assert all(ours[k]==city[k] for k in ['exhausted','overvotes','blanks'])
    if len(alive)>2:
        minimum=min(city[i] for i in alive);lowest=[i for i in alive if city[i]==minimum]
        assert len(lowest)==1
        assert ours['eliminated']==[names[lowest[0]]]
    else:lowest=[];assert not ours['eliminated']
    with (ROOT/f'data/sf_2024_mayor_round_{round_idx}_precinct_fpp.csv').open() as f:rows=list(csv.DictReader(f))
    exported=defaultdict(list)
    for row in rows:exported[row['constituency_code']].append(row)
    assert len(exported)==514 and len(rows)==514*len(alive)
    for code,tally in per_precinct.items():
        r=D['unmapped'][round_idx-1] if code=='0000' else D['precincts']['Precinct '+code]['rounds'][round_idx-1]
        expected={names[i]:tally[i] for i in sorted(alive)}
        assert r['votes']==expected and r['continuing']==sum(expected.values())
        assert all(r[k]==tally[k] for k in ['exhausted','overvotes','blanks'])
        assert r['cvr_ballots']==sum(tally.values())
        if round_idx==1:initial_ballots[code]=r['cvr_ballots']
        else:assert r['cvr_ballots']==initial_ballots[code]
        ranked=sorted(expected.items(),key=lambda x:(-x[1],x[0]));leader='No continuing votes' if not r['continuing'] else 'Tied local leaders' if ranked[0][1]==ranked[1][1] else ranked[0][0]
        assert r['leader']==leader and r['margin']==(ranked[0][1]-ranked[1][1] if r['continuing'] else 0)
        if code!='0000':
            c=exported[code];assert {row['candidate']:int(row['votes']) for row in c}==expected
            assert all(int(row['formal_votes'])==r['continuing'] and int(row['informal_votes'])==r['cvr_ballots']-r['continuing'] and int(row['total_votes'])==r['cvr_ballots'] and not row['enrolment'] and not row['turnout_pct'] and row['elected_member']==leader for row in c)
    assert sum(r['rounds'][round_idx-1]['continuing'] for r in D['precincts'].values())+D['unmapped'][round_idx-1]['continuing']==report['continuingTotal']
    assert sum(r['votes'].values())+r['exhausted']+r['overvotes']+r['blanks']==r['cvr_ballots']
    alive.difference_update(lowest)
    print(f'PASS SF round {round_idx}: all candidate totals, blank/exhausted/overvote categories, every precinct and unmapped ledger, CSV snapshots and local leaders')
assert D['rounds'][0]['votes']['Daniel Lurie']==102720 and D['rounds'][0]['votes']['London Breed']==95117
assert D['rounds'][-1]['votes']=={'Daniel Lurie':182364,'London Breed':149113}
assert len(D['precincts'])==514
geo=json.loads((ROOT/'data/sf_2024_mayor_precinct_boundaries.geojson').read_text())
assert {f['properties']['district'] for f in geo['features']}==set(D['precincts'])
assert all(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in geo['features'])
turnout=json.loads((source/'turnout.json').read_text())['precincts']
for area in D['precincts'].values():
    assert area['turnout']==turnout.get(area['code'])
    assert area['sov_suppressed']==(area['code'] in A['sovSuppressed'])
    assert area['sov_suppressed']==(area['turnout'] is None)
print('PASS SF 514 geometry joins, 13 withheld SOV/turnout labels and complete 410105-record accounting')
