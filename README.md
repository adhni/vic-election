# Australian Election Preference Explorer

A static HTML data app for exploring Victorian lower-house preference counts from state elections and Australian federal House elections.

The app is map-first and party/bloc-first:

- winner map with Labor, Coalition, Greens, Independent, and Other grouping
- zoomable/pannable seat boundary map for the selected election year
- election-wide rankings for closest seats, largest margins, changed results, and winner transfer gains
- seat search, seat picker, bloc filter, close-seat filter, and preference-changed filter
- first preference, transfer round, progressive chart, and raw row views
- exact party and candidate detail preserved inside each seat

No build step is needed. It is plain HTML/CSS/JavaScript.

## Open the app

Live site:

```text
https://adhni.github.io/vic-election/
```

Serve the folder locally so the CSV and GeoJSON files can auto-load:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

The app auto-loads the selected election:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_boundaries.geojson
```

Victorian state election options use the same naming pattern:

```text
data/vic_2014_preferences_long.csv
data/vic_2014_district_boundaries.geojson
data/vic_2018_preferences_long.csv
data/vic_2018_district_boundaries.geojson
data/vic_2010_preferences_long.csv
data/vic_2010_district_boundaries.geojson
data/vic_2006_preferences_long.csv
data/vic_2006_district_boundaries.geojson
```

Australia-wide federal `2025` and `2022` options use authoritative Australian Electoral Commission House results and matching national AEC federal division ESRI boundary datasets:

```text
data/federal_2025_au_preferences_long.csv
data/federal_2025_au_district_summary.csv
data/federal_2025_au_division_boundaries.geojson
data/federal_2022_au_preferences_long.csv
data/federal_2022_au_district_summary.csv
data/federal_2022_au_division_boundaries.geojson
```

Victoria-only federal options remain available for `2025`, `2022`, `2019`, `2016`, `2013`, `2010`, and `2007`:

```text
data/federal_2025_vic_preferences_long.csv
data/federal_2025_vic_district_summary.csv
data/federal_2025_vic_division_boundaries.geojson
data/federal_2022_vic_preferences_long.csv
data/federal_2022_vic_district_summary.csv
data/federal_2022_vic_division_boundaries.geojson
data/federal_2019_vic_preferences_long.csv
data/federal_2019_vic_district_summary.csv
data/federal_2019_vic_division_boundaries.geojson
data/federal_2016_vic_preferences_long.csv
data/federal_2016_vic_district_summary.csv
data/federal_2016_vic_division_boundaries.geojson
data/federal_2013_vic_preferences_long.csv
data/federal_2013_vic_district_summary.csv
data/federal_2013_vic_division_boundaries.geojson
data/federal_2010_vic_preferences_long.csv
data/federal_2010_vic_district_summary.csv
data/federal_2010_vic_division_boundaries.geojson
data/federal_2007_vic_preferences_long.csv
data/federal_2007_vic_district_summary.csv
data/federal_2007_vic_division_boundaries.geojson
```

If the generated CSV is unavailable, embedded sample districts are used. Manual CSV upload is available under **Data tools**.

The rankings panel is election-scoped rather than filter-scoped. It updates when the election selector changes, and clicking any ranking row opens that district or division in the existing detail view.

## Data Files

```text
data/vic_2022_preferences_long.csv        # long preference-count rows, 87 districts
data/vic_2022_district_summary.csv        # district-level result summary
data/vic_2022_district_boundaries.geojson # 2022 district boundary polygons
data/vic_2018_preferences_long.csv        # 2018 long preference-count rows
data/vic_2018_district_summary.csv        # 2018 district-level result summary
data/vic_2018_district_boundaries.geojson # 2018 district boundary polygons
data/vic_2014_preferences_long.csv        # 2014 long preference-count rows
data/vic_2014_district_summary.csv        # 2014 district-level result summary
data/vic_2014_district_boundaries.geojson # 2014 district boundary polygons
data/vic_2010_preferences_long.csv        # 2010 long preference-count rows
data/vic_2010_district_summary.csv        # 2010 district-level result summary
data/vic_2010_district_boundaries.geojson # 2001 state assembly district boundary polygons
data/vic_2006_preferences_long.csv        # 2006 long preference-count rows
data/vic_2006_district_summary.csv        # 2006 district-level result summary
data/vic_2006_district_boundaries.geojson # 2001 state assembly district boundary polygons
data/federal_2025_au_preferences_long.csv         # AEC 2025 federal House preference rows, Australia-wide
data/federal_2025_au_district_summary.csv         # AEC 2025 federal House division summary, Australia-wide
data/federal_2025_au_division_boundaries.geojson  # AEC March 2025 national federal division polygons
data/federal_2025_vic_preferences_long.csv        # AEC 2025 federal House preference rows, Victoria only
data/federal_2025_vic_district_summary.csv        # AEC 2025 federal House division summary, Victoria only
data/federal_2025_vic_division_boundaries.geojson # AEC October 2024 federal division polygons, Victoria
data/federal_2022_au_preferences_long.csv         # AEC 2022 federal House preference rows, Australia-wide
data/federal_2022_au_district_summary.csv         # AEC 2022 federal House division summary, Australia-wide
data/federal_2022_au_division_boundaries.geojson  # AEC 2021 national federal division polygons used at 2022 election
data/federal_2022_vic_preferences_long.csv        # AEC 2022 federal House preference rows, Victoria only
data/federal_2022_vic_district_summary.csv        # AEC 2022 federal House division summary, Victoria only
data/federal_2022_vic_division_boundaries.geojson # AEC July 2021 federal division polygons, Victoria
data/federal_2019_vic_preferences_long.csv        # AEC 2019 federal House preference rows, Victoria only
data/federal_2019_vic_district_summary.csv        # AEC 2019 federal House division summary, Victoria only
data/federal_2019_vic_division_boundaries.geojson # AEC July 2018 federal division polygons, Victoria
data/federal_2016_vic_preferences_long.csv        # AEC 2016 federal House preference rows, Victoria only
data/federal_2016_vic_district_summary.csv        # AEC 2016 federal House division summary, Victoria only
data/federal_2016_vic_division_boundaries.geojson # AEC December 2010 federal division polygons, Victoria
data/federal_2013_vic_preferences_long.csv        # AEC 2013 federal House preference rows, Victoria only
data/federal_2013_vic_district_summary.csv        # AEC 2013 federal House division summary, Victoria only
data/federal_2013_vic_division_boundaries.geojson # AEC December 2010 federal division polygons, Victoria
data/federal_2010_vic_preferences_long.csv        # AEC 2010 federal House preference rows, Victoria only
data/federal_2010_vic_district_summary.csv        # AEC 2010 federal House division summary, Victoria only
data/federal_2010_vic_division_boundaries.geojson # AEC 2010 national federal division polygons, Victoria features
data/federal_2007_vic_preferences_long.csv        # AEC 2007 federal House preference rows, Victoria only
data/federal_2007_vic_district_summary.csv        # AEC 2007 federal House division summary, Victoria only
data/federal_2007_vic_division_boundaries.geojson # AEC 2010 national federal division polygons, Victoria features
data/sample_melbourne_preferences_long.csv
```

Boundary data is election-year-specific. The 2022 election used boundaries from the 2020-2021 redivision, so earlier elections such as 2006, 2010, 2014, and 2018 need their own boundary file.

2014 and 2018 boundary data is adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. It is licensed under Creative Commons Attribution 4.0. These boundaries come from the 2012-2013 state redivision, which came into operation for the 2014 State election and remained in place until the writ for the 2022 State election.

2006 and 2010 boundary data is adapted from the Victorian Government / VEC Vicmap Admin State Assembly Polygon 2001 WFS dataset. These 88 Legislative Assembly districts are the pre-2014 boundaries used for the 2006 and 2010 State elections.

## Folder Structure

```text
.
├── index.html
├── app/
│   └── index.html
├── data/
├── scripts/
│   ├── build_aec_federal.py
│   ├── scrape_vec_2022_preferences.py
│   ├── validate_federal.py
│   └── validate_vec_csv.py
├── docs/
│   └── data_notes.md
├── .github/workflows/
│   └── scrape-vec-data.yml
├── requirements.txt
├── START_HERE.md
└── codex_prompt.md
```

`index.html` and `app/index.html` are kept in sync.

## Election Definitions

Election options are driven by the in-app `electionDefinitions` list in `index.html` and `app/index.html`. Each entry defines the key, label, election type, jurisdiction, year, source, preference CSV, and boundary GeoJSON. The election selector is generated from this list.

When adding an election, add the data files, add one election definition to both HTML entry points, then run:

```bash
python scripts/smoke_static_app.py
```

The smoke test reads `electionDefinitions` from the HTML files and validates that the configured CSV and boundary files exist, load, and match by district name.
It also checks that the compact rankings UI markers are present in both HTML entry points.

## CSV Format

The app expects long CSV rows:

```csv
district,elected_member,elected_party,enrolment,formal_votes,informal_votes,total_votes,turnout_pct,majority,round_number,row_type,excluded_candidate,excluded_party,candidate,candidate_party,votes
```

`row_type` should be one of:

```text
first
transfer
progressive
final
```

## Run The Scraper

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape_vec_2022_preferences.py --year 2022 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

For historical state elections:

```bash
python scripts/scrape_vec_2022_preferences.py --year 2014 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2014_preferences_long.csv
python scripts/scrape_vec_2022_preferences.py --year 2018 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2018_preferences_long.csv
python scripts/scrape_vec_2022_preferences.py --year 2010 --out data --keep-going
python scripts/build_vic_2010_boundaries.py --out data/vic_2010_district_boundaries.geojson
python scripts/validate_state_vic.py --csv data/vic_2010_preferences_long.csv --boundaries data/vic_2010_district_boundaries.geojson --expected-districts 88
python scripts/scrape_vec_2022_preferences.py --year 2006 --out data --keep-going
python scripts/build_vic_2010_boundaries.py --year 2006 --out data/vic_2006_district_boundaries.geojson
python scripts/validate_state_vic.py --csv data/vic_2006_preferences_long.csv --boundaries data/vic_2006_district_boundaries.geojson --expected-districts 88
```

For the 2025 Australia-wide federal dataset, download the official AEC event `31496` files into `tmp/aec_2025_au`, unzip the national boundary ZIP there, then run:

```bash
python3 scripts/build_aec_federal.py --year 2025 --event-id 31496 --scope au --raw-dir tmp/aec_2025_au --out data --shp tmp/aec_2025_au/AUS_ELB_region.shp --gis-source https://www.aec.gov.au/Electorates/files/2025/AUS-March-2025-esri.zip
python3 scripts/validate_vec_csv.py data/federal_2025_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2025_au_preferences_long.csv --boundaries data/federal_2025_au_division_boundaries.geojson --aec-dop tmp/aec_2025_au/HouseDopByDivisionDownload-31496.csv --expected-divisions 150 --scope au
```

For the 2025 federal Victoria dataset, download the official AEC event `31496` files into `tmp/aec_2025_vic`, unzip the boundary ZIP there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2025 --event-id 31496 --raw-dir tmp/aec_2025_vic --out data --shp tmp/aec_2025_vic/Vic-october-2024-esri/E_VIC24_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/Vic-october-2024-esri.zip
python3 scripts/validate_vec_csv.py data/federal_2025_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2025_vic_preferences_long.csv --boundaries data/federal_2025_vic_division_boundaries.geojson --aec-dop tmp/aec_2025_vic/HouseDopByDivisionDownload-31496.csv --expected-divisions 38 --scope vic
```

