"""Boston mayoral general-election returns from pinned official PDF tables."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import pdfplumber
from shapely import make_valid
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/sources/boston'
RESULTS_PAGE='https://www.boston.gov/departments/elections/state-and-city-boston-election-results'
YEARS=[2013,2017,2021]
DATES={2013:'2013-11-05',2017:'2017-11-07',2021:'2021-11-02'}
BALLOTS={2013:142007,2017:109034,2021:144380}
PDF_URLS={2013:'https://documents.boston.gov/images_documents/2013%20-%2011-05-13%20-%20Mayor%20Ward%20%26%20Precinct%20Results%20%281%29_tcm3-41970.pdf',2017:'https://www.boston.gov/sites/default/files/embed/2/2017_-_11-07-17_-_mayor_ward_precinct_results.pdf',2021:'https://www.boston.gov/sites/default/files/file/2021/11/2021-11-02-21-Mayor.pdf'}
GIS_URL='https://services.arcgis.com/sFnw0xNflSi8J0uh/arcgis/rest/services/Precincts_2017/FeatureServer'
SHA={'2013_mayor.pdf':'19433624be31130ef1501cd3ea474db5324e4aa641275634456c14d26373b028','2017_mayor.pdf':'8f26c5e4ce3d94cd2fff31802f55da8807618c964ce00b53130b0ab089f8d3a5','2021_mayor.pdf':'284fee4e10d2367cf4d1121a1d3260e508dacc721c6400aedbaeeb0cda21ed77','precincts_2017.geojson':'00af69941be217a73b1fc9956b20c1441c9d2ada684d1433f74ee15dd8ae88d6','precincts_2017_metadata.json':'8f9ae76b784ec903066d38728f6a1c6c6c422c29fa6f34984ed700c76f8e448c'}
CANDIDATES={2013:{'JOHN R CONNOLLY':'John Connolly','MARTY J WALSH':'Marty Walsh','LEE BUCKLEY (WRITE-IN)':'Lee Buckley (write-in)','DAVID JAMES WYATT (WRITE-IN)':'David James Wyatt (write-in)','ALL OTHERS':'Other / write-in votes'},2017:{'TITO JACKSON':'Tito Jackson','MARTIN J WALSH':'Marty Walsh','DONALD OSGOOD SR (WRITE-IN)':'Donald Osgood Sr. (write-in)','ALL OTHERS':'Other / write-in votes'},2021:{'MICHELLE WU':'Michelle Wu','ANNISSA ESSAIBI GEORGE':'Annissa Essaibi George','ALL OTHERS':'Other / write-in votes'}}
EXPECTED={2013:{'John Connolly':67694,'Marty Walsh':72583,'Lee Buckley (write-in)':1,'David James Wyatt (write-in)':4,'Other / write-in votes':555},2017:{'Tito Jackson':36472,'Marty Walsh':70197,'Donald Osgood Sr. (write-in)':38,'Other / write-in votes':670},2021:{'Michelle Wu':91794,'Annissa Essaibi George':51125,'Other / write-in votes':595}}
COLORS={2013:{'Marty Walsh':'#7851a9','John Connolly':'#b86d22','Lee Buckley (write-in)':'#8c564b','David James Wyatt (write-in)':'#6b7f30','Other / write-in votes':'#7a7f87'},2017:{'Marty Walsh':'#7851a9','Tito Jackson':'#288b87','Donald Osgood Sr. (write-in)':'#a66a35','Other / write-in votes':'#7a7f87'},2021:{'Michelle Wu':'#277da8','Annissa Essaibi George':'#db6a27','Other / write-in votes':'#7a7f87'}}
FIELDS=['district','district_url','distribution_url','elected_member','elected_party','enrolment','formal_votes','informal_votes','total_votes','turnout_pct','majority','round_number','row_type','excluded_candidate','excluded_party','candidate','candidate_party','votes','electorate_type','constituency_code','contest_status','result_note','candidate_grouped','ward','precinct']

def name(code):return f'Ward {int(code[:2]):02d} · Precinct {code[2:]}'

def table(page):
    t=page.extract_tables()[0];header=t[0];columns=[(i,re.sub(r'\s+', '',v)) for i,v in enumerate(header[1:-1],1) if v and v.strip()]
    result={}
    for row in t[1:]:
        label=' '.join(row[0].split());assert label not in result
        values={col:int(row[i].replace(',','')) for i,col in columns}
        total=int(row[-1].replace(',',''));assert sum(values.values())==total,(label,values,total)
        assert all(not row[i] for i in range(1,len(header)-1) if not header[i])
        result[label]={'values':values,'total':total}
    return result

def returns(year):
    areas={};wards={}
    with pdfplumber.open(SOURCE/f'{year}_mayor.pdf') as pdf:
        assert len(pdf.pages)==23;city=table(pdf.pages[0])
        for ward,page in enumerate(pdf.pages[1:],1):
            assert re.search(r'WARD\s*:\s*'+str(ward)+r'\b',page.extract_text())
            rows=table(page);assert set(rows)==set(CANDIDATES[year])|{'VOTES CAST','BLANKS','BALLOTS CAST'}
            wards[ward]=rows
            for label,r in rows.items():assert r['total']==city[label]['values'][str(ward)]
            for precinct in rows['VOTES CAST']['values']:
                votes={display:rows[label]['values'][precinct] for label,display in CANDIDATES[year].items()}
                total=rows['VOTES CAST']['values'][precinct];blank=rows['BLANKS']['values'][precinct];ballots=rows['BALLOTS CAST']['values'][precinct]
                assert sum(votes.values())==total and total+blank==ballots
                m=re.fullmatch(r'(\d+)([A-Z]?)',precinct);assert m,precinct
                code=f'{ward:02d}{int(m[1]):02d}{m[2]}';areas[code]={'votes':votes,'total':total,'blank':blank,'ballots':ballots,'ward':ward,'precinct':precinct}
    assert len(areas)==255
    assert {n:sum(r['votes'][n] for r in areas.values()) for n in EXPECTED[year]}==EXPECTED[year]
    assert sum(r['ballots'] for r in areas.values())==BALLOTS[year]
    return areas

def export_geometry(geometries,level):
    features=[]
    if level=='ward':geometries={f'{w:02d}':unary_union([g for code,g in geometries.items() if int(code[:2])==w]) for w in range(1,23)}
    for code,g in sorted(geometries.items()):
        display=name(code) if level=='precinct' else f'Ward {int(code):02d}'
        simplified=g.simplify(.000008,preserve_topology=True);assert simplified.is_valid
        features.append({'type':'Feature','properties':{'district':display,'constituency_code':code},'geometry':mapping(simplified)})
    path=ROOT/f'data/boston_historical_{level}_boundaries.geojson'
    path.write_text(json.dumps({'type':'FeatureCollection','source':'City of Boston GIS Precincts_2017, October 2017 snapshot. Used as historical reference for 2013 and 2021; election-day equivalence is not independently established.','features':features},separators=(',',':'))+'\n')

def build():
    for n,digest in SHA.items():assert hashlib.sha256((SOURCE/n).read_bytes()).hexdigest()==digest,n
    raw=json.loads((SOURCE/'precincts_2017.geojson').read_text());assert len(raw['features'])==255
    geometry={};repairs=[]
    for feature in raw['features']:
        code=feature['properties']['WARD_PRECINCT'];g=shape(feature['geometry'])
        assert code not in geometry
        if not g.is_valid:
            repaired=make_valid(g);assert abs(repaired.area-g.area)/g.area<.0001;g=repaired;repairs.append(code)
        assert g.is_valid and not g.is_empty;geometry[code]=g
    for level in ['precinct','ward']:export_geometry(geometry,level)
    dot_data={'elections':{}}
    for year in YEARS:
        areas=returns(year);assert set(areas)==set(geometry)
        for a in areas.values():
            ranked=sorted(((c,v) for c,v in a['votes'].items() if c!='Other / write-in votes'),key=lambda x:(-x[1],x[0]))
            a['leader']='No mayoral votes' if not a['total'] else 'Tied local leaders' if ranked[0][1]==ranked[1][1] else ranked[0][0]
            a['margin']=0 if not a['total'] else ranked[0][1]-ranked[1][1]
        for level in ['precinct','ward']:
            groups=areas if level=='precinct' else {f'{w:02d}':{'votes':dict(sum((Counter(a['votes']) for a in areas.values() if a['ward']==w),Counter())),'total':sum(a['total'] for a in areas.values() if a['ward']==w),'blank':sum(a['blank'] for a in areas.values() if a['ward']==w),'ballots':sum(a['ballots'] for a in areas.values() if a['ward']==w),'ward':w,'precinct':''} for w in range(1,23)}
            rows=[]
            for code,a in sorted(groups.items()):
                ranked=sorted(((c,v) for c,v in a['votes'].items() if c!='Other / write-in votes'),key=lambda x:(-x[1],x[0]))
                status='no-votes' if not a['total'] else 'tied-local' if ranked[0][1]==ranked[1][1] else 'official';winner=ranked[0][0] if status=='official' else ''
                display=name(code) if level=='precinct' else f'Ward {int(code):02d}'
                base={'district':display,'district_url':RESULTS_PAGE,'distribution_url':PDF_URLS[year],'elected_member':winner,'elected_party':winner,'enrolment':'','formal_votes':a['total'],'informal_votes':a['blank'],'total_votes':a['ballots'],'turnout_pct':'','majority':ranked[0][1]-ranked[1][1],'round_number':0,'row_type':'first','electorate_type':f"Ward {a['ward']:02d}" if level=='precinct' else 'Boston','constituency_code':code,'contest_status':status,'result_note':(f'Historical October 2017 City GIS reference; {year} boundary equivalence not independently verified. ' if year!=2017 else '')+'Candidate votes are reported, not estimated. Other / write-in votes is a grouped return, excluded from individual-candidate leader selection.','ward':a['ward'],'precinct':a['precinct']}
                for c in EXPECTED[year]:rows.append({**base,'candidate':c,'candidate_party':c,'votes':a['votes'].get(c,0),'candidate_grouped':str(c=='Other / write-in votes').lower()})
            with (ROOT/f'data/boston_{year}_mayor_{level}_fpp.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
        metadata={'year':year,'election_date':DATES[year],'results_page':RESULTS_PAGE,'results_url':PDF_URLS[year],'boundary_url':GIS_URL,'boundary_snapshot':'October 2017 City of Boston GIS','boundary_caveat':f'October 2017 historical reference. Identifier coverage matches all 255 reporting precincts in {year}; this does not establish election-day geometry equivalence for other years.','source_sha256':{f'data/sources/boston/{n}':d for n,d in SHA.items() if not n.endswith('_mayor.pdf') or n.startswith(str(year))},'candidate_totals':EXPECTED[year],'recorded_votes':sum(EXPECTED[year].values()),'ballots':sum(a['ballots'] for a in areas.values()),'blanks':sum(a['blank'] for a in areas.values()),'precinct_count':255,'ward_count':22,'geometry_repairs':repairs}
        (ROOT/f'data/boston_{year}_mayor_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        dot_data['elections'][str(year)]={'candidates':list(EXPECTED[year]),'colors':COLORS[year],'results_url':PDF_URLS[year],'metadata':metadata,'precincts':{name(code):dict(a,code=code,state=f"Ward {a['ward']:02d}") for code,a in sorted(areas.items())}}
        print(year,metadata['recorded_votes'],metadata['ballots'],'255 precincts;22 wards')
    (ROOT/'data/boston_precinct_dots.json').write_text(json.dumps(dot_data,separators=(',',':'))+'\n')

if __name__=='__main__':build()
