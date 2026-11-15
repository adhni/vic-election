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

**Flipped seats have a larger dot with a dark outline directly on the scatterplot**, explained by the chart key. A small **Flipped to Democrat/Republican** badge also identifies a changed winning party in the selected district, chart/map tooltips, and any affected swing ranking row. It compares the official elected parties in the 2022 and 2024 general-election snapshots on verified unchanged boundaries, independently of two-party share eligibility. Large swings in held seats do not receive a badge; unverified changed-plan districts remain unlabelled. This does not track intervening by-elections or party switches.

## Earlier period: 2020 → 2022

The **Comparison** dropdown switches between 2022 → 2024 and 2020 → 2022 on either supported House election page. The same map, chart, rankings, outlined flip markers, party controls and share/year outcomes update together. Shared URLs preserve `demographicPeriod=2020-2022`. The map geometry and full election results still follow the main election picker; the chart note names that year. Demographics remain the fixed 2024 ACS snapshot.

The [individual boundary audit](../data/us_house_2020_2022_boundary_audit.csv) checks **all 435 districts**, rather than excluding whole states. For 421 districts outside North Carolina it compares the actual sets of 2020 Census blocks in the [2020 Block Assignment Files](https://www.census.gov/geographies/reference-files/2020/geo/block-assignment-files.html) against the [118th Congress block equivalencies](https://www.census.gov/geographies/mapping-files/2023/dec/rdo/118-congressional-district-bef.html). Each new district is checked against every previous district in its state, so a changed district number does not prevent a match. Membership hashes, added/removed block counts and overlap percentages are retained as evidence.

North Carolina needs its actual 2020 election map: the Census baseline describes the 116th Congress, but NC changed its map for the 117th. For its 14 current districts the audit compares the [legislature's enacted-2019 map](https://www.ncleg.gov/Redistricting) with the Census 2022 polygons. Even the best earlier-district intersection/union overlap is below 95% in each case, confirming material changes; none is accepted as unchanged.

The direct audit finds **six exact matches**, all at-large: Alaska, Delaware, North Dakota, South Dakota, Vermont and Wyoming. The count happens to equal the previous conservative state-screen result, but now comes from individual checks. Similar is not identical: Hawaii 2nd added 45 blocks; Wisconsin 7th added 214 and removed 3. There is no overlap threshold that silently treats a small change as unchanged, and no reconstructed votes. Whole-block files represent tabulation plans rather than every possible legal split; the documented split Colorado block affects districts 07/08, neither of which matches its earlier membership.

The six matches also retain the geography used for the fixed 2024 demographic snapshot. Audit [metadata and source hashes](../data/us_house_2020_2022_boundary_audit_metadata.json) record the evidence and limits. Rebuild with `.venv/bin/python scripts/build_us_house_boundary_audit.py --download`; with inputs cached, `--check` recomputes the audit without network access.

Alaska is excluded from share comparisons because its count bases have not been standardized. North Dakota lacks a named Democratic candidate in 2022, and South Dakota lacks both-party matchups. This leaves **three comparable seats: Delaware, Vermont and Wyoming**, in both baseline and sensitivity views. The archived view labelled this tiny sample explicitly; it does not represent national patterns. Within-state correlation is unavailable because each retained state has one district.

Winner flips continue to use actual elected parties on verified unchanged boundaries, independently of share eligibility. Alaska therefore correctly shows a flip to Democrat for 2020 → 2022 when selected, even though it has no plotted swing. None of the three plotted seats flipped in this period.

The [2020–2022 comparison CSV](../data/us_house_2020_2022_comparison.csv) and [metadata](../data/us_house_2020_2022_comparison_metadata.json) use the same 435-district display grid as the current demographic data. Historical districts without a matching 2020 code have blank historical values and an explicit exclusion; no votes are invented for newly created seats. Redrawn same-number districts retain source values for audit but have blank comparable swings and flip flags.

```sh
python3 scripts/build_us_house_comparison.py --period 2020-2022
python3 scripts/build_us_house_comparison.py --period 2020-2022 --check
```

## 2016–2018 comparison

The Comparison selector also offers **2016 → 2018**, reaching the earliest House results in this repository. It selects the **House 2018 map** and reuses the historical 2021 ACS snapshot on 116th Congress districts, with the same 39 demographic measures, both-party chart controls, fitted axes, rankings and flip outlines. House 2016 also supports this view. A shared House 2018 URL retains its chosen comparison, since that election belongs to both historical periods.

[Census's 116th Congress documentation](https://www.census.gov/programs-surveys/decennial-census/about/rdo/congressional-districts.116th_Congress.html) identifies new boundaries for Colorado, Minnesota and Pennsylvania in the 2018 cycle, and explicitly confirms no change from 2016 for other states. We conservatively exclude all 33 seats in those three states, without claiming each individual district changed. Of **402 verified unchanged districts**, **307** pass the both-party contest and count-basis rules, or **305** in the stricter sample. Changed-plan districts are grey and unplotted. On the House 2016 map their demographic estimates are also withheld because the 116th Congress snapshot describes the later boundaries.

The fixed **2021** demographic snapshot was measured after both elections. It supports descriptive district associations, not demographic change, individual voting behavior or causal claims. No additional demographic vintage is mixed into the two historical periods.

- [2016–2018 comparison CSV](../data/us_house_2016_2018_comparison.csv).
- [Boundary evidence, eligibility counts and source hashes](../data/us_house_2016_2018_comparison_metadata.json).

```sh
python3 scripts/build_us_house_comparison.py --period 2016-2018
python3 scripts/build_us_house_comparison.py --period 2016-2018 --check
```

## 2018–2020 comparison

The Comparison selector offers **2018 → 2020** in place of the sparse 2020–2022 view. Selecting it also selects the **House 2020 map** so old district numbers are never joined to the post-redistricting map. House 2018 also supports the historical comparison. Switching back selects House 2024. Existing chart controls, flip outlines, rankings, downloads and shared links work in both periods.

[Census confirms](https://www.census.gov/programs-surveys/decennial-census/about/rdo/congressional-districts.117th_Congress.html) North Carolina was the only state to change congressional districts between the 116th and 117th Congresses. Excluding all 13 North Carolina seats leaves **422 verified unchanged districts**. The same both-party contest and count-basis rules leave **359 comparable districts**, or **355** in the stricter sample. Seat flips compare actual elected parties in the two general elections, not intervening changes of party or special elections.

The historical chart uses a fixed **2021 ACS 1-year snapshot on 116th Congress districts**, rather than joining 2024 demographics onto same-number historical seats. Its geography identifiers are `5001600US…`; the original 2024 data use `5001900US…`. Both periods use the same metric formulas and published 90% margins of error. The 2021 snapshot is measured **after** the elections and is descriptive, not a measure of demographic change. It offers 39 measures: the three B29001 citizenship-age metrics used for 2024 are unavailable in that form in the older release and are omitted. Missing language-table estimates are retained as gaps.

North Carolina's 116th ACS data do not describe its redrawn 2020 seats. Those seats are grey and unplotted; selecting one on the 2020 map also withholds its demographic estimate. The raw extract retains the actual Census geography and values for audit.

Public table-based 2021 bulk files require no Census API key. National inputs are cached under `tmp/us_house_demographics_2021`; only district extracts, metric definitions, source flags and provenance hashes are committed. The [standard 2020 ACS 1-year product was not released](https://www.census.gov/programs-surveys/acs/data/experimental-data.html); using 2021 keeps the public source format and historical geography explicit. This is a different demographic vintage from the 2022–2024 chart, so correlations across the two periods are not controlled for an identical snapshot.

- [2018–2020 comparison](../data/us_house_2018_2020_comparison.csv) and [metadata](../data/us_house_2018_2020_comparison_metadata.json).
- [Historical demographic metrics](../data/us_2021_house_demographics.csv), [raw estimates/MOEs](../data/us_2021_house_demographics_acs.csv), [source flags](../data/us_2021_house_demographics_flags.csv), and [provenance and definitions](../data/us_2021_house_demographics_metadata.json).

```sh
python3 scripts/build_us_house_demographics.py --year 2021
python3 scripts/validate_us_house_demographics.py --year 2021 --cache tmp/us_house_demographics_2021
python3 scripts/build_us_house_comparison.py --period 2018-2020
python3 scripts/build_us_house_comparison.py --period 2018-2020 --check
```

The earlier 2020–2022 files below are retained as an archival audit and are no longer an option in the app.

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
