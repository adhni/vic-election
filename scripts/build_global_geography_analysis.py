#!/usr/bin/env python3
"""Build reusable political-geography assets for supported international elections."""

from __future__ import annotations

import csv
import heapq
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
EXPLORER_HTML = ROOT / "app" / "index.html"

OUTPUT_PATHS = {
    "New Zealand": ROOT / "data" / "new_zealand_geography_analysis.json",
    "Sweden": ROOT / "data" / "sweden_geography_analysis.json",
    "South Africa": ROOT / "data" / "south_africa_geography_analysis.json",
    "Taiwan": ROOT / "data" / "taiwan_geography_analysis.json",
    "Türkiye": ROOT / "data" / "turkiye_geography_analysis.json",
    "United States": ROOT / "data" / "us_president_geography_analysis.json",
    "Germany": ROOT / "data" / "germany_geography_analysis.json",
    "Poland": ROOT / "data" / "poland_geography_analysis.json",
    "Spain": ROOT / "data" / "spain_geography_analysis.json",
    "Portugal": ROOT / "data" / "portugal_geography_analysis.json",
    "Netherlands": ROOT / "data" / "netherlands_geography_analysis.json",
}

BLOCS = {
    "New Zealand": ("Labour", "National", "Green", "ACT", "NZ First", "Te Pāti Māori", "Other"),
    "Sweden": ("Social Democrats", "Moderates", "Sweden Democrats", "Centre", "Left", "Christian Democrats", "Liberals", "Greens", "Other"),
    "South Africa": ("ANC", "DA", "EFF", "MK", "IFP", "Other"),
    "Taiwan": ("DPP", "KMT", "Third party", "Other"),
    "Türkiye": ("Erdoğan", "CHP / main opposition", "Kurdish left", "Other"),
    "United States": ("Democratic", "Republican", "Other"),
    "Germany": ("CDU / CSU", "SPD", "Greens", "AfD", "FDP", "The Left", "BSW", "Other"),
    "Poland": ("PiS-backed", "Civic Coalition", "Confederation right", "Left", "Centre / Third Way", "Other"),
    "Spain": ("PSOE / PSC", "PP", "Vox", "Broad left", "Regional parties", "Other"),
    "Portugal": ("AD / PSD-CDS", "PS", "Chega", "Liberal Initiative", "Left Bloc", "CDU", "Livre / PAN", "Other"),
    "Netherlands": ("PVV", "GL-PvdA", "VVD", "NSC", "D66", "CDA", "BBB", "SP / PvdD", "Other"),
}

COLORS = {
    "New Zealand": {
        "Labour": "#d94b49", "National": "#2f61bf", "Green": "#2d8a4b", "ACT": "#e3b21a",
        "NZ First": "#343a40", "Te Pāti Māori": "#8b4aa8", "Other": "#7a6a55",
    },
    "Sweden": {
        "Social Democrats": "#d94b49", "Moderates": "#2f61bf", "Sweden Democrats": "#d1a600",
        "Centre": "#3e9447", "Left": "#a52a52", "Christian Democrats": "#334a8b",
        "Liberals": "#28a6c7", "Greens": "#63a844", "Other": "#72777f",
    },
    "South Africa": {
        "ANC": "#238443", "DA": "#2878b5", "EFF": "#c51b32", "MK": "#168a83",
        "IFP": "#d47d20", "Other": "#72777f",
    },
    "Taiwan": {"DPP": "#2a9d55", "KMT": "#2f61bf", "Third party": "#d68a1d", "Other": "#72777f"},
    "Türkiye": {
        "Erdoğan": "#e28a22", "CHP / main opposition": "#d94b49", "Kurdish left": "#7c48aa", "Other": "#72777f",
    },
    "United States": {"Democratic": "#2f61bf", "Republican": "#d94b49", "Other": "#72777f"},
    "Germany": {
        "CDU / CSU": "#343a40", "SPD": "#d94b49", "Greens": "#2d8a4b", "AfD": "#2d75b6",
        "FDP": "#d8aa16", "The Left": "#b23a78", "BSW": "#7c48aa", "Other": "#72777f",
    },
    "Poland": {
        "PiS-backed": "#2859a9", "Civic Coalition": "#e28a22", "Confederation right": "#70452c",
        "Left": "#c13c72", "Centre / Third Way": "#d0aa17", "Other": "#72777f",
    },
    "Spain": {
        "PSOE / PSC": "#d94b49", "PP": "#2f61bf", "Vox": "#3b9145", "Broad left": "#7c48aa",
        "Regional parties": "#d68a1d", "Other": "#72777f",
    },
    "Portugal": {
        "AD / PSD-CDS": "#2f61bf", "PS": "#d94b72", "Chega": "#244276", "Liberal Initiative": "#29a3c1",
        "Left Bloc": "#b52d3f", "CDU": "#2d8a4b", "Livre / PAN": "#76a83d", "Other": "#72777f",
    },
    "Netherlands": {
        "PVV": "#2d75b6", "GL-PvdA": "#c33c4f", "VVD": "#243e84", "NSC": "#d19c19",
        "D66": "#5a9f45", "CDA": "#24724c", "BBB": "#76a83d", "SP / PvdD": "#9f315a", "Other": "#72777f",
    },
}


