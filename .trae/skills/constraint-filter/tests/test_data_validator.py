"""单元测试：data_validator.py 的各校验函数。

使用纯内存的合成数据，不依赖磁盘文件。
"""
import unittest

from tests._helpers import henan_physics_applicant  # noqa: F401（sys.path）

from constraint_filter.data_validator import (
    validate_admission_plan,
    validate_historical_ranks,
    validate_score_rank_table,
)
from constraint_filter.errors import DataIntegrityViolatedError


# ── 辅助工厂 ────────────────────────────────────────────────────────────────

def _make_plan(schools: list, valid_for_year: int = 2026) -> dict:
    return {
        "source": "test",
        "valid_for_year": valid_for_year,
        "province": "测试省",
        "schools": schools,
    }


def _make_school(name: str, majors: list[dict]) -> dict:
    return {
        "school_code": "TEST001",
        "school_name": name,
        "school_city": "某市",
        "school_province": "测试省",
        "school_tier": [],
        "is_public": True,
        "is_military": False,
        "is_police": False,
        "major_groups": [
            {
                "group_code": "01",
                "group_name": "第1组",
                "subject_requirement_raw": "不限",
                "majors": majors,
            }
        ],
    }


def _make_major(name: str, code: str = "001") -> dict:
    return {
        "major_code": code,
        "major_name": name,
        "major_category": None,
        "yearly_admission_data": [],
        "single_subject_requirement": None,
        "gender_limit": None,
        "physical_requirement_notes": [],
    }


def _make_ranks(entries: list[tuple]) -> dict:
    """entries: [(school_name, major_name, min_rank)]"""
    result = {}
    for school, major, rank in entries:
        result[(school, major)] = [
            {"year": 2024, "min_rank": rank, "min_score": "600", "data_year": 2024}
        ]
    return result


# ── validate_admission_plan 测试 ─────────────────────────────────────────────

class TestValidateAdmissionPlanFatal(unittest.TestCase):

    def test_empty_schools_raises(self):
        plan = _make_plan([])
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_admission_plan(plan, 2026)
        self.assertIn("DATA_INTEGRITY_VIOLATED", ctx.exception.error_code)
        self.assertIn("schools", ctx.exception.message)

    def test_no_majors_raises(self):
        school = _make_school("测试大学", [])
        plan = _make_plan([school])
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_admission_plan(plan, 2026)
        self.assertIn("专业数为 0", ctx.exception.message)

    def test_year_like_major_names_raises(self):
        """超过 20% 专业名称为纯数字（年份格式）→ 致命"""
        majors = [_make_major("2024", str(i)) for i in range(25)]
        majors += [_make_major("计算机科学与技术", str(i + 100)) for i in range(75)]
        school = _make_school("某大学", majors)
        plan = _make_plan([school])
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_admission_plan(plan, 2026)
        self.assertIn("纯数字", ctx.exception.message)

    def test_empty_major_names_raises(self):
        """超过 20% 专业名称为空 → 致命"""
        majors = [_make_major("", str(i)) for i in range(25)]
        majors += [_make_major("经济学", str(i + 100)) for i in range(75)]
        school = _make_school("某大学", majors)
        plan = _make_plan([school])
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_admission_plan(plan, 2026)
        self.assertIn("为空", ctx.exception.message)


class TestValidateAdmissionPlanOk(unittest.TestCase):

    def test_valid_plan_returns_no_warnings(self):
        majors = [_make_major(f"专业{i}") for i in range(10)]
        school = _make_school("某大学", majors)
        plan = _make_plan([school])
        warnings = validate_admission_plan(plan, 2026)
        self.assertEqual(warnings, [])

    def test_few_empty_names_are_warning_not_fatal(self):
        """少量（≤ 20%）空名称 → warning，不报错"""
        majors = [_make_major("", str(i)) for i in range(2)]  # 2/12 ≈ 17%
        majors += [_make_major(f"专业{i}", str(i + 10)) for i in range(10)]
        school = _make_school("某大学", majors)
        plan = _make_plan([school])
        warnings = validate_admission_plan(plan, 2026)
        self.assertTrue(any("为空" in w for w in warnings))

    def test_borderline_year_like_below_threshold_passes(self):
        """恰好 20% 年份格式 → 不超过阈值（>0.20），不报错"""
        majors = [_make_major("2024", str(i)) for i in range(20)]
        majors += [_make_major(f"专业{i}", str(i + 100)) for i in range(80)]
        school = _make_school("某大学", majors)
        plan = _make_plan([school])
        # 20/100 = 20%，阈值是 > 0.20，恰好不触发致命
        result = validate_admission_plan(plan, 2026)
        # 应该只有 warning
        self.assertIsInstance(result, list)


