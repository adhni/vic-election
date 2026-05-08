# START HERE

This repo is ready to upload to GitHub.

## Just open the prototype

Open this file in your browser:

```text
index.html
```

It already has sample districts inside the app, so you can test the dashboard immediately.

## What the repo does

- Shows a compact party-first dashboard for Victorian district preference counts.
- Lets you upload a cleaned CSV later.
- Includes a scraper script for official VEC 2022 district preference distribution pages.
- Includes a validator script to check the scraped CSV.

## The simple workflow

1. Open `index.html` and check the prototype.
2. Run the scraper to create the full CSV.
3. Upload the generated CSV inside the app.
4. Later, ask Codex to make the app auto-load the CSV instead of manual upload.

## Commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape_vec_2022_preferences.py --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

On Windows, activation is:

```bat
.venv\Scripts\activate
```

## Quick test

```bash
python scripts/scrape_vec_2022_preferences.py --out data --limit 3 --keep-going
```
