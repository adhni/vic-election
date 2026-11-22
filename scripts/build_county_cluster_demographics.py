#!/usr/bin/env python3
"""Extract the existing ACS measures for the county grouping scatterplot."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHORT = {
    "population": "Population", "median_age": "Median age", "female_pct": "Female residents",
    "under_18_pct": "Residents under 18", "age_18_29_pct": "Residents age 18–29", "age_65_plus_pct": "Residents age 65+",
    "bachelors_plus_pct": "College graduates (age 25+)", "graduate_degree_pct": "Graduate degrees (age 25+)",
    "less_than_high_school_pct": "No high-school diploma (age 25+)", "high_school_only_pct": "High-school only (age 25+)",
    "white_non_hispanic_pct": "White residents, non-Hispanic", "black_non_hispanic_pct": "Black residents, non-Hispanic",
    "asian_non_hispanic_pct": "Asian residents, non-Hispanic", "native_non_hispanic_pct": "Native residents, non-Hispanic",
    "pacific_non_hispanic_pct": "Pacific Islander residents, non-Hispanic", "other_race_non_hispanic_pct": "Other race, non-Hispanic",
    "multiracial_non_hispanic_pct": "Multiracial residents, non-Hispanic", "hispanic_pct": "Hispanic / Latino residents",
    "foreign_born_pct": "Foreign-born residents", "noncitizen_pct": "Noncitizen residents",
    "citizen_voting_age_population": "Citizens age 18+", "cvap_age_18_29_pct": "Citizens age 18–29 (of 18+)",
    "cvap_age_65_plus_pct": "Citizens age 65+ (of 18+)", "english_only_pct": "English only at home (age 5+)",
    "spanish_at_home_pct": "Spanish at home (age 5+)", "median_household_income": "Median household income",
    "household_income_under_50k_pct": "Households below $50k", "household_income_100k_plus_pct": "Households at $100k+",
    "poverty_pct": "Poverty rate", "unemployment_pct": "Unemployment rate", "labor_force_participation_pct": "Labor-force participation",
    "homeownership_pct": "Homeownership", "renter_pct": "Renter households", "median_gross_rent": "Median monthly rent",
    "median_home_value": "Median home value", "households": "Households", "married_couple_households_pct": "Married-couple households",
    "living_alone_households_pct": "Living-alone households", "work_from_home_pct": "Working from home",
    "public_transit_commute_pct": "Public-transit commuting", "manufacturing_employment_pct": "Manufacturing jobs",
    "agriculture_mining_employment_pct": "Agriculture / mining jobs",
}


def build():
    cluster_path = ROOT / "data/us_county_presidential_clusters.json"
    source_path = ROOT / "data/us_2024_county_demographics.csv"
    metadata_path = ROOT / "data/us_2024_county_demographics_metadata.json"
    clusters = json.loads(cluster_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    rows = list(csv.DictReader(source_path.open()))
    by_code = {row["constituency_code"]: row for row in rows}
    assert len(by_code) == len(rows)
    keys = list(metadata["metrics"])
    assert set(keys) == set(SHORT), "Define a readable label for every metric"
    values, missing = {}, dict.fromkeys(keys, 0)
    for name, county in clusters["counties"].items():
        code = county["constituency_code"]
        row = by_code[code]
        assert row["state"] == county["state"] and row["acs_year"] == "2024", name
        estimates = []
        for key in keys:
            value = float(row[key]) if row[key] else None
            if value is not None:
                assert value >= 0
                if metadata["metrics"][key]["unit"] == "percent":
                    assert value <= 100
            else:
                missing[key] += 1
            estimates.append(value)
        values[code] = estimates
    result = {
        "dataset": metadata["dataset"], "interpretation": metadata["interpretation"],
        "area_count": len(values), "metric_keys": keys,
        "metrics": {key: {"label": metadata["metrics"][key]["label"], "short_label": SHORT[key],
            "unit": metadata["metrics"][key]["unit"], "source_universes": metadata["metrics"][key]["source_universes"]} for key in keys},
        "values_by_code": values, "missing_by_metric": missing,
        "missing_policy": "Null estimates are omitted from the scatterplot only. Counties remain selectable on the map. No imputation; margins of error are not drawn.",
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [cluster_path, source_path, metadata_path]},
    }
    (ROOT / "data/us_county_cluster_demographics.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    print(f"Extracted {len(keys)} ACS measures for {len(values):,} counties; missing estimates: {sum(missing.values())}")
    return result


if __name__ == "__main__":
    build()