# ── validate_historical_ranks 测试 ───────────────────────────────────────────

class TestValidateHistoricalRanksFatal(unittest.TestCase):

    def test_year_like_major_name_raises(self):
        """超过 10% 专业名是年份格式 → 致命，捕获列对调 bug"""
        entries = [(f"大学{i}", "2024", 10000) for i in range(20)]
        entries += [(f"大学{i}", "计算机科学", 8000) for i in range(80)]
        ranks = _make_ranks(entries)
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_historical_ranks(ranks, "山东", 2024)
        err = ctx.exception
        self.assertIn("纯数字", err.message)
        # 应告知如何修复
        self.assertIn("重新运行", err.user_action)
        # detail 里应包含示例
        self.assertIn("examples", err.detail)

    def test_empty_major_name_raises(self):
        """超过 20% 专业名为空 → 致命"""
        entries = [(f"大学{i}", "", 10000) for i in range(25)]
        entries += [(f"大学{i}", "经济学", 8000) for i in range(75)]
        ranks = _make_ranks(entries)
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_historical_ranks(ranks, "山东", 2024)
        self.assertIn("为空", ctx.exception.message)

    def test_zero_rank_raises(self):
        """超过 30% 的 min_rank 为 0 → 致命"""
        entries = [(f"大学{i}", "计算机", 0) for i in range(40)]
        entries += [(f"大学{i}", "经济学", 8000) for i in range(60)]
        ranks = _make_ranks(entries)
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_historical_ranks(ranks, "山东", 2024)
        self.assertIn("min_rank 为 0", ctx.exception.message)


class TestValidateHistoricalRanksOk(unittest.TestCase):

    def test_empty_ranks_returns_no_warnings(self):
        result = validate_historical_ranks({}, "山东", 2024)
        self.assertEqual(result, [])

    def test_valid_ranks_returns_no_warnings(self):
        entries = [(f"大学{i}", f"专业{i}", 10000 + i * 100) for i in range(50)]
        ranks = _make_ranks(entries)
        warnings = validate_historical_ranks(ranks, "山东", 2024)
        self.assertEqual(warnings, [])

    def test_few_year_like_below_threshold_passes(self):
        """恰好 10% 年份格式 → 不超过阈值，不报错"""
        entries = [(f"大学{i}", "2024", 10000) for i in range(10)]
        entries += [(f"大学{i}", f"专业{i}", 8000) for i in range(90)]
        ranks = _make_ranks(entries)
        result = validate_historical_ranks(ranks, "山东", 2024)
        self.assertIsInstance(result, list)


# ── validate_score_rank_table 测试 ───────────────────────────────────────────

def _make_score_table(scores: list[int]) -> dict:
    return {str(s): {"score_range": str(s), "total": {"current": "100", "cumulative": "1000"}}
            for s in scores}


class TestValidateScoreRankTableFatal(unittest.TestCase):

    def test_too_few_records_raises(self):
        table = _make_score_table(range(700, 720))  # 只有 20 条
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_score_rank_table(table, "山东", 2024)
        self.assertIn("过少", ctx.exception.message)

    def test_out_of_range_scores_raises(self):
        """超过 30% 分数超出 [100, 750] → 致命"""
        valid = {str(s): {} for s in range(400, 440)}   # 40 条正常
        bad = {str(s): {} for s in range(800, 820)}      # 20 条超范围（33%）
        table = {**valid, **bad}
        with self.assertRaises(DataIntegrityViolatedError) as ctx:
            validate_score_rank_table(table, "山东", 2024)
        self.assertIn("区间", ctx.exception.message)


class TestValidateScoreRankTableOk(unittest.TestCase):

    def test_empty_table_returns_no_warnings(self):
        result = validate_score_rank_table({}, "山东", 2024)
        self.assertEqual(result, [])

    def test_valid_table_passes(self):
        table = _make_score_table(range(200, 700))  # 500 条，分数 200-699
        warnings = validate_score_rank_table(table, "山东", 2024)
        self.assertEqual(warnings, [])

    def test_few_out_of_range_is_warning_not_fatal(self):
        """少量超范围（≤ 30%）→ warning，不报错"""
        valid = {str(s): {} for s in range(400, 490)}   # 90 条正常
        bad = {str(s): {} for s in range(800, 810)}      # 10 条超范围（10%）
        table = {**valid, **bad}
        warnings = validate_score_rank_table(table, "山东", 2024)
        self.assertTrue(any("超出" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
