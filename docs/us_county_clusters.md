# County voting groups

Open [Counties that vote alike](../app/county-clusters.html). The page compares
**3,103 county reporting areas across 48 states** in the presidential general
elections of **2008, 2012, 2016, 2020 and 2024**.

It starts with four groups. Choose 2, 3, 4, 5 or 7 for broader or finer
groups. Selecting a state zooms the map and filters the county picker and
membership lists. **Groups and their average lines are always calculated
nationwide**, even when one state is shown. Select a county to see its five
election results, the 2024 winner and how Democratic support changed since
2008. Choose distinct group colours or a blue-to-red scale showing each group’s average party leaning.

Links from the homepage, presidential results and state groups lead here.
Selections survive reload and browser back/forward and can be shared, for
example `app/county-clusters.html?k=4&region=Michigan&county=Wayne+County%2C+Michigan`.
Membership lists initially show twelve counties plus the selected county when
needed, with a button to show the complete list. Exact votes, chart percentages
and statistical details can be expanded separately.

## Comparable places and source limitations

Inputs are the existing `data/us_YEAR_president_county_fpp.csv` files. These
are **compiled county returns**, rather than the official-source statewide
files used for state groups. Their source fields identify MIT Election Data
and Science Lab historical returns for 2008–2016 and the repository's public
county-results compilation for 2020–2024. See `scripts/build_us_presidential.py`
for their existing import rules. This feature does not download new results.

The builder requires positive Democratic and Republican totals, three distinct
party categories, nonnegative Other votes, exact reconciliation to formal
votes and the same reporting-area identifiers in all five elections.

- Connecticut is excluded throughout: 2024 uses nine planning regions, while
  previous years use eight counties. No votes are assigned across mismatched
  boundaries.
- Alaska is excluded because these input files contain a statewide placeholder,
  not county returns. Washington, DC is excluded from this county comparison.
- Historical Shannon County, South Dakota (`46113`) joins to Oglala Lakota
  County (`46102`), following the existing county demographics builder.
- Joins use identifiers, not spelling: historical La Salle Parish matches the
  latest LaSalle Parish name. Display names and map boundaries come from 2024.
- Existing source combinations of Kansas City/Jackson County and Bedford
  city/Bedford County are retained. These are county reporting areas and county
  equivalents; the map is not an independent reconstruction of every historical
  administrative boundary. No missing votes are estimated.

Every included reporting area has a matching feature in
`data/us_president_2024_county_boundaries.geojson`. Hawaii uses an inset; outlying
islands are omitted for legibility. Missing areas are explained above the map.
The downloadable metadata lists excluded source areas and source-file hashes.

## How groups are calculated

Each county has five values: `100 × Democratic / (Democratic + Republican)`.
Third-party votes are excluded from this percentage. Each county and election
has equal weight; large counties do not outweigh small ones. The group average
is an average of county percentages, not a pooled vote total.

Ward hierarchical clustering uses Euclidean distances between these histories.
Inputs retain their original percentage scale; they are not standardized within
a county. This groups similar political leaning, with changes over time also
contributing. It is not a separate analysis of swings or individual voters.
The county and state builders share the same model-fitting function.

Group numbers run from lower to higher five-election average Democratic support.
Plain descriptions use that average: below 30% very strongly Republican; 30% to
below 40% strongly Republican; 40% to below 47% leans Republican; 47% through 53%
closely split; above 53% through 60% leans Democratic; above 60% through 70%
strongly Democratic; above 70% very strongly Democratic. These describe the
**group average**, not every county or election. Group membership can change
when the number of groups changes. Results describe history, not a forecast.

| Groups | Separation (silhouette) | Stability (mean adjusted Rand) | Group sizes |
| --- | ---: | ---: | --- |
| 2 | 0.554 | 0.448 | 2,366 / 737 |
| 3 | 0.446 | 0.614 | 1,131 / 1,235 / 737 |
| 4 | 0.421 | 0.582 | 1,131 / 1,235 / 479 / 258 |
| 5 | 0.359 | 0.519 | 321 / 810 / 1,235 / 479 / 258 |
| 7 | 0.321 | 0.489 | 321 / 810 / 751 / 484 / 479 / 135 / 123 |

Two groups has the highest separation score; three has the highest stability. Four is
the initial exploration view, not a claim of the best statistical fit.
Separation is the average silhouette. Stability compares the complete model
with five refits, leaving out one election each time, using adjusted Rand
agreement. The JSON also stores each county's mean Jaccard overlap of group
peers across those refits. None of these scores is a probability or forecast.

## Rebuild and check

```bash
.venv/bin/python scripts/build_us_county_clusters.py
.venv/bin/python scripts/test_us_county_clusters.py
.venv/bin/python scripts/test_county_clusters_ux.py
```

Outputs are `data/us_county_presidential_clusters.json` (counts, votes, all
five models, source hashes, sensitivity checks and Ward tree) and
`data/us_county_presidential_clusters.csv` (15,515 county/model rows). There is
no new browser dependency or server-side calculation.

