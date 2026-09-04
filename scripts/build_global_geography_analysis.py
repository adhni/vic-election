#!/usr/bin/env python3
"""Build reusable political-geography assets for supported international elections."""

from __future__ import annotations

import csv
import hashlib
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
    "Argentina": ROOT / "data" / "argentina_geography_analysis.json",
    "Austria": ROOT / "data" / "austria_geography_analysis.json",
    "Belgium": ROOT / "data" / "belgium_geography_analysis.json",
    "Brazil": ROOT / "data" / "brazil_geography_analysis.json",
    "Canada": ROOT / "data" / "canada_geography_analysis.json",
    "Denmark": ROOT / "data" / "denmark_geography_analysis.json",
    "Finland": ROOT / "data" / "finland_geography_analysis.json",
    "France": ROOT / "data" / "france_geography_analysis.json",
    "Greece": ROOT / "data" / "greece_geography_analysis.json",
    "India": ROOT / "data" / "india_geography_analysis.json",
    "Indonesia": ROOT / "data" / "indonesia_geography_analysis.json",
    "Italy": ROOT / "data" / "italy_geography_analysis.json",
    "Japan": ROOT / "data" / "japan_geography_analysis.json",
    "Mexico": ROOT / "data" / "mexico_geography_analysis.json",
    "New Zealand": ROOT / "data" / "new_zealand_geography_analysis.json",
    "Norway": ROOT / "data" / "norway_geography_analysis.json",
    "Philippines": ROOT / "data" / "philippines_geography_analysis.json",
    "Singapore": ROOT / "data" / "singapore_geography_analysis.json",
    "South Korea": ROOT / "data" / "south_korea_geography_analysis.json",
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
    "Thailand": ROOT / "data" / "thailand_geography_analysis.json",
}

BLOCS = {
    "Argentina": ("Peronist", "Liberal / Milei", "PRO / centre-right", "Federal / centrist", "Left", "Other"),
    "Austria": ("ÖVP", "FPÖ", "SPÖ", "Greens", "NEOS", "KPÖ", "Other"),
    "Belgium": ("N-VA", "Vlaams Belang", "Liberals", "Socialists", "Christian democrats", "Greens", "Workers' Party", "Other"),
    "Brazil": ("PT / Lula-Haddad", "Bolsonaro", "Centre-left", "Centrist", "Other"),
    "Canada": ("Liberal", "Conservative", "NDP", "Bloc Québécois", "Green", "People's Party", "Independent", "Other"),
    "Denmark": ("Social Democrats", "Venstre", "SF", "Liberal Alliance", "Moderates", "Denmark Democrats", "Conservatives", "Danish People's Party", "Red-Green Alliance", "Social Liberals", "Other"),
    "Finland": ("National Coalition", "Social Democrats", "Finns Party", "Centre", "Greens", "Left Alliance", "Swedish People's Party", "Christian Democrats", "Movement Now", "Other"),
    "France": ("Nationalist right", "Presidential centre", "Mainstream right", "Socialists", "Left", "Greens", "Other"),
    "Greece": ("New Democracy", "SYRIZA", "PASOK / KINAL", "KKE", "Greek Solution", "MeRA25", "Course of Freedom", "Nationalist right", "Other"),
    "India": ("BJP", "Congress", "Samajwadi Party", "Trinamool Congress", "YSR Congress", "Telugu Desam", "DMK", "Left parties", "Independent / NOTA", "Other"),
    "Indonesia": ("Prabowo ticket", "PDI-P-backed ticket", "Anies ticket", "Other"),
    "Italy": ("Brothers of Italy", "Lega", "Forza Italia", "Five Star Movement", "Democratic Party", "Green / left", "Centrist liberals", "Other"),
    "Japan": ("LDP", "CDP", "Centrist Reform Alliance", "Ishin", "DPP", "Komeito", "JCP", "Reiwa", "Sanseitō", "Independent / Other"),
    "Mexico": ("Sheinbaum / governing coalition", "Gálvez / opposition coalition", "Máynez / MC", "Other"),
    "New Zealand": ("Labour", "National", "Green", "ACT", "NZ First", "Te Pāti Māori", "Other"),
    "Norway": ("Labour", "Progress", "Conservatives", "Centre", "Socialist Left", "Red", "Greens", "Liberals", "Christian Democrats", "Other"),
    "Philippines president": ("Marcos", "Robredo", "Pacquiao", "Moreno", "Other"),
    "Philippines vice president": ("Duterte", "Pangilinan", "Sotto", "Ong", "Other"),
    "Singapore": ("PAP", "WP", "PSP", "SDP", "Other opposition", "Independent"),
    "South Korea": ("Democratic", "Conservative", "Reform", "Progressive", "Other"),
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
    "Thailand": ("Bhumjaithai", "People's Party", "Pheu Thai", "Klatham", "Democrat", "Palang Pracharath", "United Thai Nation", "Other"),
}

