#!/usr/bin/env python3
"""Extract population for the exact county reporting areas in the dot explorer."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    cluster_path = ROOT / "data/us_county_presidential_clusters.json"
    source_path = ROOT / "data/us_2024_county_demographics.csv"
    metadata_path = ROOT / "data/us_2024_county_demographics_metadata.json"
    clusters = json.loads(cluster_path.read_text())
    metadata = json.loads(metadata_path.read_text())
    rows = list(csv.DictReader(source_path.open()))
    by_code = {row["constituency_code"]: row for row in rows}
    assert len(by_code) == len(rows), "Duplicate population identifiers"
    population = {}
    for name, county in clusters["counties"].items():
        code = county["constituency_code"]
        row = by_code[code]
        assert row["state"] == county["state"] and row["acs_year"] == "2024", name
        value = int(row["population"])
        assert value > 0 and code not in population, name
        population[code] = value
    assert len(population) == clusters["county_count"] == 3103
    result = {
        "dataset": metadata["dataset"],
        "interpretation": "2020–2024 ACS five-year resident population estimates for the included reporting areas. Includes children and nonvoters; not votes, voters, or a 2024-only population count.",
        "scope": clusters["coverage_note"],
        "area_count": len(population),
        "total_population": sum(population.values()),
        "dot_budget": len(population),
        "population_by_code": dict(sorted(population.items())),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [cluster_path, source_path, metadata_path]},
        "source": {"table": "B01001", "variable": "B01001_001E", "label": "Total population",
                   "dataset": metadata["dataset"], "source_files": [item for item in metadata["sources"] if "b01001" in item["filename"].lower()]},
    }
    target = ROOT / "data/us_county_cluster_population.json"
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Population covers all {len(population):,} counties: {result['total_population']:,} residents; {result['dot_budget']:,} dots")
    return result


if __name__ == "__main__":
    build()
