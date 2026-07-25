#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_repository_sizes import MAX_DATA_FILE_BYTES, find_oversized_data_files


class RepositorySizeGuardTest(unittest.TestCase):
    def test_rejects_data_file_above_project_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            oversized = Path(directory) / "oversized.csv"
            with oversized.open("wb") as handle:
                handle.truncate(MAX_DATA_FILE_BYTES + 1)

            self.assertEqual(
                find_oversized_data_files([oversized]),
                [(oversized, MAX_DATA_FILE_BYTES + 1)],
            )

    def test_accepts_data_file_at_project_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            allowed = Path(directory) / "allowed.csv"
            with allowed.open("wb") as handle:
                handle.truncate(MAX_DATA_FILE_BYTES)

            self.assertEqual(find_oversized_data_files([allowed]), [])


if __name__ == "__main__":
    unittest.main()