COLORS = {
    "Argentina": {
        "Peronist": "#3c82c4", "Liberal / Milei": "#7c48aa", "PRO / centre-right": "#e2b323",
        "Federal / centrist": "#d17b24", "Left": "#c33c4f", "Other": "#72777f",
    },
    "Austria": {
        "ÖVP": "#3d9c9a", "FPÖ": "#2f61bf", "SPÖ": "#d94b49", "Greens": "#2d8a4b",
        "NEOS": "#c23c87", "KPÖ": "#9d2435", "Other": "#72777f",
    },
    "Belgium": {
        "N-VA": "#d8aa16", "Vlaams Belang": "#6f4a23", "Liberals": "#2f61bf",
        "Socialists": "#d94b49", "Christian democrats": "#e28a22", "Greens": "#2d8a4b",
        "Workers' Party": "#9f315a", "Other": "#72777f",
    },
    "Brazil": {
        "PT / Lula-Haddad": "#d94b49", "Bolsonaro": "#2f61bf", "Centre-left": "#d88924",
        "Centrist": "#2a9b91", "Other": "#72777f",
    },
    "Canada": {
        "Liberal": "#d94b49", "Conservative": "#2f61bf", "NDP": "#e28a22",
        "Bloc Québécois": "#36a5c5", "Green": "#2d8a4b", "People's Party": "#7c48aa",
        "Independent": "#555f6d", "Other": "#8a6a3f",
    },
    "Denmark": {
        "Social Democrats": "#d94b49", "Venstre": "#2f61bf", "SF": "#b23a78",
        "Liberal Alliance": "#28a6c7", "Moderates": "#7c48aa", "Denmark Democrats": "#d39e18",
        "Conservatives": "#2d8a4b", "Danish People's Party": "#35528c",
        "Red-Green Alliance": "#9d2435", "Social Liberals": "#d45f93", "Other": "#72777f",
    },
    "Finland": {
        "National Coalition": "#2f61bf", "Social Democrats": "#d94b49", "Finns Party": "#d1a600",
        "Centre": "#3e9447", "Greens": "#63a844", "Left Alliance": "#b23a78",
        "Swedish People's Party": "#d68a1d", "Christian Democrats": "#334a8b",
        "Movement Now": "#28a6c7", "Other": "#72777f",
    },
    "France": {
        "Nationalist right": "#243e84", "Presidential centre": "#e2b323", "Mainstream right": "#2f61bf",
        "Socialists": "#d94b72", "Left": "#b2182b", "Greens": "#2d8a4b", "Other": "#72777f",
    },
    "Greece": {
        "New Democracy": "#2f61bf", "SYRIZA": "#b23a78", "PASOK / KINAL": "#2d8a4b",
        "KKE": "#b2182b", "Greek Solution": "#3e5b91", "MeRA25": "#d94b49",
        "Course of Freedom": "#7c48aa", "Nationalist right": "#6f4a23", "Other": "#72777f",
    },
    "India": {
        "BJP": "#e28a22", "Congress": "#2f61bf", "Samajwadi Party": "#d94b49",
        "Trinamool Congress": "#2d8a4b", "YSR Congress": "#2878b5", "Telugu Desam": "#d1a600",
        "DMK": "#b2182b", "Left parties": "#9f315a", "Independent / NOTA": "#555f6d", "Other": "#72777f",
    },
    "Indonesia": {
        "Prabowo ticket": "#2f61bf", "PDI-P-backed ticket": "#d94b49",
        "Anies ticket": "#2d8a4b", "Other": "#72777f",
    },
    "Italy": {
        "Brothers of Italy": "#243e84", "Lega": "#2d8a4b", "Forza Italia": "#2f61bf",
        "Five Star Movement": "#d8aa16", "Democratic Party": "#d94b49", "Green / left": "#b23a78",
        "Centrist liberals": "#28a6c7", "Other": "#72777f",
    },
    "Japan": {
        "LDP": "#d94b49", "CDP": "#2f61bf", "Centrist Reform Alliance": "#d8aa16",
        "Ishin": "#2d8a4b", "DPP": "#e28a22", "Komeito": "#c33c8b", "JCP": "#b2182b",
        "Reiwa": "#7c48aa", "Sanseitō": "#3e9447", "Independent / Other": "#72777f",
    },
    "Mexico": {
        "Sheinbaum / governing coalition": "#8c2d49", "Gálvez / opposition coalition": "#2f61bf",
        "Máynez / MC": "#e28a22", "Other": "#72777f",
    },
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
    "Norway": {
        "Labour": "#d94b49", "Progress": "#2f61bf", "Conservatives": "#2859a9",
        "Centre": "#3e9447", "Socialist Left": "#b23a78", "Red": "#9d2435",
        "Greens": "#63a844", "Liberals": "#28a6c7", "Christian Democrats": "#d1a600", "Other": "#72777f",
    },
    "Philippines": {
        "Marcos": "#d94b49", "Robredo": "#d94b8a", "Pacquiao": "#2f61bf", "Moreno": "#28a6c7",
        "Duterte": "#2d8a4b", "Pangilinan": "#c33c8b", "Sotto": "#d8aa16", "Ong": "#7c48aa",
        "Other": "#72777f",
    },
    "Singapore": {
        "PAP": "#d94b49", "WP": "#2f61bf", "PSP": "#d94b72", "SDP": "#d68a1d",
        "Other opposition": "#7c48aa", "Independent": "#555f6d",
    },
    "South Korea": {
        "Democratic": "#2f61bf", "Conservative": "#d94b49", "Reform": "#e28a22",
        "Progressive": "#b23a78", "Other": "#72777f",
    },
    "Thailand": {
        "Bhumjaithai": "#2f61bf", "People's Party": "#e28a22", "Pheu Thai": "#d94b49",
        "Klatham": "#2d8a4b", "Democrat": "#28a6c7", "Palang Pracharath": "#243e84",
        "United Thai Nation": "#7c48aa", "Other": "#72777f",
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
    bloc_key: str | None = None,
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
        "blocKey": bloc_key or jurisdiction,
    }


SPECS = [
    spec("argentina-president-2019", "Argentina", boundary_group="argentina-provinces", history_group="argentina-president-round-1", period_label="2019 R1", vote_label="Presidential vote"),
    spec("argentina-president-2023-round-1", "Argentina", boundary_group="argentina-provinces", history_group="argentina-president-round-1", comparison_key="argentina-president-2019", period_label="2023 R1", vote_label="First-round presidential vote"),
    spec("argentina-president-2023-round-2", "Argentina", boundary_group="argentina-provinces", history_group="argentina-president-round-2", period_label="2023 R2", vote_label="Runoff presidential vote"),
    spec("austria-national-council-2019", "Austria", boundary_group="austria-municipalities-2019", history_group="austria-national-council", vote_label="National Council party vote"),
    spec("austria-national-council-2024", "Austria", boundary_group="austria-municipalities-2024", history_group="austria-national-council", vote_label="National Council party vote"),
    spec("belgium-chamber-2019", "Belgium", boundary_group="belgium-chamber-constituencies", history_group="belgium-chamber", vote_label="Chamber party vote"),
    spec("belgium-chamber-2024", "Belgium", boundary_group="belgium-chamber-constituencies", history_group="belgium-chamber", comparison_key="belgium-chamber-2019", vote_label="Chamber party vote"),
    spec("brazil-president-2018-round-1", "Brazil", boundary_group="brazil-states", history_group="brazil-president-round-1", period_label="2018 R1", vote_label="First-round presidential vote"),
    spec("brazil-president-2022-round-1", "Brazil", boundary_group="brazil-states", history_group="brazil-president-round-1", comparison_key="brazil-president-2018-round-1", period_label="2022 R1", vote_label="First-round presidential vote"),
    spec("brazil-president-2018-round-2", "Brazil", boundary_group="brazil-states", history_group="brazil-president-round-2", period_label="2018 R2", vote_label="Runoff presidential vote"),
    spec("brazil-president-2022-round-2", "Brazil", boundary_group="brazil-states", history_group="brazil-president-round-2", comparison_key="brazil-president-2018-round-2", period_label="2022 R2", vote_label="Runoff presidential vote"),
    spec("canada-2021", "Canada", boundary_group="canada-ridings-2021", history_group="canada-federal", vote_label="Candidate vote"),
    spec("canada-2025", "Canada", boundary_group="canada-ridings-2025", history_group="canada-federal", vote_label="Candidate vote"),
    spec("denmark-folketing-2022", "Denmark", boundary_group="denmark-municipalities-2022", history_group="denmark-folketing", vote_label="Folketing party vote"),
    spec("denmark-folketing-2026", "Denmark", boundary_group="denmark-municipalities-2026", history_group="denmark-folketing", vote_label="Folketing party vote"),
    spec("finland-parliament-2019", "Finland", boundary_group="finland-municipalities-2019", history_group="finland-parliament", vote_label="Parliament party vote"),
    spec("finland-parliament-2023", "Finland", boundary_group="finland-municipalities-2023", history_group="finland-parliament", vote_label="Parliament party vote"),
    spec("france-president-2007-round-1", "France", geography="department", boundary_group="france-departments-2007", history_group="france-president:department:round-1", period_label="2007 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2012-round-1", "France", geography="department", boundary_group="france-departments-2012", history_group="france-president:department:round-1", period_label="2012 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2017-round-1", "France", geography="department", boundary_group="france-departments-2017", history_group="france-president:department:round-1", period_label="2017 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2022-round-1", "France", geography="department", boundary_group="france-departments-2022", history_group="france-president:department:round-1", period_label="2022 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2007-round-2", "France", geography="department", boundary_group="france-departments-2007", history_group="france-president:department:round-2", period_label="2007 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2012-round-2", "France", geography="department", boundary_group="france-departments-2012", history_group="france-president:department:round-2", period_label="2012 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2017-round-2", "France", geography="department", boundary_group="france-departments-2017", history_group="france-president:department:round-2", period_label="2017 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2022-round-2", "France", geography="department", boundary_group="france-departments-2022", history_group="france-president:department:round-2", period_label="2022 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2007-round-1", "France", geography="region", boundary_group="france-regions-2007", history_group="france-president:region:round-1", period_label="2007 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2012-round-1", "France", geography="region", boundary_group="france-regions-2012", history_group="france-president:region:round-1", period_label="2012 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2017-round-1", "France", geography="region", boundary_group="france-regions-2017", history_group="france-president:region:round-1", period_label="2017 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2022-round-1", "France", geography="region", boundary_group="france-regions-2022", history_group="france-president:region:round-1", period_label="2022 R1", clusters=False, vote_label="First-round presidential vote"),
    spec("france-president-2007-round-2", "France", geography="region", boundary_group="france-regions-2007", history_group="france-president:region:round-2", period_label="2007 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2012-round-2", "France", geography="region", boundary_group="france-regions-2012", history_group="france-president:region:round-2", period_label="2012 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2017-round-2", "France", geography="region", boundary_group="france-regions-2017", history_group="france-president:region:round-2", period_label="2017 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("france-president-2022-round-2", "France", geography="region", boundary_group="france-regions-2022", history_group="france-president:region:round-2", period_label="2022 R2", clusters=False, vote_label="Runoff presidential vote"),
    spec("greece-parliament-2019", "Greece", boundary_group="greece-constituencies-2019", history_group="greece-parliament", clusters=False, vote_label="Parliament party vote"),
    spec("greece-parliament-2023", "Greece", boundary_group="greece-constituencies-2023", history_group="greece-parliament", clusters=False, vote_label="Parliament party vote"),
    spec("india-2024", "India", boundary_group="india-constituencies-2024", history_group="india-lok-sabha", vote_label="Lok Sabha candidate vote"),
    spec("indonesia-president-2014", "Indonesia", geography="province", boundary_group="indonesia-provinces-2014", history_group="indonesia-president:province", vote_label="Presidential ticket vote"),
    spec("indonesia-president-2019", "Indonesia", geography="province", boundary_group="indonesia-provinces-2019", history_group="indonesia-president:province", vote_label="Presidential ticket vote"),
    spec("indonesia-president-2024", "Indonesia", geography="province", boundary_group="indonesia-provinces-2024", history_group="indonesia-president:province", vote_label="Presidential ticket vote"),
    spec("indonesia-president-2014", "Indonesia", geography="kabupaten-kota", boundary_group="indonesia-local-2014", history_group="indonesia-president:kabupaten-kota", vote_label="Presidential ticket vote"),
    spec("indonesia-president-2019", "Indonesia", geography="kabupaten-kota", boundary_group="indonesia-local-2024", history_group="indonesia-president:kabupaten-kota", vote_label="Presidential ticket vote"),
    spec("indonesia-president-2024", "Indonesia", geography="kabupaten-kota", boundary_group="indonesia-local-2024", history_group="indonesia-president:kabupaten-kota", comparison_key="indonesia-president-2019:kabupaten-kota", vote_label="Presidential ticket vote"),
    spec("italy-chamber-2018", "Italy", boundary_group="italy-provinces-2018", history_group="italy-chamber", vote_label="Chamber party vote"),
    spec("italy-chamber-2022", "Italy", boundary_group="italy-provinces-2022", history_group="italy-chamber", vote_label="Chamber party vote"),
    spec("japan-house-2024", "Japan", boundary_group="japan-constituencies-post-2022", history_group="japan-house", clusters=False, vote_label="Constituency candidate vote"),
    spec("japan-house-2026", "Japan", boundary_group="japan-constituencies-post-2022", history_group="japan-house", comparison_key="japan-house-2024", clusters=False, vote_label="Constituency candidate vote"),
    spec("mexico-president-2024", "Mexico", boundary_group="mexico-federal-districts-2024", history_group="mexico-president", vote_label="Presidential coalition vote"),
    spec("norway-storting-2021", "Norway", boundary_group="norway-municipalities-2021", history_group="norway-storting", vote_label="Storting party vote"),
    spec("norway-storting-2025", "Norway", boundary_group="norway-municipalities-2025", history_group="norway-storting", vote_label="Storting party vote"),
    spec("philippines-president-2022", "Philippines", boundary_group="philippines-canvass-2022", history_group="philippines-president", vote_label="Presidential candidate vote", bloc_key="Philippines president"),
    spec("philippines-vice-president-2022", "Philippines", boundary_group="philippines-canvass-2022", history_group="philippines-vice-president", vote_label="Vice-presidential candidate vote", bloc_key="Philippines vice president"),
    spec("singapore-2015", "Singapore", boundary_group="singapore-divisions-2015", history_group="singapore-general", vote_label="Candidate or team vote"),
    spec("singapore-2020", "Singapore", boundary_group="singapore-divisions-2020", history_group="singapore-general", vote_label="Candidate or team vote"),
    spec("singapore-2025", "Singapore", boundary_group="singapore-divisions-2025", history_group="singapore-general", vote_label="Candidate or team vote"),
    spec("south-korea-president-2022", "South Korea", boundary_group="south-korea-municipalities-2022", history_group="south-korea-president", vote_label="Presidential candidate vote"),
    spec("south-korea-president-2025", "South Korea", boundary_group="south-korea-municipalities-2025", history_group="south-korea-president", vote_label="Presidential candidate vote"),
    spec("thailand-2026", "Thailand", boundary_group="thailand-constituency-cartogram-2026", history_group="thailand-house", clusters=False, vote_label="Constituency candidate vote"),
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


def map_argentina(raw: str) -> str:
    candidate = normalise(raw)
    if candidate in {"Alberto Fernández", "Sergio Massa"}:
        return "Peronist"
    if candidate in {"Javier Milei", "José Luis Espert"}:
        return "Liberal / Milei"
    if candidate in {"Mauricio Macri", "Patricia Bullrich"}:
        return "PRO / centre-right"
    if candidate in {"Roberto Lavagna", "Juan Schiaretti"}:
        return "Federal / centrist"
    if candidate in {"Nicolás del Caño", "Myriam Bregman"}:
        return "Left"
    return "Other"


def map_austria(raw: str) -> str:
    party = normalise(raw)
    return party if party in {"ÖVP", "FPÖ", "SPÖ", "NEOS", "KPÖ"} else "Greens" if party == "GRÜNE" else "Other"


def map_belgium(raw: str) -> str:
    party = normalise(raw)
    folded = party.casefold()
    if party == "N-VA":
        return "N-VA"
    if folded == "vlaams belang":
        return "Vlaams Belang"
    if party in {"MR", "Open Vld"}:
        return "Liberals"
    if party in {"PS", "Vooruit", "sp.a"}:
        return "Socialists"
    if party in {"CD&V", "cd&v", "LES ENGAGÉS", "CDH"}:
        return "Christian democrats"
    if party in {"GROEN", "ECOLO"}:
        return "Greens"
    if folded.startswith("ptb") or folded == "pvda":
        return "Workers' Party"
    return "Other"


def map_brazil(raw: str) -> str:
    candidate = normalise(raw)
    if candidate in {"Luiz Inácio Lula da Silva", "Fernando Haddad"}:
        return "PT / Lula-Haddad"
    if candidate == "Jair Bolsonaro":
        return "Bolsonaro"
    if candidate == "Ciro Gomes":
        return "Centre-left"
    if candidate in {"Geraldo Alckmin", "Simone Tebet"}:
        return "Centrist"
    return "Other"


def map_canada(raw: str) -> str:
    party = normalise(raw)
    if party in {"Liberal", "Conservative", "NDP", "Bloc Québécois", "Green", "People's Party"}:
        return party
    if party in {"Independent", "No Affiliation"}:
        return "Independent"
    return "Other"


def map_denmark(raw: str) -> str:
    party = normalise(raw)
    principals = {
        "Social Democrats", "Venstre", "SF", "Liberal Alliance", "Moderates", "Denmark Democrats",
        "Conservatives", "Danish People's Party", "Red-Green Alliance", "Social Liberals",
    }
    return party if party in principals else "Other"


def map_finland(raw: str) -> str:
    return {
        "KOK": "National Coalition", "SDP": "Social Democrats", "PS": "Finns Party", "KESK": "Centre",
        "VIHR": "Greens", "VAS": "Left Alliance", "RKP": "Swedish People's Party",
        "KD": "Christian Democrats", "LIIKE": "Movement Now",
    }.get(normalise(raw), "Other")


def map_france(raw: str) -> str:
    candidate = normalise(raw)
    if candidate in {"Marine Le Pen", "Jean-Marie Le Pen", "Éric Zemmour", "Nicolas Dupont-Aignan", "Philippe de Villiers"}:
        return "Nationalist right"
    if candidate in {"Emmanuel Macron", "François Bayrou"}:
        return "Presidential centre"
    if candidate in {"Nicolas Sarkozy", "François Fillon", "Valérie Pécresse"}:
        return "Mainstream right"
    if candidate in {"François Hollande", "Ségolène Royal", "Benoît Hamon", "Anne Hidalgo"}:
        return "Socialists"
    if candidate in {
        "Jean-Luc Mélenchon", "Olivier Besancenot", "Philippe Poutou", "Fabien Roussel",
        "Marie-George Buffet", "Nathalie Arthaud", "Arlette Laguiller",
    }:
        return "Left"
    if candidate in {"Yannick Jadot", "Eva Joly", "Dominique Voynet", "José Bové"}:
        return "Greens"
    return "Other"


def map_greece(raw: str) -> str:
    party = normalise(raw)
    if party in {"New Democracy", "SYRIZA", "KKE", "Greek Solution", "MeRA25", "Course of Freedom"}:
        return party
    if party == "PASOK–KINAL":
        return "PASOK / KINAL"
    if party in {"Spartans", "Niki", "Χρυσή Αυγή"}:
        return "Nationalist right"
    return "Other"


def map_india(raw: str) -> str:
    party = normalise(raw)
    direct = {
        "Bharatiya Janata Party": "BJP", "Indian National Congress": "Congress",
        "Samajwadi Party": "Samajwadi Party", "All India Trinamool Congress": "Trinamool Congress",
        "Yuvajana Sramika Rythu Congress Party": "YSR Congress", "Telugu Desam": "Telugu Desam",
        "Dravida Munnetra Kazhagam": "DMK",
    }
    if party in direct:
        return direct[party]
    if party in {
        "Communist Party of India (Marxist)", "Communist Party of India",
        "Communist Party of India (Marxist-Leninist) (Liberation)", "Revolutionary Socialist Party",
    }:
        return "Left parties"
    if party in {"Independent", "None of the Above"}:
        return "Independent / NOTA"
    return "Other"


def map_indonesia(raw: str) -> str:
    ticket = normalise(raw)
    if ticket.startswith("Prabowo–"):
        return "Prabowo ticket"
    if ticket.startswith("Jokowi–") or ticket == "Ganjar–Mahfud":
        return "PDI-P-backed ticket"
    if ticket == "Anies–Muhaimin":
        return "Anies ticket"
    return "Other"


def map_italy(raw: str) -> str:
    party = normalise(raw)
    if party in {"Brothers of Italy", "Lega", "Forza Italia", "Five Star Movement", "Democratic Party"}:
        return party
    if party in {"Greens and Left Alliance", "Free and Equal", "People's Union", "Power to the People"}:
        return "Green / left"
    if party in {"Action–Italia Viva", "More Europe", "Us Moderates", "Civic Commitment"}:
        return "Centrist liberals"
    return "Other"


def map_japan(raw: str) -> str:
    return {
        "Liberal Democratic Party": "LDP", "Constitutional Democratic Party": "CDP",
        "Centrist Reform Alliance": "Centrist Reform Alliance", "Japan Innovation Party": "Ishin",
        "Democratic Party for the People": "DPP", "Komeito": "Komeito",
        "Japanese Communist Party": "JCP", "Reiwa Shinsengumi": "Reiwa", "Sanseitō": "Sanseitō",
    }.get(normalise(raw), "Independent / Other")


def map_mexico(raw: str) -> str:
    return {
        "Sheinbaum": "Sheinbaum / governing coalition", "Gálvez": "Gálvez / opposition coalition",
        "Máynez": "Máynez / MC",
    }.get(normalise(raw), "Other")


def map_new_zealand(raw: str) -> str:
    party = normalise(raw)
    return {
        "Labour Party": "Labour", "National Party": "National", "Green Party": "Green",
        "ACT New Zealand": "ACT", "New Zealand First Party": "NZ First",
        "Te Pāti Māori": "Te Pāti Māori", "Māori Party": "Te Pāti Māori", "Maori Party": "Te Pāti Māori",
    }.get(party, "Other")


def map_norway(raw: str) -> str:
    return {
        "A": "Labour", "FRP": "Progress", "H": "Conservatives", "SP": "Centre",
        "SV": "Socialist Left", "RØDT": "Red", "MDG": "Greens", "V": "Liberals",
        "KRF": "Christian Democrats",
    }.get(normalise(raw), "Other")


def map_philippines_president(raw: str) -> str:
    candidate = normalise(raw)
    return candidate if candidate in {"Marcos", "Robredo", "Pacquiao", "Moreno"} else "Other"


def map_philippines_vice_president(raw: str) -> str:
    candidate = normalise(raw)
    return candidate if candidate in {"Duterte", "Pangilinan", "Sotto", "Ong"} else "Other"


def map_singapore(raw: str) -> str:
    party = normalise(raw)
    if party in {"PAP", "WP", "PSP", "SDP"}:
        return party
    if "Independent" in party:
        return "Independent"
    return "Other opposition"


def map_south_korea(raw: str) -> str:
    candidate = normalise(raw)
    if candidate == "Lee Jae-myung":
        return "Democratic"
    if candidate in {"Yoon Suk Yeol", "Kim Moon-soo"}:
        return "Conservative"
    if candidate == "Lee Jun-seok":
        return "Reform"
    if candidate in {"Sim Sang-jung", "Kwon Young-guk", "Kim Jae-yeon", "Oh Jun-ho", "Lee Baek-yoon"}:
        return "Progressive"
    return "Other"


def map_thailand(raw: str) -> str:
    party = normalise(raw)
    principals = {
        "Bhumjaithai", "People's Party", "Pheu Thai", "Klatham", "Democrat",
        "Palang Pracharath", "United Thai Nation",
    }
    return party if party in principals else "Other"


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
    "Argentina": map_argentina,
    "Austria": map_austria,
    "Belgium": map_belgium,
    "Brazil": map_brazil,
    "Canada": map_canada,
    "Denmark": map_denmark,
    "Finland": map_finland,
    "France": map_france,
    "Greece": map_greece,
    "India": map_india,
    "Indonesia": map_indonesia,
    "Italy": map_italy,
    "Japan": map_japan,
    "Mexico": map_mexico,
    "New Zealand": map_new_zealand,
    "Norway": map_norway,
    "Philippines president": map_philippines_president,
    "Philippines vice president": map_philippines_vice_president,
    "Singapore": map_singapore,
    "South Korea": map_south_korea,
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
    "Thailand": map_thailand,
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
BOUNDARY_FINGERPRINT_CACHE: dict[Path, str] = {}
NEIGHBOUR_OWNER: dict[tuple[str, str | None], str] = {}


def boundary_details(
    boundary_path: Path,
    cluster_group_property: str | None,
) -> tuple[set[str], dict[str, list[str]], str]:
    cache_key = (boundary_path, cluster_group_property)
    if cache_key in NEIGHBOUR_CACHE:
        neighbours = NEIGHBOUR_CACHE[cache_key]
        return set(neighbours), neighbours, BOUNDARY_FINGERPRINT_CACHE[boundary_path]

    data = json.loads(boundary_path.read_text(encoding="utf-8"))
    canonical_geometry = {
        str(feature.get("properties", {}).get("district", "")): feature.get("geometry")
        for feature in data.get("features", [])
    }
    boundary_fingerprint = hashlib.sha256(
        json.dumps(canonical_geometry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    BOUNDARY_FINGERPRINT_CACHE[boundary_path] = boundary_fingerprint
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
    return set(neighbours), neighbours, boundary_fingerprint


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
    bloc_key = str(specification["blocKey"])
    blocs = BLOCS[bloc_key]
    mapper = MAPPERS[bloc_key]
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
    boundary_districts, neighbours, boundary_fingerprint = boundary_details(
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
        "boundaryFile": str(config["boundaries"]),
        "boundaryFingerprint": boundary_fingerprint,
        "comparisonKey": specification["comparisonKey"],
        "clusters": specification["clusters"],
        "voteLabel": specification["voteLabel"],
        "blocs": list(blocs),
        "colors": {bloc: COLORS[jurisdiction][bloc] for bloc in blocs},
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
