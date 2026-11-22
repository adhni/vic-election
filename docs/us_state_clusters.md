# State presidential voting clusters

Open **[State voting clusters](../app/state-clusters.html)**, also linked from
the homepage and every historical U.S. presidential results entry. The initial
view uses four groups and selects Michigan. Controls compare 2, 3, 4, 5 or 7
groups, inspect any state, and highlight a group's membership. The map,
selected-state vote table, voting profiles and membership buttons are linked.
Selections are shareable in URLs such as
`app/state-clusters.html?k=3&state=California&group=3`; browser back/forward and
reload restore the view. Alaska and Hawaii use map insets; outlying Hawaiian
islands are omitted for legibility. All 50 states are selectable.

## Inputs

There are **50 states × five elections = 250 state-election observations**:
2008, 2012, 2016, 2020 and 2024 presidential general elections. Each state's
feature vector contains five percentages:

```text
100 × Democratic votes ÷ (Democratic votes + Republican votes)
```

The build reads the repository's official-source statewide presidential CSVs:

```text
data/us_2008_president_state_fpp.csv
data/us_2012_president_state_fpp.csv
data/us_2016_president_state_fpp.csv
data/us_2020_president_state_fpp.csv
data/us_2024_president_state_fpp.csv
```

Their declared source is the [Federal Election Commission election-results
compilation](https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/).
The builder requires official status, identical 50-state coverage, and positive
Democratic and Republican vote totals in every state-election. It records
source-file SHA-256 hashes and the exact D/R counts in the output.

DC is excluded to match a 50-state analysis. Third-party votes are excluded
from the two-party denominator. Senate, governor, House, county, demographic
and provisional 2026 results are not inputs.

States have equal weight, regardless of population. Elections have equal
weight. Percentages use the same scale, and are not standardized within states:
doing so would remove much of the partisan-leaning signal. This setup primarily
groups similar partisan levels, with changes over time contributing to distance.
It is not a separate clustering of electoral swings.

## Method and model comparison

The method is Ward agglomerative hierarchical clustering with Euclidean distance
between the five-value vectors, implemented with pinned scikit-learn 1.6.1.
States are sorted alphabetically before fitting. For presentation, cluster IDs
are ranked by each group's mean Democratic share across all states and years,
from lower to higher. Political labels such as "swing" or "safe" are not imposed.
Group numbers and colours do not represent fixed membership across different
values of k.

| Groups | Mean silhouette | Mean leave-one-election-out adjusted Rand | Group sizes |
| --- | ---: | ---: | --- |
| 2 | 0.570 | 0.914 | 21, 29 |
| 3 | 0.496 | 0.838 | 21, 17, 12 |
| 4 | 0.424 | 0.835 | 11, 10, 17, 12 |
| 5 | 0.389 | 0.769 | 11, 10, 6, 11, 12 |
| 7 | 0.376 | 0.860 | 4, 7, 10, 6, 11, 7, 5 |

Two groups performs best on both displayed aggregate diagnostics among the
five tested cuts. Four remains the initial view requested for exploration,
clearly labelled as a starting view rather than a statistically optimal count.
These scores do not establish a single true number of electoral groups.

At four groups the observed profiles are:

| Group | States | Average Democratic two-party share across five elections |
| --- | ---: | ---: |
| 1 | 11 | 35.1% |
| 2 | 10 | 42.2% |
| 3 | 17 | 51.7% |
| 4 | 12 | 61.8% |

Solid chart lines show the arithmetic mean of state shares in a group for each
election, not a population-weighted or pooled-vote total. A dashed black line
shows the selected state's actual history. Exact chart values are also in a
table, accessible on narrow screens through horizontal scrolling.

## Separation and stability

The silhouette coefficient compares a state's mean distance to its own group
with its mean distance to the nearest other group. The displayed separation
score averages those state scores; higher indicates stronger separation on
these inputs. Selected-state scores can be negative if a state lies closer to
another group on average. See the [silhouette definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html).

For each k, the builder refits five times, omitting one election at a time.
Adjusted Rand measures agreement with the complete five-election partition,
independent of numeric group labels. The model card shows the mean of those
five comparisons. The sensitivity table exposes each comparison individually;
metadata also records the minimum. This is a sensitivity check, not a sampling
confidence interval.

Selected-state **peer stability** is computed separately. For each refit, take
the set of other states grouped with the selected state and compare it with
the original peer set using Jaccard overlap: intersection size divided by union
size. Average those five overlaps and store in the downloadable model data. It is not a
probability that the state "belongs" to a group.

The data are aggregate election returns. They cannot establish individual voter
behaviour or causes, and these groupings are not forecasts. Political patterns
are continuous; states near a boundary may change groups when the model changes.
The test range is restricted to 2–5 or 7 groups rather than claiming an exhaustive
search of clustering choices. See the [Ward clustering documentation](https://scikit-learn.org/stable/modules/clustering.html#hierarchical-clustering).

## Outputs, rebuild and verification

- `data/us_state_presidential_clusters.json` contains vote inputs, source
  hashes, software versions, all five model cuts, centroids, assignments,
  scores, sensitivity results, and the Ward linkage tree. `ward_leaf_order`
  specifies the tree's leaf identifiers.
- `data/us_state_presidential_clusters.csv` contains **250 state/model rows**:
  50 states × five model cuts. Each row contains its five election shares,
  assignment, silhouette and peer stability.

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_us_state_clusters.py
.venv/bin/python scripts/test_us_state_clusters.py
.venv/bin/python scripts/test_state_clusters_ux.py
.venv/bin/python scripts/smoke_static_app.py
```

The browser loads precomputed data; there is no server-side clustering or new
runtime dependency. The Python dependency is needed only to rebuild or audit
the models. The build is deterministic for the recorded sources and software.

The numerical audit independently reconstructs all 250 observations, compares
the scikit-learn partitions with SciPy's Ward tree cuts, calculates silhouettes
from pairwise distances, verifies every centroid and state membership,
recomputes all leave-one-election-out comparisons and peer overlaps, checks the
CSV export, and verifies an identical rebuild in a temporary directory.

Browser checks cover all five model cuts and every state map colour, selection
through map/keyboard/controls, group highlighting, exact vote profiles,
shareable URLs, reload/back navigation, invalid URL recovery, sensitivity rows,
mobile layouts at 320/390/768px, and the homepage/explorer entry points.

The page opens with the map, plain group descriptions and a selected state's election history. Statistical comparisons are in the collapsed “How this works” section. Group descriptions use the five-election mean Democratic share: below 30% very strongly Republican; 30% to below 40% strongly Republican; 40% to below 47% leans Republican; 47% through 53% closely split; above 53% through 60% leans Democratic; above 60% through 70% strongly Democratic; above 70% very strongly Democratic. These labels summarise group averages, not each member state or future outcomes.

The **Map colours** selector offers distinct group colours (the default) or
**Blue to red · party leaning**. Blue means higher Democratic support, red
means higher Republican support, and grey marks an even split. The same colour
applies to each group's map areas, chart line, legend and membership card.
Shades use the group's five-election average, not the selected area's 2024
result. The scale interpolates from grey at 50% Democratic support to blue at
75% and red at 25%, clamping beyond those endpoints. Colour choices are stored
in shareable URLs with `colors=party` and restored on reload and back/forward.

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
