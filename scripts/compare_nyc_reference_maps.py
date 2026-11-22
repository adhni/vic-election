"""Compare fixed NYC reference maps without allocating any election votes.

Measures geometry-based split burden in both directions, weighted by actual
source vote totals. Geometry fractions are not measured vote fractions.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT=Path(__file__).resolve().parents[1]
YEARS=[2017,2021,2025]
THRESHOLDS=[.95,.99,.999]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_path=ROOT/'data/nyc_precinct_dots.json'
    records=json.loads(source_path.read_text())['elections']
    hashes={str(source_path.relative_to(ROOT)):digest(source_path)}
    names={};geos={};incomplete={};meta={}
    project=Transformer.from_crs(4326,32618,always_xy=True).transform
    for year in YEARS:
        path=ROOT/f'data/nyc_{year}_mayor_ed_boundaries.geojson'
        hashes[str(path.relative_to(ROOT))]=digest(path)
        metadata_path=ROOT/f'data/nyc_{year}_mayor_metadata.json'
        hashes[str(metadata_path.relative_to(ROOT))]=digest(metadata_path)
        meta[year]=json.loads(metadata_path.read_text())
        missing=set(map(str,meta[year]['combined_ed_without_polygon']))
        incomplete[year]={name for name,r in records[str(year)]['precincts'].items() if missing.intersection(r['combined_from'].split(';'))}
        features=json.loads(path.read_text())['features']
        names[year]=[f['properties']['district'] for f in features]
        geos[year]=[transform(project,shape(f['geometry'])) for f in features]
        assert set(names[year])==set(records[str(year)]['precincts'])
        assert all(g.is_valid and g.area>0 for g in geos[year])
        print('Loaded',year,len(features),flush=True)
    pair_edges={}
    for a,b in [(2017,2021),(2017,2025),(2021,2025)]:
        # Use cached intersections only when every source checksum matches.
        cache=ROOT/f'tmp/nyc-reference-overlap-{a}-{b}.json'
        cache_key={k:v for k,v in hashes.items() if 'boundaries' in k and (str(a) in k or str(b) in k)}
        cached=json.loads(cache.read_text()) if cache.exists() else None
        if cached and cached['source_sha256']==cache_key: edges=cached['edges']
        else:
            tree=STRtree(geos[b]);edges=[]
            for i,g in enumerate(geos[a]):
                for j in tree.query(g,predicate='intersects'):
                    area=g.intersection(geos[b][j]).area
                    if area>.01: edges.append([i,int(j),area])
            cache.write_text(json.dumps({'source_sha256':cache_key,'edges':edges},separators=(',',':')))
        pair_edges[a,b]=edges
        print('Intersected',a,b,len(edges),flush=True)
    directions={}
    for source in YEARS:
      for target in YEARS:
        if source==target: continue
        a,b=sorted([source,target]);edges=pair_edges[a,b]
        intersections=[[] for _ in names[source]]
        for i,j,area in edges:
            si,tj=(i,j) if source==a else (j,i)
            intersections[si].append((tj,area))
        rows=[]
        for i,name in enumerate(names[source]):
            record=records[str(source)]['precincts'][name];area=geos[source][i].area
            hits=intersections[i];best=max(hits,key=lambda x:x[1]) if hits else None
            # Sum gives an explicit upper bound on coverage if targets overlap.
            summed=sum(v for _,v in hits)/area
            largest=min(1,best[1]/area) if best else 0
            incomplete_target=any(names[target][j] in incomplete[target] and v/area>=.01 for j,v in hits)
            rows.append({'name':name,'votes':record['total'],'two_side_votes':record['democratic']+record['opposition'],
              'largest_target_fraction':largest,'summed_coverage_fraction':summed,
              'source_geometry_incomplete':name in incomplete[source],
              'touches_incomplete_target_at_1pct':incomplete_target,
              'targets_at_least_1pct':sum(v/area>=.01 for _,v in hits),
              'best_target':names[target][best[0]] if best else None})
        total_votes=sum(r['votes'] for r in rows);total_two=sum(r['two_side_votes'] for r in rows)
        measurements=[]
        for cutoff in THRESHOLDS:
            split=[r for r in rows if r['largest_target_fraction']<cutoff]
            measurements.append({'minimum_dominant_target_fraction':cutoff,
              'source_areas_not_contained_to_tolerance':len(split),
              'recorded_votes_in_those_areas':sum(r['votes'] for r in split),
              'pct_recorded_votes_in_those_areas':100*sum(r['votes'] for r in split)/total_votes,
              'pct_two_side_votes_in_those_areas':100*sum(r['two_side_votes'] for r in split)/total_two})
        clean=[r for r in rows if not r['source_geometry_incomplete'] and not r['touches_incomplete_target_at_1pct']]
        cv=sum(r['votes'] for r in clean)
        directions[f'{source}-to-{target}']={
          'source_year':source,'target_year':target,'source_areas':len(rows),'total_recorded_votes':total_votes,'total_two_side_votes':total_two,
          'containment_sensitivity':measurements,
          'areas_intersecting_multiple_targets_at_least_1pct':sum(r['targets_at_least_1pct']>=2 for r in rows),
          'pct_votes_in_multiple_target_areas_at_1pct':100*sum(r['votes'] for r in rows if r['targets_at_least_1pct']>=2)/total_votes,
          'pct_votes_in_areas_with_upper_bound_coverage_below_99pct':100*sum(r['votes'] for r in rows if r['summed_coverage_fraction']<.99)/total_votes,
          'pct_votes_in_source_geometries_known_incomplete':100*sum(r['votes'] for r in rows if r['source_geometry_incomplete'])/total_votes,
          'pct_votes_in_sources_touching_incomplete_targets':100*sum(r['votes'] for r in rows if r['touches_incomplete_target_at_1pct'])/total_votes,
          'clean_subset_areas':len(clean),'pct_votes_in_clean_subset':100*cv/total_votes,
          'clean_subset_pct_votes_in_noncontained_areas_at_99pct':100*sum(r['votes'] for r in clean if r['largest_target_fraction']<.99)/cv if cv else None,
          'uniform_area_outside_dominant_target_proxy_pct':100*sum(r['votes']*(1-r['largest_target_fraction']) for r in rows)/total_votes,
          'largest_vote_areas_without_99pct_dominant_target':sorted((r for r in rows if r['largest_target_fraction']<.99),key=lambda r:r['votes'],reverse=True)[:5]}
        print('Measured',source,'to',target,flush=True)
    # Equal-election averages avoid making 2025 count twice because turnout was higher.
    references={}
    for target in YEARS:
        other=[directions[f'{source}-to-{target}'] for source in YEARS if source!=target]
        bycutoff=[]
        for i,cutoff in enumerate(THRESHOLDS):
            percentages=[d['containment_sensitivity'][i]['pct_recorded_votes_in_those_areas'] for d in other]
            bycutoff.append({'minimum_dominant_target_fraction':cutoff,
              'mean_pct_votes_in_noncontained_areas_among_converted_elections':sum(percentages)/2,
              'mean_pct_votes_in_noncontained_areas_across_all_three_elections':sum(percentages)/3})
        references[str(target)]={'target_areas':len(names[target]),'source_years_requiring_conversion':[y for y in YEARS if y!=target],
          'containment_sensitivity':bycutoff,
          'mean_uniform_area_outside_dominant_proxy_across_all_three_pct':sum(d['uniform_area_outside_dominant_target_proxy_pct'] for d in other)/3}
    result={'purpose':'Reference-map inspection only. No votes allocated and no multi-year clusters built.',
      'source_sha256':hashes,'projection':'EPSG:32618','numerical_overlap_floor_m2':.01,
      'metric_meaning':'Votes in a source area that lacks one sufficiently dominant target measure split exposure, not how many votes actually move or allocation accuracy.',
      'area_proxy_limit':'The outside-dominant-target proxy assumes votes uniformly distributed within each source geometry. It is not measured voting uncertainty or validated vote allocation.',
      'coverage_limit':'Coverage sums intersection areas and can overstate coverage when target polygons overlap; below-99pct coverage is therefore a conservative gap flag.',
      'incomplete_target_rule':'A source is flagged if at least 1% of its mapped area intersects a target with known missing combined-component geometry.',
      'unmapped_limit':'This audit uses mapped reporting areas only; it does not recover missing source geometry or unmatched components.',
      'directional_comparisons':directions,'reference_comparisons':references}
    path=ROOT/'data/nyc_reference_map_comparison.json';path.write_text(json.dumps(result,indent=2)+'\n')
    for year,r in references.items():
        print(year, 'all-three split exposure at 99%:',r['containment_sensitivity'][1]['mean_pct_votes_in_noncontained_areas_across_all_three_elections'],flush=True)
    print(path.relative_to(ROOT))

if __name__=='__main__': main()
