# NYC three-election voting groups on 2021 reporting areas

Open `app/nyc-history-dots.html` locally. The page parallels the federal county
dot view: **Voting similarity** or **Political bands**, 2, 3, 4, 5 or 7 groups,
blue-to-red or distinct group colours, grouped dots or a voting-pattern scatter,
and a linked map, borough filter, text search, named area picker and keyboard
navigation. URLs preserve these controls and the selected area.

Every dot represents one **2021 mapped precinct reporting area**. There are
5,697 mapped areas: **5,145** have usable three-election histories and enter the
groups; **552** remain grey, ungrouped and selectable with exclusion reasons.
The grouped areas contain **92.88% of reported 2021 two-side votes**. The voting
pattern scatter displays only complete histories; incomplete areas stay on the
map and in the picker. This is a count of geographic areas, not voters.

## Reported versus estimated

The 2021 candidate totals are preserved exactly. The other two elections are
**area-weighted estimates** on the 2021 map, including 2017, which largely
aligns geographically. They are not certified historical returns for those
target areas. No missing precinct geometry is reconstructed or invented.
Instead, unusable sources and targets are flagged and withheld from grouping.
The [directional audit](nyc_reference_map_comparison.md) explains the map choice.

| Election | Democratic side | Opposing side |
| --- | --- | --- |
| 2017 | Bill de Blasio | Nicole Malliotakis |
| 2021 | Eric Adams | Curtis Sliwa |
| 2025 | Zohran Mamdani | Andrew Cuomo + Curtis Sliwa |

Cuomo + Sliwa is an explicitly requested analytical combination, not a
classification of Cuomo's Fight and Deliver line as Republican. Candidate
fusion lines are already combined in the reported source extracts. Other
candidates and write-ins are allocated and accounted for separately but excluded
from two-side percentages. The raw single-election page remains available at
`app/nyc-precinct-dots.html`, with candidate-level reported counts.

## Crosswalk and coverage

1. Project the simplified map snapshots into EPSG:32618 (metres).
2. Intersect source reporting areas with 2021 targets **within the same borough**.
   Ignore intersection fragments of 0.01 square metres or smaller.
3. Withhold a source area's entire vote total if its combined-component geometry
   is known to be incomplete, its intersection with the union of target areas
   covers less than 99% of its mapped area, or summed target intersections
   exceed 101% of its area (overlapping-target warning).
4. For accepted sources, distribute each vote category proportionally to target
   overlap area. Normalize each source's weights to one. Thus any uncovered
   remainder below 1% is absorbed by the covered area; it is not independently
   observed. This assumes votes are uniformly spread across mapped land area.
5. For every target and estimated year, intersect its map with the union of
   accepted source polygons in the same borough. Require at least 99% coverage
   in each year before the target enters groups. Also require complete 2021
   combined-reporting geometry and nonzero two-side totals in all three years.

Both source and target coverage use **unions**, rather than summed overlaps,
so overlapping polygons cannot conceal a coverage gap. The coverage check is
geometric, not proof that the true joint reporting area was fully recorded.
Source provenance and missing historical components remain limitations.

## Vote accounting

All figures below are recorded candidate votes, including other candidates and
write-ins; they exclude unrecorded ballots. Every mapped source vote is reconciled.

| Source | Allocated to the full target map | Missing source geometry | Coverage below 99% | Excessive overlapping targets |
| --- | ---: | ---: | ---: | ---: |
| 2017 | 1,143,768 | 4,197 | 499 | 201 |
| 2025 | 2,117,043 | 29,541 | 47,620 | 0 |

Allocation totals cover the full target map, including targets later excluded
from grouping. Therefore a group-filtered view is not expected to sum to the
whole-city source total. The reported 2021 ledger is unchanged for every target.
The data fields named `republican` are shared schema keys for the **opposing
side**, which includes Cuomo in 2025; interface labels identify that explicitly.

## Grouping and sensitivity

Voting similarity uses Euclidean distance on the three Democratic-side vote
shares and Ward hierarchical clustering. Every area and election has equal
weight; there is no population weighting or per-area standardization. Display
IDs run from lower to higher three-election average Democratic-side support.
Models are fitted once on eligible areas; borough/search filtering does not
refit them. The political-band option applies the same thresholds as the county
view to the equally weighted three-election mean.

The blue-to-red palette uses each group's mean Democratic-side share: 50% is
grey, 75% and above is dark blue, 25% and below is dark red, with linear shades
between. Distinct colours use the shared group palette. Incomplete histories
stay grey in either palette.

To test allocation assumptions, recompute weights using overlap area raised to
powers **0.5, 1 and 2**, normalizing each source in every scenario. This produces
more-even, baseline and more-concentrated allocations. An area is marked
**sensitive to allocation** when its Democratic-side share varies by more than
5 percentage points in either estimated year. **103 eligible areas** meet that
condition. The sidebar shows coverage and the assumption range for both years.
This is not a statistical confidence interval, validated accuracy measure or
proof that an unflagged estimate is reliable. It does not capture every
possible distribution of voters within a precinct. Group memberships shown
are the baseline allocation, not a consensus across those assumptions.

The scatter uses average support horizontally and 2017–2025 change vertically.
Both endpoint years are estimates. Its axes remain fixed through filters:
0–100% horizontally and -100 to +100 percentage points vertically.

## Rebuild and validate

```bash
.venv/bin/python scripts/build_nyc_precinct_dots.py
.venv/bin/python scripts/compare_nyc_reference_maps.py
.venv/bin/python scripts/build_nyc_history_clusters.py
.venv/bin/python scripts/test_nyc_history_clusters.py
.venv/bin/python scripts/test_nyc_history_dots_ux.py
```

The comparison script prepares checksum-verified intersection caches under
`tmp/`. The builder rejects stale caches. `data/nyc_history_crosswalk.json`
retains every source's allocation weights or exclusion status;
`data/nyc_history_clusters.json` contains target histories, source hashes,
quality flags, vote ledgers and the precomputed Ward models.

Numerical checks independently reconstruct every target allocation and the
sensitivity ranges, reconcile every source vote, preserve the native totals,
verify coverage exclusions and independently fit the Ward groups with
scikit-learn. Browser checks cover both methods, all group counts and palettes,
all dot/map assignments, scatter coordinates, linked selection, quality labels,
keyboard access, URLs, filters, reset and phone layouts.
