# US House 2022–2024 comparison

The demographic chart supports 2022 share, 2024 share, and 2024 minus 2022 change in **percentage points**, for either party. Demographics remain the **2024 ACS one-year snapshot** throughout. This answers whether districts with a particular demographic profile shifted between elections; it does not measure demographic change or how individuals voted.

## Available views

Select **House 2022** or **House 2024**, then open **Demographics → Election outcome**. House 2022 defaults to the matched 2022 share view; the all-eligible 2024 view is available under House 2024:

- **2024 share · all eligible districts:** the original 397-district baseline.
- **2022 share · matched districts:** 312 comparable districts.
- **2024 share · matched districts:** the same 312 districts.
- **Change 2022 → 2024 · matched districts:** the same 312 districts; positive means the selected party gained two-party share.

The same matched sample makes the two yearly charts directly comparable. For example, 45% in 2022 and 48% in 2024 gives +3 percentage points of share change. Republican share is 100 minus Democratic share; Republican change has the opposite sign. This is share change, not the change in the D–R margin (which would be twice as large).

Each metric still omits its missing demographic estimates. The stricter sample checks multiple major-party candidates in either year; all 312 matched districts currently meet it. Full change axes span −100 to +100 pp, with a zero reference line. Fit data preserves negative values and adds padding. Axes do not change correlations or eligibility.

The map and full district result show the election selected in the main election picker (2022 or 2024). The note above the chart identifies that year. Selecting any district shows its demographic estimate and an exclusion explanation when it cannot be plotted. Comparable selected districts show both shares and their change.

## Swing map and biggest shifts

Choose **Colour map by → 2022 → 2024 swing** on either House election page. This opens the linked change scatterplot with a fitted Y axis. Selecting the change outcome also switches the map to swing; selecting a share outcome restores the winner map. Map mode is preserved in shared URLs and browser history.

Map colours always indicate the direction of change: blue toward Democrats, red toward Republicans, and a neutral fill for changes smaller than 0.5 percentage points. Light colours cover 0.5 to under 5 pp; dark colours cover 5 pp or more. Grey marks incomparable districts. Colours do not reverse when the chart switches parties. Chart dots use the same direction colours in the change view; the selected party still determines the Y-axis sign.

The **Biggest swings** lists show the five largest movements toward each party. Each row shows the selected party's 2022 and 2024 two-party shares and signed change. Select a row, map district, or chart dot to highlight that district across the views. Rankings and map use the comparable election sample regardless of whether the selected demographic estimate is missing; the scatterplot omits missing estimates. Map search and filters do not recalculate the election-wide rankings.

## Boundary and contest eligibility

The Census Bureau’s [2024 geography changes, Release of 119th Congressional Districts](https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2024/geography-changes.html) identifies new congressional plans in Alabama, Georgia, Louisiana, New York, and North Carolina, and explicitly confirms no changes from the 2022 cycle in all other states. The [2022 geography documentation](https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2022/geography-changes.html) associates the 118th boundaries with the 2022 election cycle.

We conservatively exclude **all 67 districts in those five changed-plan states**. We do not claim every excluded district changed: individually unchanged seats in these states could be restored after a more detailed boundary audit. The remaining **368 districts** are covered by Census's explicit continuity statement. Display GeoJSONs use different simplification scales, so raw polygon equality is not used as evidence.

We also exclude Alaska and Maine because the compact election sources can mix first and decisive ranked-choice counts between years; count bases have not been standardized. Both years must have official contests, named Democratic and Republican candidates, and positive reported votes for both parties. Explicitly party-labelled write-ins are included with their party. Absent or unopposed opponents do not become artificial 0%/100% observations. These requirements leave **312 matched districts**.

Two-party share = party votes / (Democratic votes + Republican votes). Candidate totals follow the existing official-source election files, including their documented limitations. No hypothetical results on redrawn boundaries are estimated. Year-specific source shares remain in the download for audit even on excluded districts; eligibility is explicit, and change is blank unless comparable.

A small **Flipped to Democrat/Republican** badge identifies a changed winning party in the selected district, chart/map tooltips, and any affected swing ranking row. It compares the official elected parties in the 2022 and 2024 general-election snapshots on verified unchanged boundaries, independently of two-party share eligibility. Large swings in held seats do not receive a badge; unverified changed-plan districts remain unlabelled. This does not track intervening by-elections or party switches.

## Files and reproduction

- [Comparison CSV](../data/us_house_2022_2024_comparison.csv): all 435 districts, year-specific totals and shares, boundary status, eligibility, reasons, and comparable change.
- [Metadata](../data/us_house_2022_2024_comparison_metadata.json): input/output SHA-256 hashes, sample counts, boundary evidence and policy.
- [2024 analysis CSV](../data/us_2024_house_analysis.csv): fixed demographic point estimates and margins of error, joined in the app by district code.

```sh
python3 scripts/build_us_house_comparison.py
python3 scripts/build_us_house_comparison.py --check
python3 scripts/test_us_house_comparison.py
.venv/bin/python scripts/test_house_demographics_ux.py
```

The builder reads only prepared local inputs and writes deterministic outputs. The check recomputes both artifacts and checks exact bytes; independent tests separately aggregate source candidates and verify eligibility and share-change arithmetic.

Correlations weight districts equally, use demographic point estimates, and do not propagate ACS sampling uncertainty. A 2024 demographic snapshot is measured after the 2022 election, so these are descriptive associations, not prospective predictions. Different candidates, incumbency, national conditions, and midterm versus presidential turnout can all influence the observed shift. It is not evidence that a demographic group changed its individual vote.
