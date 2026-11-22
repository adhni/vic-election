"""Validate reference-map audit provenance, vote ledger and directional scores."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'data/nyc_reference_map_comparison.json').read_text())
records=json.loads((ROOT/'data/nyc_precinct_dots.json').read_text())['elections']
for path,digest in d['source_sha256'].items():
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert len(d['directional_comparisons'])==6
for key,r in d['directional_comparisons'].items():
    source,target=map(int,key.split('-to-'))
    assert (r['source_year'],r['target_year'])==(source,target)
    votes=records[str(source)]['precincts']
    assert r['source_areas']==len(votes)
    assert r['total_recorded_votes']==sum(x['total'] for x in votes.values())
    assert r['total_two_side_votes']==sum(x['democratic']+x['opposition'] for x in votes.values())
    sensitivity=r['containment_sensitivity']
    assert [x['minimum_dominant_target_fraction'] for x in sensitivity]==[.95,.99,.999]
    counts=[x['source_areas_not_contained_to_tolerance'] for x in sensitivity]
    assert counts==sorted(counts)
    amounts=[x['recorded_votes_in_those_areas'] for x in sensitivity]
    assert amounts==sorted(amounts)
    for x in sensitivity:
        assert abs(x['pct_recorded_votes_in_those_areas']-100*x['recorded_votes_in_those_areas']/r['total_recorded_votes'])<1e-10
        assert 0<=x['pct_recorded_votes_in_those_areas']<=100
    for x in r['largest_vote_areas_without_99pct_dominant_target']:
        assert x['votes']==votes[x['name']]['total'] and x['largest_target_fraction']<.99
for target,r in d['reference_comparisons'].items():
    conversions=[d['directional_comparisons'][f'{source}-to-{target}'] for source in records if source!=target]
    for index,x in enumerate(r['containment_sensitivity']):
        expected=sum(c['containment_sensitivity'][index]['pct_recorded_votes_in_those_areas'] for c in conversions)
        assert abs(x['mean_pct_votes_in_noncontained_areas_across_all_three_elections']-expected/3)<1e-10
        assert abs(x['mean_pct_votes_in_noncontained_areas_among_converted_elections']-expected/2)<1e-10
# No source geography or vote ledger was mutated by this audit.
print('PASS six directional ledgers, source checksums, tolerance sensitivity and equal-election comparisons')
