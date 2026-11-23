"""Build both Chicago 2023 mayoral rounds from pinned, reconciled returns."""
import csv
import hashlib
import json
import re
from pathlib import Path
import pdfplumber
from shapely import make_valid
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from build_boston_mayor import FIELDS

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/sources/chicago'
ROUNDS=['first-round','runoff']
NAMES={"JA'MAL GREEN":"Ja'Mal Green",'SOPHIA KING':'Sophia King','KAM BUCKNER':'Kam Buckner','WILLIE L. WILSON':'Willie Wilson','BRANDON JOHNSON':'Brandon Johnson','PAUL VALLAS':'Paul Vallas','LORI E. LIGHTFOOT':'Lori Lightfoot','RODERICK T. SAWYER':'Roderick Sawyer','JESUS "CHUY" GARCIA':'Chuy García','KEITH M. JUDGE (WRITE-IN)':'Keith Judge (write-in)','STEPHEN HODGE (WRITE-IN)':'Stephen Hodge (write-in)','RYAN FRIEDMAN (WRITE-IN)':'Ryan Friedman (write-in)','STEPHANIE ANN MUSTARI (WRITE-IN)':'Stephanie Ann Mustari (write-in)','BRIDGETT PALMER (WRITE-IN)':'Bridgett Palmer (write-in)','JOHNNY LOGALBO (WRITE-IN)':'Johnny Logalbo (write-in)'}
COLORS=dict(zip(NAMES.values(),['#8c564b','#b34c79','#6b7f30','#a56b16','#288b87','#7851a9','#c57928','#477ea8','#bc4054','#586a88','#5c686b','#a56789','#68884a','#9b7653','#756a85']))
EXPECTED={'first-round':dict(zip(NAMES.values(),[12257,7191,11092,51567,122093,185743,94890,2440,77222,5,4,3,1,1,15])),'runoff':{'Brandon Johnson':319481,'Paul Vallas':293033}}
PDF={'first-round':'2023_first_round.pdf','runoff':'2023_runoff.pdf'}
CSV={'first-round':'municipal_general_2023.csv','runoff':'municipal_runoff_2023.csv'}
BALLOTS={'first-round':566973,'runoff':613795}
REG={'first-round':1581564,'runoff':1587153}
DATES={'first-round':'2023-02-28','runoff':'2023-04-04'}

def name(code):return f'Ward {int(code[:2]):02d} · Precinct {int(code[2:]):02d}'

def certified(round_name):
    with pdfplumber.open(SOURCE/PDF[round_name]) as pdf:
        # The mayoral summary occupies the left column of page 6 in both proclamations.
        text=pdf.pages[5].crop((0,0,pdf.pages[5].width/2,pdf.pages[5].height)).extract_text()
        mayor=text.split('Mayor\n',1)[1].split('Total ',1)[0]
        totals={}
        for line in mayor.splitlines():
            match=re.fullmatch(r'(.+?)\s+([\d,]+)\s+[\d.]+%',line)
            if match:
                totals[NAMES[match[1]]]=int(match[2].replace(',',''))
        assert totals==EXPECTED[round_name],(round_name,totals)
        # Ballot and precinct recaps are independent of the archived precinct CSV.
        text='\n'.join(p.extract_text() for p in pdf.pages[:5])
    ward_ballots={int(w):int(v.replace(',','')) for w,v in re.findall(r'(?m)^(\d+)(?:st|nd|rd|th) Ward ([\d,]+)$',text)}
    ward_precincts={int(w):int(n) for w,n,reported in re.findall(r'(?m)^(\d+)(?:st|nd|rd|th) Ward (\d+) Precincts Reported: (\d+)$',text) if n==reported}
    assert len(ward_ballots)==len(ward_precincts)==50
    assert sum(ward_ballots.values())==BALLOTS[round_name] and sum(ward_precincts.values())==1291
    return totals,ward_ballots,ward_precincts

def records(round_name):
    totals,ward_ballots,ward_counts=certified(round_name)
    areas={}
    with (SOURCE/CSV[round_name]).open() as f:
        for row in csv.DictReader(f):
            ward,precinct=int(row['WARD']),int(row['PRECINCT']);code=f'{ward:02d}{precinct:03d}'
            assert code not in areas
            votes={display:int(row[raw]) for raw,display in NAMES.items() if display in totals}
            ballots=int(row['BALLOTS CAST']);registered=int(row['REGISTERED VOTERS']);total=sum(votes.values())
            assert 0<=total<=ballots<=registered
            areas[code]={'votes':votes,'ballots':ballots,'registered':registered,'total':total,'unrecorded':ballots-total,'ward':ward,'precinct':precinct,'code':code,'state':f'Ward {ward:02d}'}
    assert len(areas)==1291
    assert {c:sum(a['votes'][c] for a in areas.values()) for c in totals}==totals
    assert sum(a['registered'] for a in areas.values())==REG[round_name]
    for ward in range(1,51):
        ward_areas=[a for a in areas.values() if a['ward']==ward]
        assert len(ward_areas)==ward_counts[ward]
        assert sum(a['ballots'] for a in ward_areas)==ward_ballots[ward]
    return areas

