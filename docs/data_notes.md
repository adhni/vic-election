# Data notes

Source target: Victorian Electoral Commission 2022 State Election results pages.

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

The map uses:

```text
data/vic_2022_district_boundaries.geojson
```

Boundary source: Wikimedia Commons map data derived from Electoral Boundaries Commission Victoria 2022 boundaries, licensed CC-BY-4.0.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
