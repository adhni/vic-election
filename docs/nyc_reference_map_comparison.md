# Which NYC reference map is best for three-election groups?

**Use 2021 as the reference map if building an explicitly estimated historical
comparison.** It largely preserves the aligned 2017 and 2021 geography and
concentrates substantial conversion in 2025. This recommendation comes from
comparing both mapping directions, rather than preferring newer boundaries.
It does not establish that historical votes can be allocated exactly.

## Directional comparison

For each source reporting area, find the target area covering the largest
fraction of its mapped geometry. The table counts votes in source areas where
that largest target covers **less than 99%**. Such source areas cannot simply
be transferred whole at that tolerance; their vote totals are exposed to
splitting or another allocation assumption.

| Fixed reference map | 2017 vote exposure | 2021 vote exposure | 2025 vote exposure |
| --- | ---: | ---: | ---: |
| 2017 | Native map | 1.26% | 92.78% |
| **2021** | **0.99%** | **Native map** | **92.67%** |
| 2025 | 65.53% | 65.44% | Native map |

These percentages are **votes in affected source areas**, not measured votes
crossing a boundary, prediction error or a claim that all those votes would
be assigned incorrectly. A source area can be affected even when most of it
is in one target. Matching 99% is a diagnostic tolerance, not exact identity.
Native map means no cross-year transfer, not that its reporting geometry is
known to be complete.

2017 and 2021 are very similar choices on split burden. The documented 2021
boundary release is 21A; the original release identifier for the 2017 archive
is unrecorded. That gives 2021 the stronger provenance as an anchor. It also
has slightly lower split exposure in both converted years.

## Does the result depend on the tolerance?

Each election receives equal weight below. The native election requires no
geographic conversion. Equal weighting avoids giving 2025 extra influence
solely because its turnout was higher.

| Required coverage by one target | 2017 reference | 2021 reference | 2025 reference |
| --- | ---: | ---: | ---: |
| 95% | 30.76% | **30.66%** | 41.95% |
| 99% | 31.35% | **31.22%** | 43.66% |
| 99.9% | 32.97% | **32.81%** | 48.47% |

The values are mean affected-vote exposure across the three elections, not
allocation accuracy estimates. A second diagnostic weights the fraction of
each source polygon outside its dominant target by source votes. It gives
12.85%, 12.80% and 14.70% respectively across all three elections, again
favouring 2021 slightly over 2017 and both over 2025. That second diagnostic
assumes votes are uniformly distributed across source area and must not be
used as a validated vote allocation or uncertainty estimate.

Excluding source polygons known to be incomplete and sources substantially
touching incomplete targets does not reverse the result: 2017-to-2021 split
exposure is 0.95%, versus 92.41% for 2025-to-2021. The equivalent historical
to-2025 exposures are 65.25% and 65.15%.

## Remaining limits

- This is based on the existing mapped reporting-area snapshots, including
  their simplification and shoreline differences. It is not an authoritative
  precinct crosswalk.
- Some jointly reported components lack polygons in every year's available
  snapshot. About 0.37% of 2017, 0.55% of 2021 and 1.35% of 2025 recorded votes
  belong to source reporting areas known to have incomplete geometry.
- For 2025-to-2021, 2.31% of votes belong to source areas whose summed mapped
  target coverage is below 99%. This is a coverage flag for those source areas,
  not the percentage of votes actually missing. Summed intersections can
  overstate union coverage, so this is a conservative gap flag.
- Historical geometry provenance and component omissions still prevent calling
  the 2017-to-2021 transfer exact merely because it mostly fits geographically.
- Land area is an imperfect basis for splitting votes, especially in parks,
  industrial sites and water-adjacent precincts. A better crosswalk should use
  appropriate population geography where possible and assess sensitivity.

## Implemented exploratory comparison

The [three-election dot view](../app/nyc-history-dots.html) now uses the 2021
reference map. It allocates 2017 and 2025 by map overlap, labels both as estimates,
and withholds incomplete source geometries rather than inventing missing map
pieces. Targets without sufficiently covered histories remain grey and outside
the groups. The original single-election page preserves reported results.
See the [implementation and validation notes](nyc_history_clusters.md) for the
source vote ledger, coverage exclusions and allocation sensitivity checks.

This reference-map inspection itself did not allocate votes; the subsequent
builder and its source files are documented separately.

## Reproduction

Run `.venv/bin/python scripts/compare_nyc_reference_maps.py`, then
`.venv/bin/python scripts/test_nyc_reference_map_comparison.py`.
The script caches pairwise polygon intersections under `tmp/` with geometry
checksums; it recomputes when a source changes. It checks all six directions
among 2017, 2021 and 2025 in EPSG:32618 with a 0.01 square metre numerical
intersection floor. Every source return and metadata file is checksummed in
[`nyc_reference_map_comparison.json`](../data/nyc_reference_map_comparison.json).

See also the [whole-area merging audit](nyc_precinct_overlap_audit.md) and
[historical source notes](nyc_mayor_history.md).