def spec(
    key: str,
    jurisdiction: str,
    *,
    geography: str = "",
    row_type: str = "first",
    boundary_group: str,
    history_group: str,
    comparison_key: str | None = None,
    period_label: str | None = None,
    cluster_group_property: str | None = None,
    clusters: bool = True,
    vote_label: str = "Vote share",
) -> dict[str, object]:
    analysis_key = f"{key}:{geography}" if geography else key
    return {
        "analysisKey": analysis_key,
        "electionKey": key,
        "jurisdiction": jurisdiction,
        "geography": geography,
        "rowType": row_type,
        "boundaryGroup": boundary_group,
        "historyGroup": history_group,
        "comparisonKey": comparison_key,
        "periodLabel": period_label,
        "clusterGroupProperty": cluster_group_property,
        "clusters": clusters,
        "voteLabel": vote_label,
    }


SPECS = [
    spec("nz-2020", "New Zealand", row_type="party_vote", boundary_group="nz-electorates-2020", history_group="nz-party-vote", cluster_group_property="electorate_type", vote_label="Party vote"),
    spec("nz-2023", "New Zealand", row_type="party_vote", boundary_group="nz-electorates-2020", history_group="nz-party-vote", comparison_key="nz-2020", cluster_group_property="electorate_type", vote_label="Party vote"),
    spec("sweden-riksdag-2018", "Sweden", boundary_group="sweden-municipalities-2018", history_group="sweden-riksdag", vote_label="Party-list vote"),
    spec("sweden-riksdag-2022", "Sweden", boundary_group="sweden-municipalities-2022", history_group="sweden-riksdag", vote_label="Party-list vote"),
    spec("south-africa-national-2014", "South Africa", geography="municipality", boundary_group="south-africa-municipalities-2011", history_group="south-africa-national:municipality", vote_label="National party vote"),
    spec("south-africa-national-2019", "South Africa", geography="municipality", boundary_group="south-africa-municipalities-2018", history_group="south-africa-national:municipality", vote_label="National party vote"),
    spec("south-africa-national-2024", "South Africa", geography="municipality", boundary_group="south-africa-municipalities-2018", history_group="south-africa-national:municipality", comparison_key="south-africa-national-2019:municipality", vote_label="National-ballot party vote"),
    spec("south-africa-national-2014", "South Africa", geography="province", boundary_group="south-africa-provinces", history_group="south-africa-national:province", vote_label="National party vote"),
    spec("south-africa-national-2019", "South Africa", geography="province", boundary_group="south-africa-provinces", history_group="south-africa-national:province", comparison_key="south-africa-national-2014:province", vote_label="National party vote"),
    spec("south-africa-national-2024", "South Africa", geography="province", boundary_group="south-africa-provinces", history_group="south-africa-national:province", comparison_key="south-africa-national-2019:province", vote_label="National-ballot party vote"),
    spec("taiwan-president-2016", "Taiwan", boundary_group="taiwan-townships", history_group="taiwan-president", vote_label="Presidential ticket vote"),
    spec("taiwan-president-2020", "Taiwan", boundary_group="taiwan-townships", history_group="taiwan-president", comparison_key="taiwan-president-2016", vote_label="Presidential ticket vote"),
    spec("taiwan-president-2024", "Taiwan", boundary_group="taiwan-townships", history_group="taiwan-president", comparison_key="taiwan-president-2020", vote_label="Presidential ticket vote"),
    spec("turkiye-president-2014", "Türkiye", boundary_group="turkiye-provinces", history_group="turkiye-president-round-1", period_label="2014", vote_label="Presidential vote"),
    spec("turkiye-president-2018", "Türkiye", boundary_group="turkiye-provinces", history_group="turkiye-president-round-1", comparison_key="turkiye-president-2014", period_label="2018", vote_label="Presidential vote"),
    spec("turkiye-president-2023-round-1", "Türkiye", boundary_group="turkiye-provinces", history_group="turkiye-president-round-1", comparison_key="turkiye-president-2018", period_label="2023 R1", vote_label="First-round presidential vote"),
    spec("turkiye-president-2023-round-2", "Türkiye", boundary_group="turkiye-provinces", history_group="turkiye-president-round-2", period_label="2023 R2", vote_label="Runoff presidential vote"),
    spec("us-president-2008", "United States", geography="county", boundary_group="us-counties-2008-2016", history_group="us-president:county", vote_label="Presidential vote"),
    spec("us-president-2012", "United States", geography="county", boundary_group="us-counties-2008-2016", history_group="us-president:county", comparison_key="us-president-2008:county", vote_label="Presidential vote"),
    spec("us-president-2016", "United States", geography="county", boundary_group="us-counties-2008-2016", history_group="us-president:county", comparison_key="us-president-2012:county", vote_label="Presidential vote"),
    spec("us-president-2020", "United States", geography="county", boundary_group="us-counties-2020", history_group="us-president:county", vote_label="Presidential vote"),
    spec("us-president-2024", "United States", geography="county", boundary_group="us-counties-2024", history_group="us-president:county", vote_label="Presidential vote"),
    spec("us-president-2008", "United States", geography="state", boundary_group="us-states", history_group="us-president:state", vote_label="Presidential vote"),
    spec("us-president-2012", "United States", geography="state", boundary_group="us-states", history_group="us-president:state", comparison_key="us-president-2008:state", vote_label="Presidential vote"),
    spec("us-president-2016", "United States", geography="state", boundary_group="us-states", history_group="us-president:state", comparison_key="us-president-2012:state", vote_label="Presidential vote"),
    spec("us-president-2020", "United States", geography="state", boundary_group="us-states", history_group="us-president:state", comparison_key="us-president-2016:state", vote_label="Presidential vote"),
    spec("us-president-2024", "United States", geography="state", boundary_group="us-states", history_group="us-president:state", comparison_key="us-president-2020:state", vote_label="Presidential vote"),
    spec("germany-bundestag-2017", "Germany", row_type="party_vote", boundary_group="germany-constituencies-2017", history_group="germany-zweitstimme", vote_label="Zweitstimme"),
    spec("germany-bundestag-2021", "Germany", row_type="party_vote", boundary_group="germany-constituencies-2021", history_group="germany-zweitstimme", vote_label="Zweitstimme"),
    spec("germany-bundestag-2025", "Germany", row_type="party_vote", boundary_group="germany-constituencies-2025", history_group="germany-zweitstimme", vote_label="Zweitstimme"),
    spec("poland-president-2020-round-1", "Poland", boundary_group="poland-voivodeships", history_group="poland-president-round-1", period_label="2020 R1", vote_label="First-round presidential vote"),
    spec("poland-president-2025-round-1", "Poland", boundary_group="poland-voivodeships", history_group="poland-president-round-1", comparison_key="poland-president-2020-round-1", period_label="2025 R1", vote_label="First-round presidential vote"),
    spec("poland-president-2020-round-2", "Poland", boundary_group="poland-voivodeships", history_group="poland-president-round-2", period_label="2020 R2", vote_label="Runoff presidential vote"),
    spec("poland-president-2025-round-2", "Poland", boundary_group="poland-voivodeships", history_group="poland-president-round-2", comparison_key="poland-president-2020-round-2", period_label="2025 R2", vote_label="Runoff presidential vote"),
    spec("spain-congress-2019", "Spain", boundary_group="spain-provinces-2021", history_group="spain-congress", vote_label="Congress party vote"),
    spec("spain-congress-2023", "Spain", boundary_group="spain-provinces-2021", history_group="spain-congress", comparison_key="spain-congress-2019", vote_label="Congress party vote"),
    spec("portugal-legislative-2024", "Portugal", boundary_group="portugal-districts-2024-2025", history_group="portugal-legislative", clusters=False, vote_label="Assembly party vote"),
    spec("portugal-legislative-2025", "Portugal", boundary_group="portugal-districts-2024-2025", history_group="portugal-legislative", comparison_key="portugal-legislative-2024", clusters=False, vote_label="Assembly party vote"),
    spec("netherlands-house-2023", "Netherlands", boundary_group="netherlands-municipalities-2024", history_group="netherlands-house", vote_label="House party vote"),
    spec("netherlands-house-2025", "Netherlands", boundary_group="netherlands-municipalities-2024", history_group="netherlands-house", comparison_key="netherlands-house-2023", vote_label="House party vote"),
]