For the 2022 Australia-wide federal dataset, download the official AEC files for event `27966` into `tmp/aec_2022_au`, unzip the national boundary ZIP there, then run:

```bash
python3 scripts/build_aec_federal.py --year 2022 --event-id 27966 --scope au --raw-dir tmp/aec_2022_au --out data --shp tmp/aec_2022_au/2021_ELB_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/2021-Cwlth_electoral_boundaries_ESRI.zip
python3 scripts/validate_vec_csv.py data/federal_2022_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2022_au_preferences_long.csv --boundaries data/federal_2022_au_division_boundaries.geojson --aec-dop tmp/aec_2022_au/HouseDopByDivisionDownload-27966.csv --expected-divisions 151 --scope au
```

For the 2022 federal Victoria dataset, download the official AEC files for event `27966` into `tmp/aec_2022_vic`, unzip `vic-july-2021-esri.zip` there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2022 --event-id 27966 --raw-dir tmp/aec_2022_vic --out data --shp tmp/aec_2022_vic/vic-july-2021-esri/E_VIC21_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/vic-july-2021-esri.zip
python3 scripts/validate_vec_csv.py data/federal_2022_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2022_vic_preferences_long.csv --boundaries data/federal_2022_vic_division_boundaries.geojson --aec-dop tmp/aec_2022_vic/HouseDopByDivisionDownload-27966.csv --expected-divisions 39 --scope vic
```

For the 2019 federal Victoria dataset, download the official AEC files for event `24310` into `tmp/aec_2019_vic`, unzip `vic-july-2018-esri.zip` there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2019 --event-id 24310 --raw-dir tmp/aec_2019_vic --out data --shp tmp/aec_2019_vic/vic-july-2018-esri/E_AUGFN3_region.shp --gis-source https://emailfooter.aec.gov.au/Electorates/gis/files/vic-july-2018-esri.zip
python3 scripts/validate_vec_csv.py data/federal_2019_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2019_vic_preferences_long.csv --boundaries data/federal_2019_vic_division_boundaries.geojson --aec-dop tmp/aec_2019_vic/HouseDopByDivisionDownload-24310.csv --expected-divisions 38 --scope vic
```

