#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd

REQUIRED = {
    "district", "elected_member", "elected_party", "formal_votes", "round_number",
    "row_type", "excluded_candidate", "excluded_party", "candidate", "candidate_party", "votes"
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="?", default="data/vic_2022_preferences_long.csv")
    args = p.parse_args()
    path = Path(args.csv)
    df = pd.read_csv(path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")
    print("Rows:", len(df))
    print("Districts:", df["district"].nunique())
    print("Row types:")
    print(df["row_type"].value_counts(dropna=False).to_string())
    bad = df[df["votes"].isna()]
    print("Missing vote rows:", len(bad))
    final_counts = df[df["row_type"].eq("final")].groupby("district").size()
    print("Districts with final rows:", len(final_counts))

if __name__ == "__main__":
    main()