def normalise(raw: str) -> str:
    return " ".join((raw or "").strip().split())


def map_new_zealand(raw: str) -> str:
    party = normalise(raw)
    return {
        "Labour Party": "Labour", "National Party": "National", "Green Party": "Green",
        "ACT New Zealand": "ACT", "New Zealand First Party": "NZ First",
        "Te Pāti Māori": "Te Pāti Māori", "Māori Party": "Te Pāti Māori", "Maori Party": "Te Pāti Māori",
    }.get(party, "Other")


def map_sweden(raw: str) -> str:
    return {
        "S": "Social Democrats", "M": "Moderates", "SD": "Sweden Democrats", "C": "Centre",
        "V": "Left", "KD": "Christian Democrats", "L": "Liberals", "MP": "Greens",
    }.get(normalise(raw), "Other")


def map_south_africa(raw: str) -> str:
    party = normalise(raw)
    return party if party in {"ANC", "DA", "EFF", "MK", "IFP"} else "Other"


def map_taiwan(raw: str) -> str:
    return {
        "Democratic Progressive Party": "DPP", "Kuomintang": "KMT",
        "Taiwan People's Party": "Third party", "People First Party": "Third party",
    }.get(normalise(raw), "Other")


def map_turkiye(raw: str) -> str:
    candidate = normalise(raw)
    if candidate == "Recep Tayyip Erdoğan":
        return "Erdoğan"
    if candidate in {"Kemal Kılıçdaroğlu", "Muharrem İnce", "Ekmeleddin Mehmet İhsanoğlu"}:
        return "CHP / main opposition"
    if candidate == "Selahattin Demirtaş":
        return "Kurdish left"
    return "Other"


