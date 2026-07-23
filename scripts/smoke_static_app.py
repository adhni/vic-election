#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from pathlib import Path


REQUIRED_ELECTION_FIELDS = {"key", "label", "type", "jurisdiction", "year", "source", "csv", "boundaries"}
REQUIRED_RANKINGS_MARKERS = (
    'id="rankingsPanel"',
    "Closest ${electorateLabel(2)}",
    "Largest winning margins",
    "Changed on preferences",
    "Biggest winner transfer gains",
)
REQUIRED_ELECTION_PICKER_MARKERS = (
    'id="electionCountry"',
    'id="electionYear"',
    "function populateElectionOptions(country)",
    "function syncElectionPicker()",
    "const electionCountry = election =>",
    '<optgroup label="${label}">',
)
REQUIRED_NZ_MARKERS = (
    '"system": "mmp-fpp"',
    '["party", "party-vote", "close"]',
    "function syncBoundaryTypeToActiveDistrict()",
)
REQUIRED_SINGAPORE_MARKERS = (
    '"key": "singapore-2025"',
    '"key": "singapore-2020"',
    '"key": "singapore-2015"',
    '"teamElection": true',
    '"totalSeats": 97',
    '"totalSeats": 93',
    '"totalSeats": 89',
    '"summaryRegions": ["SMC", "GRC"]',
    '"Plurality block vote"',
)
REQUIRED_INTERNATIONAL_HISTORY_MARKERS = (
    '"key": "uk-2019"',
    '"key": "uk-2017"',
    '"key": "malaysia-2018"',
    '"key": "malaysia-2013"',
)
REQUIRED_CANADA_MARKERS = (
    '"key": "canada-2025"',
    '"key": "canada-2021"',
    '"jurisdiction": "Canada"',
    '"totalSeats": 343',
    '"totalSeats": 338',
    'return count === 1 ? "riding" : "ridings"',
)
REQUIRED_INDIA_MARKERS = (
    '"key": "india-2024"',
    '"jurisdiction": "India"',
    '"totalSeats": 543',
    '"areaLabel": "State / union territory"',
    '"Bharatiya Janata Party": "BJP"',
    "function rankedForOutcome(d, totals)",
)
REQUIRED_THAILAND_MARKERS = (
    '"key": "thailand-2026"',
    '"jurisdiction": "Thailand"',
    '"systemLabel": "Parallel voting · constituency ballot FPTP"',
    '"electorateSeats": 400',
    '"listSeats": 100',
    '"totalSeats": 500',
    '"cartogram": true',
    "not a legal-boundary map",
    'activeElection().jurisdiction === "Thailand"',
)
REQUIRED_US_MARKERS = (
    '"key": "us-house-2024"',
    '"jurisdiction": "United States"',
    '"totalSeats": 435',
    '"areaLabel": "State"',
    '"systemLabel": "Plurality / state-specific rules"',
    'if (p === "democratic") return "#2166ac";',
    'if (p === "republican") return "#c62828";',
    'Number(d.enrolment || 0) > 0',
)
REQUIRED_INDONESIA_MARKERS = (
    '"key": "indonesia-president-2024"',
    '"key": "indonesia-president-2019"',
    '"key": "indonesia-president-2014"',
    '"contestType": "presidential"',
    '"defaultGeography": "province"',
    '"kabupaten-kota"',
    'id="geographyModes"',
    "function setGeography(geography, replaceUrl = false)",
    "function drillDownProvince(province)",
    'activeElection().contestType === "presidential"',
    'firstRow.result_note || ""',
    "provinces and kabupaten/kota do not elect separate presidents",
    "Later-created districts are dissolved into their election-time parents",
    "No digitised vote",
    'if (activeElection().contestType === "presidential") return winningParty(d);',
    ': winningParty(d)))]',
)
REQUIRED_PHILIPPINES_MARKERS = (
    '"key": "philippines-president-2022"',
    '"key": "philippines-vice-president-2022"',
    '"jurisdiction": "Philippines"',
    '"candidateVoteLabel": "Presidential candidate vote"',
    '"candidateVoteLabel": "Vice-presidential candidate vote"',
    '"districtLabel": "Province / city"',
    'if (activeElection().jurisdiction === "Philippines")',
)
REQUIRED_MEXICO_MARKERS = (
    '"key": "mexico-president-2024"',
    '"jurisdiction": "Mexico"',
    '"districtLabel": "Federal district"',
    '"wideMobileMap": true',
    '"nationalResults": [',
    '["Sheinbaum", 61.27]',
    'if (activeElection().jurisdiction === "Mexico")',
)
REQUIRED_COMPACT_FPP_MARKERS = (
    "if (isFppElection() && !d.rounds.length && Object.keys(d.first).length)",
    'totals: { ...d.first }, final: true, synthetic: true',
)
EXPECTED_ELECTION_ALIASES = {
    "federal-2025-vic": "federal-2025-au",
    "federal-2022-vic": "federal-2022-au",
    "federal-2019-vic": "federal-2019-au",
    "federal-2016-vic": "federal-2016-au",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_election_definitions(html_file: Path) -> list[dict[str, object]]:
    html = html_file.read_text(encoding="utf-8")
    if '<select id="electionYear"></select>' not in html:
        raise SystemExit(f"{html_file}: election selector should be generated from config")
    for marker in REQUIRED_ELECTION_PICKER_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing election-picker marker {marker!r}")
    for marker in REQUIRED_RANKINGS_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing rankings UI marker {marker!r}")
    for marker in REQUIRED_NZ_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing NZ MMP UI marker {marker!r}")
    for marker in REQUIRED_SINGAPORE_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Singapore team-election UI marker {marker!r}")
    for marker in REQUIRED_INTERNATIONAL_HISTORY_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing international history marker {marker!r}")
    for marker in REQUIRED_CANADA_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Canada FPTP UI marker {marker!r}")
    for marker in REQUIRED_INDIA_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing India FPTP UI marker {marker!r}")
    for marker in REQUIRED_THAILAND_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Thailand 2026 UI marker {marker!r}")
    for marker in REQUIRED_US_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing U.S. House UI marker {marker!r}")
    for marker in REQUIRED_INDONESIA_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Indonesia presidential UI marker {marker!r}")
    for marker in REQUIRED_PHILIPPINES_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Philippines 2022 UI marker {marker!r}")
    for marker in REQUIRED_MEXICO_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing Mexico 2024 UI marker {marker!r}")
    for marker in REQUIRED_COMPACT_FPP_MARKERS:
        if marker not in html:
            raise SystemExit(f"{html_file}: missing compact FPP reconstruction marker {marker!r}")
    if html.count("syncBoundaryTypeToActiveDistrict();") < 2:
        raise SystemExit(f"{html_file}: NZ map layer is not synchronized after filters and reset")
    match = re.search(r"const electionDefinitions = (\[.*?\]);", html, flags=re.S)
    if not match:
        raise SystemExit(f"{html_file}: missing electionDefinitions config")
    definitions = json.loads(match.group(1))
    if not definitions:
        raise SystemExit(f"{html_file}: electionDefinitions is empty")
    seen = set()
    for election in definitions:
        missing = REQUIRED_ELECTION_FIELDS - set(election)
        if missing:
            raise SystemExit(f"{html_file}: {election.get('key', '<missing key>')}: missing {sorted(missing)}")
        key = str(election["key"])
        if key in seen:
            raise SystemExit(f"{html_file}: duplicate election key {key}")
        seen.add(key)
    return definitions


def load_election_aliases(html_file: Path) -> dict[str, str]:
    html = html_file.read_text(encoding="utf-8")
    match = re.search(r"const electionYearAliases = (\{.*?\});", html, flags=re.S)
    if not match:
        raise SystemExit(f"{html_file}: missing electionYearAliases config")
    aliases = json.loads(match.group(1))
    if aliases != EXPECTED_ELECTION_ALIASES:
        raise SystemExit(f"{html_file}: unexpected election aliases {aliases}")
    return aliases


def walk_coordinates(coords, visit) -> None:
    if coords and isinstance(coords[0], (int, float)):
        visit(coords[0], coords[1])
        return
    for part in coords or []:
        walk_coordinates(part, visit)


def ring_path(ring, min_lon, max_lon, min_lat, max_lat) -> str:
    width, height, pad = 960, 560, 14
    scale = min((width - pad * 2) / (max_lon - min_lon), (height - pad * 2) / (max_lat - min_lat))
    map_w = (max_lon - min_lon) * scale
    map_h = (max_lat - min_lat) * scale
    offset_x = (width - map_w) / 2
    offset_y = (height - map_h) / 2
    parts = []
    for i, (lon, lat) in enumerate(ring):
        x = offset_x + (lon - min_lon) * scale
        y = offset_y + (max_lat - lat) * scale
        parts.append(f"{'L' if i else 'M'}{x:.1f},{y:.1f}")
    return "".join(parts) + "Z"


def geometry_path(geometry, bounds) -> str:
    min_lon, max_lon, min_lat, max_lat = bounds
    if geometry["type"] == "Polygon":
        return "".join(ring_path(ring, min_lon, max_lon, min_lat, max_lat) for ring in geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return "".join(
            ring_path(ring, min_lon, max_lon, min_lat, max_lat)
            for polygon in geometry["coordinates"]
            for ring in polygon
        )
    return ""


def smoke_election(key: str, csv_path: Path, boundary_path: Path, system: str) -> None:
    rows = read_csv(csv_path)
    districts = {row["district"] for row in rows}
    geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = geojson["features"]
    names = {feature["properties"]["district"] for feature in features}
    if names != districts:
        raise SystemExit(f"{key}: CSV/boundary mismatch: {sorted(names ^ districts)}")

    min_lon, max_lon, min_lat, max_lat = float("inf"), float("-inf"), float("inf"), float("-inf")
    for feature in features:
        def visit(lon, lat):
            nonlocal min_lon, max_lon, min_lat, max_lat
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
        walk_coordinates(feature["geometry"]["coordinates"], visit)

    paths = [geometry_path(feature["geometry"], (min_lon, max_lon, min_lat, max_lat)) for feature in features]
    if len([path for path in paths if path.startswith("M") and len(path) > 20]) != len(features):
        raise SystemExit(f"{key}: map path generation failed")
    row_types = {row["row_type"] for row in rows}
    if system in {"fpp", "mmp-fpp"}:
        if "first" not in row_types or "final" in row_types:
            raise SystemExit(f"{key}: FPP data should contain compact first rows without duplicate final rows")
    elif "final" not in row_types:
        raise SystemExit(f"{key}: no final rows")
    print(f"{key}: {len(districts)} districts, {len(rows)} rows, {len(paths)} map paths")


def main() -> None:
    html_files = [Path("index.html"), Path("app/index.html")]
    definitions_by_file = {html_file: load_election_definitions(html_file) for html_file in html_files}
    aliases_by_file = {html_file: load_election_aliases(html_file) for html_file in html_files}
    first = definitions_by_file[html_files[0]]
    for html_file, definitions in definitions_by_file.items():
        if definitions != first:
            raise SystemExit(f"{html_file}: electionDefinitions does not match {html_files[0]}")
        keys = {str(election["key"]) for election in definitions}
        for old_key, new_key in aliases_by_file[html_file].items():
            if old_key in keys:
                raise SystemExit(f"{html_file}: aliased key {old_key} should not remain selectable")
            if new_key not in keys:
                raise SystemExit(f"{html_file}: alias target {new_key} is not selectable")

    for election in first:
        geographies = election.get("geographies")
        if geographies:
            default = str(election.get("defaultGeography", ""))
            if default not in geographies:
                raise SystemExit(f"{election['key']}: invalid default geography {default!r}")
            if election["csv"] != geographies[default]["csv"] or election["boundaries"] != geographies[default]["boundaries"]:
                raise SystemExit(f"{election['key']}: top-level files must match the default geography")
            for geography, dataset in geographies.items():
                smoke_election(
                    f"{election['key']}:{geography}", Path(str(dataset["csv"])),
                    Path(str(dataset["boundaries"])), str(election.get("system", "")),
                )
        else:
            smoke_election(
                str(election["key"]), Path(str(election["csv"])),
                Path(str(election["boundaries"])), str(election.get("system", "")),
            )
    print("Static app smoke passed")


if __name__ == "__main__":
    main()
