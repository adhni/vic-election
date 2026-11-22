"""Extract existing NYC returns for a two-side precinct dot view."""
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SIDES = {2017: ('Bill de Blasio', ['Nicole Malliotakis']), 2021: ('Eric Adams', ['Curtis Sliwa']), 2025: ('Zohran Mamdani', ['Andrew Cuomo', 'Curtis Sliwa'])}
result = {'elections': {}}
for year, (dem, opposition) in SIDES.items():
    records = {}
    for row in csv.DictReader((ROOT / f'data/nyc_{year}_mayor_ed_fpp.csv').open()):
        record = records.setdefault(row['district'], {'state': row['electorate_type'], 'code': row['constituency_code'], 'votes': {}, 'total': int(row['formal_votes']), 'ballots': int(row['total_votes']), 'unrecorded': int(row['informal_votes']), 'combined_from': row['combined_from']})
        record['votes'][row['candidate']] = int(row['votes'])
    for record in records.values():
        assert sum(record['votes'].values()) == record['total']
        record['democratic'] = record['votes'][dem]
        record['opposition'] = sum(record['votes'][name] for name in opposition)
        record['other'] = record['total'] - record['democratic'] - record['opposition']
        denominator = record['democratic'] + record['opposition']
        record['share'] = 100 * record['democratic'] / denominator if denominator else None
    geo = json.loads((ROOT / f'data/nyc_{year}_mayor_ed_boundaries.geojson').read_text())
    assert set(records) == {f['properties']['district'] for f in geo['features']}
    result['elections'][str(year)] = {'democratic_candidate': dem, 'opposition_candidates': opposition, 'precincts': records}
path = ROOT / 'data/nyc_precinct_dots.json'
path.write_text(json.dumps(result, separators=(',', ':')) + '\n')
print('Built NYC precinct dots:', {year: len(e['precincts']) for year, e in result['elections'].items()})
