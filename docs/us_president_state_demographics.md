# US presidential demographics by state, 2008–2024

Select a US presidential election and open **Demographics**. Presidential elections now open on the **State** geography; the county map remains available from the geography buttons. The demographic chart supports both State and County views.

The five available elections are **2008, 2012, 2016, 2020 and 2024**. The Comparison selector offers every adjacent period: 2008–2012, 2012–2016, 2016–2020 and 2020–2024. Selecting a period selects its ending election and state map. Election outcome offers either year's two-party share and the change between them. Both Democratic and Republican views, independent fitted/full axes, map/dot/ranking selection, keyboard/touch controls, download links and URL/history restoration use the same interface as the House chart.

## What the values mean

Each dot represents **one of the 50 states or DC**, with equal weight. Votes use the repository's official statewide [FEC election compilations](https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/), not county estimates or House districts. All 51 areas report positive votes for both major parties in every election, so all are comparable; Alaska and Maine are included.

Democratic two-party share is `100 × D / (D + R)`; Republican share is its complement. Swing is ending share minus starting share, in **percentage points**. The change in the D–R margin would be twice this value. Third-party votes remain in the source results but are outside this two-party denominator.

Blue map colours always indicate movement toward Democrats and red toward Republicans, irrespective of the chart's selected party. Outlined points changed **statewide popular-vote leading party**. This does not represent Electoral College allocation, including the split electors in Maine and Nebraska, faithless electors, or the winner of the national presidency. The shared CSV/chart field is named `seat_flipped`, but the presidential interface says **flipped state**.

Expected statewide popular-vote flips:

| Period | States |
| --- | --- |
| 2008–2012 | Indiana, North Carolina |
| 2012–2016 | Florida, Iowa, Michigan, Ohio, Pennsylvania, Wisconsin |
| 2016–2020 | Arizona, Georgia, Michigan, Pennsylvania, Wisconsin |
| 2020–2024 | Arizona, Georgia, Michigan, Nevada, Pennsylvania, Wisconsin |

State r is Pearson correlation and Spearman uses ranks. Both describe equal-weight state/DC associations, not national vote-weighted results. The third statistic counts flipped states. A within-state correlation is not meaningful when each point is a whole state, so it is not shown. Map search does not change the sample, rankings or statistics.

## Demographics and timing

All comparisons use the same **2024 ACS 1-year state snapshot**: 42 resident/household measures with published or approximately derived **90% margins of error**. The point estimates are fixed as the election changes. Thus, the chart asks whether states with a particular *2024 demographic profile* voted differently or shifted between elections; it does **not** measure demographic change, reconstruct earlier populations, identify individual voters' choices, or establish causation. The timing mismatch is particularly material for the earlier elections and is labelled in the interface. Correlations do not propagate ACS uncertainty.

State values are extracted directly from the official national [2024 ACS summary tables](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/1YRData/), using Census state geography IDs `0400000USxx`. They are not sums or averages of congressional districts. Census state FIPS are joined by name to the existing election postal-state codes, with DC explicitly included. The 18 source tables, metric formulas and missing-value treatment are shared with the existing 2024 House demographic builder.

Negative/missing estimate sentinels become blank derived values. Controlled-estimate MOE sentinels contribute zero sampling error. Raw source tokens and flags are retained. Missing demographic estimates are excluded from the affected chart only, never imputed as zero.

## Files and reproducibility

- [State demographic metrics](../data/us_2024_state_demographics.csv).
- [Raw state estimates and MOEs](../data/us_2024_state_demographics_acs.csv).
- [Source flags](../data/us_2024_state_demographics_flags.csv).
- [Definitions, source provenance, coverage and hashes](../data/us_2024_state_demographics_metadata.json).
- Comparison CSVs and metadata: `data/us_president_START_END_comparison.csv` / `_metadata.json` for each adjacent period.

```sh
# Reuse the official ACS bulk cache; optionally fetch missing sources.
python3 scripts/build_us_president_demographics.py --download
python3 scripts/build_us_president_demographics.py --check
python3 scripts/test_us_president_demographics.py
.venv/bin/python scripts/validate_us_presidential.py
.venv/bin/python scripts/test_president_demographics_ux.py
```

