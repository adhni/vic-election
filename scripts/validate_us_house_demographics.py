#!/usr/bin/env python3
"""Validate district coverage, source provenance, demographic arithmetic and joins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from build_us_house_demographics import IDENTIFIERS, PREFIX, ROOT, TABLES


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def numeric(token: str) -> bool:
    try:
        return math.isfinite(float(token)) and float(token) >= 0
    except (ValueError, TypeError):
        return False


def validate(data: Path, cache: Path | None = None, year: int = 2024) -> None:
    PREFIX = f"us_{year}_house_demographics"
    TABLES = tuple(table for table in globals()["TABLES"] if year != 2021 or table != "B29001")
    congress = 116 if year == 2021 else 119
    geo_prefix = f"500{congress - 100:02d}00US"
    metadata = json.loads((data / f"{PREFIX}_metadata.json").read_text(encoding="utf-8"))
    require(metadata["version"] == 1 and metadata["congress"] == congress, "Unexpected dataset version / Congress")
    require(metadata["district_count"] == 435 and metadata["table_count"] == len(TABLES), "Unexpected dataset dimensions")
    require(metadata["moe_confidence"] == 0.9, "Expected ACS 90% margins of error")
    for name, info in metadata["outputs"].items():
        payload = (data / name).read_bytes()
        require(len(payload) == info["bytes"] and hashlib.sha256(payload).hexdigest() == info["sha256"], f"Output checksum mismatch: {name}")
    require(len(metadata["outputs"]) == 3, "Expected three CSV outputs")
    require(len(metadata["sources"]) == len(TABLES) * 2, "Expected 18 official tables and 18 metadata files")
    for source in metadata["sources"]:
        require(source["url"].startswith(("https://www2.census.gov/", "https://api.census.gov/")), "Unexpected source host")
        if cache:
            payload = (cache / source["filename"]).read_bytes()
            require(hashlib.sha256(payload).hexdigest() == source["sha256"], f"Cached source changed: {source['filename']}")

    expected = {}
    for row in read_csv(ROOT / "data" / f"us_{2020 if year == 2021 else 2024}_house_fpp.csv"):
        expected[row["constituency_code"]] = (row["district"], row["electorate_type"])
    boundary = json.loads((ROOT / "data" / f"us_{2020 if year == 2021 else 2024}_congressional_boundaries.geojson").read_text())
    boundary_codes = {feature["properties"]["constituency_code"] for feature in boundary["features"]}
    require(len(expected) == 435 and boundary_codes == expected.keys(), "Election / boundary district mismatch")

    datasets = [read_csv(data / f"{PREFIX}{suffix}.csv") for suffix in ("", "_acs")]
    for rows in datasets:
        require(len(rows) == 435, "Expected exactly 435 district rows")
        require({row["constituency_code"] for row in rows} == expected.keys(), "Demographics / election district mismatch")
        for row in rows:
            code = row["constituency_code"]
            require((row["district"], row["state"]) == expected[code], f"Incorrect district identity: {code}")
            require(row["census_geo_id"] == f"{geo_prefix}{code}", f"Incorrect 119th Congress GEO_ID: {code}")
            require(row["acs_year"] == str(year) and row["congress"] == str(congress), f"Incorrect vintage: {code}")

    metrics, raw = ({row["constituency_code"]: row for row in rows} for rows in datasets)
    variables = metadata["variables"]
    require(set(raw[next(iter(raw))]) == set(IDENTIFIERS) | variables.keys(), "Source columns differ from dictionary")
    require({info["table"] for info in variables.values()} == set(TABLES), "Source tables differ from configuration")
    require(len(variables) == (700 if year == 2021 else 710) and metadata["metric_count"] == (39 if year == 2021 else 42), "Unexpected source / metric count")
    require(set(metadata["table_coverage"]) == set(TABLES), "Missing coverage metadata")

    if cache:
        # Verify the district extract against the downloaded national records,
        # not merely against other generated files.
        for table in TABLES:
            with (cache / f"acsdt1y{year}-{table.lower()}.dat").open(newline="", encoding="utf-8-sig") as handle:
                found = set()
                for source_row in csv.DictReader(handle, delimiter="|"):
                    geo_id = source_row["GEO_ID"]
                    if not geo_id.startswith(geo_prefix) or geo_id[9:] not in expected:
                        continue
                    code = geo_id[9:]
                    require(code not in found, f"Duplicate district in cached {table}: {code}")
                    found.add(code)
                    for variable, definition in variables.items():
                        if definition["table"] != table:
                            continue
                        source_column = f"{table}_{variable[-1]}{variable[-4:-1]}"
                        require(raw[code][variable] == source_row[source_column], f"Source extract mismatch: {code} {variable}")
                require(found == expected.keys() - set(metadata["table_coverage"][table]["missing_district_codes"]), f"Cached source coverage mismatch: {table}")

    for table, coverage in metadata["table_coverage"].items():
        missing = set(coverage["missing_district_codes"])
        require(missing <= expected.keys(), f"Unknown missing district in {table}")
        require(coverage["districts_in_source"] + len(missing) == 435, f"Invalid coverage count for {table}")
        if table != "C16001":
            require(not missing, f"Core table incomplete: {table}")
        for code, row in raw.items():
            table_cells = [value for variable, value in row.items() if variable.startswith(table + "_")]
            require(bool(table_cells) and all(value != "" for value in table_cells) == (code not in missing), f"Coverage mismatch: {table} {code}")

    flags = read_csv(data / f"{PREFIX}_flags.csv")
    flagged = {(row["constituency_code"], row["variable"]): row for row in flags}
    require(len(flagged) == len(flags), "Duplicate source flags")
    expected_flags = {(code, variable) for code, row in raw.items() for variable in variables if not numeric(row[variable])}
    require(flagged.keys() == expected_flags, "Source flags do not exactly cover special / unavailable values")
    for (code, variable), flag in flagged.items():
        require(flag["source_value"] == raw[code][variable] and flag["district"] == expected[code][0], "Source flag does not match raw value")
        missing = code in metadata["table_coverage"][variables[variable]["table"]]["missing_district_codes"]
        reason = ("district_not_in_source_table" if missing else "controlled_estimate_moe"
                  if variable.endswith("M") and flag["source_value"] in {"-555555555", "*****"} else "source_special_value")
        require(flag["reason"] == reason, f"Incorrect flag reason: {code} {variable}")

    for code, row in raw.items():
        # Independent accounting identities catch wrong cells, missing rows and
        # joins even if an output file and its checksum were changed together.
        def total(table, *lines):
            return sum(int(row[f"{table}_{line:03d}E"]) for line in lines)

        population = total("B01001", 1)
        require(population > 0, f"Invalid population: {code}")
        require(population == total("B01001", 2, 26) == total("B03002", 1) == total("B05002", 1), f"Population reconciliation failed: {code}")
        require(total("B03002", 1) == total("B03002", *range(3, 10), 12), f"Race / ethnicity reconciliation failed: {code}")
        require(total("B15003", 1) == total("B15003", *range(2, 26)), f"Education reconciliation failed: {code}")
        require(total("B19001", 1) == total("B19001", *range(2, 18)), f"Income bracket reconciliation failed: {code}")
        require(total("B25003", 1) == total("B25003", 2, 3) == total("B11001", 1), f"Housing / household reconciliation failed: {code}")
        if year == 2024:
            require(total("B29001", 1) == total("B29001", 2, 3, 4, 5) == total("B05003", 9, 11, 20, 22), f"CVAP reconciliation failed: {code}")
        require(total("B23025", 3) == total("B23025", 4, 5), f"Labor force reconciliation failed: {code}")

        for name, definition in metadata["metrics"].items():
            estimate, moe = metrics[code][name], metrics[code][f"{name}_moe"]
            require(all(variable in variables for variable in definition["numerator"] + definition["denominator"]), f"Unknown metric source: {name}")
            source = [row[variable] for variable in definition["numerator"] + definition["denominator"]]
            available = all(numeric(value) for value in source)
            if definition["denominator"] and available:
                available = sum(float(row[variable]) for variable in definition["denominator"]) > 0
            require(bool(estimate) == available, f"Missingness mismatch: {code} {name}")
            if not available:
                require(moe == "", f"MOE without estimate: {code} {name}")
                continue
            value = sum(float(row[variable]) for variable in definition["numerator"])
            if definition["denominator"]:
                value *= 100 / sum(float(row[variable]) for variable in definition["denominator"])
            require(numeric(estimate) and abs(float(estimate) - value) <= 0.000001, f"Metric arithmetic mismatch: {code} {name}")
            if definition["unit"] == "percent":
                require(0 <= float(estimate) <= 100, f"Percentage out of range: {code} {name}")
            require(moe == "" or numeric(moe), f"Invalid margin of error: {code} {name}")

    print(f"US House {year} demographics passed: 435 districts, {metadata['metric_count']} metrics, {len(variables)//2} source estimates with MOEs, {len(flags)} source flags")
    for table, coverage in metadata["table_coverage"].items():
        if coverage["missing_district_codes"]:
            print(f"Disclosed source gaps: {table}: {', '.join(coverage['missing_district_codes'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=(2021, 2024), default=2024)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--cache", type=Path, help="Also verify cached national-source checksums")
    args = parser.parse_args()
    validate(args.data, args.cache, args.year)


if __name__ == "__main__":
    main()
