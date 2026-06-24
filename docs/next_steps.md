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

Victorian Legislative Assembly support now includes `2022`, `2018`, `2014`, `2010`, and `2006`.

Why this path comes first:

- it reuses the existing VEC historical-results scraper path
- it keeps the same election type as 2018 and 2022
- it enables state-election comparisons over time
- it avoids introducing a new electoral commission or jurisdiction

Completed work:

- generate `data/vic_2014_preferences_long.csv`
- generate `data/vic_2014_district_summary.csv`
- add matching 2014 Legislative Assembly district boundaries
- add `2014` to the election selector
- extend static smoke validation
- generate `data/vic_2010_preferences_long.csv`
- generate `data/vic_2010_district_summary.csv`
- add matching 2001 Legislative Assembly district boundaries for 2010
- add `2010` to the election selector
- add state-specific 2010 result/boundary validation
- generate `data/vic_2006_preferences_long.csv`
- generate `data/vic_2006_district_summary.csv`
- add matching 2001 Legislative Assembly district boundaries for 2006
- add `2006` to the election selector
- add state-specific 2006 result/boundary validation

## Phase 2: Federal Federal-House Depth

Federal Victoria now has `2025`, `2022`, `2019`, `2016`, `2013`, `2010`, and `2007`.
Australia-wide federal coverage now also includes `2025` and `2022`.

Why this is valuable:

- it keeps the app Victoria-focused
- AEC federal result downloads are structured and repeatable
- it lets users compare Victorian federal patterns over multiple elections
- it supports state-vs-federal pattern exploration without adding other states yet

Completed 2010 and 2007 work:

- reused `scripts/build_aec_vic.py` with AEC event `15508`
- used the AEC `national-esri-2010.zip` boundary file filtered to Victoria, matching the AEC note that Victoria used 2007 boundaries at the 2010 election
- validated 37 divisions, result/boundary names, and boundary topology
- added app selector entries and smoke coverage
- repeated the same pattern for Federal 2007 with AEC event `13745`

Completed Australia-wide 2025 and 2022 work:

- generalised the AEC federal builder and validator so they can run for `au` or a state scope
- added `Federal 2025 - Australia` and `Federal 2022 - Australia` selector entries
- generated national long CSV, summary CSV, and boundary GeoJSON files for both years
- generalised the app branding and seat wording so the mixed Victoria-state and Australia-federal scope is explicit

## Phase 3: Comparison And Rankings UI

Before adding other states, improve analysis inside the existing Victoria dataset.

Completed single-election rankings work:

- closest seats/divisions
- largest winning margins
- changed-on-preferences seats
- biggest winner transfer gains
- click-through from ranking rows into the existing district/division view
- compact smoke-covered UI in both `index.html` and `app/index.html`

Still useful next views:

- side-by-side election comparison where district/division names match
- state election vs federal election comparison for Victoria

This should be compact and data-first, not a broad dashboard.

## Phase 4: Generalise Later

Only after the Victoria state/federal model is strong, consider other states.

Before adding other states, keep improving config-driven election definitions so future election additions are less repetitive.

Completed small config cleanup:

- kept election definitions inside the existing app JavaScript
- added a richer election definition object with `type`, `jurisdiction`, `year`, `source`, `label`, `csv`, and `boundaries`
- generated the election selector from those definitions instead of hand-maintaining duplicate option lists
- kept `index.html` and `app/index.html` behaviour identical
- updated `scripts/smoke_static_app.py` so it validates the same definitions and data files

Do not move to external JSON yet. A separate `data/elections.json` can wait until the app is ready to support multiple states or a larger election catalogue.

Possible later targets:

- NSW lower-house elections beyond 2023
- Queensland lower-house elections

Likely prerequisite work:

- config-driven election definitions, starting with the small in-JS cleanup above
- cleaner source/type/year labels
- less VEC-specific naming in shared code
- broader party normalisation
- jurisdiction-specific boundary handling

NSW lower-house feasibility is now proven by the `NSW State 2023` integration:

- official NSWEC district result pages are structured enough to scrape repeatably
- the 2021 redistribution shapefile matches the 2023 election
- small source-specific normalisation is still needed, such as NSW party labels and footnote-marked district names

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

Add comparison UI only.

Insyallah, the best sequence is:

1. comparison UI for matching district/division names
2. consider earlier Victorian state elections if VEC archive pages and boundaries are workable
3. generalise to other states only after that
