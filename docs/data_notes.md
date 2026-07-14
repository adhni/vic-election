# Data notes

Source targets:

- Victorian Electoral Commission State Election results pages
- Australian Electoral Commission Federal Election House of Representatives downloads
- Australian Electoral Commission federal division GIS boundaries
- Tasmanian Electoral Commission House of Assembly result workbooks
- New Zealand Electoral Commission 2023 and 2020 General Election result pages
- Stats NZ 2020 general and Māori electorate boundaries
- UK Parliament 2024 general election candidate results
- ONS July 2024 Westminster parliamentary constituency boundaries
- SPR Malaysia GE15 official candidate results
- ElectionData.MY parliamentary delimitation boundaries for Peninsular Malaysia, Sabah, and Sarawak

This repo is built around three levels of data:

## 1. District-level result metadata

Examples:

- elected member
- elected party
- enrolment
- formal votes
- informal votes
- turnout

## 2. Preference distribution rows

The app expects a long table where each row is one candidate's vote value in one count stage.

Important row types:

- `first`: first preference votes
- `transfer`: votes transferred from an excluded candidate
- `progressive`: progressive total after a round
- `final`: final standing after distribution
- `party_vote`: New Zealand's separate MMP party vote within an electorate

## 3. District boundary polygons

The map uses an election-year-specific boundary file:

```text
data/vic_2022_district_boundaries.geojson
```

For earlier elections, use a matching file such as:

```text
data/vic_2014_district_boundaries.geojson
data/vic_2018_district_boundaries.geojson
data/vic_2010_district_boundaries.geojson
data/vic_2006_district_boundaries.geojson
```

For Australia-wide federal options, use the matching national AEC federal division file for the election period:

```text
data/federal_2025_au_division_boundaries.geojson
data/federal_2022_au_division_boundaries.geojson
data/federal_2019_au_division_boundaries.geojson
data/federal_2016_au_division_boundaries.geojson
```

Victoria-only federal options are retained only for years without an Australia-wide dataset:

```text
data/federal_2013_vic_division_boundaries.geojson
data/federal_2010_vic_division_boundaries.geojson
data/federal_2007_vic_division_boundaries.geojson
```

Do not reuse 2022 boundaries for earlier elections. The 2022 election used boundaries from the 2020-2021 redivision, 2014 and 2018 used the 2012-2013 redivision, and 2006 and 2010 used the earlier 2001 Legislative Assembly boundaries.

The 2014 and 2018 boundary files are adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. The source is licensed CC-BY-4.0 and the repo files keep the 88 Legislative Assembly district polygons that match the preference CSVs. These boundaries come from the 2012-2013 state redivision, which came into operation for the 2014 State election and remained in place until the writ for the 2022 State election.

The 2006 and 2010 state boundary files are adapted from the Victorian Government / VEC Vicmap Admin State Assembly Polygon 2001 WFS dataset, `open-data-platform:state_assembly_2001`. The repo files keep the 88 Legislative Assembly district polygons and normalise `district_label` values such as `Gippsland East District` to the app's `district` property.

The Victorian state 2010 result rows are generated from the VEC historical archive under `state2010/state2010resultsummary.html`. The 2010 pages use two source shapes: 44 districts expose full distribution pages, while 44 districts expose first preference plus two-candidate-preferred result tables on the district page. The scraper preserves full transfer/progressive rows where VEC published them and uses the district page's final preferred table where a full distribution page is not linked.

The Victorian state 2006 result rows are generated from the VEC historical archive under `state2006/state2006resultsummary.html`. The 2006 pages use the same legacy HTML shape as 2010: 49 districts expose full distribution pages, while 39 districts expose result-page-only tables. Some full distributions stop when a candidate reaches an absolute majority, so final rows may include more than two candidates. Gippsland East follows the archived HTML standard distribution; the later VEC report describes an extra statistical distribution.

The NSW state 2011 result rows are generated from the official NSWEC district summary archive under `SGE2011/la_index.htm`. Those pages expose final first-preference tables and final two-candidate-preferred tables but not machine-readable round-by-round distributions, so the scraper stores first rows plus final preferred rows for each district. The boundary file is adapted from the Terria/NationalMap historical `FID_SED_2011_AUST` ABS State Electoral Division vector tiles at zoom 6, filtered to the 93 NSW districts used at the 26 March 2011 election.

The Queensland state 2024 result rows are generated from the Electoral Commission of Queensland public results JSON service under `resultsdata.elections.qld.gov.au`, using the `SGE2024` district `primary` and `preference` count files. The boundary file is generated from the official Queensland Spatial `State electoral boundary 2017` ArcGIS REST layer, which the dataset metadata states remains the official state electoral boundary set until the next redistribution.

The Queensland state 2020 result rows are generated from the same Electoral Commission of Queensland JSON service, using the `state2020` district `primary` and `preference` count files. The 2020 boundary file uses the same Queensland Spatial `State electoral boundary 2017` layer because those 93 districts were also in force for the 31 October 2020 election.

The Western Australia 2025 and 2021 Legislative Assembly rows are generated from official WAEC final XML result feeds for enrolment, first preferences, and turnout metadata. Final two-candidate totals come from the certified WAEC Results and Statistics reports because the media XML can retain zeroed election-night indicative pairings rather than the final distribution pairing. Both elections therefore contain official first and final rows without fabricated intermediate exclusions. The 2025 boundaries use Landgate's current MLA layer for the 2023 distribution; the 2021 boundaries use the ABS 2021 State Electoral Division layer filtered to Western Australia, matching all 59 districts from the 2019 distribution.

