# START HERE

Bismillah, this repo is ready to run locally or publish with GitHub Pages.

## Run The App

Use a local server so the CSV and map boundary files load correctly:

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000/
```

Opening `index.html` directly may fall back to embedded sample data because browsers usually block local `fetch()` calls.

## What The App Does

- Shows a real Victorian district boundary map for the selected election year.
- Colours winners by bloc: Labor, Coalition, Greens, Independent, Other.
- Lets you zoom, pan, hover, and click electorates.
- Lets you search districts and filter by bloc, close margin, or preference-changed result.
- Shows first preferences, preference rounds, progressive totals, and raw rows.
- Keeps exact party names in district details and raw data.

## Data Included

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_summary.csv
data/vic_2022_district_boundaries.geojson
```

Historical state elections use matching year-specific files:

```text
data/vic_2014_preferences_long.csv
data/vic_2014_district_summary.csv
data/vic_2014_district_boundaries.geojson
data/vic_2018_preferences_long.csv
data/vic_2018_district_summary.csv
data/vic_2018_district_boundaries.geojson
```

Federal Victoria options use matching AEC result and boundary files:

```text
data/federal_2025_vic_preferences_long.csv
data/federal_2025_vic_division_boundaries.geojson
data/federal_2022_vic_preferences_long.csv
data/federal_2022_vic_division_boundaries.geojson
data/federal_2019_vic_preferences_long.csv
data/federal_2019_vic_division_boundaries.geojson
data/federal_2016_vic_preferences_long.csv
data/federal_2016_vic_division_boundaries.geojson
```

Use separate boundary files for 2014 and 2018 because the 2022 election used redistributed boundaries. The 2014 and 2018 boundary files are adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au.

The app auto-loads the preference CSV and boundary GeoJSON. Manual CSV upload is under **Data tools**.

## Validate Data

```bash
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

Expected current result:

```text
Rows: 6082
Districts: 87
Missing vote rows: 0
Districts with final rows: 87
```

## Rebuild VEC Data

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape_vec_2022_preferences.py --year 2022 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

On Windows, activation is:

```bat
.venv\Scripts\activate
```

Quick scraper test:

```bash
python scripts/scrape_vec_2022_preferences.py --year 2022 --out data --limit 3 --keep-going
```

## Next Good Improvements

- Add shareable URLs like `?district=Richmond&mode=changed`.
- Add comparison and rankings views.
- Run a GitHub Pages smoke test after publishing.
