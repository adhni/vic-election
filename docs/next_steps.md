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

Completed federal data cleanup:

- removed duplicate Victoria-only 2016, 2019, 2022, and 2025 datasets because the Australia-wide files already contain every Victorian division
- retained Victoria-only 2007, 2010, and 2013 until equivalent national datasets are available
- removed the duplicate selector and CI validation paths, reducing checked-out data by about 30 MB
- tested generic boundary coordinate rounding but deferred it because rounding invalidated some official polygon geometries; future boundary reduction must preserve shared topology

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

- NSW lower-house elections earlier than 2011
- Queensland lower-house elections earlier than 2020
- earlier Tasmania House of Assembly elections if TEC workbooks remain available and the multi-member display is useful

Likely prerequisite work:

- config-driven election definitions, starting with the small in-JS cleanup above
- cleaner source/type/year labels
- less VEC-specific naming in shared code
- broader party normalisation
- jurisdiction-specific boundary handling

NSW lower-house feasibility is now proven by the `NSW State 2023`, `NSW State 2019`, `NSW State 2015`, and `NSW State 2011` integrations:

- official NSWEC district result pages are structured enough to scrape repeatably
- the 2021 redistribution shapefile matches the 2023 election
- the 2013 redistribution MID/MIF boundary dataset matches the 2019 election
- the older `SGE2015` VTR structure still fits the same core importer with a small route/HTML compatibility adjustment
- the older `SGE2011` archive still yields first-preference and final preferred rows, even without full round-by-round distributions
- small source-specific normalisation is still needed, such as NSW party labels and footnote-marked district names

Queensland lower-house feasibility is now also proven by the `Queensland State 2024` and `Queensland State 2020` integrations:

- the ECQ public results app exposes stable district `primary` and `preference` JSON blobs keyed by election stub and district stub
- the same 2017 Queensland redistribution boundary layer matches both 2020 and 2024 because that boundary set remained in force
- the importer can reuse the app's existing long-row model with explicit `transfer`, `progressive`, and `final` rows from the ECQ preference payload

South Australia lower-house feasibility is now proven by the `South Australia State 2022` and `South Australia State 2018` integrations:

- ECSA publishes official House of Assembly first-preference CSVs by district and final distribution CSVs by district
- Data SA publishes the matching 2022 state electorate boundary GeoJSON
- the importer can reuse the single-member state long-row model with first, transfer, progressive, and final rows
- the archived 2018 ECSA pages expose final first-preference and two-candidate-preferred totals for all 47 districts, while Location SA retains the matching 2018 boundary layer
- 2018 therefore includes first and final rows without fabricated intermediate transfers; 2022 retains the complete round-by-round distribution

Western Australia lower-house feasibility is now proven by the `Western Australia State 2025` and `Western Australia State 2021` integrations:

- WAEC publishes final Legislative Assembly XML feeds with district enrolment, first-preference totals, candidate metadata, and turnout fields
- certified WAEC Results and Statistics reports provide the final two-candidate totals for every district, including contests where the election-night indicative pairing was zeroed or superseded
- the 2025 election uses the Landgate 2023 distribution MLA layer, while 2021 uses the ABS 2021 State Electoral Division approximation of the 2019 WA distribution
- both elections cover all 59 districts with first and final rows and no fabricated intermediate preference rounds

Tasmania House of Assembly feasibility is now proven by the `Tasmania State 2025`, `Tasmania State 2024`, and `Tasmania State 2021` integrations:

- official TEC final result workbooks expose candidate first preferences, final count totals, candidate status, elected order, quota, and formal/informal ballot totals
- Tasmania needed a multi-member Hare-Clark path rather than the existing single-winner margin model
- the app now treats Tasmanian divisions as multi-member contests and shows elected member lists, party seat splits, quota, and last-seat gaps
- the boundary files can be generated by filtering existing AEC federal division layers to Bass, Braddon, Clark, Franklin, and Lyons; 2024/2025 use the March 2025 layer, while 2021 uses the 2019 layer
- 2021 uses the older TEC HTML result snippets rather than final-result XLSX workbooks, and elected five members per division rather than seven

New Zealand MMP feasibility is now proven by the `New Zealand General 2023` and `New Zealand General 2020` integrations:

- candidate-vote and party-vote totals are modelled separately
- first-past-the-post electorate contests do not show Australian preference-transfer UI
- the nationwide electorate/list seat result is shown alongside electorate detail
- overlapping general and Māori boundaries use an explicit map-layer toggle
- Port Waikato remains cancelled in the 2023 general election rather than being merged with the later by-election
- the same 65 general and 7 Māori electorate boundary layers are valid for both elections

United Kingdom first-past-the-post feasibility is now proven by the 2024, 2019, and 2017 integrations:

- UK Parliament publishes candidate results for all 650 constituencies in one official CSV
- ONS publishes matching July 2024 and December 2019 Westminster constituency boundaries; the 2017 election used the latter constituency set
- the app reuses its no-transfer election path while keeping New Zealand-only MMP controls separate
- country and party seat summaries provide useful nationwide context without cross-election matching

Malaysia first-past-the-post feasibility is now proven by the GE15, GE14, and GE13 integrations:

- SPR's official open-data portal provides candidate and ballot metadata for the complete election
- the delayed Padang Serai result is incorporated from SPR's companion result file
- three CC0 delimitation datasets combine cleanly into all 222 parliamentary constituencies
- the existing generic FPTP interface supports Malaysia without preference-transfer assumptions

Singapore mixed SMC/GRC feasibility is now proven by the 2025, 2020, and 2015 integrations:

- ELD publishes a complete final-results page and a Statement of Poll for every contested electoral division
- dedicated official data.gov.sg boundaries match every electoral division in each election
- GRC teams are modelled as one vote choice while retaining all elected member names
- election-wide party summaries count elected MPs rather than treating every division as one seat
- the uncontested Marine Parade–Braddell Heights GRC is retained without fabricated votes or turnout

Canada first-past-the-post feasibility is now proven by the `Canada Federal 2025` and `Canada Federal 2021` integrations:

- Elections Canada publishes compact nationwide candidate and riding summary tables
- exact ballot, turnout, official-majority, candidate-count, province, and party-seat checks cover all 343 ridings in 2025 and 338 ridings in 2021
- matching official shapefiles preserve the different riding maps used before and after the latest representation order
- the generic no-transfer interface supports Canadian ridings with jurisdiction-specific party colours and terminology

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