def map_us(raw: str) -> str:
    party = normalise(raw)
    return party if party in {"Democratic", "Republican"} else "Other"


def map_germany(raw: str) -> str:
    party = normalise(raw)
    if party in {"CDU", "CSU"}:
        return "CDU / CSU"
    if party == "SPD":
        return "SPD"
    if party == "GRÜNE":
        return "Greens"
    if party in {"DIE LINKE", "Die Linke"}:
        return "The Left"
    if party in {"AfD", "FDP", "BSW"}:
        return party
    return "Other"


def map_poland(raw: str) -> str:
    candidate = normalise(raw)
    if candidate in {"Andrzej Duda", "Karol Nawrocki"}:
        return "PiS-backed"
    if candidate == "Rafał Trzaskowski":
        return "Civic Coalition"
    if candidate in {"Krzysztof Bosak", "Sławomir Mentzen", "Grzegorz Braun", "Marek Jakubiak"}:
        return "Confederation right"
    if candidate in {"Robert Biedroń", "Magdalena Biejat", "Adrian Zandberg", "Joanna Senyszyn"}:
        return "Left"
    if candidate in {"Szymon Hołownia", "Władysław Kosiniak-Kamysz"}:
        return "Centre / Third Way"
    return "Other"


SPAIN_BROAD_LEFT_PREFIXES = ("SUMAR", "PODEMOS", "PODEMOS-", "ECP-", "M.PAIS", "M.PAÍS", "MÁS PAÍS", "MÉS COMPROMÍS", "PUEDE")
SPAIN_REGIONAL_PREFIXES = (
    "BNG", "CCa", "CUP", "EAJ-PNV", "EH Bildu", "ERC", "JUNTS", "JxCAT", "GBAI", "UPN",
    "NA+", "PRC", "¡TERUEL", "EXISTE", "UPL", "MÉS-ESQUERRA", "MÉS COMPROMÍS", "CHA",
)


