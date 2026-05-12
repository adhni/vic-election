# Data notes

Source target: Victorian Electoral Commission State Election results pages.

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

Do not reuse 2022 boundaries for 2018. The 2022 election used boundaries from the 2020-2021 redivision, while 2018 used the previous electoral boundaries.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
