#!/usr/bin/env python3
from build_qld_state import main


if __name__ == "__main__":
    main(
        default_raw_dir="tmp/qld_2024",
        default_election_stub="SGE2024",
        default_prefix="qld_2024",
        default_expected_districts=93,
    )
