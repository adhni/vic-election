"""Independent native-cell, certified recap and boundary validation for Chicago."""
import csv
import hashlib
import json
import re
from pathlib import Path
from collections import defaultdict
import pdfplumber
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'data/sources/chicago'
manifest=json.loads((source/'source_manifest.json').read_text())
for n,m in manifest['sources'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==m['sha256']
dots=json.loads((ROOT/'data/chicago_precinct_dots.json').read_text())['elections']
for round_name,source_type,pdf_name in [('first-round','general','2023_first_round.pdf'),('runoff','runoff','2023_runoff.pdf')]:
    data=dots[round_name]
    with (source/f'municipal_{source_type}_2023.csv').open() as f:original=list(csv.DictReader(f))
    assert len(original)==1291
    # Validate source column identities against candidate totals in the official PDF.
    count=15 if round_name=='first-round' else 2
    candidate_columns=list(original[0])[4:4+count]
    with pdfplumber.open(source/pdf_name) as pdf:
        # Positioned words, independent of the builder's cropped text lines.
        words=pdf.pages[5].extract_words();left=[w for w in words if w['x0']<pdf.pages[5].width/2]
        lines=defaultdict(list)
        for w in left:lines[round(w['top'],1)].append(w)
        in_mayor=False;official={}
        for _,line in sorted(lines.items()):
            txt=' '.join(w['text'] for w in sorted(line,key=lambda w:w['x0']))
            if txt=='Mayor':in_mayor=True;continue
            if not in_mayor:continue
            if txt.startswith('Total '):break
            m=re.fullmatch(r'(.+?) ([\d,]+) [\d.]+%',txt)
            if m:official[m[1]]=int(m[2].replace(',',''))
        assert set(official)==set(candidate_columns),(round_name,official.keys(),candidate_columns)
        assert {c:sum(int(r[c]) for r in original) for c in candidate_columns}==official
        recap='\n'.join(p.extract_text() for p in pdf.pages[:5])
    ballot_recap={int(w):int(n.replace(',','')) for w,n in re.findall(r'(?m)^(\d+)(?:st|nd|rd|th) Ward ([\d,]+)$',recap)}
    counts={int(w):int(n) for w,n,reported in re.findall(r'(?m)^(\d+)(?:st|nd|rd|th) Ward (\d+) Precincts Reported: (\d+)$',recap) if n==reported}
    assert len(ballot_recap)==len(counts)==50
    # The output order corresponds to the source mayor columns; no other office enters.
    display=data['candidates'];assert len(display)==len(candidate_columns)
    assert display[:2]==(["Ja'Mal Green",'Sophia King'] if round_name=='first-round' else ['Brandon Johnson','Paul Vallas'])
    source_by_code={f"{int(r['WARD']):02d}{int(r['PRECINCT']):03d}":r for r in original}
    for level,records in data['geographies'].items():
        csv_file=ROOT/f'data/chicago_2023_mayor_{round_name}_{level}_fpp.csv'
        with csv_file.open() as f:exported=list(csv.DictReader(f))
        by_area=defaultdict(list)
        for r in exported:by_area[r['constituency_code']].append(r)
        assert len(by_area)==(1291 if level=='precinct' else 50)
        assert len(exported)==len(by_area)*len(display)
        geo=json.loads((ROOT/f'data/chicago_2023_{level}_boundaries.geojson').read_text())
        assert {f['properties']['constituency_code'] for f in geo['features']}==set(by_area)
        assert {f['properties']['district'] for f in geo['features']}==set(records)
        assert all(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in geo['features'])
        for name,r in records.items():
            rows=by_area[r['code']]
            raw=[source_by_code[r['code']]] if level=='precinct' else [v for k,v in source_by_code.items() if int(k[:2])==r['ward']]
            expected={c:sum(int(v[col]) for v in raw) for c,col in zip(display,candidate_columns)}
            assert r['votes']==expected and r['total']==sum(expected.values())
            ballots=sum(int(v['BALLOTS CAST']) for v in raw);registered=sum(int(v['REGISTERED VOTERS']) for v in raw)
            assert r['ballots']==ballots and r['registered']==registered and r['unrecorded']==ballots-r['total']>=0
            if level=='ward':assert ballots==ballot_recap[r['ward']] and len(raw)==counts[r['ward']]
            ranked=sorted(expected.items(),key=lambda x:(-x[1],x[0]))
            leader='No mayoral votes' if not r['total'] else 'Tied local leaders' if ranked[0][1]==ranked[1][1] else ranked[0][0]
            assert r['leader']==leader and r['margin']==ranked[0][1]-ranked[1][1]
            assert {v['candidate']:int(v['votes']) for v in rows}==expected
            assert all(int(v['formal_votes'])==r['total'] and int(v['total_votes'])==ballots and int(v['enrolment'])==registered and int(v['informal_votes'])==r['unrecorded'] and abs(float(v['turnout_pct'])-100*ballots/registered)<1e-10 for v in rows)
    assert sum(r['registered'] for r in data['geographies']['precinct'].values())==({'first-round':1581564,'runoff':1587153}[round_name])
    print(f'PASS Chicago {round_name}: every precinct cell, 50 ward aggregates/ballot recaps, official candidate totals, registration, turnout, write-ins and map joins')
assert len([c for c in dots['first-round']['candidates'] if 'write-in' in c])==6
metadata=json.loads((source/'precincts_2023_metadata.json').read_text())
assert 'Feb 28, 2023' in metadata['description'] and 'November 5, 2024' in metadata['description']
print('PASS City GIS documentation covers both 2023 rounds')
