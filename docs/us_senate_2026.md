# U.S. Senate 2026: provisional State and County results

Choose **United States → Senate 2026 · Provisional**. It opens on **State**, with **County** available through the existing map buttons. The snapshot was published **14 November 2026 at 15:01:38 UTC** and does not update live. It contains **35 races: 34 source-reported winners and Alaska uncalled**. Race totals describe the seats on the ballot, not control of all 100 Senate seats.

## Scope and sources

The snapshot includes the **33 regular Class II elections** and the **Florida and Ohio Class III special elections**, one race per participating state. These special elections are included explicitly, whereas the older Senate series in this repository covers regular elections only. CSV fields `race_id`, `election_kind` and `senate_class` preserve that distinction.

The [Senate's Class II list](https://www.senate.gov/senators/Class_II.htm) identifies the regular cycle; the [Class III list](https://www.senate.gov/senators/Class_III.htm), [Florida election listing](https://dos.elections.myflorida.com/candidates/CanList.asp?OfficeCode=USS&elecid=20261103-GEN) and [Ohio special-election writ](https://www.ohiosos.gov/globalassets/elections/directives/2025/directive-2025-54---writ-of-special-election-for-united-states-senate-election.pdf) document the additional seats.

Vote counts and explicit race calls come from [Call the Map's downloadable results](https://www.callthemap.com/results/data), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit **Call the Map (callthemap.com/results)** and **[civicAPI](https://civicapi.org)** for rows using that feed. Original statewide rows retain underlying source URLs, update/retrieval times and candidate outcomes. This is a provisional compilation, not the certified FEC/MIT series used for previous cycles.

The builder accepts a reported winner only when the source has `outcome=won`, and verifies that the candidate leads the published count. A vote lead alone never becomes a declared winner. All races carry provisional status even if an individual source marks its count final. Alaska has blank winner fields and grey map colouring; its current leader remains visible with “not called.” No ranked-choice rounds are reconstructed.

## County coverage and grouped votes

The County view contains **2,442 counties/parishes plus one labelled Alaska statewide fallback**, for **2,443 map areas**. County GEOIDs join exactly to the repository's existing Census county geometry. State geometry is reused from the existing state boundary file; input hashes are recorded. Only states with a 2026 Senate race appear.

Call the Map's county table names two compared candidates and combines every remaining candidate/write-in as **Other candidates (combined)**. All these votes remain in the county total and candidate-vote bars. The named candidates' actual source parties are retained: independent candidates in Idaho, Montana, Nebraska and South Dakota are never relabelled Democratic. Some statewide candidates, including Democrats, can be in the grouped county remainder. The county download therefore cannot be treated as a complete Democratic/Republican vote-share dataset.

The grouped Other votes are explicitly flagged `candidate_grouped=true` and excluded from candidate outcome ranking. A county is accepted only when one named candidate leads every possible candidate in the remainder: its votes exceed the entire grouped remainder, and the two named candidates are not tied. Otherwise the builder stops for review. County rows never assign an elected senator; map colours and summary counts describe local leaders only.

County **margins compare the two named candidates** and divide by all reported votes. They are labelled “Named-candidate margin,” including in rankings. This matters in Roosevelt County, Montana (1,116 versus 704, margin 412; Other combines 731) and Grant County, Nebraska (253 versus 12, margin 241; Other combines 20). Treating the grouped remainder as a single runner-up would give incorrect candidate margins. State margins use the full candidate list.

## Alaska and statewide residuals

Alaska's source local results use **40 state House districts**, not borough/census-area counties. Those reporting units are retained in the raw source download but are not joined to county polygons. Instead, the County map shows the Alaska state shape, clearly labelled **Alaska (statewide fallback)**, with the exact statewide candidate counts (**276,513 votes**), including all individual candidates and its uncalled status.

County and state updates need not reconcile exactly in a provisional feed. The metadata records totals and named-candidate differences for every state. In this snapshot:

| State | State votes | Source local votes | Not allocated locally |
|---|---:|---:|---:|
| Alaska | 276,513 | 276,313 | 200 |
| Rhode Island | 360,406 | 359,628 | 778 |

Alaska uses the exact statewide fallback. Rhode Island's five counties retain the published local counts, with a visible note about the extra 778 statewide votes. No residual votes are allocated, estimated or silently dropped from the state view. Other states' county and state totals reconcile exactly, including each of the two named candidates. County votes exceeding the state total, inconsistent names/parties, duplicate areas, negative counts or invalid geometry joins stop the build.

## Files and reproduction

- `data/us_2026_senate_source.csv`: all 257 statewide candidate rows, including calls and original source links.
- `data/us_2026_senate_county_source.csv`: all 2,482 original reporting rows, including Alaska's 40 House districts.
- `data/us_2026_senate_{state,county}_fpp.csv`: app-format results, retaining snapshot, race kind/class, update time, grouped-vote flags and explanatory notes.
- `data/us_senate_2026_{state,county}_boundaries.geojson`: matching map features.
- `data/us_2026_senate_metadata.json`: licensing, provenance, source/geometry/output hashes, scope and reconciliation details.

Validate committed files offline with standard Python:

```sh
python3 scripts/build_us_senate_2026.py --check
python3 scripts/test_us_senate_2026.py
```

To deliberately refresh the snapshot:

```sh
python3 scripts/build_us_senate_2026.py --download
```

Downloads go to ignored `tmp/us_senate/2026/`. Both source tables must match the published manifest's SHA-256. Running without flags rebuilds from the cache. The committed Senate-only sources permit deterministic result and geometry reconstruction without network access. After refreshing, review new coverage/calls/parties and residuals, update the visible date/counts and this document, then rerun checks; changed snapshot totals intentionally require test review.

```sh
.venv/bin/python scripts/test_senate_2026_ux.py
```

The browser audit covers both map scopes, all county area identifiers, special seats, Alaska's uncalled status, independent labels, grouped-Other margins, Rhode Island residuals, mobile layout, reload/history and switching to older Senate results. No extra controls or forecasts are introduced.
