# New York City mayor, 2025 general election

[2021 and 2017 general elections](nyc_mayor_history.md) are also available as
separate entries with historical precinct maps and documented source limits.

Choose **United States → New York City Mayor 2025** in the explorer. The default
map shows NYC election districts (EDs), the precinct-level units used to report
votes. These are not police precincts. Buttons switch to the five boroughs or
65 Assembly districts. Search accepts borough and AD/ED names, for example
`Manhattan · AD 65 ED 046`.

The local-lead map shades each candidate's colour by the lead over the next
named candidate, divided by recorded mayoral votes. Bands are ≤2, 2–5, 5–10,
10–20 and >20 percentage points: close leads are pale and large leads are
dark. The same scale applies to precinct, Assembly-district and borough views.
Ties and zero-vote areas remain grey.

This entry covers only the **4 November 2025 general election**, certified on
2 December 2025. It does not include the ranked-choice primary. One mayor is
elected citywide by plurality; area colours indicate local candidate leaders.

## Results and accounting

The source is the NYC Board of Elections' [2025 certified results page](https://www.vote.nyc/page/election-results-summary-2025),
using its citywide [ED-level CSV](https://www.vote.nyc/sites/default/files/pdf/election_results/2025/20251104General%20Election/00000100000Citywide%20Mayor%20Citywide%20EDLevel.csv)
and [certification recap CSV](https://www.vote.nyc/sites/default/files/pdf/election_results/2025/20251104General%20Election/00000100000Citywide%20Mayor%20Citywide%20Recap.csv).
All precinct totals reconcile exactly to both the borough and citywide recaps.

| Candidate | Recorded votes |
| --- | ---: |
| Zohran Mamdani | 1,114,184 |
| Andrew Cuomo | 906,614 |
| Curtis Sliwa | 153,749 |
| Eric Adams | 6,897 |
| Irene Estrada | 2,856 |
| Jim Walden | 2,319 |
| Joseph Hernandez | 1,379 |
| Write-ins, grouped | 6,206 |
| **Total recorded mayoral votes** | **2,194,204** |

There were **2,218,647 ballots**, including **24,443 unrecorded mayoral votes**.
The explorer displays those as unrecorded votes, not as invalid ballots. For
compatibility with the shared CSV schema, `formal_votes` stores recorded
candidate votes and `informal_votes` stores the unrecorded balance.
Registration and turnout are left unavailable rather than treating ballots
cast as registration.

New York permits fusion voting: the same candidate can appear on multiple
ballot lines. Mamdani's Democratic and Working Families votes are combined;
Sliwa's Republican and Protect Animals votes are combined. Each CSV row's
`ballot_lines` JSON preserves the original ballot-line counts. `Write-ins`
combines BOE's Scattered returns and is excluded from individual-candidate
leader selection. Short display names retain the official full names in the
ballot-line detail.

## Boundaries and joint reporting

The geometry is NYC Department of City Planning's **25C, August 2025**
shoreline-clipped release, containing 4,264 ED polygons. The live NYC Open Data
layer now describes newer boundaries. The build uses a checksum-verified,
[pinned copy in nycmaps](https://github.com/kjhealy/nycmaps/blob/8b0b6bf6997bb3c0253517cca58828b4be27b44f/data/nyc_election_precincts_sf.rda),
whose [source script](https://github.com/kjhealy/nycmaps/blob/8b0b6bf6997bb3c0253517cca58828b4be27b44f/data-raw/districts_election_precincts.R)
identifies the `nyed_25c` release. NYC Planning remains the boundary producer;
nycmaps is the download mirror. Coordinates are transformed from EPSG:2263 to
EPSG:4326 and lightly simplified for the static map.

BOE lists 4,338 ED records, including **221 combined districts** with zero
separate returns. Their available polygons are dissolved into their designated
reporting ED's polygon. Each combined area is labelled in its result note and
the CSV `combined_from` field. Votes are counted once. No component precinct
counts are inferred.

Of 4,117 reporting EDs, **4,102 reporting areas are mapped**: 4,030 with votes and
72 with zero votes. Fifteen additional zero-ballot reporting EDs have no polygon
in this shoreline-clipped snapshot; their names remain in
`nyc_2025_mayor_metadata.json`. Every district with recorded votes is mapped.
The map shows **nine tied local leads** and zero-vote areas neutrally, with no
invented winner. Borough and Assembly-district views sum the same returns and
dissolve the same reporting-area geometry; Assembly areas therefore describe
BOE's reporting attribution where EDs were combined across district lines.

## Rebuild and validate

```bash
.venv/bin/python scripts/build_nyc_mayor_2025.py
.venv/bin/python scripts/validate_nyc_mayor_2025.py
.venv/bin/python scripts/build_home_assets.py
.venv/bin/python scripts/smoke_static_app.py
.venv/bin/python scripts/test_nyc_mayor_2025_ux.py
```

The first build needs `Rscript` with the R `sf` package to convert the pinned
boundary object, in addition to the repository's Python dependencies. Later
builds reuse the ignored `tmp/nyc` cache. `--boundaries` accepts a previously
converted 25C GeoJSON with its `elect_dist` identifier. `--refresh` downloads
and verifies sources again; a changed checksum stops the build for review.

Validation checks every candidate and fusion line, the borough and citywide
certification recaps, ballots and unrecorded totals, exact map joins, all
geometry validity, ties, zero-vote areas, and combined-reporting metadata.
The browser check covers geography switching, search, candidate filters,
map selection, shared links, ties, zero-vote labels, and mobile layout.
