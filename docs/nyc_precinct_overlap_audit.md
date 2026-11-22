# Can NYC precincts be compared exactly across 2017, 2021 and 2025?

The existing files do not support a reliable, detailed, exact three-election
precinct crosswalk. Keep the single-election dot page as actual reported
results. A subsequent [directional comparison](nyc_reference_map_comparison.md)
favours 2021 as the reference map. A historical comparison would still require
estimated vote allocation and prominent estimate labels, plus better geometry
for jointly reported precincts whose full areas are currently missing.

## What was checked

The audit projects the three mapped reporting-area layers to EPSG:32618
(metres), intersects each pair of years, and connects any reporting areas
sharing more than 0.01 square metres. A whole source area's vote total cannot
be split exactly without additional data. Consequently, a grouping that
respects all these intersections must merge each connected component. This is
a diagnostic using simplified map snapshots, not a certified electoral
crosswalk or proof that every small intersection is a real boundary change.

| Minimum intersection as fraction of smaller polygon | Connected groups represented in all three years |
| --- | ---: |
| All intersections above the numerical area floor | 31 |
| At least 0.1% | 296 |
| At least 1% | 677 |
| At least 5% | 815 |

Ignoring small overlaps is a sensitivity check, not an exact solution. These
counts do not include disconnected groups missing one or more election years.
They are not a proposed set of usable analysis areas.

With all intersections, the largest connected group spans Brooklyn, Manhattan
and Queens and includes 4,325 reporting areas from 2017, 4,303 from 2021 and
3,156 from 2025. At the 1% threshold, the largest group still includes 507,
501 and 382 reporting areas respectively. Thus a simple whole-precinct merge
fails to retain a useful precinct-like level of detail.

Of 5,671 names repeated in 2017 and 2021, 5,549 have at least 99% geographic
intersection-over-union. But of 4,053 names repeated in 2017 and 2025, only one
passes that test; the median overlap is zero. The 2021–2025 comparison is
similar (one of 4,043 repeated names). Repeated AD/ED labels must not be used
as a cross-year join.

## Source limits and next step

Historical extracts omit some combined-component polygons: 142 in 2017 and
145 in 2021. Some reporting area's votes therefore cover a larger area than
the available geometry. Historical provenance and shoreline/simplification
also differ. Those gaps prevent claiming exactness even after a geometric
merge. See [historical source notes](nyc_mayor_history.md).

The practical route toward the county-style experience is a fixed target
geography (the directional comparison favours 2021 reporting areas) and a documented vote
crosswalk. First recover and validate the missing historical reporting
geometries or an authoritative crosswalk. Where older precincts must be split,
allocate votes using an explicit estimation method, preferably a relevant
population distribution rather than land area alone. Reconcile source totals,
flag coverage gaps, quantify sensitivity, and label older results as estimates.
Only then fit the three-election voting groups. Cuomo + Sliwa remains the
2025 opposing side as requested; other votes remain excluded from two-side
shares. No estimated votes or new multi-year clusters were added by this audit.

Reproduce with `.venv/bin/python scripts/audit_nyc_precinct_overlap.py`.
Machine-readable results and source checksums:
[`nyc_precinct_overlap_audit.json`](../data/nyc_precinct_overlap_audit.json).

An [exploratory three-election view](nyc_history_clusters.md) is now implemented
on 2021 areas. It excludes incomplete geometry instead of reconstructing it
and labels both converted years as area-weighted estimates.
