"""Independently check vote shares, map screening and all Boston partitions."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import shape
from shapely.ops import transform
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / 'data/boston_history_clusters.json').read_text())
assert d['summary'] == {'total':255,'complete':254,'boundary_pass':38,'screened':38}
for filename, digest in d['source_sha256'].items():
    assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest, filename
assert d['threshold'] == .99
candidates = ['Marty Walsh','Marty Walsh','Michelle Wu']
opponents = ['John Connolly','Tito Jackson','Annissa Essaibi George']
# Source CSVs, rather than the builder's dot extract, independently establish each share.
for i, year in enumerate([2013,2017,2021]):
    by_code = {}
    with (ROOT / f'data/boston_{year}_mayor_precinct_fpp.csv').open() as f:
        for row in csv.DictReader(f):
            by_code.setdefault(row['constituency_code'], {})[row['candidate']] = int(row['votes'])
    assert len(by_code) == 255
    for name, area in d['areas'].items():
        votes = by_code[area['code']]
        assert area['votes'][str(year)] == votes
        denominator = votes[candidates[i]] + votes[opponents[i]]
        expected = 100 * votes[candidates[i]] / denominator if denominator else None
        assert area['shares'][i] == expected
source = ROOT / 'data/sources/boston'
project = Transformer.from_crs(4326,26986,always_xy=True).transform
city = {f['properties']['WARD_PRECINCT']: transform(project,make_valid(shape(f['geometry'])))
        for f in json.loads((source/'precincts_2017.geojson').read_text())['features']}
for year, filename in [('2012_2016','ma_2012_2016_boston.geojson'),('2020','ma_2020_vtd_boston.geojson')]:
    other = {f['properties']['code']:make_valid(shape(f['geometry'])) for f in json.loads((source/filename).read_text())['features']}
    for area in d['areas'].values():
        check = area['boundary_audit'][year]; code = area['code']
        assert check['present'] == (code in other)
        if code in other:
            a,b = city[code],other[code]
            expected = a.intersection(b).area / max(a.area,b.area)
            # PROJ/GEOS versions differ across macOS and Linux. Allow a tiny
            # area-ratio tolerance while checking the 99% decision exactly.
            assert abs(check['minimum_coverage']-expected) < 1e-7, (code, year, check['minimum_coverage'], expected)
            assert check['passes'] == (expected >= .99)
        else:
            assert check['minimum_coverage'] is None and not check['passes']
for area in d['areas'].values():
    assert area['complete'] == (None not in area['shares'])
    assert area['boundary_pass'] == all(a['passes'] for a in area['boundary_audit'].values())
    assert bool(area['exclusion_reasons']) == (not area['complete'] or not area['boundary_pass'])
for mode in ['screened','exploratory']:
    names = sorted(n for n,a in d['areas'].items() if a['complete'] and (mode=='exploratory' or a['boundary_pass']))
    x = np.array([d['areas'][n]['shares'] for n in names])
    for k in [2,3,4,5,7]:
        m=d['models'][mode][str(k)];assert set(m['assignments'])==set(names)
        labels=np.array([m['assignments'][n] for n in names]); assert set(labels)==set(range(1,k+1))
        independent=AgglomerativeClustering(n_clusters=k,linkage='ward').fit_predict(x)
        assert adjusted_rand_score(labels,independent)==1
        assert abs(silhouette_score(x,labels)-m['silhouette'])<1e-12
        for group in m['groups']:
            members=x[labels==group['id']]; assert len(members)==group['size']
            assert np.allclose(members.mean(axis=0),group['centroid'])
        # Reversing the candidate axis changes no distances and no grouping.
        flipped=AgglomerativeClustering(n_clusters=k,linkage='ward').fit_predict(100-x)
        assert adjusted_rand_score(labels,flipped)==1
assert d['areas']['Ward 01 · Precinct 15']['shares'][1] is None
assert not d['areas']['Ward 05 · Precinct 02A']['boundary_pass']
print('PASS Boston histories: every native vote/share, independent 99% geometry screen, source hashes, all 10 partitions and candidate-axis reversal')
