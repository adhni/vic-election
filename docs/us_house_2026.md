# U.S. House 2026: provisional results and 2024 comparison

Choose **United States → House 2026 · Provisional** in the explorer. The existing Demographics view offers **2024 → 2026** swing, either party's matched share, fitted axes, the swing map and outlined flip markers. Selecting this comparison from House 2024 switches to the actual 2026 map.

This is a frozen snapshot published **14 November 2026 at 15:01:38 UTC**, not a live feed or certified final results. All **435 voting districts** are present, with **421 source-reported winners and 14 uncalled races**. Uncalled seats are grey on the results map, retain current candidate counts, and display “Current leader · not called” rather than an elected member. They have no swing or flip marker. Do not interpret blank winner fields as missing district coverage.

## Results and attribution

Counts and race calls come from [Call the Map's downloadable 2026 data](https://www.callthemap.com/results/data), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit **Call the Map (callthemap.com/results)** and **[civicAPI](https://civicapi.org)** for rows using that feed. The original candidate rows retain their source name, source URL, retrieval time, call outcome and count-update time. This is a compiled provisional source, rather than the House Clerk's certified compilation used for earlier cycles.

- `data/us_2026_house_source.csv`: the 1,491 House candidate rows, filtered from the source's all-office CSV.
- `data/us_2026_house_fpp.csv`: app format, retaining snapshot and count timestamps and explanatory result notes.
- `data/us_2026_house_metadata.json`: attribution, source URLs, published manifest checksum, source checksums, snapshot totals and output hashes.

A winner requires an explicit source `outcome=won`; a leading vote count alone is insufficient. A race can still have `status=counting` after its winner is called, so the parser uses the candidate outcome. Candidate sums must reconcile to the reported race total, and a reported winner must lead the published count. All winner calls remain provisional.

Florida 10th has a reported winner but no published candidate vote totals in this snapshot. App-format zeros are structural placeholders, explicitly noted in the result and excluded from analysis. The district summary displays “Not published.” No turnout or registration estimates are invented. Alaska and Maine retain the source counts without reconstructing ranked-choice transfers.

## Geography and demographics

The 2026 map uses the official Census **120th Congress** [TIGERweb Legislative layer](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0). Three `ZZ` unassigned-water features are omitted, leaving exactly 435 numbered districts, joined by Census GEOID. Geometry is simplified at 0.005 degrees for display; invalid rings are repaired and Alaska's antimeridian coordinates unwrapped. This display simplification is not used to prove district continuity.

[Census's 120th Congress documentation](https://www.census.gov/programs-surveys/decennial-census/about/rdo/congressional-districts.120th_Congress.html) identifies nine states with new 2026 plans: **Alabama, California, Florida, Louisiana, North Carolina, Ohio, Tennessee, Texas and Utah**. Every seat in those states is conservatively excluded from the comparison; this does not claim every individual seat changed. The 2026 map also withholds their demographic estimates, because the available 2024 ACS snapshot describes the earlier districts. Their 2026 results remain visible.

Census confirms continuity for the other states, leaving **262 verified unchanged districts**. Missouri is included: the [Census correction](https://www.census.gov/programs-surveys/geography/technical-documentation/user-note/120cd.html) explains that the new plan was blocked and products were regenerated on or after 20 October 2026 using the unchanged 2022 plan. The downloaded TIGERweb data uses those corrected boundaries.

The chart holds the existing **2024 ACS one-year snapshot** fixed. It does not claim to measure 2026 demographics or demographic change. See the [demographic dictionary and methodology](us_house_2024_demographics.md) for its 42 indicators and margins of error. On the House 2024 map, the corresponding 2024 demographic estimates remain valid even where comparison eligibility is false.

## Comparison rules

`data/us_house_2024_2026_comparison.csv` contains one row per district, with eligibility flags and reasons. Its metadata records snapshot, geography policy, sample sizes and input hashes.

The matched sample requires unchanged boundaries, a source-reported 2026 winner, and named Democratic and Republican candidates with positive reported votes in both years. Alaska and Maine are excluded because ranked-choice count bases have not been standardized. The stricter sample additionally excludes multiple major-party candidates in either year. Both samples currently contain **236 districts**; the metric's missing estimates can reduce an individual chart further.

Share is D / (D + R), or R / (D + R); swing is the percentage-point difference. Both years and swing use the same matched sample. National Pearson, Spearman and within-state correlations weight districts equally and use demographic point estimates without propagating ACS uncertainty. These are descriptive district associations, not individual voting behavior or causal effects. Differences in turnout, candidates and national conditions also affect presidential-year versus midterm comparisons.

A provisional flip means a different 2024 elected party and 2026 source-reported winning party on verified unchanged boundaries. This can be known independently of share-comparison eligibility; for example, a called Maine seat can have a flip badge in its selection even though its share comparison is excluded. Redrawn and uncalled seats have blank flip flags.

## Reproduce and refresh

Validate committed artifacts offline with standard Python:

```sh
python3 scripts/build_us_house_2026.py --check
python3 scripts/test_us_house_2026.py
```

To fetch a fresh snapshot and rebuild (requires the repository's Shapely environment and network access):

```sh
.venv/bin/python scripts/build_us_house_2026.py --download
```

This downloads `manifest.json`, `races.csv`, the source dictionary and the TIGERweb query to ignored `tmp/us_house/2026/`. The source CSV must match the published manifest SHA-256. Running without `--download` rebuilds from that cache. Source URLs are recorded in metadata; the committed House-only source permits result/comparison reconstruction even without cached downloads.

After refreshing, inspect any eligibility or call changes, update the app's visible snapshot date/counts and this document, then rerun data and browser checks. Snapshot changes require review; the app never refreshes silently. Keep source credit and underlying source links when sharing derivatives.

```sh
.venv/bin/python scripts/test_house_2026_ux.py
.venv/bin/python scripts/test_house_demographics_ux.py
```

The 2026 browser check audits every plotted district and flip against the comparison download, checks Republican inversion, uncalled labels/colours, suppressed demographics on changed maps, mobile layout, shared URLs and comparison history.
