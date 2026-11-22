"""Estimated three-election NYC histories on the 2021 reporting-area map.

Area-weighted crosswalk; no nearest-neighbour filling. Incomplete source
geometry and <99% source coverage are withheld. Only fully covered target
histories enter clustering. Every source vote is accounted for in the ledger.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from scipy.cluster.hierarchy import linkage, cut_tree

ROOT=Path(__file__).resolve().parents[1]
YEARS=[2017,2021,2025]
KS=[2,3,4,5,7]
PALETTE=['#7851a9','#c57928','#288b87','#4267b2','#bd4c71','#6b7f30','#8c564b']

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    path=ROOT/'data/nyc_precinct_dots.json';raw=json.loads(path.read_text())['elections']
    hashes={str(path.relative_to(ROOT)):sha(path)}
    names={};geos={};missing={};records={int(y):e['precincts'] for y,e in raw.items()}
    project=Transformer.from_crs(4326,32618,always_xy=True).transform
    for y in YEARS:
        path=ROOT/f'data/nyc_{y}_mayor_ed_boundaries.geojson';hashes[str(path.relative_to(ROOT))]=sha(path)
        f=json.loads(path.read_text())['features'];names[y]=[x['properties']['district'] for x in f];geos[y]=[transform(project,shape(x['geometry'])) for x in f]
        path=ROOT/f'data/nyc_{y}_mayor_metadata.json';hashes[str(path.relative_to(ROOT))]=sha(path)
        missing_codes=set(map(str,json.loads(path.read_text())['combined_ed_without_polygon']))
        missing[y]={n for n,r in records[y].items() if missing_codes.intersection(r['combined_from'].split(';'))}
        assert all(g.is_valid and g.area>0 for g in geos[y])
        print('Loaded',y,flush=True)
    target=2021;target_names=names[target];n=len(target_names)
    boroughs=sorted({r['state'] for r in records[target].values()})
    target_unions={b:unary_union([g for name,g in zip(target_names,geos[target]) if records[target][name]['state']==b]) for b in boroughs}
    histories={name:{'state':records[target][name]['state'],'constituency_code':records[target][name]['code'],
      'votes':{},'quality':{},'eligible':False} for name in target_names}
    ledgers={};crosswalks={}
    for y in YEARS:
        if y==target:
            for name,r in records[y].items():
                histories[name]['votes'][str(y)]={'democratic':r['democratic'],'republican':r['opposition'],'other':r['other']}
                histories[name]['quality'][str(y)]={'status':'Reported 2021 total','coverage':1 if name not in missing[y] else None,'incomplete_geometry':name in missing[y]}
            continue
        pair=sorted([y,target]);cache_path=ROOT/f'tmp/nyc-reference-overlap-{pair[0]}-{pair[1]}.json'
        cache=json.loads(cache_path.read_text())
        expected={k:v for k,v in hashes.items() if 'boundaries' in k and any(str(a) in k for a in pair)}
        assert cache['source_sha256']==expected,'Run compare_nyc_reference_maps.py to refresh crosswalk cache'
        hits=[[] for _ in names[y]]
        for i,j,a in cache['edges']:
            si,tj=(i,j) if y==pair[0] else (j,i)
            if records[y][names[y][si]]['state']==records[target][target_names[tj]]['state']:hits[si].append((tj,a))
        allocations=np.zeros((3,n,3));accepted=[];source_rows=[]
        ledger={reason:{'areas':0,'democratic':0,'republican':0,'other':0} for reason in ['allocated','missing_component_geometry','coverage_below_99pct','overlapping_targets']}
        for i,(name,g) in enumerate(zip(names[y],geos[y])):
            r=records[y][name];b=r['state'];coverage=min(1,g.intersection(target_unions[b]).area/g.area)
            summed=sum(a for _,a in hits[i]);reason='allocated'
            if name in missing[y]:reason='missing_component_geometry'
            elif coverage<.99 or not summed:reason='coverage_below_99pct'
            elif summed/g.area>1.01:reason='overlapping_targets'
            l=ledger[reason];l['areas']+=1
            for key,v in [('democratic',r['democratic']),('republican',r['opposition']),('other',r['other'])]:l[key]+=v
            row={'source':name,'coverage':round(coverage,8),'status':reason,'targets':[]}
            if reason=='allocated':
                accepted.append(i)
                indices=np.array([j for j,_ in hits[i]],dtype=int);areas=np.array([a for _,a in hits[i]])
                vector=np.array([r['democratic'],r['opposition'],r['other']])
                for scenario,power in enumerate([1,.5,2]):
                    weights=areas**power;weights/=weights.sum()
                    allocations[scenario,indices,:]+=weights[:,None]*vector[None,:]
                    if scenario==0:row['targets']=[[target_names[j],float(w)] for j,w in zip(indices,weights)]
                assert abs(sum(w for _,w in row['targets'])-1)<1e-10
            source_rows.append(row)
        accepted_union={b:unary_union([geos[y][i] for i in accepted if records[y][names[y][i]]['state']==b]) for b in boroughs}
        for j,(name,g) in enumerate(zip(target_names,geos[target])):
            b=records[target][name]['state'];coverage=min(1,g.intersection(accepted_union[b]).area/g.area)
            d,r,o=allocations[0,j];alternatives=[]
            for scenario in range(3):
                sd,sr,_=allocations[scenario,j];alternatives.append(float(100*sd/(sd+sr)) if sd+sr else None)
            histories[name]['votes'][str(y)]={'democratic':float(d),'republican':float(r),'other':float(o)}
            histories[name]['quality'][str(y)]={'status':'Area-weighted estimate','coverage':round(coverage,8),'incomplete_geometry':False,
              'allocation_sensitivity_pp':float(max(alternatives)-min(alternatives)) if all(v is not None for v in alternatives) else None}
        for col,key in enumerate(['democratic','republican','other']):
            assert abs(allocations[0,:,col].sum()-ledger['allocated'][key])<1e-6
            assert sum(l[key] for l in ledger.values())==sum(r['democratic' if key=='democratic' else 'opposition' if key=='republican' else 'other'] for r in records[y].values())
        ledgers[str(y)]=ledger;crosswalks[str(y)]=source_rows
        print('Allocated',y,ledger,flush=True)
    eligible=[]
    for name,r in histories.items():
        reasons=[];shares=[]
        if r['quality']['2021']['incomplete_geometry']:reasons.append('2021 reporting area has missing component geometry')
        for y in YEARS:
            v=r['votes'][str(y)];q=r['quality'][str(y)];den=v['democratic']+v['republican']
            shares.append(100*v['democratic']/den if den else None)
            if not den:reasons.append(f'No usable two-side votes in {y}')
            if y!=2021 and q['coverage']<.99:reasons.append(f'Less than 99% mapped coverage from usable {y} source areas')
        r['democratic_share']=shares;r['eligible']=not reasons;r['exclusion_reasons']=reasons
        r['allocation_sensitive']=any((r['quality'][str(y)].get('allocation_sensitivity_pp') or 0)>5 for y in [2017,2025])
        if not reasons:eligible.append(name)
    eligible.sort();x=np.array([histories[name]['democratic_share'] for name in eligible]);assert len(x)>7 and np.isfinite(x).all()
    tree=linkage(x,method='ward');models={}
    for k in KS:
        old=cut_tree(tree,n_clusters=k).ravel();order=sorted(set(old),key=lambda a:(x[old==a].mean(),a));remap={a:i+1 for i,a in enumerate(order)}
        labels=np.array([remap[a] for a in old]);groups=[]
        for i in range(1,k+1):
            members=[name for name,label in zip(eligible,labels) if label==i];centroid=x[labels==i].mean(axis=0)
            groups.append({'id':i,'color':PALETTE[i-1],'size':len(members),'members':members,'centroid':centroid.tolist(),'mean_democratic_share':float(centroid.mean())})
        models[str(k)]={'k':k,'method':'similarity','groups':groups,'assignments':{name:{'group':int(label)} for name,label in zip(eligible,labels)}}
    summary={'target_year':2021,'mapped_areas':n,'eligible_areas':len(eligible),'excluded_areas':n-len(eligible),
      'allocation_sensitive_eligible_areas':sum(histories[name]['allocation_sensitive'] for name in eligible),
      'native_2021_two_side_votes_in_eligible_areas_pct':100*sum(sum(histories[name]['votes']['2021'][key] for key in ['democratic','republican']) for name in eligible)/sum(r['democratic']+r['opposition'] for r in records[2021].values())}
    result={'years':YEARS,'target_year':2021,'summary':summary,'source_sha256':hashes,
      'method':'Ward hierarchical clustering of three equally weighted Democratic-side vote shares; each eligible 2021 reporting area has equal weight.',
      'allocation':'Uniform area weights across same-borough target intersections, normalized only for complete source geometry with at least 99% union target coverage and no more than 1% overlapping-target excess. Ineligible source votes are withheld and reconciled separately.',
      'sensitivity':'Range of Democratic-side share under overlap-area powers 0.5, 1 and 2. A range over 5 percentage points is flagged. These are assumption checks, not confidence intervals.',
      'caveat':'2017 and 2025 are estimates, not reported 2021-area results. Uniform area allocation does not account for where voters live. Missing geometry is flagged/excluded, not invented.',
      'sides':{y:{'democratic':raw[str(y)]['democratic_candidate'],'opposition':raw[str(y)]['opposition_candidates']} for y in YEARS},
      'areas':histories,'models':models,'source_vote_ledger':ledgers}
    (ROOT/'data/nyc_history_clusters.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
    (ROOT/'data/nyc_history_crosswalk.json').write_text(json.dumps({'target_year':2021,'source_sha256':hashes,'sources':crosswalks},separators=(',',':'),allow_nan=False)+'\n')
    print(summary,flush=True)

if __name__=='__main__':main()
