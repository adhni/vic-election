# Senate swing on the same six-year cycle

Choose a Senate election, then **Colour map by → [six-year period] swing**, or open **Demographics**. The existing linked map, chart, flip outlines, before/after share cards, rankings, Democratic/Republican controls, fitted axes and comparison download all work at **State** and **County** scope. No separate tool or new comparison controls are needed.

The available comparisons follow the same regular Senate seat, six years apart:

| Comparison | Senate class | Comparable state races | Comparable counties |
|---|---|---:|---:|
| 2016 → 2022 | III | 30 | 1,895 |
| 2018 → 2024 | I | 28 | 1,630 |
| 2020 → 2026 | II | 27 | 1,933 |

These are baseline samples before a selected demographic measure's missing values. For example, the bachelor's-degree chart has 1,894 points in 2016 → 2022 because one eligible county lacks that estimate. The existing stricter sample also excludes multiple major-party candidates in either year; its respective state samples are 29, 28 and 26, and county samples 1,830, 1,630 and 1,869.

The [Senate Class I](https://www.senate.gov/senators/Class_I.htm), [Class II](https://www.senate.gov/senators/Class_II.htm) and [Class III](https://www.senate.gov/senators/Class_III.htm) documentation establishes the seat cycles. A comparison selected on the ending-year map can also be viewed on its starting-year map. Selecting another comparison opens its ending election and preserves State/County scope. Shared URLs preserve the comparison and chart settings.

## Same-seat rules

The historical Senate datasets contain regular elections only. Match regular seats by state within the corresponding class, rather than comparing different seats two years apart. The 2026 Florida and Ohio races are special Class III elections and are excluded from 2020 → 2026 Class II swing. They remain visible in 2026 results and display an exclusion explanation in the chart selector/map.

The **2020 Georgia baseline is Jon Ossoff's regular seat**, using the decisive January 2021 runoff already retained in the source dataset. It is not Raphael Warnock's concurrent special election. The 2016 → 2022 Georgia comparison follows the separate Class III seat. Earlier decisive regular-seat runoffs likewise retain the existing dataset's count basis.

The 2026 counts remain the **provisional 14 November 2026 snapshot**. Alaska is not called and is excluded. Alaska and Maine are excluded from all share comparisons because ranked-choice count bases have not been standardized. An uncalled race never acquires a swing or seat-flip flag.

## Vote shares and county limitations

Swing is the ending minus starting **Democratic two-party share**, in percentage points: D / (D + R). Republican swing reverses that sign; the map's blue/red direction always means movement toward Democrats/Republicans. Matched shares for either year use the same sample as change.

Both years require named Democratic and Republican candidates with positive reported party votes. Sum individually party-labelled source candidates; never assign independent or grouped Other votes to a major party. Independent candidates and minor parties can still affect the contest and interpretation of two-party shares.

The 2026 county source names only two candidates, with every other candidate/write-in grouped together. Where those names represent an independent versus a Republican—in Idaho, Montana, Nebraska and South Dakota—the county D/R comparison is unavailable. Montana's statewide full candidate list does separately report Democratic votes, so a statewide comparison can be available while its counties are excluded. The chart explains these exclusions. See [2026 Senate source methods](us_senate_2026.md) for attribution, grouped-vote handling and state/county residuals; no residual votes are imputed in comparisons.

County comparisons match reporting identifiers in both years; they do **not** claim an individual boundary audit. Missing reporting areas are excluded. Alaska's statewide placeholders are never treated as counties. Connecticut's historical counties do not match the current county demographic geography and are excluded. Every original year's district name/code is retained so both maps join correctly.

## Flips and demographics

On the State view, an outlined point means the elected party changed for that same regular seat. County outlines mean the **local leading party changed**, not that a county elected a senator. Flips are independent of the chart's selected party; 2026 flags remain provisional. Special elections and uncalled races do not receive flip flags. Excluded state races can retain a known elected-party flip independently of share-comparison eligibility; county flip flags require an eligible reporting-area comparison.

Demographics reuse the fixed **2024 ACS one-year state** and **2020–2024 ACS five-year county** snapshots. Each point is weighted equally. Missing estimates are omitted, never zero-filled. National/state/county Pearson and Spearman correlations describe areas; the third statistic counts flipped states or counties. These charts do not measure demographic change, individual voting behavior or causation. The demographic snapshot postdates earlier elections, and populations may have changed.

## Reproduction and checks

`data/us_senate_{state,county}_{start}_{end}_comparison.csv` retains all areas appearing in either year, with original year identifiers, raw named D/R totals, shares, exclusion reasons, class, sample flags and flips. `data/us_senate_comparison_metadata.json` records source links, every input/output hash and sample counts. Preparation requires no new network downloads.

```sh
python3 scripts/build_us_senate_comparison.py
python3 scripts/build_us_senate_comparison.py --check
python3 scripts/test_us_senate_comparison.py
.venv/bin/python scripts/test_senate_swing_ux.py
```

The data audit independently checks every source party total and share, six-year class identity, special-seat exclusion, Georgia regular-seat identity, grouped/independent votes, uncalled races, reporting geography, flip arithmetic and deterministic rebuilds. The browser audit checks every plotted identifier and map colour across all three periods and both scopes, flip sets, both matched shares, Republican inversion, exclusion explanations, selected share cards, fitted axes, downloads, mobile, reload and family/period switching.
