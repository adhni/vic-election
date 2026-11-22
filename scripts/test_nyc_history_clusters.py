"""Independently reconcile estimated target histories and Ward groups."""
import hashlib
import json
from pathlib import Path
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/nyc_history_clusters.json').read_text())
cross=json.loads((ROOT/'data/nyc_history_crosswalk.json').read_text())
raw=json.loads((ROOT/'data/nyc_precinct_dots.json').read_text())['elections']
for path,digest in data['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert cross['source_sha256']==data['source_sha256']
areas=data['areas'];names=list(areas);index={n:i for i,n in enumerate(names)}
assert set(names)==set(raw['2021']['precincts']) and len(names)==5697
for y in [2017,2025]:
    reconstructed=np.zeros((len(names),3));alternative=np.zeros((2,len(names),3));seen=set();ledger={k:[0,0,0,0] for k in data['source_vote_ledger'][str(y)]}
    metadata=json.loads((ROOT/f'data/nyc_{y}_mayor_metadata.json').read_text());missing=set(map(str,metadata['combined_ed_without_polygon']))
    for row in cross['sources'][str(y)]:
        n=row['source'];assert n not in seen;seen.add(n);source=raw[str(y)]['precincts'][n]
        vector=[source['democratic'],source['opposition'],source['other']]
        bucket=ledger[row['status']];bucket[0]+=1
        for i,v in enumerate(vector):bucket[i+1]+=v
        if row['status']=='allocated':
            assert row['coverage']>=.99 and not missing.intersection(source['combined_from'].split(';'))
            assert abs(sum(w for _,w in row['targets'])-1)<1e-10
            assert all(w>0 for _,w in row['targets'])
            weights=np.array([w for _,w in row['targets']])
            alternatives=[weights**.5,weights**2]
            alternatives=[w/w.sum() for w in alternatives]
            for position,(target,w) in enumerate(row['targets']):
                assert areas[target]['state']==source['state']
                reconstructed[index[target]]+=np.array(vector)*w
                for scenario,alternative_weights in enumerate(alternatives):
                    alternative[scenario,index[target]]+=np.array(vector)*alternative_weights[position]
        else:assert not row['targets']
    assert seen==set(raw[str(y)]['precincts'])
    for status,bucket in ledger.items():
        expected=data['source_vote_ledger'][str(y)][status]
        assert bucket==[expected[k] for k in ['areas','democratic','republican','other']]
    observed=np.array([[areas[n]['votes'][str(y)][k] for k in ['democratic','republican','other']] for n in names])
    np.testing.assert_allclose(observed,reconstructed,atol=1e-8,rtol=1e-12)
    np.testing.assert_allclose(observed.sum(axis=0),ledger['allocated'][1:],atol=1e-6)
    for i,n in enumerate(names):
        values=np.vstack([observed[i],alternative[:,i]])
        denominator=values[:,0]+values[:,1]
        if all(denominator):
            shares=100*values[:,0]/denominator
            spread=float(shares.max()-shares.min())
            assert abs(spread-areas[n]['quality'][str(y)]['allocation_sensitivity_pp'])<1e-7
        else:assert areas[n]['quality'][str(y)]['allocation_sensitivity_pp'] is None
for n,r in areas.items():
    original=raw['2021']['precincts'][n]
    assert r['votes']['2021']==dict(democratic=original['democratic'],republican=original['opposition'],other=original['other'])
    for i,y in enumerate(data['years']):
        v=r['votes'][str(y)];den=v['democratic']+v['republican']
        assert r['democratic_share'][i]==(100*v['democratic']/den if den else None)
    assert r['eligible']==(not r['exclusion_reasons'])
    if r['eligible']:
        assert all(v is not None and 0<=v<=100 for v in r['democratic_share'])
        assert all(r['quality'][str(y)]['coverage']>=.99 for y in [2017,2025])
        assert not r['quality']['2021']['incomplete_geometry']
    assert r['allocation_sensitive']==any((r['quality'][str(y)].get('allocation_sensitivity_pp') or 0)>5 for y in [2017,2025])
valid=sorted(n for n,r in areas.items() if r['eligible']);x=np.array([areas[n]['democratic_share'] for n in valid])
for k in [2,3,4,5,7]:
    model=data['models'][str(k)];assert set(model['assignments'])==set(valid)
    assignments=np.array([model['assignments'][n]['group'] for n in valid])
    independent=AgglomerativeClustering(n_clusters=k,linkage='ward').fit_predict(x)
    assert adjusted_rand_score(assignments,independent)==1
    means=[]
    for g in model['groups']:
        members=[n for n in valid if model['assignments'][n]['group']==g['id']]
        assert members==g['members'] and len(members)==g['size']
        centroid=np.array([areas[n]['democratic_share'] for n in members]).mean(axis=0)
        np.testing.assert_allclose(centroid,g['centroid'])
        assert abs(centroid.mean()-g['mean_democratic_share'])<1e-10
        means.append(g['mean_democratic_share'])
    assert means==sorted(means)
assert data['summary']['eligible_areas']==len(valid)
assert data['summary']['excluded_areas']==len(areas)-len(valid)
assert data['sides']['2025']['opposition']==['Andrew Cuomo','Curtis Sliwa']
print('PASS source hashes, every source vote ledger, all target allocations, withheld votes, coverage eligibility, sensitivity flags and independent Ward fits for 2–5 and 7 groups')