def build():
    manifest=json.loads((SOURCE/'source_manifest.json').read_text())
    for filename,details in manifest['sources'].items():assert hashlib.sha256((SOURCE/filename).read_bytes()).hexdigest()==details['sha256'],filename
    raw=json.loads((SOURCE/'precincts_2023.geojson').read_text());geometries={};repairs=[]
    for f in raw['features']:
        code=f['properties']['ward_precinct'];g=shape(f['geometry'])
        assert code==f"{int(float(f['properties']['ward'])):02d}{int(float(f['properties']['precinct'])):03d}"
        assert code not in geometries
        if not g.is_valid:
            fixed=make_valid(g);assert abs(fixed.area-g.area)/g.area<.0001;g=fixed;repairs.append(code)
        assert not g.is_empty and g.is_valid;geometries[code]=g
    assert len(geometries)==1291
    for level in ['precinct','ward']:
        shapes=geometries if level=='precinct' else {f'{w:02d}':unary_union([g for code,g in geometries.items() if int(code[:2])==w]) for w in range(1,51)}
        features=[]
        for code,g in sorted(shapes.items()):
            simplified=g.simplify(.000012,preserve_topology=True);assert simplified.is_valid
            features.append({'type':'Feature','properties':{'district':name(code) if level=='precinct' else f'Ward {int(code):02d}','constituency_code':code},'geometry':mapping(simplified)})
        (ROOT/f'data/chicago_2023_{level}_boundaries.geojson').write_text(json.dumps({'type':'FeatureCollection','source':'City of Chicago Ward Precincts 2023–2024 (6piy-vbxa), applicable to both 2023 mayoral rounds. Wards dissolved from precincts.','features':features},separators=(',',':'))+'\n')
    dot_data={'elections':{}}
    for round_name in ROUNDS:
        areas=records(round_name);assert set(areas)==set(geometries)
        election={'candidates':list(EXPECTED[round_name]),'colors':{c:COLORS[c] for c in EXPECTED[round_name]},'date':DATES[round_name],'results_url':manifest['sources'][PDF[round_name]]['url'],'geographies':{}}
        for level in ['precinct','ward']:
            groups=areas if level=='precinct' else {f'{w:02d}':{'votes':{c:sum(a['votes'][c] for a in areas.values() if a['ward']==w) for c in EXPECTED[round_name]},'total':sum(a['total'] for a in areas.values() if a['ward']==w),'ballots':sum(a['ballots'] for a in areas.values() if a['ward']==w),'registered':sum(a['registered'] for a in areas.values() if a['ward']==w),'unrecorded':sum(a['unrecorded'] for a in areas.values() if a['ward']==w),'ward':w,'precinct':'','code':f'{w:02d}','state':'Chicago'} for w in range(1,51)}
            rows=[];dots={}
            for code,a in sorted(groups.items()):
                display=name(code) if level=='precinct' else f'Ward {int(code):02d}'
                ranked=sorted(a['votes'].items(),key=lambda r:(-r[1],r[0]));leader='No mayoral votes' if not a['total'] else 'Tied local leaders' if ranked[0][1]==ranked[1][1] else ranked[0][0]
                margin=ranked[0][1]-ranked[1][1] if a['total'] else 0
                base={'district':display,'district_url':election['results_url'],'distribution_url':manifest['sources'][CSV[round_name]]['url'],'elected_member':leader,'elected_party':leader,'enrolment':a['registered'],'formal_votes':a['total'],'informal_votes':a['unrecorded'],'total_votes':a['ballots'],'turnout_pct':100*a['ballots']/a['registered'] if a['registered'] else '', 'majority':margin,'round_number':0,'row_type':'first','electorate_type':a['state'],'constituency_code':code,'contest_status':'no-votes' if not a['total'] else 'tied-local' if leader=='Tied local leaders' else 'official','result_note':'Native reported mayoral counts preserved by DataMade; city candidate totals and ward ballot counts reconcile to the official proclamation. Local leader is not a separately elected mayor. Ballots without a recorded mayoral vote are not classified as blanks or overvotes.','ward':a['ward'],'precinct':a['precinct']}
                for candidate,votes in a['votes'].items():rows.append({**base,'candidate':candidate,'candidate_party':candidate,'votes':votes,'candidate_grouped':'false'})
                dots[display]={**a,'leader':leader,'margin':margin}
            with (ROOT/f'data/chicago_2023_mayor_{round_name}_{level}_fpp.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
            election['geographies'][level]=dots
        metadata={'round':round_name,'date':DATES[round_name],'candidate_totals':EXPECTED[round_name],'recorded_votes':sum(EXPECTED[round_name].values()),'ballots':BALLOTS[round_name],'registered':REG[round_name],'unrecorded':BALLOTS[round_name]-sum(EXPECTED[round_name].values()),'precinct_count':1291,'ward_count':50,'geometry_repairs':repairs,'sources':manifest}
        (ROOT/f'data/chicago_2023_mayor_{round_name}_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        dot_data['elections'][round_name]=election;print(round_name,metadata['recorded_votes'],metadata['ballots'],'1291 precincts / 50 wards')
    (ROOT/'data/chicago_precinct_dots.json').write_text(json.dumps(dot_data,separators=(',',':'))+'\n')

if __name__=='__main__':build()
