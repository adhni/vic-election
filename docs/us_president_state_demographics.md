# US presidential demographics by state, 2008–2024

Select a US presidential election and open **Demographics**. Presidential elections now open on the **State** geography; the county map remains available from the geography buttons. The demographic chart applies only to the state view.

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
