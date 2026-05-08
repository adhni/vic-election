#!/usr/bin/env bash
set -e

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/scrape_vec_2022_preferences.py --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv

echo "Done. Open index.html and upload data/vic_2022_preferences_long.csv"
