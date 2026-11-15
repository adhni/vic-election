#!/usr/bin/env python3
"""Audit individual 2020–2022 House districts, including renumbered candidates.

Use --download once; otherwise read the cached official inputs. No vote totals
are estimated. North Carolina uses its actual 2020 election map because the
Census 116th baseline predates that state's 2020 map.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'tmp/house_boundary_audit'
STEM = 'us_house_2020_2022_boundary_audit'
BEF_URL = 'https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2023/118-congressional-district-bef/cd118.zip'
BAF_BASE = 'https://www2.census.gov/geo/docs/maps-data/data/baf2020/'
NC_URL = 'https://services5.arcgis.com/gRcZqepTaRC6tVZL/ArcGIS/rest/services/NCGA_Congress_2019/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson'
POLYGON_URL = 'https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_cd118_20m.zip'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def cached(name, url, download):
    path = CACHE / name
    if not path.exists():
        if not download:
            raise ValueError(f'Missing cached input: {path}. Run with --download.')
        with urllib.request.urlopen(url, timeout=60) as response:
            body = response.read()
        path.write_bytes(body)
    return path


def block_hash(blocks):
    return digest(('\n'.join(sorted(blocks)) + '\n').encode())


def compare_blocks(old, new):
    """Try every earlier district in-state, rather than assuming identical IDs."""
    result = []
    for number, blocks in sorted(new.items()):
        previous = max(sorted(old), key=lambda n: len(blocks & old[n]) / len(blocks | old[n]))
        earlier = old[previous]
        shared = len(earlier & blocks)
        result.append({
            'number': number, 'previous_number': previous,
            'audit_method': 'census_2020_block_membership',
            'boundary_unchanged_verified': str(blocks == earlier).lower(),
            'previous_block_count': len(earlier), 'current_block_count': len(blocks),
            'shared_block_count': shared, 'added_block_count': len(blocks - earlier),
            'removed_block_count': len(earlier - blocks),
            'block_overlap_pct': f'{100 * shared / len(earlier | blocks):.8f}',
            'previous_block_sha256': block_hash(earlier), 'current_block_sha256': block_hash(blocks),
            'polygon_overlap_pct': '',
        })
    return result


def build(download=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = cached('cd118.zip', BEF_URL, download)
    with zipfile.ZipFile(archive) as z:
        states = {n[:2]: n[3:5] for n in z.namelist() if n.endswith('_CD118.txt')
                  and len(n.split('_')[0]) == 2 and n[:2] not in {'11', '72', '37'}}
    sources = [{'file': archive.name, 'url': BEF_URL, 'sha256': digest(archive.read_bytes())}]

    def state_rows(item):
        fips, abbr = item
        name = f'BlockAssign_ST{fips}_{abbr}.zip'
        url = BAF_BASE + name
        path = cached(name, url, download)
        old, new = defaultdict(set), defaultdict(set)
        with zipfile.ZipFile(path) as z, z.open(f'BlockAssign_ST{fips}_{abbr}_CD.txt') as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle), delimiter='|'):
                if row['DISTRICT'].isdigit():
                    old[row['DISTRICT']].add(row['BLOCKID'])
        with zipfile.ZipFile(archive) as z, z.open(f'{fips}_{abbr}_CD118.txt') as handle:
            for row in csv.reader(io.TextIOWrapper(handle)):
                if len(row) == 2 and row[1].strip().isdigit():
                    new[row[1].strip()].add(row[0].strip())
        rows = []
        for row in compare_blocks(old, new):
            row['constituency_code'] = fips + row.pop('number')
            row['previous_constituency_code'] = fips + row.pop('previous_number')
            rows.append(row)
        return rows, {'file': name, 'url': url, 'sha256': digest(path.read_bytes())}

    output = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for rows, source in pool.map(state_rows, sorted(states.items())):
            output.extend(rows)
            sources.append(source)

    # NC's 116th block assignments do not describe its 2020 election. Use the
    # legislature's enacted-2019/117th map, not the obsolete Census baseline.
    import geopandas as gpd
    nc = cached('nc_2020_official.geojson', NC_URL, download)
    polygons = ROOT / 'tmp/us_house/2022/cb_2022_us_cd118_20m.zip'
    if not polygons.exists():
        polygons = cached('cb_2022_us_cd118_20m.zip', POLYGON_URL, download)
    previous = gpd.read_file(nc).to_crs(5070)
    current = gpd.read_file(f'zip://{polygons.resolve()}').to_crs(5070)
    current = current[current.STATEFP == '37']
    if len(previous) != 13 or len(current) != 14:
        raise ValueError('Unexpected North Carolina plan size')
    for _, row in current.iterrows():
        score, number = max((row.geometry.intersection(before.geometry).area / row.geometry.union(before.geometry).area,
                             int(before.District)) for _, before in previous.iterrows())
        # These are materially different polygons, not uncertain coastline
        # rounding differences. Do not infer exact matches from generalized GIS.
        if score >= .95:
            raise ValueError('NC polygon is too close to classify without a finer boundary audit')
        output.append({
            'constituency_code': row.GEOID, 'previous_constituency_code': f'37{number:02d}',
            'audit_method': 'nc_official_117th_vs_census_118th_polygons',
            'boundary_unchanged_verified': 'false',
            'previous_block_count': '', 'current_block_count': '', 'shared_block_count': '',
            'added_block_count': '', 'removed_block_count': '', 'block_overlap_pct': '',
            'previous_block_sha256': '', 'current_block_sha256': '', 'polygon_overlap_pct': f'{100 * score:.8f}',
        })
    sources.extend([{'file': nc.name, 'url': NC_URL, 'sha256': digest(nc.read_bytes())},
                    {'file': polygons.name, 'url': POLYGON_URL, 'sha256': digest(polygons.read_bytes())}])
    with (ROOT / 'data/us_2022_house_fpp.csv').open() as handle:
        names = {row['constituency_code']: row['district'] for row in csv.DictReader(handle)}
    if len(output) != 435 or {row['constituency_code'] for row in output} != names.keys():
        raise ValueError('Boundary audit must cover exactly the 435 voting districts')
    for row in output:
        row['district'] = names[row['constituency_code']]
    output.sort(key=lambda row: row['constituency_code'])
    fields = ['constituency_code', 'district', 'previous_constituency_code', 'audit_method',
              'boundary_unchanged_verified', 'previous_block_count', 'current_block_count',
              'shared_block_count', 'added_block_count', 'removed_block_count', 'block_overlap_pct',
              'previous_block_sha256', 'current_block_sha256', 'polygon_overlap_pct']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(output)
    content = stream.getvalue().encode()
    metadata = {
        'period': '2020-2022', 'districts_audited': len(output),
        'verified_unchanged_districts': sum(r['boundary_unchanged_verified'] == 'true' for r in output),
        'method': 'Compare identical 2020 Census block sets against every previous district in the state. Changed sets remain changed even when overlap is high. This does not compare votes or estimate vote transfers.',
        'baseline_vintage': 'Census 116th districts match 2020 election districts outside North Carolina. NC uses its legislature\'s enacted-2019 map for the 117th Congress.',
        'north_carolina_method': 'Compare all 13 actual 2020 NC polygons with each of 14 Census 2022 polygons in equal-area EPSG:5070. Best intersection/union overlap is below 95% for each. No generalized-polygon approximate equality is accepted.',
        'split_block_limit': 'Whole-block tabulation equivalence is not a general proof of identical legal boundaries. Census lists one split 118th block in Colorado (07/08); neither district matches the earlier membership set.',
        'references': ['https://www.census.gov/geographies/reference-files/2020/geo/block-assignment-files.html',
                       'https://www.census.gov/geographies/mapping-files/2023/dec/rdo/118-congressional-district-bef.html',
                       'https://www.census.gov/programs-surveys/geography/guidance/geo-areas/congressional-dist.html',
                       'https://www.ncleg.gov/Redistricting'],
        'sources': sources, 'output_sha256': digest(content),
    }
    return content, (json.dumps(metadata, indent=2) + '\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content, metadata = build(args.download)
    for suffix, body in (('.csv', content), ('_metadata.json', metadata)):
        path = ROOT / 'data' / (STEM + suffix)
        if args.check:
            if path.read_bytes() != body:
                raise SystemExit(f'Stale boundary audit: {path}')
        else:
            path.write_bytes(body)
    summary = json.loads(metadata)
    print(f"Audited {summary['districts_audited']} districts individually; {summary['verified_unchanged_districts']} exact unchanged matches.")


if __name__ == '__main__':
    main()
