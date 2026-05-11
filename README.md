# Victoria 2022 Preference Explorer

A static HTML data app for exploring Victorian Legislative Assembly preference counts from the 2022 state election.

The app is map-first and party/bloc-first:

- winner map with Labor, Coalition, Greens, Independent, and Other grouping
- zoomable/pannable 2022 district boundary map
- district search, district picker, bloc filter, close-seat filter, and preference-changed filter
- first preference, transfer round, progressive chart, and raw row views
- exact party and candidate detail preserved inside each district

No build step is needed. It is plain HTML/CSS/JavaScript.

## Open the app

Serve the folder locally so the CSV and GeoJSON files can auto-load:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

The app auto-loads:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_boundaries.geojson
```

If the generated CSV is unavailable, embedded sample districts are used. Manual CSV upload is available under **Data tools**.

## Data Files

```text
data/vic_2022_preferences_long.csv        # long preference-count rows, 87 districts
data/vic_2022_district_summary.csv        # district-level result summary
data/vic_2022_district_boundaries.geojson # 2022 district boundary polygons
data/sample_melbourne_preferences_long.csv
```

Boundary data is from Wikimedia Commons map data derived from Electoral Boundaries Commission Victoria 2022 boundaries, licensed CC-BY-4.0.

## Folder Structure

```text
.
├── index.html
├── app/
│   └── index.html
├── data/
├── scripts/
│   ├── scrape_vec_2022_preferences.py
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

python scripts/scrape_vec_2022_preferences.py --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

This writes:

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

Best next improvements:

- URL sharing for selected district and map mode
- compact statewide summary strip
- GitHub Pages smoke test after each release
