# Chicago mayoral election, 2023: both rounds

Open [Chicago precinct and ward dots](../app/chicago-precinct-dots.html), or
choose **United States → Chicago Mayor 2023 · First Round / Runoff** in the
main explorer. Both pages offer **1,291 precincts** and **50 wards**, candidate
lead shading, exact vote counts and turnout. The dots page links map selection,
ward/candidate filters, name/code search, a picker, keyboard browsing and URLs.
Every dot is one selected unit; precincts and wards are separate views.

The February 28 first round includes nine ballot candidates and six separately
named write-ins. No candidate won outright. Brandon Johnson and Paul Vallas
advanced to the April 4 runoff, which Johnson won citywide. Local leads do not
represent separately elected mayors. These elections are nonpartisan, and
candidate colours do not denote Democratic or Republican affiliation.

## Results and source provenance

The Chicago Board of Election Commissioners' official proclamations are pinned:

- [February 28 certified proclamation](https://app.chicagoelections.gov/documents/proclamations/Proc-2023-02-28.pdf).
- [April 4 certified proclamation](https://app.chicagoelections.gov/documents/general/Proc%202023%2004%2004.pdf).

These PDFs provide candidate city totals, ballots by ward and precinct counts,
but not every precinct candidate cell. Precinct returns come from
[DataMade's preserved Chicago municipal election CSVs](https://github.com/datamade/chicago-municipal-elections),
retained under `data/sources/chicago/`. Only mayoral columns and each precinct's
registration/ballot counts are imported; alderperson and other contests in
the same CSV are excluded. The archive's MIT licence and README are retained.
The old official historical export endpoint returned HTTP 403 during import.

**All archived precinct cells are retained, but are not independently verified
against an official precinct export.** They reconcile exactly to every
certified candidate city total, every ward's ballot total and precinct count,
and the citywide registration and ballot totals. Ward candidate results are
aggregates of these archived precinct returns, not independently sourced ward
candidate tables. Source URLs and SHA-256 digests are in the
[source manifest](../data/sources/chicago/source_manifest.json).

| Candidate or return | February 28 | April 4 |
| --- | ---: | ---: |
| Paul Vallas | 185,743 | 293,033 |
| Brandon Johnson | 122,093 | 319,481 |
| Lori Lightfoot | 94,890 | — |
| Chuy García | 77,222 | — |
| Willie Wilson | 51,567 | — |
| Ja'Mal Green | 12,257 | — |
| Kam Buckner | 11,092 | — |
| Sophia King | 7,191 | — |
| Roderick Sawyer | 2,440 | — |
| Johnny Logalbo (write-in) | 15 | — |
| Keith Judge (write-in) | 5 | — |
| Stephen Hodge (write-in) | 4 | — |
| Ryan Friedman (write-in) | 3 | — |
| Stephanie Ann Mustari (write-in) | 1 | — |
| Bridgett Palmer (write-in) | 1 | — |
| **Recorded mayoral votes** | **564,524** | **612,514** |
| Ballots without a recorded mayoral vote | 2,449 | 1,281 |
| **Ballots cast** | **566,973** | **613,795** |
| Registered voters | 1,581,564 | 1,587,153 |

Shares are recalculated from integer counts and include all recorded mayoral
votes, including the six named write-ins. Zero-vote named candidates remain
in precinct and ward details. The difference between ballots and recorded
mayoral votes is **not classified as blank ballots or overvotes** because the
import does not distinguish those categories. It is excluded from candidate
vote shares. Turnout is ballots divided by that round's registered-voter count;
ward turnout uses summed ballots and registration, not an average of percentages.

## Election-specific geography

The [City's Ward Precincts 2023–2024 dataset](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Ward-Precincts-2023-2024-/6piy-vbxa)
explicitly states that it applies from the February 28, 2023 election through
the November 5, 2024 election. It includes the January 2023 split of Ward 24
Precinct 16, creating Precinct 20 and increasing the total from 1,290 to 1,291.
Thus **both 2023 rounds use the same applicable published precinct map**; a
modern map is not substituted. The City's general legal-precision limitation
still applies. Both raw GeoJSON and the dataset metadata are pinned.

Codes preserve two ward digits plus three precinct digits (`24020` means
Ward 24 Precinct 20). All 1,291 codes join both round result tables exactly.
Ward geometries are dissolved from their constituent precinct polygons, and
ward results sum those same precincts. Shapes are lightly simplified with
topology preserved for display. Any invalid geometry is repaired only if area
changes by less than 0.01%, with repaired codes recorded in each metadata file.
No votes are split, interpolated or reassigned.

## Shading and interactions

Every named candidate has a consistent colour across rounds. The lead is the
difference between the top two candidate counts divided by all recorded
mayoral votes. Five bands shade leads up to 2, 2–5, 5–10, 10–20 and above 20
percentage points. Closer leads are lighter. Ties/no-vote areas are neutral,
and the code does not invent an elected mayor for those areas. Dots count
local leads, not votes or population.

The source and result notices distinguish archived precinct returns from
certified summary figures. This feature does not add cross-election clustering
or infer individual voter transfers between the first round and runoff.

## Rebuild and checks

```bash
python scripts/build_chicago_mayor.py
python scripts/validate_chicago_mayor.py
python scripts/test_chicago_mayor_ux.py
python scripts/smoke_static_app.py
python scripts/check_repository_sizes.py
```

The builder checks source hashes and validates the official recaps before
export. The independent validator reads positioned PDF words rather than
reusing the builder's cropped text parser. It checks every imported precinct
cell against the preserved CSV, all ward aggregates, certified candidate city
totals and ward ballot/precinct recaps, registration, turnout, write-ins and
all map joins. Browser checks cover both rounds at both levels, exact dot/map
colours, the Ward 24 split, local selection, candidate/ward filtering, keyboard
use, URL restoration, result-table wrapping and 320/390/768px layouts in both
pages. These checks are part of the voting-groups workflow.
