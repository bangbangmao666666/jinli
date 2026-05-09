import unittest

from tests import _helpers  # noqa: F401
from constraint_filter.rank_tier import compute, should_include


YEARLY = [
    {"year": 2025, "min_rank": 40000},
    {"year": 2024, "min_rank": 42000},
    {"year": 2023, "min_rank": 44000},
]


class RankTierTests(unittest.TestCase):
    def test_chong_tier(self):
        ratio, tier, incomplete, missing = compute(YEARLY, applicant_rank=34000)
        self.assertLess(ratio, 1.0)
        self.assertGreaterEqual(ratio, 0.8)
        self.assertEqual(tier, "冲")
        self.assertFalse(incomplete)
        self.assertEqual(missing, [])

    def test_wen_tier(self):
        ratio, tier, incomplete, _ = compute(YEARLY, applicant_rank=45000)
        self.assertEqual(tier, "稳")

    def test_bao_tier(self):
        _, tier, _, _ = compute(YEARLY, applicant_rank=60000)
        self.assertEqual(tier, "保")

    def test_extreme_chong_excluded_by_default(self):
        ratio, tier, _, _ = compute(YEARLY, applicant_rank=10000)
        self.assertEqual(tier, "极冲")
        self.assertFalse(should_include(tier, aggressive_mode=False))
        self.assertTrue(should_include(tier, aggressive_mode=True))

    def test_extreme_bao_excluded(self):
        _, tier, _, _ = compute(YEARLY, applicant_rank=200000)
        self.assertEqual(tier, "极保")
        self.assertFalse(should_include(tier, aggressive_mode=False))

    def test_no_data_unknown(self):
        ratio, tier, incomplete, _ = compute([], applicant_rank=50000)
        self.assertIsNone(ratio)
        self.assertEqual(tier, "unknown")
        self.assertTrue(incomplete)

    def test_partial_data_weighted(self):
        partial = [{"year": 2025, "min_rank": 40000}]
        ratio, tier, incomplete, missing = compute(partial, applicant_rank=40000)
        self.assertAlmostEqual(ratio, 1.0, places=3)
        self.assertTrue(incomplete)
        self.assertEqual(set(missing), {2023, 2024})


if __name__ == "__main__":
    unittest.main()
