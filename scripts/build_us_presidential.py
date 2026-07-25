#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


YEARS = (2024, 2020, 2016, 2012, 2008)
COUNTY_SOURCE_PAGE = "https://github.com/tonmcg/US_County_Level_Election_Results_08-24"
MIT_COUNTY_SOURCE_PAGE = "https://doi.org/10.7910/DVN/VOQCHQ"
FEC_SOURCE_PAGE = "https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/"

SOURCES = {
    "county_historical": (
        "https://media.githubusercontent.com/media/Hackquantumcpp/california_MRP/"
        "95d50c189434ac12464f3be82b2cc76251e851cd/"
        "countypres_2000-2024.csv",
        "1a2323d8d6ebb77c6593a0403aaec680c17f53a86c1664e74dcd58d8e63c3f5a",
        "countypres_2000-2024-current.csv",
    ),
    "county_2020": (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
        "master/2020_US_County_Level_Presidential_Results.csv",
        "98c7412018bfaa2a9ac4fea088fd5bb4bbf1c5f2b93f524da574a2d83c25ccbe",
        "2020_US_County_Level_Presidential_Results.csv",
    ),
    "county_2024": (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
        "master/2024_US_County_Level_Presidential_Results.csv",
        "538a8fbe2d7a20524b049dd1b3b9ec7e215c4433d99f91fbd7b0dea05270136a",
        "2024_US_County_Level_Presidential_Results.csv",
    ),
    "fec_2008": (
        "https://www.fec.gov/documents/1661/2008pres.xls",
        "2f5021737b1b49d880c78d1e732225fd8c626242229c5ae38181cf889ebcaffc",
        "2008pres.xls",
    ),
    "fec_2012": (
        "https://www.fec.gov/documents/1684/2012pres.xls",
        "8b3cb324ef9d14b69bd643681f753c3c3d5aa1c4b72eadbf03e010046ecf8067",
        "2012pres.xls",
    ),
    "fec_2016": (
        "https://www.fec.gov/documents/1890/federalelections2016.xlsx",
        "b4a1d1383602bc388cfbdf1fbea2476476d32e0b44b44236d3a3910fa9782eb6",
        "federalelections2016.xlsx",
    ),
    "fec_2020": (
        "https://www.fec.gov/documents/4228/federalelections2020.xlsx",
        "5073b6d2c76c86c941508dfb1a11cc497e8529b0068c5132aceb0f385c19352e",
        "federalelections2020.xlsx",
    ),
    "fec_2024": (
        "https://www.fec.gov/documents/5645/2024presgeresults.xlsx",
        "68acdee2924d771b92a05cd950dec850b462c633c05563207ac7e206116e7366",
        "2024presgeresults.xlsx",
    ),
    "counties_2010": (
        "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
        "e540149b7525e71ee6b6cab6dea2a95205f11e0c3e7374d27a7c9c47ea96e8c0",
        "geojson-counties-fips.json",
    ),
    "counties_2019": (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
        "master/cartography/2020/build/cb_2019_us_county_500k.zip",
        "1c4b703cd34c3f5e5e6368f91f1bd80de9281ef81ad91e005844848df9976c4b",
        "cb_2019_us_county_500k.zip",
    ),
    "counties_2023": (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
        "master/cartography/2024/build/cb_2023_us_county_500k.zip",
        "99d6597b1fc7767deef62e01d28d8b5dcbd578e151855f7dc0d173cbf5bf0868",
        "cb_2023_us_county_500k.zip",
    ),
    "states_2019": (
        "https://raw.githubusercontent.com/tonmcg/US_County_Level_Election_Results_08-24/"
        "master/cartography/2020/build/cb_2019_us_state_500k.zip",
        "22ed6c5050c6481bd375ad7b4fa4b1b741a90f8ac550e301555629ee5fa1b497",
        "cb_2019_us_state_500k.zip",
    ),
}

CANDIDATES = {
    2008: ("Barack Obama", "John McCain"),
    2012: ("Barack Obama", "Mitt Romney"),
    2016: ("Hillary Clinton", "Donald Trump"),
    2020: ("Joe Biden", "Donald Trump"),
    2024: ("Kamala Harris", "Donald Trump"),
}

FEC_IDS = {
    2008: ("P80003338", "P80002801"),
    2012: ("P80003338", "P80003353"),
    2016: ("P00003392", "P80001571"),
    2020: ("P80000722", "P80001571"),
}

