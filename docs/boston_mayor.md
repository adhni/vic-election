# Boston mayoral general elections, 2013, 2017 and 2021

Choose **United States → Boston Mayor 2013 / 2017 / 2021** in the main
explorer, or open [Boston precinct dots](../app/boston-precinct-dots.html).
The main explorer switches between **255 precincts** and **22 wards**. The dot
view provides one equal-size dot per precinct, grouped by the local candidate
leader, with linked map selection, ward and candidate filters, text/code search,
a named picker, keyboard browsing and shareable URLs.

These are the **November general elections**, not the preliminary elections.
Candidate colours identify people, not Republican or Democratic affiliation.
No cross-year candidate pairing, voting-history clustering, vote splitting or
population-based redistribution is performed.

A separate [voting-history grouping view](../app/boston-history-dots.html) compares
the three elections with explicit map agreement screening and provisional histories.
See its [method and limitations](boston_history_clusters.md).

## Official counts

The sources are the City of Boston's official
[2013 ward and precinct PDF](https://documents.boston.gov/images_documents/2013%20-%2011-05-13%20-%20Mayor%20Ward%20%26%20Precinct%20Results%20%281%29_tcm3-41970.pdf),
[2017 ward and precinct PDF](https://www.boston.gov/sites/default/files/embed/2/2017_-_11-07-17_-_mayor_ward_precinct_results.pdf)
and [2021 ward and precinct PDF](https://www.boston.gov/sites/default/files/file/2021/11/2021-11-02-21-Mayor.pdf),
linked from its [election archive](https://www.boston.gov/departments/elections/state-and-city-boston-election-results).
Each PDF contains a citywide/ward recap plus one page for each of the 22 wards.
The pinned original PDFs are retained under `data/sources/boston/` so every
precinct cell can be audited without relying on future website availability.

| Candidate or return | 2013 | 2017 | 2021 |
| --- | ---: | ---: | ---: |
| Marty Walsh | 72,583 | 70,197 | — |
| John Connolly | 67,694 | — | — |
| Lee Buckley (named write-in) | 1 | — | — |
| David James Wyatt (named write-in) | 4 | — | — |
| Tito Jackson | — | 36,472 | — |
| Donald Osgood Sr. (named write-in) | — | 38 | — |
| Michelle Wu | — | — | 91,794 |
| Annissa Essaibi George | — | — | 51,125 |
| Other / write-in votes (grouped source return) | 555 | 670 | 595 |
| **Recorded candidate votes** | **140,837** | **107,377** | **143,514** |
| Blank mayoral ballots | 1,170 | 1,657 | 866 |
| **Ballots cast** | **142,007** | **109,034** | **144,380** |

Every precinct's candidate sum, blank ballots and ballots cast reconcile. All
precincts sum exactly to the ward recaps and citywide totals. Percentages are
recomputed from counts; published PDF percentage cells are not imported.
For example, Ward 1 Precinct 15 in 2021 reports one Wu vote despite a printed
0.0% in the source percentage table. Its displayed share is correctly 100% of
recorded candidate votes. It has zero ballots in 2017 and remains a grey dot.

The separately named 2013 and 2017 write-in candidates are retained. Grouped Other /
write-in votes are included in candidate-share denominators but excluded from
individual-candidate leader selection. The 2017 election has **four tied
precinct leads** and **one zero-vote precinct**. The 2013 election has one tied
precinct lead and no zero-vote precincts; the 2021 election has neither.
Turnout is unavailable because no election-specific registration denominator
has been imported; ballots cast are not treated as registration.

## Boundaries and their limitation

The map comes from the City's
[Precincts_2017 GIS service](https://services.arcgis.com/sFnw0xNflSi8J0uh/arcgis/rest/services/Precincts_2017/FeatureServer),
whose description identifies an **October 2017** update. The original GeoJSON
and layer metadata are retained as checksummed source fixtures. All 255 codes
join the result tables in all three years, including **Ward 5 Precinct 2A** (`0502A`).
That subprecinct is preserved independently rather than cast to a number,
combined with Precinct 2 or omitted.

**For 2013 and 2021, this is a historical reference map, not an independently verified
election-day boundary snapshot.** Matching identifiers establishes reporting
coverage, not geometric identity across years. The main explorer notice, dot
page and selected-precinct notes explain this limit. No 2022-or-later precinct
map is substituted, and no claim of exact cross-year precinct correspondence
is made. Candidate counts are reported values, not spatially estimated votes.

The same reference geometry is used for all three years. Ward shapes are dissolved
from the precinct reference. Shapes are lightly simplified with topology
preserved for display. The builder checks for geometry defects and permits a
repair only if the area change is below 0.01%; repaired identifiers, if any,
are recorded in each election's metadata.

## Candidate shading and dots

Each named candidate has a distinct colour. A local lead's strength is the
lead over the next named candidate divided by **all recorded candidate votes**,
including grouped other votes. Blank ballots are excluded. Both the map and
dot views use five bands: up to 2, 2–5, 5–10, 10–20 and above 20 percentage
points. Closer leads are lighter; larger leads are darker. Ties and zero-vote
precincts are neutral. There is no invented local winner in those areas.

Dot blocks count precinct leaders, not candidate votes or population. A named
candidate with no local leads is still shown in result details. No geographic
precision is inferred from dot position within a block.

## Reproduce and validate

```bash
pip install -r requirements.txt
python scripts/build_boston_mayor.py
python scripts/validate_boston_mayor.py
python scripts/test_boston_mayor_ux.py
python scripts/smoke_static_app.py
python scripts/check_repository_sizes.py
```

The builder checks source SHA-256 digests, reads PDF table cells and exports
precinct/ward CSVs, shared reference geometry, per-year metadata and the dot
extract. Source changes stop the build for review; no network request is
needed to rebuild from the retained fixtures.

The independent validator reads positioned PDF text rather than reusing the
builder's table detector. It checks every precinct candidate/blank/ballot cell,
all ward and city totals, the alphanumeric precinct identifier, every map join,
local ties and zero-vote status, and agreement of the dot records with CSVs.
Browser checks cover all three elections, all 255 dot/map colours and leaders,
ward zoom, the main explorer's two geographies, candidate shades, selection,
search, keyboard use, URL reload/reset and 320/390/768px layouts. These checks
are included in the voting-groups CI workflow.
