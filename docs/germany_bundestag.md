# German Bundestag elections

The app includes the 2025, 2021, and 2017 Bundestag elections at constituency level. Every option contains all 299 constituencies, the Erststimme result, the separate Zweitstimme result, turnout metadata, the Bundestag seat allocation, and the matching election-year boundary map.

## Sources

Results and boundaries come from the Federal Returning Officer:

- [2025 final results and open data](https://www.bundeswahlleiterin.de/bundestagswahlen/2025/ergebnisse.html)
- [2021 certified results after the partial Berlin repeat vote](https://www.bundeswahlleiterin.de/bundestagswahlen/2021/ergebnisse.html)
- [2017 final results](https://www.bundeswahlleiterin.de/bundestagswahlen/2017/ergebnisse.html)
- election-specific generalized WGS84 constituency shapefiles from each election's official boundary-download page

The build script locks each downloaded result and boundary archive to a SHA-256 checksum. Current machine-readable result files identify first-vote choices by party or independent-group label, which is what the app displays.

## 2025 mandate rule

The 2025 result file distinguishes the local Erststimme leader from an actually awarded constituency mandate. The app preserves that distinction: 299 local plurality leaders are shown, while only 276 received constituency mandates because 23 lacked sufficient Zweitstimme coverage under the electoral law then in force.

The 2021 and 2017 constituency plurality winners all received direct mandates.

## Rebuild and validate

```bash
python scripts/build_germany_bundestag.py
python scripts/validate_germany_bundestag.py
python scripts/smoke_static_app.py
```

Validation requires 299 unique result areas and 299 matching boundary features per year, reconciles first-vote and ballot totals in every constituency, and checks national first-vote leader and awarded-mandate counts.

## Boundary attribution

- 2025: © Die Bundeswahlleiterin, Statistisches Bundesamt, Wiesbaden 2024, Wahlkreiskarte für die Wahl zum 21. Deutschen Bundestag. Grundlage der Geoinformationen © Geobasis-DE / BKG 2024. Datenlizenz Deutschland – Namensnennung – Version 2.0.
- 2021: © Der Bundeswahlleiter, Statistisches Bundesamt, Wiesbaden 2020, Wahlkreiskarte für die Wahl zum 20. Deutschen Bundestag. Grundlage der Geoinformationen © Geobasis-DE / BKG 2020.
- 2017: © Der Bundeswahlleiter, Statistisches Bundesamt, Wiesbaden 2016, Wahlkreiskarte für die Wahl zum 19. Deutschen Bundestag. Grundlage der Geoinformationen © Geobasis-DE / BKG 2016.
