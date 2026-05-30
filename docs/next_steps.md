# Next Steps: Victoria-First Election Depth

Bismillah, the project should stay focused on state and federal lower-house elections before considering local council data.

## Direction

Do not add local council elections yet.

Local elections are a separate data problem: many councils, wards, candidate groups, inconsistent boundaries, large candidate counts, and weaker comparability with state and federal lower-house electorates. Adding them now would broaden the project into council-specific data cleaning before the state/federal explorer is mature.

The stronger path is to deepen Victoria first:

- go further back in Victorian state elections
- expand federal elections within Victoria
- add comparison and rankings views
- generalise only after the Victoria-focused model is stable

## Phase 1: Victorian State Depth

Add `2014` Victorian Legislative Assembly support next.

Why this comes first:

- it reuses the existing VEC historical-results scraper path
- it keeps the same election type as 2018 and 2022
- it enables state-election comparisons over time
- it avoids introducing a new electoral commission or jurisdiction

Target work:

- confirm whether VEC 2014 historical pages expose enough first/final and distribution data
- generate `data/vic_2014_preferences_long.csv`
- generate `data/vic_2014_district_summary.csv`
- source matching 2014 Legislative Assembly district boundaries
- add `2014` to the election selector
- extend static smoke validation

After 2014, consider `2010` if the historical pages and boundary data are workable.

## Phase 2: Federal Victoria Depth

Federal Victoria now has `2025`, `2022`, and `2019`.

Next federal target:

- add Federal `2016 - Victoria`

Potential later federal target:

- add Federal `2013 - Victoria`, if source data and boundaries are workable

Why this is valuable:

- it keeps the app Victoria-focused
- AEC federal result downloads are structured and repeatable
- it lets users compare Victorian federal patterns over multiple elections
- it supports state-vs-federal pattern exploration without adding other states yet

Target work:

- reuse `scripts/build_aec_vic.py` with the correct AEC event id
- source the matching AEC Victorian division boundary file for the election period
- validate expected division count, result/boundary names, and topology
- add app selector entries and smoke coverage

## Phase 3: Comparison And Rankings UI

Before adding other states, improve analysis inside the existing Victoria dataset.

Useful views:

- closest seats/divisions
- changed-on-preferences seats
- biggest winner transfer gains
- bloc totals by election
- side-by-side election comparison where district/division names match
- state election vs federal election comparison for Victoria

This should be compact and data-first, not a broad dashboard.

## Phase 4: Generalise Later

Only after the Victoria state/federal model is strong, consider other states.

Possible later targets:

- NSW lower-house elections
- Queensland lower-house elections

Likely prerequisite work:

- config-driven election definitions
- cleaner source/type/year labels
- less VEC-specific naming in shared code
- broader party normalisation
- jurisdiction-specific boundary handling

At that point, consider whether the project should become a broader Australian preference explorer.

## Deferred: Local Council Elections

Local council elections are deferred.

They may be useful later as a separate project or a separate app mode, but they should not be the next step for this repo.

Reasons:

- council/ward structures vary heavily
- candidate groups and local tickets need different modelling
- boundaries are less stable and less comparable
- the number of contests is much larger
- the result format is less aligned with this app's current lower-house district/division model

## Recommended Next Concrete Task

Add Victorian state election `2014`.

Second choice: add Federal `2016 - Victoria`.

Insyallah, the best sequence is:

1. VIC 2014 state
2. Federal 2016 Victoria
3. comparison/rankings UI
4. VIC 2010 or Federal 2013
5. generalise to other states only after that
