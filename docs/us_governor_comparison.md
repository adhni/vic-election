# Governor 2026: swing since the previous election

The State and County explorers offer one automatic comparison: **Swing since previous election**. New Hampshire and Vermont compare **2024 → 2026**; the other 34 participating states compare **2022 → 2026**. These are the previous regular gubernatorial elections, following the two- and four-year terms described by the [National Governors Association](https://www.nga.org/governors/powers-and-authority/). Special elections cannot substitute for a regular baseline.

Select an area to see its actual comparison years, both party shares and the percentage-point change. The previous-election share option follows the same per-state rule. Changes are not annualised: a two-year change and a four-year change measure different intervals. County comparisons describe local vote leaders rather than separately elected governors. This feature applies to the 2026 governor view.

## Calculation and sample

Democratic two-party share is `100 × named Democratic votes / (named Democratic + named Republican votes)`. Swing subtracts the unrounded previous share from the unrounded 2026 share. Republican swing reverses its sign. Independent candidates and grouped Other votes are never assigned to either party. Switching between the previous share, 2026 share and swing uses the same matched sample. Map colours consistently show Democratic/Republican movement regardless of the chart party selector.

The frozen provisional [15 November 2026 snapshot](us_governor_2026.md) has 36 state races and 2,151 county/reporting areas. **34 states and 2,109 county/reporting areas** are eligible for comparison. The stricter sample also requires no multiple named candidates from either major party in either election: **33 states and 2,107 local areas**. An individual demographic metric can further reduce the plotted sample when its value is missing.

Both years require positive named Democratic and Republican votes, a resolved result/leader, a corresponding reporting area and compatible count bases. In particular:

- Alaska is excluded because its count bases have not been standardised; its county view is also a labelled statewide fallback. A known statewide party flip can still appear on selection without a numeric swing.
- Rhode Island has no named Republican in the 2026 snapshot; its independent candidate is not treated as Republican.
- Connecticut's historical counties cannot be matched to the current planning regions.
- Franklin County, Arkansas has grouped Other votes that prevent resolving the individual local leader; no swing or local flip is inferred.
- Other local areas without a matching baseline or positive votes for both parties are excluded with a reason.
- Maine governor elections use plurality. The ranked-choice exclusion applied to Senate comparisons does not apply to Maine governor races.

Outlined chart points indicate a Democratic/Republican flip between the selected area's actual election years. County flips require an eligible local comparison. Excluded areas remain visible in grey on the map and explain their exclusion on selection. Results and flips remain provisional.

The chart holds the existing **2024 ACS** demographics fixed (2020–2024 five-year estimates for counties). It does not claim that the electorate or population stayed constant, and a correlation is not evidence of causation.

## Rebuild and audit

The builder uses committed 2022, 2024 and 2026 Governor results and the existing demographic identifiers. It emits one row for each area in the current 2026 map; only the applicable baseline-year columns are populated. Metadata records source and output hashes and exclusion/sample counts.

```sh
python3 scripts/build_us_governor_comparison.py
python3 scripts/build_us_governor_comparison.py --check
python3 scripts/test_us_governor_comparison.py
.venv/bin/python scripts/test_governor_swing_ux.py
```

Outputs are `data/us_governor_{state,county}_2026_previous_comparison.csv` and `data/us_governor_comparison_metadata.json`. Checks independently verify source votes, shares, raw changes, baselines, exclusions and flips. Browser checks audit chart membership, map colours, year labels, matched outcomes, party inversion, stricter samples, navigation and mobile layout.