def map_spain(raw: str) -> str:
    party = normalise(raw)
    if party in {"PSOE", "PSC"}:
        return "PSOE / PSC"
    if party == "PP" or party.startswith("PP-"):
        return "PP"
    if party == "VOX":
        return "Vox"
    if party.startswith(SPAIN_BROAD_LEFT_PREFIXES):
        return "Broad left"
    if party.startswith(SPAIN_REGIONAL_PREFIXES):
        return "Regional parties"
    return "Other"


def map_portugal(raw: str) -> str:
    party = normalise(raw)
    if party.startswith("PPD/PSD"):
        return "AD / PSD-CDS"
    return {
        "PS": "PS", "CH": "Chega", "IL": "Liberal Initiative", "B.E.": "Left Bloc",
        "PCP-PEV": "CDU", "L": "Livre / PAN", "PAN": "Livre / PAN",
    }.get(party, "Other")


def map_netherlands(raw: str) -> str:
    party = normalise(raw)
    if party in {"PVV", "GL-PvdA", "VVD", "NSC", "D66", "CDA", "BBB"}:
        return party
    if party in {"SP", "PvdD"}:
        return "SP / PvdD"
    return "Other"


MAPPERS: dict[str, Callable[[str], str]] = {
    "New Zealand": map_new_zealand,
    "Sweden": map_sweden,
    "South Africa": map_south_africa,
    "Taiwan": map_taiwan,
    "Türkiye": map_turkiye,
    "United States": map_us,
    "Germany": map_germany,
    "Poland": map_poland,
    "Spain": map_spain,
    "Portugal": map_portugal,
    "Netherlands": map_netherlands,
}


def load_election_definitions() -> dict[str, dict[str, object]]:
    html = EXPLORER_HTML.read_text(encoding="utf-8")
    match = re.search(r"const electionDefinitions = (\[.*?\]);", html, flags=re.S)
    if not match:
        raise SystemExit(f"Could not find electionDefinitions in {EXPLORER_HTML}")
    return {str(item["key"]): item for item in json.loads(match.group(1))}


def dataset_config(definition: dict[str, object], geography: str) -> dict[str, object]:
    if not geography:
        return definition
    layer = dict(definition.get("geographies", {}).get(geography, {}))
    if not layer:
        raise SystemExit(f"{definition['key']}: geography {geography!r} is missing")
    return {**definition, **layer}


def coordinates(value):
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (int, float)):
        yield float(value[0]), float(value[1])
    elif isinstance(value, list):
        for child in value:
            yield from coordinates(child)


def feature_centre(feature: dict[str, object]) -> tuple[float, float]:
    points = list(coordinates(feature.get("geometry", {}).get("coordinates", [])))
    if not points:
        raise SystemExit(f"Boundary feature {feature.get('properties')} has no coordinates")
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    latitude = math.radians((left[1] + right[1]) / 2)
    dx = (left[0] - right[0]) * math.cos(latitude)
    dy = left[1] - right[1]
    return dx * dx + dy * dy


NEIGHBOUR_CACHE: dict[tuple[Path, str | None], dict[str, list[str]]] = {}
NEIGHBOUR_OWNER: dict[tuple[str, str | None], str] = {}


def boundary_details(
    boundary_path: Path,
    cluster_group_property: str | None,
) -> tuple[set[str], dict[str, list[str]]]:
    cache_key = (boundary_path, cluster_group_property)
    if cache_key in NEIGHBOUR_CACHE:
        neighbours = NEIGHBOUR_CACHE[cache_key]
        return set(neighbours), neighbours

    data = json.loads(boundary_path.read_text(encoding="utf-8"))
    grouped: dict[str, list[tuple[str, tuple[float, float]]]] = defaultdict(list)
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        district = str(properties.get("district", ""))
        if not district:
            raise SystemExit(f"{boundary_path}: feature without district")
        group = str(properties.get(cluster_group_property, "all")) if cluster_group_property else "all"
        grouped[group].append((district, feature_centre(feature)))

    neighbours: dict[str, list[str]] = {}
    for points in grouped.values():
        for district, centre in points:
            nearest = heapq.nsmallest(
                min(4, len(points) - 1),
                ((distance(centre, other_centre), other) for other, other_centre in points if other != district),
            )
            neighbours[district] = [other for _, other in nearest]
    NEIGHBOUR_CACHE[cache_key] = neighbours
    return set(neighbours), neighbours


def number(value: str, cast=float):
    value = (value or "").strip()
    return cast(float(value)) if value else None


