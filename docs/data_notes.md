# Data notes

Source targets:

- Victorian Electoral Commission State Election results pages
- Australian Electoral Commission Federal Election House of Representatives downloads for Victoria
- Australian Electoral Commission Victoria federal division GIS boundaries

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

## 3. District boundary polygons

The map uses an election-year-specific boundary file:

```text
data/vic_2022_district_boundaries.geojson
```

For earlier elections, use a matching file such as:

```text
data/vic_2014_district_boundaries.geojson
data/vic_2018_district_boundaries.geojson
```

For federal Victoria options, use the matching AEC federal division file for the election period:

```text
data/federal_2025_vic_division_boundaries.geojson
data/federal_2022_vic_division_boundaries.geojson
data/federal_2019_vic_division_boundaries.geojson
data/federal_2016_vic_division_boundaries.geojson
data/federal_2013_vic_division_boundaries.geojson
data/federal_2010_vic_division_boundaries.geojson
```

Do not reuse 2022 boundaries for 2014 or 2018. The 2022 election used boundaries from the 2020-2021 redivision, while 2014 and 2018 used the previous electoral boundaries.

The 2014 and 2018 boundary files are adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. The source is licensed CC-BY-4.0 and the repo files keep the 88 Legislative Assembly district polygons that match the preference CSVs. These boundaries come from the 2012-2013 state redivision, which came into operation for the 2014 State election and remained in place until the writ for the 2022 State election.

The 2025 federal Victoria boundary file is adapted from the AEC `Vic-october-2024-esri.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2025 House of Representatives Distribution of Preferences by Division CSV, event `31496`, filtered to `StateAb == VIC`. The AEC GIS file uses `Mcewen`; the app boundary property is normalised to the AEC result spelling `McEwen` so result rows join to the matching division.

The 2022 federal Victoria boundary file is adapted from the AEC `vic-july-2021-esri.zip` superseded boundary shapefile. The result rows are generated from the AEC 2022 House of Representatives Distribution of Preferences by Division CSV, event `27966`, filtered to `StateAb == VIC`.

The 2019 federal Victoria boundary file is adapted from the AEC `vic-july-2018-esri.zip` redistribution boundary shapefile. The result rows are generated from the AEC 2019 House of Representatives Distribution of Preferences by Division CSV, event `24310`, filtered to `StateAb == VIC`.

The 2016 federal Victoria boundary file is adapted from the AEC `vic-esri-24122010.zip` superseded boundary shapefile. The result rows are generated from the AEC 2016 House of Representatives Distribution of Preferences by Division CSV, event `20499`, filtered to `StateAb == VIC`. The older GIS file uses VicGrid projected metres, legacy field names, and the boundary property spelling `Mcmillan`; the builder reprojects the coordinates to WGS84 lon/lat and normalises the district spelling to the AEC result spelling `McMillan`.

The 2013 federal Victoria boundary file uses the same AEC `vic-esri-24122010.zip` shapefile because those Victorian federal divisions were gazetted on 24 December 2010 and applied to the 2013 federal election. The result rows are generated from the AEC 2013 House of Representatives Distribution of Preferences by Division CSV, event `17496`, filtered to `StateAb == VIC`.

The 2010 federal Victoria boundary file is adapted from the AEC `national-esri-2010.zip` shapefile because the AEC states the 2010 federal election in Victoria ran on the same boundaries as the 2007 election while the 2010 Victorian redistribution was still underway. The result rows are generated from the AEC 2010 House of Representatives Distribution of Preferences by Division CSV, event `15508`, filtered to `StateAb == VIC`. The older national GIS file provides `ELECT_DIV` and `STATE` fields but no numeric division ID, so the builder filters `STATE == VIC` and leaves `division_id` blank for this boundary source.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
