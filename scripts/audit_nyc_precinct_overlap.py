"""Audit whether existing mapped NYC returns can form exact shared areas.

This is a diagnostic, not a crosswalk. Overlap thresholds intentionally test
sensitivity; ignoring intersections would introduce an approximation.
"""
import hashlib
import json
from pathlib import Path
from collections import Counter
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT=Path(__file__).resolve().parents[1]
YEARS=[2017,2021,2025]

def main():
    project=Transformer.from_crs(4326,32618,always_xy=True).transform
    records_path=ROOT/'data/nyc_precinct_dots.json'
    records=json.loads(records_path.read_text())['elections']
    geometries={};names={};hashes={str(records_path.relative_to(ROOT)):hashlib.sha256(records_path.read_bytes()).hexdigest()}
    for year in YEARS:
        path=ROOT/f'data/nyc_{year}_mayor_ed_boundaries.geojson'
        features=json.loads(path.read_text())['features']
        names[year]=[f['properties']['district'] for f in features]
        geometries[year]=np.array([transform(project,shape(f['geometry'])) for f in features],dtype=object)
        assert all(g.is_valid and not g.is_empty and g.area>0 for g in geometries[year])
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    offsets={year:sum(len(names[y]) for y in YEARS if y<year) for year in YEARS}
    count=sum(map(len,names.values()))
    edges=[];pairs={}
    for a,b in [(2017,2021),(2017,2025),(2021,2025)]:
        tree=STRtree(geometries[b]); local=[]; unmatched=[]
        for i,g in enumerate(geometries[a]):
            hits=tree.query(g,predicate='intersects')
            areas=[]
            for j in hits:
                area=g.intersection(geometries[b][j]).area
                if area<=.01: continue
                fraction=area/min(g.area,geometries[b][j].area)
                local.append((int(i),int(j),float(area),float(fraction)))
                edges.append((offsets[a]+i,offsets[b]+int(j),float(area),float(fraction)))
                areas.append((area,int(j)))
            if not areas: unmatched.append(names[a][i])
        # Same identifier is not proof of the same geographic area.
        byname={n:j for j,n in enumerate(names[b])}
        repeated=[]
        for i,n in enumerate(names[a]):
            if n in byname:
                g,h=geometries[a][i],geometries[b][byname[n]]
                repeated.append(g.intersection(h).area/g.union(h).area)
        pairs[f'{a}-{b}']={'intersections_over_0_01_m2':len(local),'unmatched_source_areas':unmatched,
          'same_name_count':len(repeated),'same_name_overlap_over_99pct':sum(v>=.99 for v in repeated),
          'same_name_median_intersection_over_union':float(np.median(repeated))}
        print(f'Compared {a}–{b}: {len(local):,} intersections',flush=True)
    # A source reporting area cannot be split without estimating its votes.
    # Therefore any shared grouping must contain whole connected components
    # of this overlap graph. Thresholds beyond numerical noise are diagnostic.
    thresholds=[]
    for minimum_fraction in [0,.001,.01,.05]:
        parent=list(range(count));size=[1]*count
        def find(x):
            while x!=parent[x]: parent[x]=parent[parent[x]];x=parent[x]
            return x
        for i,j,area,fraction in edges:
            if fraction<minimum_fraction: continue
            x,y=find(i),find(j)
            if x!=y:
                if size[x]<size[y]: x,y=y,x
                parent[y]=x;size[x]+=size[y]
        components={}
        for year in YEARS:
            for i,n in enumerate(names[year]):
                c=components.setdefault(find(offsets[year]+i),{'areas_by_year':{str(y):0 for y in YEARS},'votes_by_year':{str(y):0 for y in YEARS},'boroughs':set()})
                r=records[str(year)]['precincts'][n]
                c['areas_by_year'][str(year)]+=1;c['votes_by_year'][str(year)]+=r['total'];c['boroughs'].add(r['state'])
        complete=[c for c in components.values() if all(c['areas_by_year'].values())]
        biggest=sorted(complete,key=lambda c:sum(c['votes_by_year'].values()),reverse=True)[:10]
        thresholds.append({'minimum_overlap_fraction_of_smaller_polygon':minimum_fraction,'components_total':len(components),'components_with_all_three_years':len(complete),
          'largest_components':[dict(c,boroughs=sorted(c['boroughs'])) for c in biggest],
          'ignored_intersections':sum(f<minimum_fraction for _,_,_,f in edges),
          'ignored_overlap_area_m2':sum(a for _,_,a,f in edges if f<minimum_fraction)})
        print(f'Threshold {minimum_fraction}: {len(complete)} components covering all three years',flush=True)
    result={'purpose':'Diagnostic only; not a vote allocation or verified exact crosswalk.',
      'projection':'EPSG:32618 (metres)','numerical_overlap_floor_m2':.01,'source_sha256':hashes,
      'mapped_areas':{str(y):len(names[y]) for y in YEARS},'pairwise':pairs,'connected_components':thresholds,
      'known_source_limits':['Historical extracts have unavailable combined-component polygons, so some reporting geometries do not cover the entire vote reporting area.',
        'Historical boundaries are archive snapshots; the 2017 release identifier is unrecorded.',
        'Displayed maps are simplified and different releases have differing shorelines. Geometric intersection alone cannot establish an exact electoral crosswalk.']}
    path=ROOT/'data/nyc_precinct_overlap_audit.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(path.relative_to(ROOT))
if __name__=='__main__': main()
