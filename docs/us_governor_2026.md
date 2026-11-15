# U.S. Governor 2026: provisional State and County results

Choose **United States → Governor 2026 · Provisional**. It opens on **State**, with the existing **County** button available. This frozen snapshot was published **15 November 2026 at 18:19:21 UTC** (16 November, 05:19 AEDT). It contains **36 state races and 36 source-reported winners**, including Alaska. Results remain provisional and do not update live.

## Scope and attribution

The view covers the 36 U.S. states holding gubernatorial elections in 2026. It does not cover territorial elections or claim to describe all 50 current governors. The [National Governors Association election overview](https://www.nga.org/governors/elections/) counts states and territories together; this repository's dataset is state/county based.

Counts and explicit winner calls come from [Call the Map's downloadable results](https://www.callthemap.com/results/data), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit **Call the Map (callthemap.com/results)** and **[civicAPI](https://civicapi.org)** for rows using its feeds. Original candidate rows retain the underlying source URLs, update/retrieval timestamps, candidate party and call outcome. This is a provisional compilation, not a certified final FEC/MIT series.

The builder requires an explicit `outcome=won` before assigning an elected member. A current vote lead alone is insufficient. It checks that a source-reported winner leads the published count, preserves all 256 statewide candidate rows and verifies that candidate sums equal the reported total. State labels say “Reported winner · provisional.” Count status and source notes remain available without expanding the main controls.

This governor snapshot is newer than the separately frozen 14 November House/Senate snapshots. Adding it does not refresh or silently change those datasets. Alaska's governor race is called in this source version; the older House/Senate snapshots retain their original uncalled statuses.

## County/reporting-area view

The County map has **2,151 areas**: **2,141 counties**, **nine Connecticut planning regions**, and **one labelled Alaska statewide fallback**. It shows local vote leaders, not separately elected governors. All county totals and both individually named candidates reconcile exactly to statewide counts in this snapshot; no residual votes are imputed or distributed.

The local source reports two named candidates and groups every remaining candidate/write-in as **Other candidates (combined)**. Keep the original candidate parties; independent votes are not relabelled Democratic. The grouped remainder stays in vote bars and total votes, with `candidate_grouped=true`, but is excluded from candidate outcome ranking. County margins compare the **two named candidates**, divided by all reported votes, and are labelled “Named-candidate margin.” They should not be treated as a complete party-by-party county vote-share dataset.

**Franklin County, Arkansas** cannot be assigned an individual local leader from this grouped source. It reports Fred Love 676, Sarah Huckabee Sanders 2,152 and combined Other 2,354, out of 5,182 votes. Because the remainder exceeds either named candidate, it could contain a leading individual candidate or several smaller candidates. The app retains every vote, colours the county grey and says **Local leader unavailable**. It does not present the combined group or the largest named candidate as a winner, and excludes this county from candidate-margin rankings. Its displayed named-pair margin remains 1,476 votes; the full source note explains the limitation.

Connecticut joins the source's nine planning-region GEOIDs to the current Census reporting geometry. Alaska reports by 40 state House districts rather than county/borough boundaries: these rows are retained in the original source download, while the map uses the Alaska state shape and exact statewide candidate counts, labelled **Alaska (statewide fallback)**. No House reporting district is joined to a borough polygon.

State and county geometry reuse the repository's existing Census boundary files. Exact input hashes and GEOID/name joins are validated; no new boundary audit or cross-election swing is implied.

## Files and reproduction

- `data/us_2026_governor_source.csv`: all 256 statewide candidate rows and underlying source links.
- `data/us_2026_governor_county_source.csv`: all 2,190 original reporting rows, including Alaska's 40 House districts.
- `data/us_2026_governor_{state,county}_fpp.csv`: app format with snapshot and update times, explicit statuses, grouped-vote flags and result notes.
- `data/us_governor_2026_{state,county}_boundaries.geojson`: matching map features.
- `data/us_2026_governor_metadata.json`: licensing, source/geometry/output hashes, calls, unresolved local leaders and state/county reconciliation.

Validate the committed snapshot offline with standard Python:

```sh
python3 scripts/build_us_governor_2026.py --check
python3 scripts/test_us_governor_2026.py
```

To deliberately refresh:

```sh
python3 scripts/build_us_governor_2026.py --download
```

Downloads go to ignored `tmp/us_governor/2026/`. Both original tables must match the published manifest's SHA-256. Running without flags rebuilds from that cache. Committed Governor-only source rows allow deterministic result and map reconstruction without network access. After a refresh, review calls, scope, residuals and ambiguous local leaders, update visible snapshot dates/counts and documentation, then rerun validation. Frozen-snapshot test expectations intentionally require review when the source changes.

```sh
.venv/bin/python scripts/test_governor_2026_ux.py
```

Data tests independently audit all candidate counts/calls, every local vote and party, grouped margins, unresolved Franklin County, Connecticut geometry, Alaska's fallback, checksums and deterministic rebuilds. A mutation test removes Alaska's explicit call to prove a vote lead cannot become an elected member. Browser checks cover all map identifiers, source notes, state/local labels, grey unresolved areas, county ranking exclusions, mobile layout, reload/history and geography preservation across governor years. Existing Senate result and general explorer checks protect the shared presentation.
