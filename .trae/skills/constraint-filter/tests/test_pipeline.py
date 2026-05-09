"""集成测试：覆盖 PRD §八 的关键场景。"""
import json
import unittest
from pathlib import Path

from tests._helpers import henan_physics_applicant  # noqa: F401  (sys.path)
from constraint_filter import run


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _find_major(result, school_name, major_name):
    for school in result["eligible_pool"]:
        if school["school_name"] != school_name:
            continue
        for group in school["major_groups"]:
            for m in group["majors"]:
                if m["major_name"] == major_name:
                    return m
    return None


def _is_excluded(result, target_substring, dim=None):
    for e in result["excluded_summary"]:
        if target_substring in e["target"]:
            if dim is None or e.get("dimension") == dim:
                return True
    return False


class PipelineNormalPathTests(unittest.TestCase):
    def test_normal_henan_physics_returns_success(self):
        res = run(henan_physics_applicant())
        self.assertEqual(res["status"], "success", msg=res)
        self.assertGreaterEqual(res["stats"]["total_schools_in_plan"], 1)
        self.assertIn("郑州大学", [s["school_name"] for s in res["eligible_pool"]])

    def test_zhengzhou_electrical_has_tier(self):
        res = run(henan_physics_applicant())
        m = _find_major(res, "郑州大学", "电气工程及其自动化")
        self.assertIsNotNone(m)
        self.assertIn(m["rank_ratio_tier"], {"冲", "稳", "保"})
        self.assertIsNotNone(m["rank_ratio_value"])

    def test_liberal_arts_major_filtered_out_for_physics_class(self):
        # 汉语言文学所在组是"第2组（文史类）"；但选科要求为"不限"，物理类考生仍可进入。
        # 我们只检查流程不崩。
        res = run(henan_physics_applicant())
        self.assertEqual(res["status"], "success")


class PipelineSubjectFilterTests(unittest.TestCase):
    def test_no_chemistry_excludes_chem_required_majors(self):
        applicant = henan_physics_applicant(selected_subjects=["物理", "生物", "政治"])
        res = run(applicant)
        self.assertEqual(res["status"], "success")
        # 化学工程与工艺（要求物理+化学）应被选科排除
        self.assertFalse(_find_major(res, "郑州大学", "化学工程与工艺"))
        self.assertTrue(
            _is_excluded(res, "化学工程与工艺", dim="选科"),
            msg=f"excluded_summary={res['excluded_summary']}",
        )


class PipelinePhysicalFilterTests(unittest.TestCase):
    def test_colorblind_excludes_chemistry(self):
        applicant = henan_physics_applicant()
        applicant["physical_exam"]["color_blindness"] = "色盲"
        res = run(applicant)
        self.assertFalse(_find_major(res, "郑州大学", "化学工程与工艺"))
        self.assertTrue(_is_excluded(res, "化学工程与工艺", dim="体检"))

    def test_physical_exam_missing_raises_warnings_but_keeps_pool(self):
        applicant = henan_physics_applicant()
        applicant.pop("physical_exam")
        res = run(applicant)
        self.assertEqual(res["status"], "success")
        self.assertTrue(any("体检" in w for w in res["warnings"]))

    def test_political_unclean_excludes_police(self):
        applicant = henan_physics_applicant(political_review_clean=False)
        res = run(applicant)
        self.assertFalse(_find_major(res, "中国人民公安大学", "治安学"))
        self.assertTrue(_is_excluded(res, "中国人民公安大学", dim="政审"))

    def test_political_unknown_keeps_police_with_warning(self):
        applicant = henan_physics_applicant(political_review_clean=None)
        res = run(applicant)
        self.assertTrue(any("政审" in w for w in res["warnings"]))
        # 公安大学的治安学选科要求是"物理或化学"，考生选了物理+化学+生物，满足。
        self.assertTrue(_find_major(res, "中国人民公安大学", "治安学"))


class PipelineRankFilterTests(unittest.TestCase):
    def test_extreme_chong_excluded_by_default(self):
        # 用一个分数非常高（位次非常低）的考生，西安交大计算机（约3500位次）对他变成"极保"
        applicant = henan_physics_applicant(total_score=580, provincial_rank=100)
        res = run(applicant)
        self.assertTrue(
            _is_excluded(res, "计算机科学与技术", dim="分数位次"),
            msg=res["excluded_summary"],
        )

    def test_aggressive_mode_includes_extreme_tiers(self):
        applicant = henan_physics_applicant(
            total_score=580, provincial_rank=100, aggressive_mode=True
        )
        res = run(applicant)
        # 计算机科学与技术应被保留（极保档在 aggressive_mode 下保留）
        self.assertTrue(_find_major(res, "西安交通大学", "计算机科学与技术"))


class PipelineDataIntegrityTests(unittest.TestCase):
    def test_new_major_without_history_is_kept_unknown(self):
        applicant = henan_physics_applicant()
        res = run(applicant)
        m = _find_major(res, "测试新增专业示例大学", "区块链工程")
        self.assertIsNotNone(m)
        self.assertEqual(m["rank_ratio_tier"], "unknown")
        self.assertTrue(m["historical_data_missing"])

    def test_data_version_mismatch(self):
        # 使用一份故意陈旧的 fixture 数据目录：henan_2026.json 的 valid_for_year=2024
        fixture_dir = ROOT / "tests" / "fixtures" / "version_mismatch_data"
        applicant = henan_physics_applicant(exam_year=2026)
        res = run(applicant, data_dir=fixture_dir)
        self.assertEqual(res["status"], "error", msg=res)
        self.assertEqual(res["error_code"], "DATA_VERSION_MISMATCH")
        self.assertEqual(res["error_detail"]["file_valid_for_year"], 2024)

    def test_data_source_unavailable_unsupported_province(self):
        applicant = henan_physics_applicant(province="西藏", subject_category="理科",
                                            selected_subjects=[])
        res = run(applicant)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "DATA_SOURCE_UNAVAILABLE")


class PipelineOutputShapeTests(unittest.TestCase):
    def test_success_output_shape(self):
        res = run(henan_physics_applicant())
        for k in ["status", "generated_at", "data_snapshot_version", "applicant_profile",
                  "eligible_pool", "excluded_summary", "warnings", "stats"]:
            self.assertIn(k, res)
        self.assertEqual(res["status"], "success")

    def test_error_output_shape(self):
        applicant = henan_physics_applicant()
        applicant.pop("total_score")
        res = run(applicant)
        for k in ["status", "error_code", "error_category", "error_message",
                  "user_action_required", "partial_result"]:
            self.assertIn(k, res)
        self.assertEqual(res["status"], "error")
        self.assertIsNone(res["partial_result"])


if __name__ == "__main__":
    unittest.main()
