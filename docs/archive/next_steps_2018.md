# Next Steps: 2018 Election Support

Archived note. This was the working checklist for the 2018 support branch and is no longer the active roadmap. See `docs/next_steps.md` for the current state/federal-first plan.

This branch has the first working 2018 pass:

- year selector in the app for `2022` and `2018`
- 2018 preference CSV and district summary CSV
- 2018 district boundary GeoJSON
- scraper support for VEC historical-results pages

## 1. Browser Smoke Test

Run the app locally:

```bash
python3 -m http.server 8000
```

Check:

- `http://localhost:8000/` loads 2022 by default
- `http://localhost:8000/?year=2018` loads 2018
- switching between years reloads both data and boundaries
- map click, hover, pan, and zoom still work
- district search and bloc filters work for both years
- no stale 2022 district remains selected after switching to 2018

## 2. Data Quality Review

Validate both CSVs:

```bash
./.venv/bin/python scripts/validate_vec_csv.py data/vic_2018_preferences_long.csv
./.venv/bin/python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

Expected 2018 shape:

- 88 districts
- 2,137 preference rows
- all districts have `first` and `final` rows
- 48 districts have full transfer/progressive distribution rounds
- 40 districts have first-preference and final preferred results only, because the VEC historical pages do not expose full distribution tables for those seats

## 3. Boundary Verification

Confirm the 2018 map file still matches the CSV exactly:

```bash
./.venv/bin/python - <<'PY'
import json, pandas as pd
geo = json.load(open("data/vic_2018_district_boundaries.geojson"))
geo_names = {f["properties"]["district"] for f in geo["features"]}
csv_names = set(pd.read_csv("data/vic_2018_preferences_long.csv")["district"].unique())
print("features", len(geo["features"]))
print("missing", sorted(csv_names - geo_names))
print("extra", sorted(geo_names - csv_names))
PY
```

Expected:

- `features 88`
- no missing names
- no extra names

## 4. UI Polish

Consider small labels so users understand 2018 limitations:

- add a data note in the status area when the selected election is 2018
- mention that some 2018 seats only have first/final rows
- avoid showing an empty transfer-round UI for districts without transfer rows

## 5. Scraper Cleanup

The current scraper still has `2022` in the filename. Before merging, consider either:

- rename `scripts/scrape_vec_2022_preferences.py` to `scripts/scrape_vec_preferences.py`, or
- leave the filename for now and rename in a separate cleanup PR

If renaming, update:

- `README.md`
- `START_HERE.md`
- any workflow or helper script references

## 6. PR and Merge

Before opening or merging the PR:

- run the CSV validators
- run browser smoke tests for both years
- check `git status --short` is clean after committing
- open PR from `try-2018-election`
- note the 2018 partial-distribution limitation in the PR description

## 7. Later Improvements

Good follow-up tasks:

- add a compact year summary strip
- support URL state for selected year plus selected district
- add a small data-source modal or page
- add 2014 using the same historical-results pattern, if VEC pages expose enough data
- create a scraper test fixture from one 2018 historical district page and one 2022 current district page
