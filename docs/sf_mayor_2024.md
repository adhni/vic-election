# San Francisco mayor, November 5, 2024: all 14 counting rounds

Open [San Francisco precinct rounds](../app/sf-precinct-dots.html). The same
514-precinct map and one-precinct-one-dot view update with a round selector and
Previous/Next controls. All 14 snapshots are also available under **United
States → San Francisco Mayor 2024 · Count N of 14** in the main explorer.

This is **one ranked-choice election**, not 14 elections, a two-election
runoff, or the ten positions voters could rank on their ballots. Candidates
are eliminated using the citywide count. Precinct figures reflect those same
eliminations; no independent precinct election is run. Local leaders may differ
from the citywide winner. Candidate colours identify people, not parties.

## Provenance and limits

Source data originate with the San Francisco Department of Elections:

- [Final election results](https://www.sfelections.org/results/20241105/).
- [Published round table](https://www.sfelections.org/results/20241105/final/round-pages/mayor_short-rounds-en.html).
- [Final detail report](https://www.sfelections.org/results/20241105/data/20241203/mayor/mayor_detail.xlsx).
- [Final Dominion CVR export](https://www.sfelections.org/results/20241105/data/20241203/CVR_Export_20241202143051.zip).

**The official result archive was inaccessible during import (HTTP 403 / TLS
failure).** The pinned source is the compact public CVR-pattern archive and
published-round transcription in
[DataDiver revision 647b2beb](https://github.com/sfbay/datadiver/tree/647b2beb42f7d1b63cccd9d962cdef65024344c9).
We independently replay the weighted ballot patterns and reproduce every
candidate total and each blank, overvote and exhausted count across all 14
rounds of that transcription. **Precinct round figures are reconstructed CVR
results, not official native precinct round reports.** Direct byte comparison
against the original official export was not possible in this import.

DataDiver by Jesse Garnier (SF State Journalism),
[datadiver.jlabsf.org](https://datadiver.jlabsf.org), provides its derived data
under **CC BY 4.0**. Its content licence and code licence are retained in
`data/sources/sf/`. Its compact archive is already resolved into effective
rankings: candidate indices, skipped/duplicate rankings collapsed, and an
explicit overvote terminator. We do not reconstruct those decisions from
raw ballot images or claim independent validation of raw mark interpretation.
The archive includes the latest adjudicated ballot state rather than a naive
reading of original unadjudicated marks. Our code independently checks the
resulting effective patterns and tabulation.

The [source manifest](../data/sources/sf/source_manifest.json) records URLs,
revision and SHA-256 digests. Retained files include the compact mayoral
patterns, round-table transcription, statement-of-vote first-rank snapshot,
turnout snapshot, archive manifest, and official DataSF geometry/metadata.
No source is downloaded during a normal rebuild. The all-contest 296 MB raw
CVR ZIP is not bundled.

## Vote accounting

| Count | Daniel Lurie | London Breed | Continuing votes | Exhausted | Overvotes | Blank / no usable ranking |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Round 1 | 102,720 | 95,117 | 390,184 | 0 | 1,381 | 18,540 |
| Round 14 | 182,364 | 149,113 | 331,477 | 57,859 | 2,229 | 18,540 |

The final split is **55.02% / 44.98% of continuing votes**. All 15 qualified
candidates, including Marc Roth and Michael Lin as named write-ins, enter
round 1. One candidate is eliminated after each round through round 13; the
count stops with Lurie and Breed in round 14. We match that order by checking
the unique minimum candidate citywide, rather than inventing local eliminations.

The archive contains **410,105 mayoral CVR records** in 64,589 effective ranking
patterns, grouped into 152,521 weighted precinct/pattern groups:

- **410,102 records** join the 514 map precincts.
- **3 records** have the source's `0000` sentinel for no precinct attribution.
  Their votes and ballot categories remain in a separate per-round ledger.
  They are included in citywide figures and never assigned to a nearby precinct.

For every precinct and every round:

`continuing candidate votes + exhausted + overvotes + blanks = CVR records`.

That denominator stays constant across rounds. Exhausted means no remaining
valid choice; overvotes terminate counting when reached. The main map and dot
shades use continuing candidate votes only. Round 1 reflects the official
RCV initial count (first usable choices), which need not equal a mechanical
count of marks in the first rank column. Do not substitute as-cast first-rank
statement-of-vote numbers or count preference rank 2 as elimination round 2.

The main explorer uses one CSV **snapshot per counting round**. Its generic
`row_type=first` field carries that selected round's continuing tally, not a
claim that all 14 files contain first preferences. `formal_votes` is continuing
votes; `informal_votes` is the remainder of the CVR records, including exhausted
ballots, and must not be interpreted as all invalid votes. `total_votes` is
CVR records, not the all-election voter-turnout denominator. All are explicitly
labelled as round snapshots in the UI. The dedicated page displays the actual
blank/exhausted/overvote categories separately.

## Turnout and withheld statement-of-vote rows

The statement-of-vote turnout snapshot has usable published rows for **501
precincts**. Their all-election ballots and registration counts produce
turnout, which remains fixed as the round changes. Those ballot counts can
differ from the count of mayoral CVR records; the UI labels both rather than
silently substituting one denominator for the other.

**13 precincts** have withheld statement-of-vote rows: `1103`, `1116`, `7203`,
`7204`, `7206`, `7338`, `7636`, `9147`, `9513`, `9901`, `9902`, `9903`, `9904`.
Their publicly available CVR-derived round figures remain selectable with a
withheld-row notice. Their turnout is **unavailable**, not zero or estimated.
The main explorer leaves registration/turnout blank for the round snapshots;
the dedicated view supplies the explicitly labelled SOV turnout where available.

## Geography and interactions

The map uses the official
[DataSF precincts defined in 2022](https://data.sfgov.org/Geographic-Locations-and-Boundaries/Election-Precincts-Current-Defined-2022/d6x4-hefw),
updated in March 2024. It has exactly 514 codes matching all located CVR
precincts. Supervisorial district and neighborhood labels come from that same
geometry, not inferred demographics. Raw geometry/metadata are pinned. Display
geometry is lightly simplified with topology preserved; invalid geometry may
be repaired only if its area changes by less than 0.01%, with codes recorded
in the generated metadata. Map shapes never change between counting rounds.

Every dot is one precinct. Candidate colours remain consistent. The local
lead over the next candidate is divided by local continuing votes and shaded
in five bands: up to 2, 2–5, 5–10, 10–20 and above 20 percentage points. Ties
and precincts with no continuing votes are neutral. Candidate, district and
name/neighborhood filters, linked map/dot selection, a precinct picker, keyboard
browsing and URL restoration work across rounds. The sidebar shows transfer
gains from the previous count and the candidate eliminated after the current
round, where applicable. There is no demographic or history-clustering model.

## Reproduce and verify

```bash
python scripts/build_sf_mayor_2024.py
python scripts/validate_sf_mayor_2024.py
python scripts/test_sf_mayor_2024_ux.py
python scripts/smoke_static_app.py
python scripts/check_repository_sizes.py
```

The builder uses NumPy indexed accumulation and reconciles all city totals
before producing snapshots. The independent validator uses Python counters
and scans weighted ranking patterns directly, checking every precinct/round
candidate total, ballot category, exclusion, local lead, map join, CSV cell,
fixed CVR denominator and the three-record unlocated ledger. It checks source
hashes and all withheld turnout labels. Browser checks verify all 14 rounds,
every dot/map colour, the explorer snapshots, step controls, fixed turnout,
withheld labels, linked selection, filters, keyboard use, URLs and
320/390/768px layouts. The voting-groups workflow runs these checks.
