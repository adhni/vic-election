#!/usr/bin/env python3
"""Download 2024 ACS 1-year tables and join demographics to the 2024 House seats.

Uses official public bulk files; no Census API key or third-party packages needed.
Large national source files are cached in ignored tmp/, not committed to data/.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tmp" / "us_house_demographics"
PREFIX = "us_2024_house_demographics"
BULK_BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/1YRData/"
METADATA_BASE = "https://api.census.gov/data/2024/acs/acs1/groups/"
TABLES = (
    "B01001", "B01002", "B03002", "B05002", "B05003", "C08301",
    "B11001", "B15003", "C16001", "B17001", "B19001", "B19013",
    "B23025", "B25003", "B25064", "B25077", "B29001", "C24030",
)
IDENTIFIERS = ("constituency_code", "district", "state", "census_geo_id", "acs_year", "congress")
CD_PATTERN = re.compile(r"5001900US(\d{4})\Z")


def source_specs() -> list[tuple[str, str]]:
    return [item for table in TABLES for item in (
        (f"acsdt1y2024-{table.lower()}.dat", f"{BULK_BASE}acsdt1y2024-{table.lower()}.dat"),
        (f"{table}.json", f"{METADATA_BASE}{table}.json"),
    )]


def fetch_source(spec: tuple[str, str], cache: Path, refresh: bool = False) -> None:
    name, url = spec
    path = cache / name
    if path.exists() and not refresh:
        return
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ElectionExplorer-demographics/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
            if name.endswith(".json"):
                if "variables" not in json.loads(payload):
                    raise ValueError(f"{url}: missing variable metadata")
            elif not payload.startswith(b"GEO_ID|"):
                raise ValueError(f"{url}: expected a pipe-delimited ACS table")
            temporary = path.with_suffix(path.suffix + ".part")
            temporary.write_bytes(payload)
            temporary.replace(path)
            print(f"Downloaded {name}: {len(payload):,} bytes", flush=True)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def election_districts() -> dict[str, dict[str, str]]:
    districts = {}
    with (ROOT / "data" / "us_2024_house_fpp.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code = row["constituency_code"]
            identity = {"constituency_code": code, "district": row["district"], "state": row["electorate_type"]}
            if code in districts and districts[code] != identity:
                raise ValueError(f"Conflicting election identity for {code}")
            districts[code] = identity
    if len(districts) != 435:
        raise ValueError(f"Expected 435 election districts; found {len(districts)}")
    return districts


def census_code(geo_id: str) -> str | None:
    match = CD_PATTERN.fullmatch(geo_id)
    return match.group(1) if match else None


def number(value: str) -> float | None:
    """Special Census strings and negative sentinel values remain missing, never zero."""
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def cells(table: str, *lines: int) -> list[str]:
    return [f"{table}_{line:03d}E" for line in lines]


def margin_of_error(value: str) -> float | None:
    # Census-controlled estimates have no sampling variability. This specific
    # MOE sentinel means controlled, unlike missing/suppressed estimate codes.
    return 0.0 if value in {"-555555555", "*****"} else number(value)


def metric_definitions() -> dict[str, dict]:
    metrics = {}

    def direct(name, label, table, line, unit):
        metrics[name] = {"label": label, "unit": unit, "numerator": cells(table, line), "denominator": []}

    def share(name, label, table, lines, denominator=1):
        metrics[name] = {"label": label, "unit": "percent", "numerator": cells(table, *lines), "denominator": cells(table, denominator)}

    direct("population", "Total resident population", "B01001", 1, "people")
    direct("median_age", "Median age", "B01002", 1, "years")
    share("female_pct", "Female share of residents", "B01001", [26])
    share("under_18_pct", "Residents under 18", "B01001", [*range(3, 7), *range(27, 31)])
    share("age_18_29_pct", "Residents aged 18–29", "B01001", [*range(7, 12), *range(31, 36)])
    share("age_65_plus_pct", "Residents aged 65 and over", "B01001", [*range(20, 26), *range(44, 50)])
    share("white_non_hispanic_pct", "Non-Hispanic White alone residents", "B03002", [3])
    share("black_non_hispanic_pct", "Non-Hispanic Black alone residents", "B03002", [4])
    share("asian_non_hispanic_pct", "Non-Hispanic Asian alone residents", "B03002", [6])
    share("native_non_hispanic_pct", "Non-Hispanic American Indian / Alaska Native alone residents", "B03002", [5])
    share("pacific_non_hispanic_pct", "Non-Hispanic Native Hawaiian / Pacific Islander alone residents", "B03002", [7])
    share("other_race_non_hispanic_pct", "Non-Hispanic residents of some other race alone", "B03002", [8])
    share("multiracial_non_hispanic_pct", "Non-Hispanic residents of two or more races", "B03002", [9])
    share("hispanic_pct", "Hispanic / Latino residents of any race", "B03002", [12])
    share("foreign_born_pct", "Foreign-born residents", "B05002", [13])
    share("noncitizen_pct", "Residents who are not U.S. citizens", "B05002", [21])
    direct("citizen_voting_age_population", "U.S. citizens aged 18 and over (not registered or eligible voters)", "B29001", 1, "people")
    share("cvap_age_18_29_pct", "Citizens aged 18–29 as a share of citizens aged 18+", "B29001", [2])
    share("cvap_age_65_plus_pct", "Citizens aged 65+ as a share of citizens aged 18+", "B29001", [5])
    share("bachelors_plus_pct", "Adults 25+ with a bachelor's degree or higher", "B15003", [22, 23, 24, 25])
    share("graduate_degree_pct", "Adults 25+ with a graduate or professional degree", "B15003", [23, 24, 25])
    share("less_than_high_school_pct", "Adults 25+ without a high-school diploma or equivalent", "B15003", list(range(2, 17)))
    share("high_school_only_pct", "Adults 25+ with high-school diploma / GED as highest attainment", "B15003", [17, 18])
    share("english_only_pct", "Residents 5+ speaking only English at home", "C16001", [2])
    share("spanish_at_home_pct", "Residents 5+ speaking Spanish at home", "C16001", [3])
    direct("median_household_income", "Median household income in 2024 inflation-adjusted dollars", "B19013", 1, "USD_2024")
    share("household_income_under_50k_pct", "Households with income below $50,000", "B19001", list(range(2, 11)))
    share("household_income_100k_plus_pct", "Households with income of $100,000 or more", "B19001", list(range(14, 18)))
    share("poverty_pct", "People below the poverty level, among those with poverty status determined", "B17001", [2])
    share("unemployment_pct", "Unemployed share of the civilian labor force aged 16+", "B23025", [5], 3)
    share("labor_force_participation_pct", "Residents 16+ in the labor force, including Armed Forces", "B23025", [2])
    share("homeownership_pct", "Owner-occupied share of occupied housing units", "B25003", [2])
    share("renter_pct", "Renter-occupied share of occupied housing units", "B25003", [3])
    direct("median_gross_rent", "Median monthly gross rent for renter-occupied units paying cash rent", "B25064", 1, "USD_2024_per_month")
    direct("median_home_value", "Median value of owner-occupied housing units", "B25077", 1, "USD_2024")
    direct("households", "Total households", "B11001", 1, "households")
    share("married_couple_households_pct", "Married-couple family households as a share of all households", "B11001", [3])
    share("living_alone_households_pct", "One-person households as a share of all households", "B11001", [8])
    share("work_from_home_pct", "Workers 16+ who worked from home", "C08301", [11])
    share("public_transit_commute_pct", "Workers 16+ commuting by public transportation, excluding taxicab", "C08301", [8])
    # C24030 industry line IDs are resolved against official labels below.
    return metrics


def load_sources(cache: Path, districts: dict) -> tuple[dict, dict, list, dict]:
    raw = {code: {} for code in districts}
    variables = {}
    sources = []
    coverage = {}
    for table in TABLES:
        metadata = json.loads((cache / f"{table}.json").read_text(encoding="utf-8"))["variables"]
        with (cache / f"acsdt1y2024-{table.lower()}.dat").open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="|")
            columns = {}
            for column in reader.fieldnames or []:
                if column == "GEO_ID":
                    continue
                match = re.fullmatch(rf"{table}_([EM])(\d{{3}})", column)
                if not match:
                    raise ValueError(f"Unexpected source column: {column}")
                kind, line = match.groups()
                variable = f"{table}_{line}{kind}"
                definition = metadata[variable]
                variables[variable] = {"table": table, "label": definition["label"],
                                       "concept": definition["concept"], "universe": definition["universe"]}
                columns[column] = variable
            seen = set()
            for row in reader:
                code = census_code(row["GEO_ID"])
                if code not in districts:
                    continue
                if code in seen:
                    raise ValueError(f"{table}: duplicate district {code}")
                seen.add(code)
                raw[code].update({variable: row[column] for column, variable in columns.items()})
            missing = sorted(districts.keys() - seen)
            # Detailed language tables are not released for every district in
            # the 1-year product. Preserve these real gaps instead of imputing.
            if missing and table != "C16001":
                raise ValueError(f"{table}: missing districts {missing}")
            for code in missing:
                raw[code].update({variable: "" for variable in columns.values()})
            coverage[table] = {"districts_in_source": len(seen), "missing_district_codes": missing}
        print(f"Loaded {table}: {len(seen)} districts, {len(columns) // 2} estimates with MOEs", flush=True)
    for name, url in source_specs():
        path = cache / name
        sources.append({"filename": name, "url": url, "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "retrieved_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    return raw, variables, sources, coverage


def add_industry_metrics(metrics: dict, variables: dict) -> None:
    for name, industry in (("manufacturing_employment_pct", "Manufacturing"),
                           ("agriculture_mining_employment_pct", "Agriculture, forestry, fishing and hunting, and mining")):
        numerator = [code for code, definition in variables.items()
                     if code.startswith("C24030_") and code.endswith("E")
                     and definition["label"].split("!!")[-1].rstrip(":") == industry]
        if len(numerator) != 2:
            raise ValueError(f"Expected male and female industry cells for {industry}; found {numerator}")
        metrics[name] = {"label": f"Civilian employed residents 16+ in {industry.lower()}",
                         "unit": "percent", "numerator": sorted(numerator), "denominator": cells("C24030", 1)}


def aggregate(raw: dict, codes: list[str]) -> tuple[float | None, float | None]:
    estimates = [number(raw[code]) for code in codes]
    moes = [margin_of_error(raw[code[:-1] + "M"]) for code in codes]
    estimate = sum(estimates) if all(value is not None for value in estimates) else None
    moe = math.sqrt(sum(value ** 2 for value in moes)) if all(value is not None for value in moes) else None
    return estimate, moe


def metric_value(raw: dict, definition: dict) -> tuple[float | None, float | None]:
    numerator, numerator_moe = aggregate(raw, definition["numerator"])
    if not definition["denominator"]:
        return numerator, numerator_moe
    denominator, denominator_moe = aggregate(raw, definition["denominator"])
    if numerator is None or denominator is None or denominator <= 0:
        return None, None
    ratio = numerator / denominator
    if numerator_moe is None or denominator_moe is None:
        return ratio * 100, None
    # ACS subset-proportion approximation; fall back to the ratio formula when
    # subtraction yields a negative radicand. MOEs are at 90% confidence.
    radicand = numerator_moe ** 2 - ratio ** 2 * denominator_moe ** 2
    if radicand < 0:
        radicand = numerator_moe ** 2 + ratio ** 2 * denominator_moe ** 2
    return ratio * 100, math.sqrt(radicand) / denominator * 100


def csv_number(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value.is_integer() else f"{value:.6f}".rstrip("0").rstrip(".")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(cache: Path, output: Path) -> None:
    districts = election_districts()
    raw, variables, sources, coverage = load_sources(cache, districts)
    metrics = metric_definitions()
    add_industry_metrics(metrics, variables)
    for definition in metrics.values():
        definition["source_universes"] = sorted({variables[code]["universe"] for code in definition["numerator"] + definition["denominator"]})
        definition["formula"] = "100 * sum(numerator) / sum(denominator)" if definition["denominator"] else "sum(numerator)"
    raw_rows, metric_rows, flags = [], [], []
    for code, district in sorted(districts.items()):
        identity = {**district, "census_geo_id": f"5001900US{code}", "acs_year": 2024, "congress": 119}
        raw_rows.append({**identity, **raw[code]})
        row = dict(identity)
        for name, definition in metrics.items():
            estimate, moe = metric_value(raw[code], definition)
            row[name] = csv_number(estimate)
            row[f"{name}_moe"] = csv_number(moe)
        metric_rows.append(row)
        for variable, token in sorted(raw[code].items()):
            if number(token) is None:
                reason = ("district_not_in_source_table" if code in coverage[variables[variable]["table"]]["missing_district_codes"]
                          else "controlled_estimate_moe" if variable.endswith("M") and token in {"-555555555", "*****"}
                          else "source_special_value")
                flags.append({"constituency_code": code, "district": district["district"], "variable": variable,
                              "source_value": token, "reason": reason})
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / f"{PREFIX}_acs.csv"
    metrics_path = output / f"{PREFIX}.csv"
    flags_path = output / f"{PREFIX}_flags.csv"
    write_csv(raw_path, [*IDENTIFIERS, *sorted(variables)], raw_rows)
    write_csv(metrics_path, [*IDENTIFIERS, *(column for name in metrics for column in (name, f"{name}_moe"))], metric_rows)
    write_csv(flags_path, ["constituency_code", "district", "variable", "source_value", "reason"], flags)
    manifest = {
        "version": 1, "dataset": "2024 ACS 1-year estimates", "congress": 119,
        "boundary_vintage": "2024 election cycle; 119th Congress",
        "district_count": len(districts), "table_count": len(TABLES), "metric_count": len(metrics),
        "join_key": "constituency_code: two-digit state FIPS + two-digit district; 00 for at-large",
        "scope": "435 voting House districts in 50 states; DC and territories excluded",
        "missing_values": "Raw source tokens retained in _acs.csv and enumerated in _flags.csv; unavailable estimates/MOEs become blanks in derived metrics, never zeros. Exception: the controlled-estimate MOE token -555555555 (*****) contributes zero sampling error, with its status retained in flags.",
        "moe_confidence": 0.90,
        "methodology_sources": [
            "https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html",
            "https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2024/geography-changes.html",
            "https://www2.census.gov/programs-surveys/acs/tech_docs/statistical_testing/2024_Instructions_for_Stat_Testing_ACS.pdf",
            "https://www.census.gov/data/developers/data-sets/acs-1year/data-notes.html",
        ],
        "moe_method": "Direct published MOEs; sums use root-sum-of-squares; percentages use the ACS subset-proportion approximation, falling back to the ratio formula for negative radicands. Derived MOEs are approximations and are not clipped to 0–100.",
        "interpretation": "Resident / household characteristics, not demographics of actual voters. CVAP is not registered-voter or voting-eligible population. No correlations or turnout estimates are calculated.",
        "sources": sources, "table_coverage": coverage, "variables": variables, "metrics": metrics,
        "outputs": {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
                    for path in (raw_path, metrics_path, flags_path)},
    }
    (output / f"{PREFIX}_metadata.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(districts)} districts, {len(metrics)} metrics, {len(variables) // 2} source estimates; {len(flags)} special-value cells")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    parser.add_argument("--refresh", action="store_true", help="Redownload cached official source files")
    parser.add_argument("--offline", action="store_true", help="Rebuild entirely from cached sources")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args()
    if args.offline and args.refresh:
        parser.error("--offline and --refresh cannot be combined")
    args.cache.mkdir(parents=True, exist_ok=True)
    if not args.offline:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda spec: fetch_source(spec, args.cache, args.refresh), source_specs()))
    if not args.download_only:
        build(args.cache, args.out)


if __name__ == "__main__":
    main()
