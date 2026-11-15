#!/usr/bin/env python3
"""Regression checks for contest aggregation, sample selection and correlation edge cases."""

import unittest

from build_us_house_analysis import average_ranks, joined_rows, pearson, sample_rows, summarize_result


def contest(candidates, status="official"):
    total = sum(votes for _, _, votes in candidates)
    return [{"district": "Example 1st", "constituency_code": "0101", "electorate_type": "Alabama",
             "elected_member": max(candidates, key=lambda candidate: candidate[2])[0], "elected_party": "Republican",
             "contest_status": status, "formal_votes": str(total), "total_votes": str(total), "informal_votes": "0",
             "row_type": "first", "round_number": "0", "candidate": name, "candidate_party": party, "votes": str(votes)}
            for name, party, votes in candidates]


class HouseAnalysisTests(unittest.TestCase):
    def test_write_ins_are_counted_once_in_their_explicit_party(self):
        result = summarize_result(contest([("D", "Democratic", 40), ("R", "Republican", 50),
                                            ("D write-in", "Write-in (Democratic)", 10), ("Unknown", "Write-in", 5)]))
        self.assertEqual((result["democratic_votes"], result["republican_votes"], result["other_votes"]), (50, 50, 5))
        self.assertEqual(result["democratic_named_candidate_count"], 1)
        self.assertEqual(result["democratic_two_party_share_pct"], "50")
        self.assertEqual(result["candidate_margin_votes"], 10)
        self.assertEqual(result["two_party_analysis_eligible"], "true")

    def test_same_party_contest_has_no_two_party_share(self):
        result = summarize_result(contest([("D one", "Democratic", 70), ("D two", "Democratic", 30)]))
        self.assertEqual(result["two_party_analysis_eligible"], "false")
        self.assertEqual(result["democratic_two_party_share_pct"], "")
        self.assertEqual(result["candidate_margin_votes"], 40)
        self.assertIn("no_named_republican_candidate", result["two_party_exclusion_reason"])

    def test_unreported_unopposed_votes_do_not_become_zero_percent(self):
        result = summarize_result(contest([("R", "Republican", 0)], "uncontested"))
        self.assertEqual(result["votes_reported"], "false")
        self.assertIn("candidate_vote_totals_unavailable", result["two_party_exclusion_reason"])
        for field in ("democratic_vote_share_pct", "republican_vote_share_pct", "democratic_two_party_share_pct", "candidate_margin_votes", "candidate_margin_pct"):
            self.assertEqual(result[field], "")

    def test_multiple_candidates_affect_sensitivity_not_party_totals(self):
        result = summarize_result(contest([("D one", "Democratic", 20), ("D two", "Democratic", 30), ("R", "Republican", 50)]))
        self.assertEqual(result["democratic_two_party_share_pct"], "50")
        self.assertEqual(result["multiple_major_party_candidates"], "true")
        self.assertEqual(sample_rows([result], "both_major_parties"), [result])
        self.assertEqual(sample_rows([result], "single_matchup_excluding_ranked_choice_states"), [])

    def test_duplicate_candidate_and_mismatched_district_are_rejected(self):
        rows = contest([("D", "Democratic", 40), ("R", "Republican", 60)])
        with self.assertRaisesRegex(ValueError, "Duplicate candidate"):
            summarize_result([rows[0], rows[0]])
        demo = {"constituency_code": "0101", "district": "Different district", "state": "Alabama"}
        with self.assertRaisesRegex(ValueError, "District identity mismatch"):
            joined_rows(rows, [demo], {})
        with self.assertRaisesRegex(ValueError, "Duplicate demographic"):
            joined_rows(rows, [demo, demo], {})

    def test_tied_ranks_and_degenerate_correlations(self):
        self.assertEqual(average_ranks([1, 1, 3]), [1.5, 1.5, 3])
        self.assertAlmostEqual(pearson(average_ranks([1, 1, 3]), average_ranks([1, 2, 2])), 0.5)
        self.assertEqual(pearson([1, 2, 3], [3, 2, 1]), -1)
        self.assertEqual(pearson([1, 2, 3], [1, -2, 1]), 0)
        self.assertIsNone(pearson([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(pearson([1, 2], [1, 2]))
        with self.assertRaises(ValueError):
            pearson([1, 2, 3], [1, 2])


if __name__ == "__main__":
    unittest.main()