For the 2016 federal Victoria dataset, download the official AEC files for event `20499` into `tmp/aec_2016_vic`, unzip `vic-esri-24122010.zip` there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2016 --event-id 20499 --raw-dir tmp/aec_2016_vic --out data --shp "tmp/aec_2016_vic/vic-esri-24122010/vic 24122010.shp" --prj tmp/aec_2016_vic/vic-esri-24122010/vic24122010.prj --gis-source https://www.aec.gov.au/Electorates/gis/files/vic-esri-24122010.zip
python3 scripts/validate_vec_csv.py data/federal_2016_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2016_vic_preferences_long.csv --boundaries data/federal_2016_vic_division_boundaries.geojson --aec-dop tmp/aec_2016_vic/HouseDopByDivisionDownload-20499.csv --expected-divisions 37 --scope vic
```

For the 2013 federal Victoria dataset, download the official AEC files for event `17496` into `tmp/aec_2013_vic`, use the AEC `vic-esri-24122010.zip` boundary shapefile, then run:

```bash
python3 scripts/build_aec_vic.py --year 2013 --event-id 17496 --raw-dir tmp/aec_2013_vic --out data --shp "tmp/aec_2016_vic/vic-esri-24122010/vic 24122010.shp" --prj tmp/aec_2016_vic/vic-esri-24122010/vic24122010.prj --gis-source https://www.aec.gov.au/Electorates/gis/files/vic-esri-24122010.zip
python3 scripts/validate_vec_csv.py data/federal_2013_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2013_vic_preferences_long.csv --boundaries data/federal_2013_vic_division_boundaries.geojson --aec-dop tmp/aec_2013_vic/HouseDopByDivisionDownload-17496.csv --expected-divisions 37 --scope vic
```

For the 2010 federal Victoria dataset, download the official AEC files for event `15508` into `tmp/aec_2010_vic`, unzip the AEC `national-esri-2010.zip` boundary shapefile, then run:

```bash
python3 scripts/build_aec_vic.py --year 2010 --event-id 15508 --raw-dir tmp/aec_2010_vic --out data --shp tmp/aec_2010_vic/national-esri-2010/COM_ELB_2010_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/national-esri-2010.zip
python3 scripts/validate_vec_csv.py data/federal_2010_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2010_vic_preferences_long.csv --boundaries data/federal_2010_vic_division_boundaries.geojson --aec-dop tmp/aec_2010_vic/HouseDopByDivisionDownload-15508.csv --expected-divisions 37 --scope vic
```

For the 2007 federal Victoria dataset, download the official AEC files for event `13745` into `tmp/aec_2007_vic`, unzip the AEC `national-esri-2010.zip` boundary shapefile there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2007 --event-id 13745 --raw-dir tmp/aec_2007_vic --out data --shp tmp/aec_2007_vic/national-esri-2010/COM_ELB_2010_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/national-esri-2010.zip
python3 scripts/validate_vec_csv.py data/federal_2007_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2007_vic_preferences_long.csv --boundaries data/federal_2007_vic_division_boundaries.geojson --aec-dop tmp/aec_2007_vic/HouseDopByDivisionDownload-13745.csv --expected-divisions 37 --scope vic
```

