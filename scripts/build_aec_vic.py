#!/usr/bin/env python3
from build_aec_federal import main


if __name__ == "__main__":
    main(
        default_scope="vic",
        default_raw_dir="tmp/aec_2025_vic",
        default_gis_source="https://www.aec.gov.au/Electorates/gis/files/Vic-october-2024-esri.zip",
        default_shp="tmp/aec_2025_vic/Vic-october-2024-esri/E_VIC24_region.shp",
    )
