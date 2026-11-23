# Boston mayoral voting-history groups

Open [Boston voting groups](../app/boston-history-dots.html). The page links a
map, one-precinct-one-dot groups, an election-comparison scatterplot and each
precinct's native results. It defaults to **three groups** and the conservative
**map agreement check**. Options are 2, 3, 4, 5 and 7 groups. Ward, group and
code/name filters, keyboard selection and shareable URLs work across views.

## What is compared

Each precinct contributes three percentages, equally weighted:

- Marty Walsh / (Walsh + John Connolly), 2013.
- Marty Walsh / (Walsh + Tito Jackson), 2017.
- Michelle Wu / (Wu + Annissa Essaibi George), 2021.

These are reported counts under matching codes from the official Boston PDFs;
[the result documentation](boston_mayor.md) describes their reconciliation.
Other candidates, named/grouped write-ins and blank ballots do not enter the
two-candidate shares. They remain available on the reported-results page.
No votes are allocated across boundaries. Ward 1 Precinct 15 has zero votes in
2017, so **254 of 255** precincts have complete numerical histories.

The method is Ward hierarchical clustering on Euclidean distances between the
three percentages. Every precinct has equal weight, independently of turnout
or population. Reversing any candidate axis preserves all distances: this is
not an assertion that Walsh and Wu represent the same side. No left–right
average, Democratic/Republican label, equal-size constraint or political band
is imposed. Groups are ordered by average Wu support only to keep their display
predictable. Their distinct colours identify groups, not parties.

The scatterplot lets the user choose any election on either axis. The same
three-election group assignment colours the points. Each group's displayed
profile is the unweighted mean of member precinct percentages, not the share
of pooled votes. Group summaries use the leading main candidate in each year,
with 45–55% described as a close split. These are descriptive, not predictions,
individual voter histories or permanent political blocs.

## Boundary screening and its limits

Matching codes are insufficient evidence of identical geography. MassGIS
[documents Boston boundary revisions in 2016](https://www.mass.gov/info-details/massgis-data-2012-wards-and-precincts).
A [City map](https://www.boston.gov/sites/default/files/file/2022/03/Council-Districts-citywide-2016.pdf)
references 2018 ward/precinct boundaries with 2019 revisions. These statements
alone do not distinguish legal electoral changes from cartographic corrections.

The screen compares the raw October 2017 City GIS geometry, projected to
EPSG:26986, with two pinned geometry extracts in the same projected CRS:

1. [MGGG's processed 2012–2016 Massachusetts precinct data](https://github.com/mggg-states/MA-shapefiles),
   restricted to Boston. This source has 254 areas and no separate `0502A`.
2. [Census 2020 TIGER/Line voting districts](https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/tl_2020_25_vtd20.zip),
   restricted to Suffolk County codes matching Boston's code pattern. It has
   255 areas, including `2023` but no `1823`. No guessed correction is made.

For each same-code comparison, agreement is the smaller of
`intersection area / 2017 area` and `intersection area / comparison area`.
Both source comparisons must reach **99%**, and all three elections must have
usable main-candidate votes. Invalid shapes are made valid before comparison;
raw 2017 geometry is used rather than the simplified display file. A missing
code fails the screen. No manual exemptions or threshold changes are applied.

**38 precincts pass.** The default groups those 38 and leaves the other 217
grey and selectable. This subset is small and **not representative of Boston**.
Passing is evidence of close map agreement, **not verification of election-day
boundaries**. Failing does not prove voters moved between precincts: the maps
have different purposes, coastlines, processing and potential corrections.
Neither historical comparison is an independently certified 2013/2021 map.

The **All matching codes · provisional** option groups the 254 complete
same-code histories and leaves the zero-vote precinct grey. This intentionally
relaxes the map agreement screen, with a prominent warning. It must not be
interpreted as an exact comparison of unchanged territory or the same voters.
The per-precinct details show both shape coverage measurements and reasons
for exclusion under the active rule.

## Exploratory findings

For all 254 numerical histories, the three-group trial gives:

| Precincts | Walsh 2013 | Walsh 2017 | Wu 2021 |
| ---: | ---: | ---: | ---: |
| 42 | 66.1% | 80.4% | 41.8% |
| 73 | 36.0% | 71.8% | 63.7% |
| 139 | 57.7% | 54.5% | 75.1% |

Three groups have the highest silhouette score among the tested counts
(0.391, versus 0.346 for two and 0.325 for four). This is a useful starting
point, not proof of three natural political blocs. Omitting an election
changes the partition substantially (adjusted Rand agreements 0.396–0.586).
The screened subset has different memberships and profiles: 3, 9 and 26
precincts at three groups. Its smaller first group reinforces that these
results should remain exploratory.

## Sources, attribution and reproduction

Pinned extracts are under `data/sources/boston/`. The accompanying
[history source manifest](../data/sources/boston/history_geometry_sources.json)
records archive URLs, archive/extract SHA-256 digests, source CRS, extraction
rules, attribution and licence. It retains only geometry and reporting codes,
not the MGGG election or demographic attributes. MGGG's source README and
licence are retained alongside it. The extracted MGGG geometry database is
provided under the Open Database License 1.0, with individual contents under
the Database Contents License; see [its licence](../data/sources/boston/mggg_LICENSE.md).
The extracts preserve full polygon precision and are not re-downloaded during
normal builds. Original ZIP archives are unnecessary for an offline rebuild.

```bash
python scripts/build_boston_mayor.py
python scripts/build_boston_history_clusters.py
python scripts/test_boston_history_clusters.py
python scripts/test_boston_history_dots_ux.py
```

Dependencies are listed in `requirements.txt`. The cluster builder pins source
hashes, recomputes all geometry screens, checks finite shares and generates
both coverage models for every group count. It also records silhouette and
leave-one-election-out agreement as inspection metrics.

The independent validator checks votes against the result CSVs, all source
hashes, every overlap measurement and exclusion, and every partition against
scikit-learn's independent Ward implementation. It checks centroids, sizes,
silhouette scores and invariance to reversing the candidate axes. Browser
checks verify all ten model/coverage combinations, every dot/map colour,
scatter coordinates, excluded/zero-vote areas, linked selection, keyboard
navigation, URL restoration, filters and 320/390/768px layouts.
