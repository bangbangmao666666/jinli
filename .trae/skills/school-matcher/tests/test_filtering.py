
import unittest
from school_matcher.output_formatter import extract_combinations

class TestFiltering(unittest.TestCase):
    def setUp(self):
        self.eligible_pool = [
            {
                "school_name": "School A",
                "major_groups": [
                    {
                        "majors": [
                            {"major_name": "Major 1", "rank_ratio_tier": "稳档"},
                            {"major_name": "Major 2", "rank_ratio_tier": "冲档"},
                        ]
                    }
                ]
            },
            {
                "school_name": "School B",
                "major_groups": [
                    {
                        "majors": [
                            {"major_name": "Major 1", "rank_ratio_tier": "保档"},
                            {"major_name": "Major 3", "rank_ratio_tier": "稳档"},
                        ]
                    }
                ]
            }
        ]
        self.passed_majors = [
            {"major_name": "Major 1", "traffic_light": "green"},
            {"major_name": "Major 2", "traffic_light": "yellow"},
            {"major_name": "Major 3", "traffic_light": "green"},
        ]

    def test_no_filter(self):
        # 如果不提供 selected_majors，应包含所有 passed_majors 中的专业
        combos = extract_combinations(self.eligible_pool, self.passed_majors)
        major_names = {c["major_name"] for c in combos}
        self.assertEqual(len(combos), 4)
        self.assertIn("Major 1", major_names)
        self.assertIn("Major 2", major_names)
        self.assertIn("Major 3", major_names)

    def test_with_filter(self):
        # 如果提供 selected_majors，应只包含这些专业
        selected = ["Major 1", "Major 3"]
        combos = extract_combinations(self.eligible_pool, self.passed_majors, selected)
        major_names = {c["major_name"] for c in combos}
        self.assertEqual(len(combos), 3) # School A (Major 1), School B (Major 1, Major 3)
        self.assertIn("Major 1", major_names)
        self.assertIn("Major 3", major_names)
        self.assertNotIn("Major 2", major_names)

    def test_empty_passed_with_filter(self):
        # 如果 passed_majors 为空但提供了 selected_majors，应以 selected_majors 为准
        selected = ["Major 1"]
        combos = extract_combinations(self.eligible_pool, [], selected)
        major_names = {c["major_name"] for c in combos}
        self.assertEqual(len(combos), 2)
        self.assertIn("Major 1", major_names)
        self.assertNotIn("Major 2", major_names)
        self.assertNotIn("Major 3", major_names)

if __name__ == "__main__":
    unittest.main()