The VEC scraper writes:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_summary.csv
```

If any districts fail, the scraper also writes:

```text
data/vic_2022_scrape_errors.csv
```

## Current Status

The app currently validates against:

- 6,082 preference rows
- 87 districts
- 87 boundary features
- no missing vote rows

The federal 2025 Victoria option validates against:

- 2,056 preference rows
- 38 federal divisions
- 38 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2022 Victoria option validates against:

- 2,783 preference rows
- 39 federal divisions
- 39 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2019 Victoria option validates against:

- 1,804 preference rows
- 38 federal divisions
- 38 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2016 Victoria option validates against:

- 1,921 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2013 Victoria option validates against:

- 3,303 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2010 Victoria option validates against:

- 1,008 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2007 Victoria option validates against:

- 1,570 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The Victorian state 2010 option validates against:

- 2,002 preference rows
- 88 Legislative Assembly districts
- 88 boundary features
- matching result and boundary names
- no large boundary overlaps or internal gaps

The Victorian state 2006 option validates against:

- 1,685 preference rows
- 88 Legislative Assembly districts
- 88 boundary features
- matching result and boundary names
- no large boundary overlaps or internal gaps

The VEC 2006 archive has 49 districts with full distribution pages and 39 districts with result-page-only tables. Gippsland East follows the archived HTML standard distribution; the later VEC report describes an extra statistical distribution.

Best next improvements:

- visual regression screenshot smoke test after each release
- scraper fixture tests for one current VEC page and one historical VEC page
