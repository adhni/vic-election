# Governor: swing since the previous election

The 2018, 2020, 2022, 2024 and 2026 State and County explorers offer one automatic comparison: **Swing since previous election**. New Hampshire and Vermont compare with **two years earlier**; other participating states compare with **four years earlier**. For example, 2024 uses 2022 for New Hampshire/Vermont and 2020 elsewhere. These are the previous regular gubernatorial elections, following the two- and four-year terms described by the [National Governors Association](https://www.nga.org/governors/powers-and-authority/). Special elections cannot substitute for a regular baseline.

Select an area to see its actual comparison years, both election shares and the percentage-point change. The previous-election share option follows the same per-state rule. Changes are not annualised: a two-year change and a four-year change measure different intervals. County comparisons describe local vote leaders rather than separately elected governors. The earliest stored Governor results are from 2016. Therefore, 2018 comparisons cover only New Hampshire and Vermont, whose baseline is 2016. Other 2018 states need 2014 results and remain grey with an explicit explanation. The 2016 view retains results only because no preceding election is stored. A 2016 special election, such as Oregon’s, cannot replace the 2014 regular baseline for 2018.

## Calculation and sample

Democratic two-party share is `100 × named Democratic votes / (named Democratic + named Republican votes)`. Swing subtracts the unrounded previous share from the unrounded current-election share. Republican swing reverses its sign. Independent candidates and grouped Other votes are never assigned to either party. Switching between the previous share, current share and swing uses the same matched sample. Map colours consistently show Democratic/Republican movement regardless of the chart party selector.

The following counts describe comparison eligibility before a demographic metric's missing values can further reduce the plotted sample:

| Election | Eligible state races | Stricter state races | Eligible local areas | Stricter local areas |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 2 | 2 | 23 | 23 |
| 2020 | 10 | 10 | 474 | 474 |
| 2022 | 34 | 31 | 2,104 | 2,059 |
| 2024 | 11 | 10 | 518 | 511 |
| 2026 | 34 | 33 | 2,109 | 2,107 |

The stricter sample also requires no multiple named candidates from either major party in either election. The [2026 snapshot](us_governor_2026.md) remains provisional as of 15 November 2026; historical cycles retain their compiled-result provenance. Fixed demographics may describe populations several years after these earlier elections.

Both years require positive named Democratic and Republican votes, a resolved result/leader, a corresponding reporting area and compatible count bases. In particular:

- Comparisons involving Alaska’s 2022/2026 ranked-choice count bases are excluded because they have not been standardised; its county view is also a labelled statewide fallback. A known statewide party flip can still appear on selection without a numeric swing.
- Rhode Island has no named Republican in the 2026 snapshot; its independent candidate is not treated as Republican.
- Connecticut's historical counties cannot be matched to the fixed demographic snapshot's planning regions; the 2026 planning regions also lack a matching historical result baseline.
- Franklin County, Arkansas has grouped Other votes that prevent resolving the individual local leader; no swing or local flip is inferred.
- Other local areas without a matching baseline or positive votes for both parties are excluded with a reason.
- Maine governor elections use plurality. The ranked-choice exclusion applied to Senate comparisons does not apply to Maine governor races.

Outlined chart points indicate a Democratic/Republican flip between the selected area's actual election years. County flips require an eligible local comparison. Excluded areas remain visible in grey on the map and explain their exclusion on selection. 2026 results and flips remain provisional.

The chart holds the existing **2024 ACS** demographics fixed (2020–2024 five-year estimates for counties). It does not claim that the electorate or population stayed constant, and a correlation is not evidence of causation.

## Rebuild and audit

The builder uses committed 2016–2026 Governor results and the existing demographic identifiers. It emits one row for each area in the selected election map; only the applicable baseline-year columns are populated. Metadata records source and output hashes and exclusion/sample counts.

```sh
python3 scripts/build_us_governor_comparison.py
python3 scripts/build_us_governor_comparison.py --check
python3 scripts/test_us_governor_comparison.py
.venv/bin/python scripts/test_governor_swing_ux.py
```

Outputs are `data/us_governor_{state,county}_{year}_previous_comparison.csv` and `data/us_governor_comparison_metadata.json`. Checks independently verify source votes, shares, raw changes, baselines, exclusions and flips. Browser checks audit chart membership, map colours, year labels, matched outcomes, party inversion, stricter samples, navigation and mobile layout.
