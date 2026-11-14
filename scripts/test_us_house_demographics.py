#!/usr/bin/env python3
"""Checks for Census geography and uncertainty edge cases in demographic imports."""

import math
import unittest

from build_us_house_demographics import census_code, margin_of_error, metric_value, number


class CensusImportTests(unittest.TestCase):
    def test_boundary_vintage_and_at_large_codes(self):
        self.assertEqual(census_code("5001900US0200"), "0200")
        self.assertEqual(census_code("5001900US0101"), "0101")
        for geo_id in ("5001800US0101", "0400000US01", "5001900US101", "5001900US0101junk"):
            self.assertIsNone(census_code(geo_id))

    def test_special_values_are_not_zero_estimates(self):
        for value in ("", "(X)", "N", "-666666666", "-555555555", "nan", "inf"):
            self.assertIsNone(number(value))
        self.assertEqual(number("0"), 0)
        self.assertEqual(margin_of_error("-555555555"), 0)
        self.assertIsNone(margin_of_error("-999999999"))

    def test_proportion_moe_and_controlled_denominator(self):
        definition = {"numerator": ["X_002E"], "denominator": ["X_001E"]}
        raw = {"X_002E": "40", "X_002M": "4", "X_001E": "100", "X_001M": "5"}
        value, moe = metric_value(raw, definition)
        self.assertEqual(value, 40)
        self.assertAlmostEqual(moe, math.sqrt(12))
        raw["X_001M"] = "-555555555"
        self.assertEqual(metric_value(raw, definition), (40, 4))

    def test_negative_radicand_uses_ratio_formula(self):
        definition = {"numerator": ["X_002E"], "denominator": ["X_001E"]}
        raw = {"X_002E": "50", "X_002M": "1", "X_001E": "100", "X_001M": "10"}
        value, moe = metric_value(raw, definition)
        self.assertEqual(value, 50)
        self.assertAlmostEqual(moe, math.sqrt(26))

    def test_missing_component_does_not_produce_partial_sum(self):
        definition = {"numerator": ["X_002E", "X_003E"], "denominator": ["X_001E"]}
        raw = {"X_002E": "30", "X_002M": "3", "X_003E": "-666666666", "X_003M": "-999999999", "X_001E": "100", "X_001M": "5"}
        self.assertEqual(metric_value(raw, definition), (None, None))
        raw["X_003E"] = "20"
        self.assertEqual(metric_value(raw, definition), (50, None))
        raw["X_001E"] = "0"
        self.assertEqual(metric_value(raw, definition), (None, None))


if __name__ == "__main__":
    unittest.main()