The numerical audit independently checks all 15,515 county-election joins,
source vote accounting, identifiers, boundary coverage, SciPy Ward partitions,
every silhouette, group averages, five sensitivity refits and CSV exports.
Browser checks verify every county map colour in all five models, state zoom,
exact vote tables, Hawaii, keyboard selection, complete group lists, shareable
URLs, reload/back navigation, invalid inputs and 320/390/768px layouts. Existing
state-page numerical and browser checks also cover the shared code.

The **Map colours** selector offers distinct group colours (the default) or
**Blue to red · party leaning**. Blue means higher Democratic support, red
means higher Republican support, and grey marks an even split. The same colour
applies to each group's map areas, chart line, legend and membership card.
Shades use the group's five-election average, not the selected area's 2024
result. The scale interpolates from grey at 50% Democratic support to blue at
75% and red at 25%, clamping beyond those endpoints. Colour choices are stored
in shareable URLs with `colors=party` and restored on reload and back/forward.

## One county, one dot

[County dots](../app/county-dots.html) shows every included county as one equal
size dot, starting with five existing groups. The “By group” view packs dots
in blocks so the unequal group sizes are visible. The “Voting patterns” view
plots five-election average Democratic support against the 2008–2024 change
in Democratic support, in percentage points. This is an interpretable two-axis
view, not a projection preserving distances between the five-value histories;
dots can overlap. County selection is also available in a named picker.

Controls choose 2, 3, 4, 5 or 7 groups, state, group, county/state search and
the same two colour schemes as the map. Hover shows county names; click or
keyboard selection opens the voting history. Arrow keys browse matching
counties. Filters change which dots appear, not the existing assignments.
The side panel links the selected county to its map view. View, filters, colours
and selection survive reload and browser history through shareable URLs.

This page does **not** rebalance groups. It loads the same existing model JSON
as the map. Each county, rather than each voter, receives one dot.

Browser checks: `.venv/bin/python scripts/test_county_dots_ux.py`.

## Methodology option: political bands

The methodology selector offers the original **Voting similarity** groups and
**Political bands** on the state map, county map and county dot page.
Similarity remains the default. Political bands are a threshold classification,
not a refit or rebalancing of the Ward models. Both use the same five elections.

Each place's score is the unweighted mean of its Democratic two-party percentage
in 2008, 2012, 2016, 2020 and 2024. Scores are calculated from the stored raw vote
counts to avoid rounding across cutoffs. Votes are not pooled across elections.

| Bands | Labels and average Democratic-share cutoffs |
| --- | --- |
| 2 | Republican <50%; Democratic ≥50% |
| 3 | Republican <45%; Swing / competitive 45–55% inclusive; Democratic >55% |
| 4 | Republican <40%; Lean Republican 40% to <50%; Lean Democratic 50–60% inclusive; Democratic >60% |
| 5 | Republican <40%; Lean Republican 40% to <45%; Swing / competitive 45–55% inclusive; Lean Democratic >55% through 60%; Democratic >60% |

These cutoffs are chosen definitions, not official electoral classifications.
“Swing / competitive” describes an average close to an even split; it does not
require a county to have changed winners. An exact 50% average goes in the
Democratic half for two and four bands as an explicit boundary convention,
not a claim that Democrats won an election. Empty categories remain visible
with no invented averages. Sizes follow the vote distribution and need not
be equal; this option may be more uneven than the similarity groups.

The shared `app/voting-methods.js` supplies assignments, labels and group means
to all three views. Existing source data and Ward models are unchanged. The
method persists in URLs as `method=bands`, including selected-county links
between maps and dots. The method explanation displays the exact current
cutoffs; Ward separation/stability diagnostics are hidden for bands.

“Download bands” exports the active number of bands for every included place,
with methodology, label, group, five election shares and average support.
The similarity download retains its existing model export.

Checks: `node scripts/test_voting_methods.cjs` verifies all cutoff boundaries,
empty categories, raw-count precision, equal election weighting, every actual
state/county assignment and centroid for 2, 3, 4, 5 and 7 bands, exports and
unchanged Ward models. `.venv/bin/python scripts/test_political_bands_ux.py`
verifies all three views, exact colours, filters, method switches, cutoffs,
downloads, shared links, reload/history and mobile layouts.

### Linked map on the dot page

The county dot page includes an interactive county map above the dot views.
Both use the same selected methodology, group count, colour scheme, state,
group filter and county search. Selecting a county on either view highlights
it in both and updates the shared history panel. Keyboard arrows browse the
matching counties while keeping focus in the current map or dot view.

The state selector zooms the map to that state. Counties excluded by a search
or group filter remain pale for geographic context and cannot be selected
until they match the filters. The map includes the same 3,103 comparable
county reporting areas as the dots; Hawaii uses an inset in the national view.
Alaska, Connecticut and DC remain excluded. Changing the state, methodology
or filters never recalculates a different subset-based grouping.

`app/county-map.js` reads existing 2024 boundary geometry. The map does not
introduce a new data source or external browser dependency. Checks in
`scripts/test_county_dots_map_ux.py` verify every polygon and dot colour for
both methodologies, 2, 3, 4, 5 and 7 groups and both palettes, selections,
keyboard access, filters, empty results, Hawaii, reload/history and phone
layouts including touch selection.