The Northern Territory 2024 and 2020 Legislative Assembly rows are generated from the official NTEC electorate result summaries. They preserve each candidate's first preferences and the published final two-candidate-preferred totals, plus enrolment, formal, informal, total-counted, and turnout metadata. Intermediate exclusion counts are not inferred. The boundary files use the ABS 2024 and ABS 2021 State Electoral Division layers respectively, filtered to the 25 Northern Territory electorates and normalised to the app's district property.

The Tasmania state 2025 and 2024 result rows are generated from the Tasmanian Electoral Commission final House of Assembly result workbooks for the divisions of Bass, Braddon, Clark, Franklin, and Lyons. Tasmania uses Hare-Clark STV, so each division elects seven members rather than a single winner. The app stores first-preference rows and final-count rows with extra fields for quota, elected order, elected status, and members to elect. The boundary files are filtered from the AEC March 2025 national federal division boundary file because Tasmanian House of Assembly divisions share the names and boundaries of the five Tasmanian federal divisions.

The New Zealand 2023 and 2020 rows are generated from Electoral Commission candidate-vote and party-vote totals for all 72 electorates. The 2020 builder matches each official named candidate total to the public electorate-candidate table rather than assuming both sources use the same row order; the detailed-page vote columns must match the named totals exactly. Party labels are aligned to Wikipedia's public electorate-candidate tables because the Commission's candidate-list CSV currently blocks automated downloads. Candidate voting uses first past the post, so `first` and `final` rows are identical and the app hides preference-transfer views. Port Waikato is marked `cancelled` only in 2023 and retains its party vote; all 72 electorate contests were completed in 2020. The boundary files combine Stats NZ's 65 general and 7 Māori electorate layers used at both elections; the app toggles them because those layers overlap geographically. Stats NZ boundary data is licensed CC BY 4.0.

The United Kingdom 2024 rows are generated from UK Parliament's official general-election candidacies CSV for all 650 House of Commons constituencies. Candidate totals are checked against each constituency's valid-vote total, official majority, turnout metadata, country split, and nationwide winning-party seat totals. The UK uses first past the post, so `first` and `final` rows are identical and the app hides preference-transfer views. Boundaries come from the ONS July 2024 Westminster Parliamentary Constituencies UK BSC ArcGIS layer; the builder simplifies the already super-generalised polygons for the static app and normalises the single Glyndŵr spelling difference between the two official sources.

The Malaysia 2022 rows are generated from the official Election Commission (SPR) open-data portal's `keputusan-pru` result file, supplemented by its `keputusan-prk` file for P.017 Padang Serai, where polling was delayed until 7 December 2022. The combined dataset contains all 945 candidates in all 222 Dewan Rakyat constituencies. Candidate votes, rejected ballots, unreturned ballots, electorate size, turnout, computed winning margins, state totals, and official nationwide party seat totals are validated. Exact ballot totals are used to calculate turnout because three SPR one-decimal turnout values differ from the underlying totals by up to 0.33 percentage points. Malaysia uses first past the post, so `first` and `final` rows are identical. The boundary file combines the ElectionData.MY CC0 Peninsular 2018, Sabah 2019, and Sarawak 2015 parliamentary delimitation datasets that were in force for GE15.

The 2025 federal Australia boundary file is adapted from the AEC `AUS-March-2025-esri.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2025 House of Representatives Distribution of Preferences by Division CSV, event `31496`, with no `StateAb` filtering.

The 2022 federal Australia boundary file is adapted from the AEC `2021-Cwlth_electoral_boundaries_ESRI.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2022 House of Representatives Distribution of Preferences by Division CSV, event `27966`, with no `StateAb` filtering.

The 2019 federal Australia boundary file is adapted from the AEC `national-esri-fe2019.zip` shapefile. The result rows are generated from the AEC 2019 House of Representatives Distribution of Preferences by Division CSV, event `24310`, with no `StateAb` filtering. The boundary file uses the legacy spelling `Mcpherson`; the builder normalises this to the AEC result spelling `McPherson`.

The 2016 federal Australia boundary file is assembled from the official AEC jurisdiction files used for the 2016 election period: `act-tab-20072016.zip`, `nsw-esri-06042016.zip`, `NT-20080919-elb.zip`, `qld-shape-files-13012010.zip`, `sa-esri-16122011.zip`, `TAS-20080216-elb.zip`, `vic-esri-24122010.zip`, and `wa-esri-19012016.zip`. The result rows are generated from the AEC 2016 House of Representatives Distribution of Preferences by Division CSV, event `20499`, with no `StateAb` filtering. The builder reprojects each jurisdiction to WGS84 lon/lat and normalises `Mcpherson` to `McPherson`.

The 2013 federal Victoria boundary file uses the same AEC `vic-esri-24122010.zip` shapefile because those Victorian federal divisions were gazetted on 24 December 2010 and applied to the 2013 federal election. The result rows are generated from the AEC 2013 House of Representatives Distribution of Preferences by Division CSV, event `17496`, filtered to `StateAb == VIC`.

The 2010 federal Victoria boundary file is adapted from the AEC `national-esri-2010.zip` shapefile because the AEC states the 2010 federal election in Victoria ran on the same boundaries as the 2007 election while the 2010 Victorian redistribution was still underway. The result rows are generated from the AEC 2010 House of Representatives Distribution of Preferences by Division CSV, event `15508`, filtered to `StateAb == VIC`. The older national GIS file provides `ELECT_DIV` and `STATE` fields but no numeric division ID, so the builder filters `STATE == VIC` and leaves `division_id` blank for this boundary source.

The 2007 federal Victoria boundary file uses the same AEC `national-esri-2010.zip` shapefile filtered to Victoria because the Victorian federal division names and shapes match the 2007-era boundaries also used for the 2010 election. The result rows are generated from the AEC 2007 House of Representatives Distribution of Preferences by Division CSV, event `13745`, filtered to `StateAb == VIC`.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
