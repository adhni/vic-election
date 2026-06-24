#!/usr/bin/env python3
from build_nsw_state import main


if __name__ == "__main__":
    main(
        default_raw_dir="tmp/nsw_2023",
        default_results_url="https://pastvtr.elections.nsw.gov.au/SG2301/LA/results",
        default_boundary_zip_url="https://elections.nsw.gov.au/getmedia/cb9324ee-078f-405b-b4e9-0b95d4e6cefe/2021-gda-94.zip",
        default_boundary_zip_name="2021-gda-94.zip",
        default_boundary_extract_dir="2021-gda-94",
        default_boundary_dataset_relpath="2021GDA94/StateElectoralDistrict2021_GDA94_region.shp",
        default_prefix="nsw_2023",
        default_expected_districts=93,
    )