FEC_SHEETS = {
    2008: "2008 PRES GENERAL RESULTS",
    2012: "2012 Pres General Results",
    2016: "2016 Pres General Results",
    2020: "9. 2020 Pres General Results",
}

STATE_INFO = {
    "01": ("AL", "Alabama"), "02": ("AK", "Alaska"), "04": ("AZ", "Arizona"),
    "05": ("AR", "Arkansas"), "06": ("CA", "California"), "08": ("CO", "Colorado"),
    "09": ("CT", "Connecticut"), "10": ("DE", "Delaware"),
    "11": ("DC", "District of Columbia"), "12": ("FL", "Florida"),
    "13": ("GA", "Georgia"), "15": ("HI", "Hawaii"), "16": ("ID", "Idaho"),
    "17": ("IL", "Illinois"), "18": ("IN", "Indiana"), "19": ("IA", "Iowa"),
    "20": ("KS", "Kansas"), "21": ("KY", "Kentucky"), "22": ("LA", "Louisiana"),
    "23": ("ME", "Maine"), "24": ("MD", "Maryland"), "25": ("MA", "Massachusetts"),
    "26": ("MI", "Michigan"), "27": ("MN", "Minnesota"), "28": ("MS", "Mississippi"),
    "29": ("MO", "Missouri"), "30": ("MT", "Montana"), "31": ("NE", "Nebraska"),
    "32": ("NV", "Nevada"), "33": ("NH", "New Hampshire"), "34": ("NJ", "New Jersey"),
    "35": ("NM", "New Mexico"), "36": ("NY", "New York"),
    "37": ("NC", "North Carolina"), "38": ("ND", "North Dakota"), "39": ("OH", "Ohio"),
    "40": ("OK", "Oklahoma"), "41": ("OR", "Oregon"), "42": ("PA", "Pennsylvania"),
    "44": ("RI", "Rhode Island"), "45": ("SC", "South Carolina"),
    "46": ("SD", "South Dakota"), "47": ("TN", "Tennessee"), "48": ("TX", "Texas"),
    "49": ("UT", "Utah"), "50": ("VT", "Vermont"), "51": ("VA", "Virginia"),
    "53": ("WA", "Washington"), "54": ("WV", "West Virginia"),
    "55": ("WI", "Wisconsin"), "56": ("WY", "Wyoming"),
}
STATE_BY_ABBR = {abbr: (fips, name) for fips, (abbr, name) in STATE_INFO.items()}
STATE_BY_NAME = {name.lower(): (fips, abbr, name) for fips, (abbr, name) in STATE_INFO.items()}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct",
    "majority", "round_number", "row_type", "excluded_candidate", "excluded_party",
    "candidate", "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)