### Counties / Population dot toggle

The group dot blocks offer **Counties** (one dot per county, the default) and
**Population** (resident population, keeping the full-view budget at **3,103
equally sized dots**). Population mode does not alter political assignments,
cutoffs, similarity models, geographic polygons or county voting averages.

Population comes from the repository's 2020–2024 ACS five-year estimates,
variable `B01001_001E`, matched by constituency identifier to all 3,103 included
reporting areas. The extracted snapshot contains **329,880,924 residents**,
so each population dot represents approximately **106,310 residents**. It
includes children and nonvoters, not just voters, and is not a 2024-only count.
The scope still excludes Alaska, Connecticut and DC. Existing source reporting
combinations are retained. `data/us_county_cluster_population.json` records
identifiers, source hashes, coverage, the total and provenance. Build it with
`.venv/bin/python scripts/build_county_cluster_population.py`.

First, allocate the fixed dot budget to groups in proportion to their resident
populations using largest remainders: floor each exact quota, then award the
remaining dots to the largest fractional remainders, with stable identifier
ties. Then allocate each group's dots among its counties using the same rule.
This preserves exactly 3,103 dots and group quotas rounded to whole dots. All
dots have the same size and approximate resident value. Counties can receive
multiple dots or zero; no minimum of one is imposed, because that would defeat
population proportions. A clicked population dot is attributed to a county
after rounding, not a claim about individual residents' votes.

Group headers and legends show population totals for the matching counties.
Headers show percentages of the included
population, plus allocated dot counts. Filtering displays the matching counties'
already allocated dots, retaining the same nationwide scale rather than
redistributing a fresh 3,103 dots to each search or state. Thus a filtered view
may have fewer dots, or no dots for a very small county. Such counties remain
selectable on the map and in the named picker, with a clear scale explanation.
Population mode uses the grouped blocks; the individual-county scatter view
becomes available again when switching to Counties. Selection highlights all
population dots attributed to the selected county and its matching map polygon.

The unit is preserved in URLs with `measure=population`, reload and browser
history. Reset restores Counties. Arithmetic/source checks run with
`node scripts/test_population_dots.cjs`; browser checks run with
`.venv/bin/python scripts/test_population_dots_ux.py`. They cover all eight
method/group-count combinations, exact source joins and totals, integer
apportionment, proportional group quotas, equal-size dots, both colour schemes,
selection and keyboard access, small counties, filters, history and phone
layouts. The existing county map/dot browser tests check the default mode.

### Seven groups

The group selector offers **2, 3, 4, 5 or 7** groups; six is not offered.
Seven works for voting similarity and political bands, on maps and county
dots, including the population toggle. Similarity uses a seven-way cut of
the same Ward model. The political bands extend the five-band definitions:

| Label | Five-election average Democratic support |
| --- | --- |
| Strong Republican | Below 30% |
| Republican | 30% to below 40% |
| Lean Republican | 40% to below 45% |
| Swing / competitive | 45% through 55% |
| Lean Democratic | Above 55% through 60% |
| Democratic | Above 60% through 70% |
| Strong Democratic | Above 70% |

These are descriptive cutoffs rather than predictions or official categories.
Seven-band views can include empty categories, especially at state level;
empty categories are kept without inventing averages. Population mode still
uses exactly 3,103 full-view dots and the same resident snapshot.

### Demographic scatterplot

The county dot page includes a **Demographics** view. Each dot represents one
county. The horizontal selector offers 42 existing demographic measures, with
college graduates (bachelor's degree or higher, age 25+) selected initially.
The vertical selector offers presidential support in 2008, 2012, 2016, 2020 or
2024, the five-election average, or change between elections. Either party can
be selected. Support uses the two-party vote share; swing is percentage points.
Colours retain the chosen voting groups and palette. Map, search, state/group
filters, county details and keyboard selection remain linked.

Demographics come from the existing 2020–2024 ACS five-year county extract.
Older elections use this same snapshot. The measure's population and units are
shown beside the controls; dollar amounts are in 2024 inflation-adjusted dollars.
The chart shows estimates without margins of error. Missing values are omitted
from the chart, counted explicitly, and remain available through the map and
county picker. There are 12 missing values across all measures. County-level
relationships do not establish causes or describe individual voters.

Percentage demographic axes span 0–100; other demographic axes begin at zero
and extend to a rounded nationwide maximum. Voting support spans 0–100, while
swing uses a symmetric nationwide range around zero. Filtering preserves these
scales. Demographic mode always uses one county per dot; the Population toggle
returns to the grouped population view.

Rebuild the compact extract with
`.venv/bin/python scripts/build_county_cluster_demographics.py`.
Validate source joins, values and voting calculations with
`node scripts/test_county_scatter_demographics.cjs`, and browser interactions,
plotted positions, missing data and mobile layouts with
`.venv/bin/python scripts/test_county_demographic_scatter_ux.py`.
