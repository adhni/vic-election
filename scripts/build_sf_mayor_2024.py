"""Replay SF's 2024 mayoral count, reconciling every round to its published table."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from shapely import make_valid
from shapely.geometry import shape, mapping

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/sources/sf'
UPSTREAM='https://www.sfelections.org/results/20241105/data/20241203/'
ARCHIVE='https://github.com/sfbay/datadiver/tree/647b2beb42f7d1b63cccd9d962cdef65024344c9'
COLORS=['#288b87','#7851a9','#c57928','#4267b2','#bd4c71','#6b7f30','#8c564b','#62798e','#a56b16','#824d70','#4f8056','#a65d42','#6571a0','#85733e','#735b77']
NAMES=['Daniel Lurie','London Breed','Aaron Peskin','Mark Farrell','Ahsha Safaí','Ellen Lee Zhou','Dylan Hirsch-Shell','Keith Freedman','Nelson Mei','Shahram Shariati','Henry Flynn','Paul Ybarra Robertson','Jon Soderstrom','Marc Roth (write-in)','Michael Lin (write-in)']
# These columns describe a selected-round map snapshot, not a new election.
FIELDS=['district','elected_member','elected_party','enrolment','formal_votes','informal_votes','total_votes','turnout_pct','majority','round_number','row_type','candidate','candidate_party','votes','electorate_type','constituency_code','contest_status']


def replay(artifact, published):
    patterns=artifact['patterns'];groups=np.array(artifact['groups'],dtype=np.int64).reshape(-1,3)
    n=len(artifact['candidates']);alive=set(range(n));records=[]
    for round_idx,official in enumerate(published['rounds'],1):
        assert official['round']==round_idx
        destinations=[]
        for pattern in patterns:
            dest=n+2 if not pattern else n
            for value in pattern:
                if value==-1:dest=n+1;break
                if value in alive:dest=value;break
            destinations.append(dest)
        counts=np.zeros((len(artifact['precincts']),n+3),dtype=np.int64)
        np.add.at(counts,(groups[:,0],np.array(destinations)[groups[:,1]]),groups[:,2])
        city=counts.sum(axis=0)
        assert {c:int(city[i]) for i,c in enumerate(artifact['candidates'])}=={r['name']:r['votes'] for r in official['candidates']}
        assert int(city[:n].sum())==official['continuingTotal']
        assert list(map(int,city[n:]))==[official['exhausted'],official['overvotes'],official['blanks']]
        assert int(city.sum())==410105
        eliminated=[i for i,c in enumerate(artifact['candidates']) if next(r for r in official['candidates'] if r['name']==c)['isEliminated']]
        if len(alive)>2:
            minimum=min(int(city[i]) for i in alive)
            lowest=[i for i in alive if city[i]==minimum]
            assert len(lowest)==1 and eliminated==lowest
        else:assert not eliminated
        records.append({'round':round_idx,'counts':counts,'alive':sorted(alive),'eliminated':eliminated})
        alive.difference_update(eliminated)
    assert len(records)==14 and records[-1]['counts'].sum(axis=0)[:2].tolist()==[182364,149113]
    return records


def build():
    manifest=json.loads((SOURCE/'source_manifest.json').read_text())
    for filename,details in manifest['sources'].items():
        assert hashlib.sha256((SOURCE/filename).read_bytes()).hexdigest()==details['sha256'],filename
    a=json.loads((SOURCE/'cvr_mayor.json').read_text());published=json.loads((SOURCE/'rcv_mayor.json').read_text())
    turnout=json.loads((SOURCE/'turnout.json').read_text())['precincts']
    assert len(a['candidates'])==15 and len(a['precincts'])==515
    replayed=replay(a,published)
    geometry=json.loads((SOURCE/'precincts_2022.geojson').read_text());features=[];repairs=[];props={}
    for f in geometry['features']:
        code=f['properties']['prec_2022'];g=shape(f['geometry']);assert code not in props
        if not g.is_valid:
            fixed=make_valid(g);assert abs(fixed.area-g.area)/g.area<.0001;g=fixed;repairs.append(code)
        g=g.simplify(.000008,preserve_topology=True);assert g.is_valid and not g.is_empty
        props[code]=f['properties']
        features.append({'type':'Feature','properties':{'district':'Precinct '+code,'constituency_code':code},'geometry':mapping(g)})
    assert len(features)==514 and set(a['precincts'])-set(props)=={'0000'}
    (ROOT/'data/sf_2024_mayor_precinct_boundaries.geojson').write_text(json.dumps({'type':'FeatureCollection','source':'San Francisco Department of Elections, precincts defined 2022, DataSF d6x4-hefw (March 2024 update).','features':features},separators=(',',':'))+'\n')
    areas={}
    for code in a['precincts']:
        if code=='0000':continue
        p=props[code];t=turnout.get(code)
        areas['Precinct '+code]={'code':code,'state':'District '+str(p['supe22']).zfill(2),'neighborhood':p['neigh22'],
             'sov_suppressed':code in a['sovSuppressed'],'turnout':t,'rounds':[]}
    rounds=[];unmapped=[]
    for model in replayed:
        r=model['round'];counts=model['counts'];official=published['rounds'][r-1];eliminated=model['eliminated'];rows=[]
        rounds.append({'round':r,'active':[NAMES[i] for i in model['alive']],'eliminated':[NAMES[i] for i in eliminated],
            'votes':{NAMES[i]:int(counts[:,i].sum()) for i in model['alive']},'continuing':official['continuingTotal'],
            'exhausted':official['exhausted'],'overvotes':official['overvotes'],'blanks':official['blanks']})
        for idx,code in enumerate(a['precincts']):
            c=counts[idx];votes={NAMES[i]:int(c[i]) for i in model['alive']};total=sum(votes.values());ballots=int(c.sum())
            ranked=sorted(votes.items(),key=lambda pair:(-pair[1],pair[0]));leader='No continuing votes' if not total else 'Tied local leaders' if ranked[0][1]==ranked[1][1] else ranked[0][0]
            record={'votes':votes,'continuing':total,'exhausted':int(c[15]),'overvotes':int(c[16]),'blanks':int(c[17]),'cvr_ballots':ballots,'leader':leader,'margin':ranked[0][1]-ranked[1][1] if total else 0}
            if code=='0000':unmapped.append({'round':r,**record});continue
            name='Precinct '+code;areas[name]['rounds'].append(record)
            base={'district':name,'elected_member':leader,'elected_party':leader,'enrolment':'','formal_votes':total,'informal_votes':ballots-total,'total_votes':ballots,'turnout_pct':'','majority':record['margin'],'round_number':0,'row_type':'first','electorate_type':areas[name]['state'],'constituency_code':code,'contest_status':'no-votes' if not total else 'tied-local' if leader=='Tied local leaders' else 'official'}
            for candidate,v in votes.items():rows.append({**base,'candidate':candidate,'candidate_party':candidate,'votes':v})
        with (ROOT/f'data/sf_2024_mayor_round_{r}_precinct_fpp.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
        assert sum(x['rounds'][-1]['continuing'] for x in areas.values())+unmapped[-1]['continuing']==official['continuingTotal']
    result={'year':2024,'date':'2024-11-05','candidates':NAMES,'colors':dict(zip(NAMES,COLORS)),'rounds':rounds,'precincts':areas,'unmapped':unmapped,
        'summary':{'precincts':514,'rounds':14,'cvr_ballots':410105,'mapped_cvr_ballots':410102,'unmapped_cvr_ballots':3,'sov_suppressed_precincts':len(a['sovSuppressed']), 'turnout_precincts':len(turnout)},
        'geometry_repairs':repairs,'source_manifest':manifest,'caveat':'Precinct round counts are independently replayed from DataDiver’s compact public CVR archive and reconcile to its transcription of the published official round table. They are not official precinct round reports. Three CVR records without precinct location remain in a separate citywide ledger. CVR record totals differ from all-election ballots cast; continuing votes are not turnout.'}
    (ROOT/'data/sf_2024_mayor_rounds.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
    print('PASS 14 rounds, 514 mapped precincts, 410102 mapped + 3 unlocated CVR records; final Lurie 182364 / Breed 149113')


if __name__=='__main__':build()
