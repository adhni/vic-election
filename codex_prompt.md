# Codex prompt

You are working on a repo called `vic-election-preference-explorer`.

Goal: make the Victoria 2022 Preference Explorer a clean GitHub Pages data app.

Current state:
- `index.html` is a compact standalone HTML prototype.
- It has embedded sample data for a few districts.
- It supports manual CSV upload.
- `scripts/scrape_vec_2022_preferences.py` scrapes official VEC district results and preference distribution pages.
- `scripts/validate_vec_csv.py` validates the output CSV.

Tasks:
1. Run the scraper with `--limit 3` first and fix any obvious parsing issues.
2. Then run the scraper for all districts.
3. Inspect `data/scrape_errors.csv` if generated.
4. Make `index.html` auto-load `data/vic_2022_preferences_long.csv` when available.
5. Keep manual CSV upload as a fallback.
6. Keep the UI compact. Do not add long explanatory text.
7. Keep party visually primary and candidate secondary.
8. Do not invent election data. Only use scraped VEC rows or sample rows clearly marked as sample.
9. Commit generated CSV only after validating it.

Acceptance criteria:
- App opens from `index.html`.
- App works without build tools.
- With generated CSV present, it auto-loads all districts.
- If auto-load fails, embedded sample data still works.
- No map yet.
