#!/usr/bin/env python3
from build_nsw_state import main


if __name__ == "__main__":
    main(
        default_raw_dir="tmp/nsw_2015",
        default_results_url="https://pastvtr.elections.nsw.gov.au/SGE2015/la-home.htm",
        default_boundary_zip_url="https://elections.nsw.gov.au/getmedia/256fccc5-1419-4aa4-addd-55387a7e60b5/gis-files-zip.zip",
        default_boundary_zip_name="gis-files-zip.zip",
        default_boundary_extract_dir="gis-files-zip",
        default_boundary_dataset_relpath="DeterminedBoundaries2013.MID",
        default_prefix="nsw_2015",
        default_expected_districts=93,
    )
