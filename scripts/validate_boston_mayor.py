"""Independently audit every reported precinct cell, ward total and map join."""
import csv
import hashlib
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
import pdfplumber
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1]
LABELS={2013:{'JOHN R CONNOLLY':'John Connolly','MARTY J WALSH':'Marty Walsh','LEE BUCKLEY (WRITE-IN)':'Lee Buckley (write-in)','DAVID JAMES WYATT (WRITE-IN)':'David James Wyatt (write-in)','ALL OTHERS':'Other / write-in votes'},2017:{'TITO JACKSON':'Tito Jackson','MARTIN J WALSH':'Marty Walsh','DONALD OSGOOD SR (WRITE-IN)':'Donald Osgood Sr. (write-in)','ALL OTHERS':'Other / write-in votes'},2021:{'MICHELLE WU':'Michelle Wu','ANNISSA ESSAIBI GEORGE':'Annissa Essaibi George','ALL OTHERS':'Other / write-in votes'}}
EXPECTED={2013:{'John Connolly':67694,'Marty Walsh':72583,'Lee Buckley (write-in)':1,'David James Wyatt (write-in)':4,'Other / write-in votes':555},2017:{'Marty Walsh':70197,'Tito Jackson':36472,'Donald Osgood Sr. (write-in)':38,'Other / write-in votes':670},2021:{'Michelle Wu':91794,'Annissa Essaibi George':51125,'Other / write-in votes':595}}

def read_text_rows(page,year):
    # Deliberately use positioned text rather than the builder's table detector.
    text=page.extract_text().split('PERCENTAGE')[0]
    lines=text.splitlines();header=next(l for l in lines if l.startswith('CANDIDATES '))
    columns=header.split()[1:-1];rows={}
    for label in set(LABELS[year])|{'VOTES CAST','BLANKS','BALLOTS CAST'}:
        line=next(l for l in lines if re.fullmatch(re.escape(label)+r'(?:\s+[\d,]+)+',l))
        values=[int(v.replace(',','')) for v in line[len(label):].split()]
        assert len(values)==len(columns)+1 and sum(values[:-1])==values[-1]
        rows[label]=dict(zip(columns,values[:-1]))
    return rows

for year in [2013,2017,2021]:
    metadata=json.loads((ROOT/f'data/boston_{year}_mayor_metadata.json').read_text())
    for p,digest in metadata['source_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest
    precincts=defaultdict(list)
    for row in csv.DictReader((ROOT/f'data/boston_{year}_mayor_precinct_fpp.csv').open()):precincts[row['constituency_code']].append(row)
    assert len(precincts)==255 and '0502A' in precincts
    with pdfplumber.open(ROOT/f'data/sources/boston/{year}_mayor.pdf') as pdf:
        city=read_text_rows(pdf.pages[0],year)
        for ward,page in enumerate(pdf.pages[1:],1):
            rows=read_text_rows(page,year)
            for label,values in rows.items():assert sum(values.values())==city[label][str(ward)]
            for number in rows['VOTES CAST']:
                match=re.fullmatch(r'(\d+)([A-Z]?)',number);code=f'{ward:02d}{int(match[1]):02d}{match[2]}'
                entries=precincts[code];votes={r['candidate']:int(r['votes']) for r in entries}
                assert votes=={display:rows[label][number] for label,display in LABELS[year].items()}
                assert all(int(r['formal_votes'])==rows['VOTES CAST'][number] for r in entries)
                assert all(int(r['informal_votes'])==rows['BLANKS'][number] for r in entries)
                assert all(int(r['total_votes'])==rows['BALLOTS CAST'][number] for r in entries)
    for level,count in [('precinct',255),('ward',22)]:
        rows=list(csv.DictReader((ROOT/f'data/boston_{year}_mayor_{level}_fpp.csv').open()));groups=defaultdict(list);totals=Counter()
        for r in rows:groups[r['district']].append(r);totals[r['candidate']]+=int(r['votes'])
        assert len(groups)==count and dict(totals)==EXPECTED[year]
        geo=json.loads((ROOT/f'data/boston_historical_{level}_boundaries.geojson').read_text())
        assert {f['properties']['district'] for f in geo['features']}==set(groups)
        assert all(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in geo['features'])
        for n,entries in groups.items():
            first=entries[0];recorded=sum(int(r['votes']) for r in entries)
            assert recorded==int(first['formal_votes']) and recorded+int(first['informal_votes'])==int(first['total_votes'])
            named=sorted(((r['candidate'],int(r['votes'])) for r in entries if r['candidate_grouped']!='true'),key=lambda x:(-x[1],x[0]))
            status='no-votes' if not recorded else 'tied-local' if named[0][1]==named[1][1] else 'official'
            assert all(r['contest_status']==status and r['elected_member']==(named[0][0] if status=='official' else '') for r in entries)
            assert all(r['enrolment']==r['turnout_pct']=='' for r in entries)
            if level=='ward':
                ward=int(first['ward']);expected=Counter()
                for code,rs in precincts.items():
                    if int(code[:2])==ward:expected.update({r['candidate']:int(r['votes']) for r in rs})
                assert expected==Counter({r['candidate']:int(r['votes']) for r in entries})
        assert sum(int(rs[0]['total_votes']) for rs in groups.values())=={2013:142007,2017:109034,2021:144380}[year]
    dots=json.loads((ROOT/'data/boston_precinct_dots.json').read_text())['elections'][str(year)]['precincts']
    assert {r['code'] for r in dots.values()}==set(precincts)
    for n,r in dots.items():
        original=precincts[r['code']]
        assert r['votes']=={x['candidate']:int(x['votes']) for x in original}
        assert r['ballots']==int(original[0]['total_votes']) and r['blank']==int(original[0]['informal_votes'])
        status=original[0]['contest_status'];leader='No mayoral votes' if status=='no-votes' else 'Tied local leaders' if status=='tied-local' else original[0]['elected_member']
        assert r['leader']==leader and r['margin']==int(original[0]['majority'])
    print(f'PASS {year}: all PDF precinct cells, 22 ward recaps, citywide totals, 255 map joins, 2A identifier, blanks, named/grouped write-ins and dot records')
