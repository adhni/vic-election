# Victoria 2022 Preference Explorer

A compact interactive HTML prototype for exploring how Victorian Legislative Assembly districts voted in the 2022 state election.

The app is **party-first**: party is highlighted visually, while candidate names are kept as secondary detail.

## Open the app

Open:

```text
index.html
```

No build step is needed. It is plain HTML/CSS/JavaScript.

The app has a few sample districts built in so it works immediately.

## Folder structure

```text
.
├── index.html                         # open this first
├── app/
│   └── index.html                     # same app, kept for cleaner repo structure
├── data/
│   └── sample_melbourne_preferences_long.csv
├── scripts/
│   ├── scrape_vec_2022_preferences.py # official VEC scraper
│   └── validate_vec_csv.py            # CSV checker
├── docs/
│   └── data_notes.md
├── .github/workflows/
│   └── scrape-vec-data.yml            # optional manual GitHub Action
├── requirements.txt
├── START_HERE.md
└── codex_prompt.md
```

## What data format does the app expect?

Long CSV:

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

## Run the scraper

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape_vec_2022_preferences.py --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

This should create:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_summary.csv
```

Then open `index.html` and upload `data/vic_2022_preferences_long.csv`.

## Easier GitHub option

After uploading this repo to GitHub:

1. Go to **Actions**
2. Run **Scrape VEC 2022 data**
3. Download the generated artifact
4. Put the CSV into `data/` or upload it manually in the app

## Current status

This is a clean repo prototype. It is not yet a finished full data product.

Best next improvements:

- make the app auto-load `data/vic_2022_preferences_long.csv`
- add district search
- add party filters
- add a map after the data is stable
