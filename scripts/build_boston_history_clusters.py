"""Candidate-history clusters with conservative cross-source geometry screening."""
import hashlib
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.cluster.hierarchy import cut_tree, linkage
from shapely import make_valid
from shapely.geometry import shape
from shapely.ops import transform
from sklearn.metrics import adjusted_rand_score, silhouette_score

ROOT = Path(__file__).resolve().parents[1]
YEARS = [2013, 2017, 2021]
CANDIDATES = ['Marty Walsh', 'Marty Walsh', 'Michelle Wu']
OPPONENTS = ['John Connolly', 'Tito Jackson', 'Annissa Essaibi George']
KS = [2, 3, 4, 5, 7]
PALETTE = ['#7851a9', '#c57928', '#288b87', '#4267b2', '#bd4c71', '#6b7f30', '#8c564b']
THRESHOLD = .99
SOURCE = ROOT / 'data/sources/boston'
FIXTURES = {
    'ma_2012_2016_boston.geojson': '72ce83e07ee996c0dd7cc2f97406c3aca349d3aac11e0051e4e8324b7efd1b75',
    'ma_2020_vtd_boston.geojson': '4938bb7a73d6ea260175fe3dee217e7fc74afbafb0d097abee718805b4317515',
    'precincts_2017.geojson': '00af69941be217a73b1fc9956b20c1441c9d2ada684d1433f74ee15dd8ae88d6',
}


def read_shapes(filename):
    return {f['properties']['code']: make_valid(shape(f['geometry']))
            for f in json.loads((SOURCE / filename).read_text())['features']}


def geometry_audit():
    for name, digest in FIXTURES.items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == digest, name
    old = read_shapes('ma_2012_2016_boston.geojson')
    new = read_shapes('ma_2020_vtd_boston.geojson')
    project = Transformer.from_crs(4326, 26986, always_xy=True).transform
    city = {f['properties']['WARD_PRECINCT']: transform(project, make_valid(shape(f['geometry'])))
            for f in json.loads((SOURCE / 'precincts_2017.geojson').read_text())['features']}
    audit = {}
    for code, reference in sorted(city.items()):
        comparisons = {}
        for label, shapes in [('2012_2016', old), ('2020', new)]:
            other = shapes.get(code)
            if other is None:
                comparisons[label] = {'present': False, 'minimum_coverage': None, 'passes': False}
            else:
                intersection = reference.intersection(other).area
                coverage = min(intersection / reference.area, intersection / other.area)
                comparisons[label] = {'present': True, 'minimum_coverage': coverage,
                                      'passes': coverage >= THRESHOLD}
        audit[code] = {'comparisons': comparisons,
                       'passes': all(v['passes'] for v in comparisons.values())}
    return audit


def profile_label(center):
    names = [('Walsh', 'Connolly'), ('Walsh', 'Jackson'), ('Wu', 'Essaibi George')]
    return ' → '.join('Close split' if abs(v - 50) <= 5 else names[i][0 if v > 50 else 1]
                      for i, v in enumerate(center))


def models(areas, mode):
    names = sorted(n for n, a in areas.items() if a['complete'] and (mode == 'exploratory' or a['boundary_pass']))
    x = np.array([areas[n]['shares'] for n in names])
    assert len(names) > max(KS)
    tree = linkage(x, method='ward')
    result = {}
    for k in KS:
        raw = cut_tree(tree, n_clusters=k).ravel()
        order = sorted(set(raw), key=lambda g: (x[raw == g, 2].mean(), *x[raw == g].mean(axis=0)))
        remap = {g: i + 1 for i, g in enumerate(order)}
        labels = np.array([remap[g] for g in raw])
        groups = []
        for g in range(1, k + 1):
            center = x[labels == g].mean(axis=0).tolist()
            groups.append({'id': g, 'label': profile_label(center), 'color': PALETTE[g - 1],
                           'size': int(sum(labels == g)), 'centroid': center})
        result[str(k)] = {'groups': groups, 'assignments': dict(zip(names, labels.tolist())),
                          'silhouette': float(silhouette_score(x, labels)),
                          'omit_year_agreement': {str(y): float(adjusted_rand_score(labels, cut_tree(
                              linkage(np.delete(x, i, axis=1), method='ward'), n_clusters=k).ravel()))
                              for i, y in enumerate(YEARS)}}
    return result


def build():
    raw = json.loads((ROOT / 'data/boston_precinct_dots.json').read_text())['elections']
    audit = geometry_audit()
    areas = {}
    for name, r in sorted(raw['2017']['precincts'].items()):
        votes = {str(y): raw[str(y)]['precincts'][name]['votes'] for y in YEARS}
        shares = []
        for y, candidate, opponent in zip(YEARS, CANDIDATES, OPPONENTS):
            v = votes[str(y)]
            denominator = v[candidate] + v[opponent]
            shares.append(100 * v[candidate] / denominator if denominator else None)
        reasons = []
        if None in shares:
            reasons.extend(f'No votes for the two main candidates in {y}.' for y, share in zip(YEARS, shares) if share is None)
        quality = audit[r['code']]
        for label, comparison in quality['comparisons'].items():
            if not comparison['present']:
                reasons.append(f'No matching code in the {label.replace("_", "–")} comparison map.')
            elif not comparison['passes']:
                reasons.append(f'Shape agreement below 99% with the {label.replace("_", "–")} comparison map.')
        areas[name] = {'code': r['code'], 'state': r['state'], 'shares': shares, 'votes': votes,
                       'complete': None not in shares, 'boundary_pass': quality['passes'],
                       'boundary_audit': quality['comparisons'], 'exclusion_reasons': reasons}
    model_sets = {mode: models(areas, mode) for mode in ['screened', 'exploratory']}
    summary = {'total': len(areas), 'complete': sum(a['complete'] for a in areas.values()),
               'boundary_pass': sum(a['boundary_pass'] for a in areas.values()),
               'screened': len(model_sets['screened']['3']['assignments'])}
    result = {'years': YEARS, 'candidates': CANDIDATES, 'opponents': OPPONENTS,
              'threshold': THRESHOLD, 'summary': summary, 'areas': areas, 'models': model_sets,
              'source_sha256': {**{f'data/sources/boston/{f}': h for f, h in FIXTURES.items()},
                                'data/boston_precinct_dots.json': hashlib.sha256((ROOT / 'data/boston_precinct_dots.json').read_bytes()).hexdigest()},
              'method': 'Ward hierarchical clustering of three equally weighted main-candidate vote shares; one precinct, one weight.',
              'caveat': 'Map agreement is a conservative screening rule, not verification of election-day boundaries. Historical sources have mapping differences and may contain corrections. All matching-code histories are provisional. Votes are native reported counts; none are allocated across boundaries.'}
    (ROOT / 'data/boston_history_clusters.json').write_text(json.dumps(result, separators=(',', ':'), allow_nan=False) + '\n')
    print(summary)
    for mode in model_sets:
        print(mode, [(g['size'], g['label'], [round(v, 1) for v in g['centroid']]) for g in model_sets[mode]['3']['groups']])


if __name__ == '__main__':
    build()
