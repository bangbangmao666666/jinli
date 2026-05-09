import unittest

from tests import _helpers  # noqa: F401
from constraint_filter.physical_filter import evaluate, collect_missing_fields_warning
from constraint_filter.data_loader import load_physical_restrictions


class PhysicalFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_physical_restrictions()

    def _chemistry_major(self):
        return {
            "major_name": "化学工程与工艺",
            "major_category": "化学工程与工艺",
            "physical_requirement_notes": ["色盲、色弱不宜报考"],
        }

    def test_colorblind_excludes_chemistry(self):
        pe = {"color_blindness": "色盲", "vision_left": 4.9, "vision_right": 4.9,
              "height_cm": 175, "hearing_normal": True}
        kept, reason, verified = evaluate(self._chemistry_major(), pe, "男", self.rules)
        self.assertFalse(kept)
        self.assertIn("色盲", reason or "")
        self.assertTrue(verified)

    def test_normal_keeps_chemistry(self):
        pe = {"color_blindness": "正常", "vision_left": 4.9, "vision_right": 4.9,
              "height_cm": 175, "hearing_normal": True}
        kept, reason, verified = evaluate(self._chemistry_major(), pe, "男", self.rules)
        self.assertTrue(kept)
        self.assertIsNone(reason)

    def test_missing_physical_exam_keeps_everything(self):
        kept, reason, verified = evaluate(self._chemistry_major(), None, "男", self.rules)
        self.assertTrue(kept)
        self.assertFalse(verified)

    def test_collect_missing_fields_warnings(self):
        ws = collect_missing_fields_warning(None)
        self.assertTrue(any("体检维度未过滤" in w for w in ws))

        pe = {"color_blindness": "未知", "vision_left": None, "vision_right": None,
              "height_cm": None, "hearing_normal": None}
        ws = collect_missing_fields_warning(pe)
        self.assertTrue(any("color_blindness" in w for w in ws))
        self.assertTrue(any("视力" in w for w in ws))
        self.assertTrue(any("height_cm" in w for w in ws))

    def test_vision_below_threshold_excludes_flight(self):
        flight = {"major_name": "飞行技术", "major_category": "飞行技术", "physical_requirement_notes": []}
        pe = {"color_blindness": "正常", "vision_left": 4.5, "vision_right": 4.9,
              "height_cm": 175, "hearing_normal": True}
        kept, reason, _ = evaluate(flight, pe, "男", self.rules)
        self.assertFalse(kept)


if __name__ == "__main__":
    unittest.main()
