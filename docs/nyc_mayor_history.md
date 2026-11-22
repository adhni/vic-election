# NYC mayoral general elections: 2021 and 2017

Choose **United States → New York City Mayor 2021** or **New York City Mayor
2017**. Each entry has borough, Assembly-district and election-district (ED,
precinct-level) maps, candidate totals, search and local margins. These are
general elections, decided by citywide plurality; the ranked-choice primaries
are not included. [2025 coverage](nyc_mayor_2025.md) remains available separately.

Candidate colours use the same local-lead shading as the 2025 view: ≤2, 2–5,
5–10, 10–20 and >20 percentage-point leads over the next named candidate.
Lighter shades show closer leads and darker shades show larger leads. Each
year uses this scale across all three map geographies; ties and zero-vote
areas remain grey.

| General election | Mapped ED reporting areas | Assembly districts | Boroughs | Recorded mayoral votes | Ballots |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 November 2021 | 5,697 | 65 | 5 | 1,125,258 | 1,149,172 |
| 7 November 2017 | 5,720 | 65 | 5 | 1,148,665 | 1,166,314 |

Every ED with recorded candidate votes has a map polygon. Results are read
directly from NYC Board of Elections CSVs, preserving every named candidate
and grouped write-ins. Fusion ballot lines are combined for the same person
and retained individually in each CSV row's `ballot_lines` JSON. Registration
and turnout are left unavailable.

## Official results and the 2017 correction

- [BOE 2021 results](https://www.vote.nyc/page/election-results-summary-2021):
  citywide ED-level CSV and certification recap, attested 30 November 2021.
- [BOE 2017 results](https://www.vote.nyc/page/election-results-summary-2017):
  citywide ED-level CSV, Manhattan and Kings ED-level CSVs, and the currently
  published certification recap, attested 16 July 2019.

The 2021 citywide totals are Eric Adams 753,801, Curtis Sliwa 312,385,
Catherine Rojas 27,982, William Pepitone 12,575, Quanda Francis 3,792,
Stacey Prussman 3,189, Raja Michael Flores 2,387, Fernando Mateo 1,870,
Skiboky Stora 264, and write-ins 7,013. There are 23,914 unrecorded mayoral votes.

The 2017 totals are Bill de Blasio 760,112, Nicole Malliotakis 316,948,
Sal Albanese 24,484, Akeem Browder 16,536, Michael Tolkin 11,309, Bo Dietl
11,163, Aaron Commey 2,770, and write-ins 5,343. There are 17,649 unrecorded
mayoral votes citywide.

The 2017 citywide ED file is stale by one ballot and one Malliotakis vote.
The official [Manhattan ED file](https://www.vote.nyc/sites/default/files/pdf/election_results/2017/20171107General%20Election/00101100000New%20York%20Mayor%20Citywide%20EDLevel.csv)
identifies the corrected AD 76, ED 067 return: eight absentee/military ballots
instead of seven, and 101 Malliotakis Republican votes instead of 100.
The build uses the complete Manhattan file in place of its citywide-file
records. It asserts this is the sole changed precinct and records the source
in metadata. No citywide residual is assigned to an invented precinct.
All candidate totals and ballot totals then reconcile to every borough and
the citywide certification recap.

One source inconsistency remains in **Brooklyn AD 57, ED 057**: 254 mayoral
votes against 253 ballots. Both BOE's citywide and separate Kings ED file
contain these same counts. The app preserves them, labels the ballot balance
**Source counts inconsistent**, and explains the difference in the area note.
The schema's `informal_votes` field retains the raw balance of `-1` for this
one precinct; this is an accounting discrepancy, not a negative number of
unrecorded votes. Borough and citywide totals still reconcile exactly.
Brooklyn AD 46, ED 037 has one ballot and zero mayoral votes, and is labelled
accordingly rather than being described as a zero-ballot area.

## Historical map provenance and limits

Only geometry is read from the [pinned NYC election archive](https://github.com/joshgreenman1973/nyc-election-archive/tree/325cee637986542918fde0ff156cb2fd685229b8).
Its [methodology](https://github.com/joshgreenman1973/nyc-election-archive/blob/325cee637986542918fde0ff156cb2fd685229b8/docs/methodology.html)
identifies the 2021 source as NYC Planning release **21A, February 2021**.
For 2017, the original NYC Planning release identifier is **not recorded**.
That limitation is displayed in the 2017 entry. These are historical boundary
snapshots; they are not asserted to be an independently verified legal map
for each election date. No cross-year precinct swing or same-boundary match
is inferred from a repeated AD/ED code.

The archive's exported layers omit some zero-vote and combined ED polygons.
For 2021, geometry is merged from the general-election and primary exports
of the same 21A release; duplicate ED geometries must be identical. No primary
votes or third-party calculated results are imported. This recovers 5,728
distinct polygons before dissolving available combined components into their
reporting EDs. The 2017 export contains 5,720 polygons.

The BOE source lists 5,901 ED records in each year. In 2021, 176 EDs are
combined into 5,725 reporting EDs; in 2017, 142 are combined into 5,759 reporting
EDs. Some combined component polygons are unavailable (145 in 2021; all 142
in the 2017 export). Such a result therefore shows the **available reporting
ED polygon**, with an explicit note that the complete joint area cannot be
drawn. Assembly and borough maps dissolve the available historical geometry;
their vote totals include all component returns.

Twenty-eight 2021 and 39 2017 zero-ballot reporting EDs have no available
polygon and are listed in metadata rather than assigned a false location.
The displayed 2021 map has 92 zero-vote areas and 18 tied local leads; the
2017 map has 117 zero-vote areas and 16 ties. Ties and zero-vote areas are grey.

Two 2021 and five 2017 source polygons have minor geometry defects. The build
repairs invalid polygon topology with Shapely `make_valid`, records each ED
identifier, and rejects a repair that changes area materially. It then applies
the shared map simplification and verifies every output geometry.

## Rebuild and validate

```bash
.venv/bin/python scripts/build_nyc_mayor_history.py
.venv/bin/python scripts/validate_nyc_mayor_history.py
.venv/bin/python scripts/validate_nyc_mayor_2025.py
.venv/bin/python scripts/build_home_assets.py
.venv/bin/python scripts/smoke_static_app.py
.venv/bin/python scripts/check_repository_sizes.py
.venv/bin/python scripts/test_nyc_mayor_2025_ux.py
```

`--year 2021` or `--year 2017` rebuilds one historical entry. Downloads are
cached under ignored `tmp/nyc/history` and verified against fixed SHA-256
checksums. `--refresh` downloads and verifies them again. Historical builds
need the Python dependencies; they do not require the R conversion used by
the 2025 boundary source.

The shared builder now accepts election-specific source metadata while
preserving the 2025 command. Independent validators check official totals,
fusion lines, the corrected 2017 precinct, the known source discrepancy,
ballot accounting, neutral ties and zero-vote labels, and exact CSV/map joins.
The browser suite covers all three years, geography switching, shared links,
search, source notes and mobile layout.
