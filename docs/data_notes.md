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
data/vic_2018_district_boundaries.geojson
```

For federal Victoria options, use the matching AEC federal division file for the election period:

```text
data/federal_2025_vic_division_boundaries.geojson
data/federal_2022_vic_division_boundaries.geojson
data/federal_2019_vic_division_boundaries.geojson
```

Do not reuse 2022 boundaries for 2018. The 2022 election used boundaries from the 2020-2021 redivision, while 2018 used the previous electoral boundaries.

The 2018 boundary file is adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. The source is licensed CC-BY-4.0 and the repo file keeps the 88 Legislative Assembly district polygons that match the 2018 preference CSV.

The 2025 federal Victoria boundary file is adapted from the AEC `Vic-october-2024-esri.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2025 House of Representatives Distribution of Preferences by Division CSV, event `31496`, filtered to `StateAb == VIC`. The AEC GIS file uses `Mcewen`; the app boundary property is normalised to the AEC result spelling `McEwen` so result rows join to the matching division.

The 2022 federal Victoria boundary file is adapted from the AEC `vic-july-2021-esri.zip` superseded boundary shapefile. The result rows are generated from the AEC 2022 House of Representatives Distribution of Preferences by Division CSV, event `27966`, filtered to `StateAb == VIC`.

The 2019 federal Victoria boundary file is adapted from the AEC `vic-july-2018-esri.zip` redistribution boundary shapefile. The result rows are generated from the AEC 2019 House of Representatives Distribution of Preferences by Division CSV, event `24310`, filtered to `StateAb == VIC`.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
