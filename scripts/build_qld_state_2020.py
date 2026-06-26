#!/usr/bin/env python3
from build_qld_state import main


if __name__ == "__main__":
    main(
        default_raw_dir="tmp/qld_2020",
        default_election_stub="state2020",
        default_prefix="qld_2020",
        default_expected_districts=93,
    )