def build_election(specification: dict[str, object], definitions: dict[str, dict[str, object]]) -> dict[str, object]:
    key = str(specification["electionKey"])
    analysis_key = str(specification["analysisKey"])
    definition = definitions[key]
    config = dataset_config(definition, str(specification["geography"]))
    csv_path = ROOT / str(config["csv"])
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    row_type = str(specification["rowType"])
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("row_type") == row_type:
            grouped[row["district"]].append(row)
    if not grouped:
        raise SystemExit(f"{analysis_key}: no {row_type!r} rows")

    jurisdiction = str(specification["jurisdiction"])
    blocs = BLOCS[jurisdiction]
    mapper = MAPPERS[jurisdiction]
    areas: dict[str, object] = {}
    for district in sorted(grouped):
        district_rows = grouped[district]
        metadata = district_rows[0]
        totals = {bloc: 0 for bloc in blocs}
        for row in district_rows:
            totals[mapper(row.get("candidate_party", ""))] += number(row.get("votes", ""), int) or 0
        represented = sum(totals.values())
        formal = represented if row_type == "party_vote" else (number(metadata.get("formal_votes", ""), int) or 0)
        if represented != formal:
            raise SystemExit(f"{analysis_key} {district}: selected votes {represented} != formal votes {formal}")

        informal = number(metadata.get("informal_votes", ""), int)
        total_votes = number(metadata.get("total_votes", ""), int)
        areas[district] = {
            "formal": formal,
            "turnout": number(metadata.get("turnout_pct", "")),
            "informal": round((informal / total_votes) * 100, 3) if informal is not None and total_votes else None,
            "blocs": {bloc: round(votes / formal * 100, 3) if formal else 0 for bloc, votes in totals.items()},
        }

    boundary_path = ROOT / str(config["boundaries"])
    boundary_districts, neighbours = boundary_details(
        boundary_path,
        str(specification["clusterGroupProperty"]) if specification["clusterGroupProperty"] else None,
    )
    if boundary_districts != set(areas):
        raise SystemExit(
            f"{analysis_key}: result/boundary mismatch; "
            f"no result={sorted(boundary_districts - set(areas))[:5]}, "
            f"no boundary={sorted(set(areas) - boundary_districts)[:5]}"
        )

    neighbour_cache_key = (str(config["boundaries"]), specification["clusterGroupProperty"])
    neighbour_owner = NEIGHBOUR_OWNER.get(neighbour_cache_key)
    if neighbour_owner is None:
        NEIGHBOUR_OWNER[neighbour_cache_key] = analysis_key

    result = {
        "label": definition["label"],
        "jurisdiction": jurisdiction,
        "level": definition["type"],
        "year": definition["year"],
        "periodLabel": specification["periodLabel"] or str(definition["year"]),
        "geography": specification["geography"],
        "historyGroup": specification["historyGroup"],
        "boundaryGroup": specification["boundaryGroup"],
        "comparisonKey": specification["comparisonKey"],
        "clusters": specification["clusters"],
        "voteLabel": specification["voteLabel"],
        "blocs": list(blocs),
        "colors": COLORS[jurisdiction],
        "defaultBloc": blocs[0],
        "areas": areas,
    }
    if neighbour_owner:
        result["neighbourSourceKey"] = neighbour_owner
    else:
        result["neighbours"] = neighbours
    return result


def build_payloads() -> dict[str, dict[str, object]]:
    NEIGHBOUR_OWNER.clear()
    definitions = load_election_definitions()
    elections_by_jurisdiction: dict[str, dict[str, object]] = defaultdict(dict)
    for specification in SPECS:
        jurisdiction = str(specification["jurisdiction"])
        analysis_key = str(specification["analysisKey"])
        elections_by_jurisdiction[jurisdiction][analysis_key] = build_election(specification, definitions)
    return {
        jurisdiction: {
            "version": 1,
            "method": "Area-level vote shares grouped into stable, country-specific political families.",
            "elections": elections,
        }
        for jurisdiction, elections in elections_by_jurisdiction.items()
    }


def main() -> None:
    payloads = build_payloads()
    for jurisdiction, payload in payloads.items():
        output_path = OUTPUT_PATHS[jurisdiction]
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        elections = payload["elections"]
        area_count = sum(len(election["areas"]) for election in elections.values())
        print(f"Wrote {output_path.relative_to(ROOT)} ({len(elections)} views, {area_count} area records)")


if __name__ == "__main__":
    main()
