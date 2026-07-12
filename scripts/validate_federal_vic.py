#!/usr/bin/env python3
from validate_federal import main


if __name__ == "__main__":
    main(
        default_scope="vic",
        default_csv="data/federal_2013_vic_preferences_long.csv",
        default_boundaries="data/federal_2013_vic_division_boundaries.geojson",
        default_expected_divisions=37,
    )