CURRENT_COUNTY_NOTE = (
    "County-level Democratic, Republican and total vote figures come from a public compilation "
    "of state and media results; Other candidates is the residual. Alaska and the District of "
    "Columbia use official statewide totals because they do not report by county."
)
HISTORICAL_COUNTY_NOTE = (
    "County-level candidate totals come from the MIT Election Data and Science Lab historical "
    "returns. Kansas City is combined with Jackson County and Bedford City with Bedford County "
    "to match the shared historical boundary file. Alaska and the District of Columbia use "
    "official statewide totals."
)
STATE_NOTE = "Official statewide presidential totals compiled by the Federal Election Commission."
EXPECTED_STATE_RECONCILIATION_SHA256 = {
    2008: "ac799a48bfbf3838275dcf060c6295c152b41a4c14b46d94323c4b1e0fc468d8",
    2012: "20c779898c272ab44c68c7318f50956dd134d67829c49873cd4c97b43877e6b8",
    2016: "2d5babea9d5c85f358612b0cbcfaf290d84128ef2a5d0ffe32349be25c459a8a",
    2020: "0883c0be1d70ca18dff3386d12671af0d46eb08de727973ac97ff4c7214a0c35",
    2024: "1b2e4645469b974bf743424ea806fa85aec4cf667701eaf2631bc9014307cc27",
}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and path.stat().st_size and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=300, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                handle.write(chunk)


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def number(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip().replace(",", "").replace("[", "").replace("]", "")
    if not text or text.lower() == "nan":
        return 0
    return int(float(text))


def candidate_total(rows: pd.DataFrame, fec_id: str) -> int:
    selected = rows[rows["FEC ID"].astype(str).str.strip() == fec_id]
    combined = selected[selected["PARTY"].astype(str).str.strip() == "Combined Parties:"]
    if not combined.empty:
        row = combined.iloc[0]
        for column in ("GENERAL RESULTS", "COMBINED GE PARTY TOTALS (NY)", "TOTAL VOTES #"):
            if column in row.index and number(row[column]):
                return number(row[column])
    return sum(number(value) for value in selected["GENERAL RESULTS"])


def parse_fec_states(year: int, path: Path) -> dict[str, dict[str, object]]:
    dem_name, rep_name = CANDIDATES[year]
    results: dict[str, dict[str, object]] = {}
    if year == 2024:
        frame = pd.read_excel(path, sheet_name="OFFICIAL 2024 PRES GE RESULTS")
        for _, row in frame.iterrows():
            abbr = str(row.get("STATE", "")).strip()
            if abbr not in STATE_BY_ABBR:
                continue
            fips, state = STATE_BY_ABBR[abbr]
            dem = number(row["HARRIS"])
            rep = number(row["TRUMP"])
            total = number(row["TOTAL VOTES"])
            results[abbr] = {
                "fips": fips, "state": state, "dem": dem, "rep": rep,
                "other": total - dem - rep, "total": total,
            }
    else:
        frame = pd.read_excel(path, sheet_name=FEC_SHEETS[year])
        dem_id, rep_id = FEC_IDS[year]
        for abbr, (fips, state) in STATE_BY_ABBR.items():
            rows = frame[frame["STATE ABBREVIATION"].astype(str).str.strip() == abbr]
            if rows.empty:
                raise SystemExit(f"FEC {year}: missing {abbr}")
            dem = candidate_total(rows, dem_id)
            rep = candidate_total(rows, rep_id)
            total = max(number(value) for value in rows["TOTAL VOTES #"])
            results[abbr] = {
                "fips": fips, "state": state, "dem": dem, "rep": rep,
                "other": total - dem - rep, "total": total,
            }
    if len(results) != 51:
        raise SystemExit(f"FEC {year}: expected 51 state/DC totals, found {len(results)}")
    for abbr, result in results.items():
        if min(result["dem"], result["rep"], result["other"]) < 0:
            raise SystemExit(f"FEC {year} {abbr}: invalid candidate totals {result}")
        if result["dem"] + result["rep"] + result["other"] != result["total"]:
            raise SystemExit(f"FEC {year} {abbr}: totals do not reconcile")
    return results


def title_name(name: str) -> str:
    return " ".join(part.capitalize() if part not in {"of", "the"} else part for part in name.lower().split())


def county_label(name: str, state_abbr: str) -> str:
    label = title_name(name)
    if label.endswith((" County", " Parish", " City", " Borough", " Census Area", " Municipality")):
        return label
    if state_abbr == "LA":
        return f"{label} Parish"
    return f"{label} County"


def parse_historical_counties(path: Path, year: int) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    dem_name, rep_name = (name.upper() for name in CANDIDATES[year])
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if number(row["year"]) != year:
                continue
            state_abbr = str(row["state_po"]).strip()
            if state_abbr not in STATE_BY_ABBR or state_abbr in {"AK", "DC"}:
                continue
            if str(row["mode"]).strip() != "TOTAL":
                raise SystemExit(f"MIT {year}: unexpected non-total mode {row['mode']!r}")
            if not str(row["county_fips"]).strip():
                if str(row["county_name"]).strip() not in {
                    "STATEWIDE WRITEIN", "MAINE UOCAVA", "FEDERAL PRECINCT",
                }:
                    raise SystemExit(f"MIT {year}: unknown non-geographic return {row['county_name']!r}")
                continue
            raw_code = number(row["county_fips"])
            if raw_code == 2_938_000 and state_abbr == "MO":
                code = "29095"
            else:
                code = str(raw_code).zfill(5)
            code = {"51515": "51019", "46102": "46113"}.get(code, code)
            if len(code) != 5 or code[:2] not in STATE_INFO:
                raise SystemExit(
                    f"MIT {year}: unsupported reporting code {row['county_fips']!r} "
                    f"for {row['county_name']}"
                )
            _, state = STATE_BY_ABBR[state_abbr]
            fixed_label = {
                "29095": "Jackson County",
                "51019": "Bedford County",
                "46113": "Shannon County",
            }.get(code)
            if state_abbr == "VA" and int(code[2:]) >= 500:
                city_name = title_name(str(row["county_name"]))
                fixed_label = city_name if city_name.endswith(" City") else f"{city_name} City"
            area = areas.setdefault(code, {
                "code": code,
                "district": f"{fixed_label or county_label(str(row['county_name']), state_abbr)}, {state}",
                "state": state,
                "dem": 0,
                "rep": 0,
                "other": 0,
                "total": 0,
            })
            candidate = str(row["candidate"]).strip().upper()
            bucket = "dem" if candidate == dem_name else "rep" if candidate == rep_name else "other"
            votes = number(row["candidatevotes"])
            area[bucket] += votes
            area["total"] += votes
    if len(areas) != 3_111:
        raise SystemExit(f"MIT {year}: expected 3,111 mapped county areas before fallbacks, found {len(areas)}")
    return areas


def parse_new_counties(path: Path) -> dict[str, dict[str, object]]:
    areas: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            state_key = str(row["state_name"]).strip().lower()
            if state_key not in STATE_BY_NAME:
                continue
            fips, _, state = STATE_BY_NAME[state_key]
            if fips in {"02", "11"}:
                continue
            code = str(row["county_fips"]).strip().zfill(5)
            total = number(row["total_votes"])
            dem = number(row["votes_dem"])
            rep = number(row["votes_gop"])
            other = total - dem - rep
            if len(code) != 5 or code[:2] != fips or other < 0:
                raise SystemExit(f"{state} {code}: invalid compiled county row")
            county = str(row["county_name"]).strip()
            areas[code] = {
                "code": code, "district": f"{county}, {state}", "state": state,
                "dem": dem, "rep": rep, "other": other, "total": total,
            }
    return areas


def add_statewide_fallbacks(
    areas: dict[str, dict[str, object]],
    state_results: dict[str, dict[str, object]],
) -> None:
    for abbr, code, district in (
        ("AK", "02", "Alaska statewide"),
        ("DC", "11001", "District of Columbia"),
    ):
        source = state_results[abbr]
        areas[code] = {
            "code": code, "district": district, "state": source["state"],
            "dem": source["dem"], "rep": source["rep"],
            "other": source["other"], "total": source["total"],
        }


def validate_state_reconciliation(
    year: int,
    areas: dict[str, dict[str, object]],
    state_results: dict[str, dict[str, object]],
) -> None:
    county_totals = {abbr: Counter() for abbr in state_results}
    for area in areas.values():
        abbr = STATE_BY_NAME[str(area["state"]).lower()][1]
        for bucket in ("dem", "rep", "other"):
            county_totals[abbr][bucket] += int(area[bucket])
    report = {
        abbr: [
            int(state_results[abbr][bucket]) - county_totals[abbr][bucket]
            for bucket in ("dem", "rep", "other")
        ]
        for abbr in sorted(state_results)
    }
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_STATE_RECONCILIATION_SHA256[year]:
        changed = {abbr: delta for abbr, delta in report.items() if any(delta)}
        raise SystemExit(
            f"{year}: county/FEC state reconciliation changed to {digest}: {changed}"
        )


def outcome(area: dict[str, object], year: int) -> tuple[str, str, int]:
    dem_name, rep_name = CANDIDATES[year]
    choices = [
        (dem_name, "Democratic", int(area["dem"])),
        (rep_name, "Republican", int(area["rep"])),
        ("Other candidates", "Other", int(area["other"])),
    ]
    choices.sort(key=lambda item: (-item[2], item[0]))
    return choices[0]


def build_rows(
    year: int,
    areas: dict[str, dict[str, object]],
    geography: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    dem_name, rep_name = CANDIDATES[year]
    source_url = (
        FEC_SOURCE_PAGE if geography == "state"
        else MIT_COUNTY_SOURCE_PAGE if year <= 2016
        else COUNTY_SOURCE_PAGE
    )
    note = (
        STATE_NOTE if geography == "state"
        else HISTORICAL_COUNTY_NOTE if year <= 2016
        else CURRENT_COUNTY_NOTE
    )
    for _, area in sorted(areas.items(), key=lambda item: (str(item[1]["state"]), str(item[1]["district"]))):
        code = str(area["code"])
        winner, winner_party, _ = outcome(area, year)
        choices = (
            (dem_name, "Democratic", int(area["dem"])),
            (rep_name, "Republican", int(area["rep"])),
            ("Other candidates", "Other", int(area["other"])),
        )
        ranked = sorted(choices, key=lambda item: (-item[2], item[0]))
        majority = ranked[0][2] - ranked[1][2]
        base = {
            "district": area["district"], "district_url": source_url,
            "distribution_url": source_url, "elected_member": winner,
            "elected_party": winner_party, "enrolment": 0,
            "formal_votes": area["total"], "informal_votes": 0,
            "total_votes": area["total"], "turnout_pct": 0, "majority": majority,
            "round_number": 0, "row_type": "first", "excluded_candidate": "",
            "excluded_party": "", "electorate_type": area["state"] if geography == "county" else "United States",
            "constituency_code": f"US-{geography.upper()}-{code}",
            "contest_status": "official" if geography == "state" else "compiled",
            "result_note": note,
        }
        for candidate, party, votes in choices:
            rows.append({**base, "candidate": candidate, "candidate_party": party, "votes": votes})
    return rows


def unwrap_antimeridian_coordinates(coordinates):
    if coordinates and isinstance(coordinates[0], (int, float)):
        longitude, latitude, *rest = coordinates
        return (longitude - 360 if longitude > 0 else longitude, latitude, *rest)
    return tuple(unwrap_antimeridian_coordinates(part) for part in coordinates)


def display_geometry(geometry, state_fips: str):
    simplified = geometry.simplify(0.02, preserve_topology=True)
    if simplified.is_empty or not simplified.is_valid:
        simplified = simplified.buffer(0)
    if simplified.is_empty or not simplified.is_valid:
        simplified = geometry.buffer(0).simplify(0.01, preserve_topology=True).buffer(0)
    result = mapping(simplified)
    if state_fips == "02":
        result["coordinates"] = unwrap_antimeridian_coordinates(result["coordinates"])
    checked = shape(result)
    if checked.is_empty or not checked.is_valid:
        raise SystemExit(f"State {state_fips}: invalid display geometry")
    return result


def state_geometries(path: Path):
    frame = gpd.read_file(f"zip://{path.resolve()}").to_crs(epsg=4326)
    return {
        str(row["STATEFP"]): row.geometry
        for _, row in frame.iterrows()
        if str(row["STATEFP"]) in STATE_INFO
    }


def build_historical_counties(
    path: Path,
    areas: dict[str, dict[str, object]],
    states: dict[str, object],
) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    geometries = {
        str(feature["id"]).zfill(5): shape(feature["geometry"])
        for feature in source["features"]
        if str(feature["id"]).zfill(5)[:2] in STATE_INFO
    }
    if "51515" in geometries:
        geometries["51019"] = unary_union([geometries["51019"], geometries.pop("51515")])
    geometries["02"] = states["02"]
    features = []
    for code, area in sorted(areas.items()):
        if code not in geometries:
            raise SystemExit(f"Historical county boundary missing result {code} {area['district']}")
        features.append({
            "type": "Feature",
            "properties": {
                "district": area["district"], "constituency_code": f"US-COUNTY-{code}",
                "electorate_type": area["state"],
            },
            "geometry": display_geometry(geometries[code], code[:2]),
        })
    if set(geometries).intersection(areas) != set(areas):
        raise SystemExit("Historical county/result join is incomplete")
    return {"type": "FeatureCollection", "name": "us_presidential_historical_counties", "features": features}


def apply_historical_boundary_labels(
    path: Path,
    historical_areas: list[dict[str, dict[str, object]]],
) -> None:
    source = json.loads(path.read_text(encoding="utf-8"))
    labels = {}
    for feature in source["features"]:
        code = str(feature["id"]).zfill(5)
        properties = feature["properties"]
        name = str(properties["NAME"])
        suffix = str(properties.get("LSAD", "")).strip()
        labels[code] = name if not suffix or name.lower().endswith(suffix.lower()) else f"{name} {suffix}"
    for areas in historical_areas:
        for code, area in areas.items():
            if code in {"02", "11001"}:
                continue
            if code not in labels:
                raise SystemExit(f"Historical boundary label missing for {code}")
            area["district"] = f"{labels[code]}, {area['state']}"


def build_modern_counties(
    path: Path,
    areas: dict[str, dict[str, object]],
    states: dict[str, object],
    name: str,
) -> dict[str, object]:
    frame = gpd.read_file(f"zip://{path.resolve()}").to_crs(epsg=4326)
    geometries = {
        str(row["GEOID"]): row.geometry
        for _, row in frame.iterrows()
        if str(row["STATEFP"]) in STATE_INFO
    }
    geometries["02"] = states["02"]
    features = []
    for code, area in sorted(areas.items()):
        if code not in geometries:
            raise SystemExit(f"{name}: county boundary missing result {code} {area['district']}")
        features.append({
            "type": "Feature",
            "properties": {
                "district": area["district"], "constituency_code": f"US-COUNTY-{code}",
                "electorate_type": area["state"],
            },
            "geometry": display_geometry(geometries[code], code[:2]),
        })
    return {"type": "FeatureCollection", "name": name, "features": features}


def build_state_boundaries(states: dict[str, object]) -> dict[str, object]:
    features = []
    for fips, (abbr, state) in STATE_INFO.items():
        features.append({
            "type": "Feature",
            "properties": {
                "district": state, "constituency_code": f"US-STATE-{abbr}",
                "electorate_type": "United States",
            },
            "geometry": display_geometry(states[fips], fips),
        })
    return {"type": "FeatureCollection", "name": "us_presidential_states", "features": features}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_geojson(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build U.S. presidential county and state maps, 2008-2024")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/us_presidential"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"
    paths = {}
    for key, (url, checksum, filename) in SOURCES.items():
        path = args.raw_dir / filename
        download(session, url, path, args.refresh)
        require_sha256(path, checksum)
        paths[key] = path

    fec_states = {
        year: parse_fec_states(year, paths[f"fec_{year}"])
        for year in YEARS
    }
    county_areas = {
        year: (
            parse_historical_counties(paths["county_historical"], year)
            if year <= 2016
            else parse_new_counties(paths[f"county_{year}"])
        )
        for year in YEARS
    }
    for year in YEARS:
        add_statewide_fallbacks(county_areas[year], fec_states[year])
        validate_state_reconciliation(year, county_areas[year], fec_states[year])

    state_areas = {
        year: {
            result["state"]: {
                "code": abbr, "district": result["state"], "state": "United States",
                "dem": result["dem"], "rep": result["rep"],
                "other": result["other"], "total": result["total"],
            }
            for abbr, result in fec_states[year].items()
        }
        for year in YEARS
    }

    states = state_geometries(paths["states_2019"])
    apply_historical_boundary_labels(
        paths["counties_2010"],
        [county_areas[2008], county_areas[2012], county_areas[2016]],
    )
    historical = build_historical_counties(paths["counties_2010"], county_areas[2008], states)
    if set(county_areas[2008]) != set(county_areas[2012]) or set(county_areas[2008]) != set(county_areas[2016]):
        raise SystemExit("Historical county identifier sets changed; shared boundary is unsafe")
    modern_2020 = build_modern_counties(
        paths["counties_2019"], county_areas[2020], states, "us_presidential_2020_counties"
    )
    modern_2024 = build_modern_counties(
        paths["counties_2023"], county_areas[2024], states, "us_presidential_2024_counties"
    )
    state_boundaries = build_state_boundaries(states)

    write_geojson(args.output_dir / "us_president_2008_2016_county_boundaries.geojson", historical)
    write_geojson(args.output_dir / "us_president_2020_county_boundaries.geojson", modern_2020)
    write_geojson(args.output_dir / "us_president_2024_county_boundaries.geojson", modern_2024)
    write_geojson(args.output_dir / "us_president_state_boundaries.geojson", state_boundaries)

    for year in YEARS:
        write_csv(
            args.output_dir / f"us_{year}_president_county_fpp.csv",
            build_rows(year, county_areas[year], "county"),
        )
        write_csv(
            args.output_dir / f"us_{year}_president_state_fpp.csv",
            build_rows(year, state_areas[year], "state"),
        )
        county_winners = Counter(outcome(area, year)[1] for area in county_areas[year].values())
        national = Counter()
        for result in fec_states[year].values():
            national.update({
                "dem": int(result["dem"]), "rep": int(result["rep"]),
                "other": int(result["other"]), "total": int(result["total"]),
            })
        print(
            f"{year}: {len(county_areas[year]):,} county/reporting areas, 51 state/DC areas; "
            f"{county_winners['Democratic']:,} Democratic / {county_winners['Republican']:,} Republican local wins; "
            f"{national['total']:,} official national votes"
        )


if __name__ == "__main__":
    main()