The check deterministically recomputes every comparison and checks exact bytes. When all ACS sources are cached, it also rebuilds all demographic artifacts and verifies exact bytes. CI validates committed demographic hashes and arithmetic, source election shares and expected flips; it does not need network access or an API key. The browser suite separately compares all 51 displayed values, Pearson/Spearman correlations, flip outlines and map colours with prepared data in each period and party view, and exercises direct entries for all five years, state/county scope, mobile/touch and browser history across House/presidential pages.

## County / reporting-area view

Choose **County** beside the map to use the same comparisons, both-party shares, flip outlines, fitted axes and downloads for county-level reporting areas. The selected geography persists when changing comparison periods and in shared URLs. All four periods have **3,104 comparable areas**. The chart and map use the selected election’s names and identifiers; for example, the 2016 map shows Shannon County while the 2020 map shows its renamed Oglala Lakota County.

County demographics use a fixed **2020–2024 ACS five-year snapshot**, with the same 42 measures and 90% margins of error. The five-year product covers small counties, unlike the one-year product used for states. It is a multi-year estimate, not a 2024-only measurement. Earlier populations may differ. State and county views therefore use different ACS products; correlations are descriptive associations within the selected geography, not directly controlled comparisons between those products.

The county chart weights reporting areas equally and reports Pearson, Spearman and the number of flipped counties. It uses the existing county election sources: [MIT historical returns](https://doi.org/10.7910/DVN/VOQCHQ) for older elections, and the repository’s [public county compilation](https://github.com/tonmcg/US_County_Level_Election_Results_08-24) for 2020/2024, with official statewide Alaska/DC returns. These have different source status from the statewide FEC compilations. Historical data already combine Bedford city into Bedford County and Kansas City reporting returns into Jackson County.

Reporting-area identifiers are matched across years; this is **not a block-by-block boundary audit**. The following cases are explicit:

- **Alaska** is a statewide placeholder in the county election data. It is grey and unplotted, with no invented county demographics. Use State view for Alaska.
- **DC** is a county equivalent covering the same territory as its reported vote total and is included.
- **Connecticut** changed from eight historical counties to nine planning regions. The older county areas cannot be joined to the current ACS planning regions by renaming. Both old/new areas are retained for map selection but excluded from county charts/comparable swings; their historical demographics and unsupported changes are withheld. See [Census geography changes](https://www.census.gov/programs-surveys/acs/geography-acs/geography-boundaries-by-year.2024.html).
- **Shannon County (46113)** was renamed Oglala Lakota County (46102). This is a code/name alias rather than the creation of a new county; historical display names and source vote totals are preserved. See [Census geography documentation](https://www.census.gov/content/dam/Census/topics/research/2020%20State%20and%20County%20PDB%20Documentation_V2.pdf).

The current demographic extract has 3,114 reporting-area rows, including a blank Alaska placeholder; all actual current county areas are extracted directly from official Census five-year county rows (`0500000USxxxxx`). Older Connecticut counties have no matching current demographic row. The 2020–2024 comparison retains the union of old/new Connecticut reporting areas so selection works on either map; these do not increase the comparable sample.

### County files and rebuild

- [County metrics](../data/us_2024_county_demographics.csv), [raw estimates/MOEs](../data/us_2024_county_demographics_acs.csv), [flags](../data/us_2024_county_demographics_flags.csv), [definitions and provenance](../data/us_2024_county_demographics_metadata.json).
- Comparison files: `data/us_president_county_START_END_comparison.csv` and `_metadata.json` for all four adjacent periods.

```sh
python3 scripts/build_us_president_county_demographics.py --download
python3 scripts/build_us_president_county_demographics.py --check
python3 scripts/test_us_president_county_demographics.py
.venv/bin/python scripts/test_president_county_demographics_ux.py
```

Official table downloads use bounded HTTP byte ranges, retaining complete county sections before the much larger tract/subdivision sections. Cached response prefixes, Content-Range values, exact response hashes, metadata and extracted output hashes are recorded. Every target county must be present, and the prefix must reach a later summary level, or the build fails. Census five-year commuting table B08301 supplies the same work-from-home/public-transport measures that use C08301 in the one-year product.

The checks independently verify every cached county cell, derived arithmetic and source vote shares; preserve rename aliases and explicit exclusions; and validate exact deterministic rebuilds. Browser checks cover all four periods, both years’ shares and change for both parties, correlations, map colours, flips, older/current display names, selection, geography switching, mobile and history.
