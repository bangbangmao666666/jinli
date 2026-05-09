"""输入校验器单元测试（v1.1）。

运行方式：
    cd .trae/skills/major-evaluator
    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from major_evaluator.errors import EvaluatorError
from major_evaluator.input_validator import (
    summarize_willingness_availability,
    validate_applicant_scores,
    validate_pipeline_input,
    validate_search_findings,
    validate_single_input,
    validate_willingness_info,
)


# ---------- 流水线模式 ----------

class TestValidatePipelineInput(unittest.TestCase):

    def _make_pool(self, majors=None):
        """构造最小合法的 硬约束过滤模块 输出。"""
        if majors is None:
            majors = [{"major_code": "080601", "major_name": "电气工程及其自动化"}]
        return {
            "status": "success",
            "eligible_pool": [
                {
                    "school_name": "郑州大学",
                    "school_code": "10459",
                    "major_groups": [
                        {
                            "group_code": "01",
                            "majors": majors,
                        }
                    ],
                }
            ],
            "applicant_profile": {
                "province": "河南",
                "total_score": 580,
                "provincial_rank": 45000,
            },
        }

    def test_valid_input_returns_unique_majors(self):
        data = self._make_pool()
        majors, profile = validate_pipeline_input(data)
        self.assertEqual(len(majors), 1)
        self.assertEqual(majors[0]["major_name"], "电气工程及其自动化")

    def test_deduplication(self):
        """同一专业出现在多个院校，去重后只保留一个。"""
        major = {"major_code": "080601", "major_name": "电气工程及其自动化"}
        data = {
            "status": "success",
            "eligible_pool": [
                {
                    "school_name": "郑州大学",
                    "major_groups": [{"majors": [major]}],
                },
                {
                    "school_name": "河南理工大学",
                    "major_groups": [{"majors": [major]}],
                },
            ],
            "applicant_profile": {},
        }
        majors, _ = validate_pipeline_input(data)
        self.assertEqual(len(majors), 1)

    def test_status_not_success_raises(self):
        data = {"status": "error", "eligible_pool": []}
        with self.assertRaises(EvaluatorError) as ctx:
            validate_pipeline_input(data)
        self.assertEqual(ctx.exception.code, "INPUT_UPSTREAM_FORMAT_ERROR")

    def test_missing_eligible_pool_raises(self):
        data = {"status": "success"}
        with self.assertRaises(EvaluatorError) as ctx:
            validate_pipeline_input(data)
        self.assertEqual(ctx.exception.code, "INPUT_UPSTREAM_FORMAT_ERROR")

    def test_empty_pool_raises(self):
        data = {"status": "success", "eligible_pool": []}
        with self.assertRaises(EvaluatorError) as ctx:
            validate_pipeline_input(data)
        self.assertEqual(ctx.exception.code, "INPUT_EMPTY_POOL")

    def test_pool_with_no_majors_raises(self):
        """eligible_pool 非空但所有专业列表均为空。"""
        data = {
            "status": "success",
            "eligible_pool": [
                {"school_name": "XX大学", "major_groups": [{"majors": []}]}
            ],
            "applicant_profile": {},
        }
        with self.assertRaises(EvaluatorError) as ctx:
            validate_pipeline_input(data)
        self.assertEqual(ctx.exception.code, "INPUT_EMPTY_POOL")

    def test_non_dict_input_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_pipeline_input("not a dict")
        self.assertEqual(ctx.exception.code, "INPUT_UPSTREAM_FORMAT_ERROR")


# ---------- 单专业查询模式 ----------

class TestValidateSingleInput(unittest.TestCase):

    def test_valid_major_only(self):
        data = {"major_name": "计算机科学与技术"}
        major_name, school_name, profile = validate_single_input(data)
        self.assertEqual(major_name, "计算机科学与技术")
        self.assertEqual(school_name, "")

    def test_valid_school_and_major(self):
        data = {"major_name": "法学", "school_name": "郑州大学"}
        major_name, school_name, _ = validate_single_input(data)
        self.assertEqual(major_name, "法学")
        self.assertEqual(school_name, "郑州大学")

    def test_missing_major_name_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_single_input({"school_name": "郑州大学"})
        self.assertEqual(ctx.exception.code, "INPUT_MISSING_REQUIRED_FIELD")

    def test_empty_major_name_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_single_input({"major_name": "  "})
        self.assertEqual(ctx.exception.code, "INPUT_MISSING_REQUIRED_FIELD")


# ---------- 分数校验 ----------

class TestValidateApplicantScores(unittest.TestCase):

    def test_valid_scores(self):
        profile = {"math_score": 125, "physics_score": 88}
        warnings = validate_applicant_scores(profile)
        self.assertEqual(warnings, [])

    def test_boundary_scores(self):
        """边界值：0 和 150 均合法。"""
        profile = {"math_score": 0, "physics_score": 150}
        warnings = validate_applicant_scores(profile)
        self.assertEqual(warnings, [])

    def test_negative_score_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_applicant_scores({"math_score": -1})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_SCORE")

    def test_over_max_score_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_applicant_scores({"physics_score": 200})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_SCORE")

    def test_non_numeric_score_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_applicant_scores({"math_score": "很高"})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_SCORE")

    def test_missing_scores_no_error(self):
        """未提供分数：不报错，不报警。"""
        profile = {"system_preference": "体制内"}
        warnings = validate_applicant_scores(profile)
        self.assertEqual(warnings, [])

    def test_invalid_system_preference_warns(self):
        """非法的体制偏好值：产生 warning，不抛错。"""
        profile = {"system_preference": "不知道"}
        warnings = validate_applicant_scores(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("system_preference", warnings[0])


# ---------- v1.1 意愿信息校验 ----------

class TestValidateWillingnessInfo(unittest.TestCase):

    def test_empty_profile_no_warnings(self):
        """空 profile：意愿字段全部缺失，但不报错也不报警。"""
        warnings = validate_willingness_info({})
        self.assertEqual(warnings, [])

    def test_valid_interest_directions(self):
        profile = {"interest_directions": ["电力系统", "稳定工作"]}
        warnings = validate_willingness_info(profile)
        self.assertEqual(warnings, [])

    def test_valid_explicit_rejections(self):
        profile = {"explicit_rejections": ["医学", "化学"]}
        warnings = validate_willingness_info(profile)
        self.assertEqual(warnings, [])

    def test_interest_directions_not_list_raises(self):
        """interest_directions 传了字符串而不是数组：抛异常。"""
        with self.assertRaises(EvaluatorError) as ctx:
            validate_willingness_info({"interest_directions": "电力系统"})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_FIELD")

    def test_explicit_rejections_not_list_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_willingness_info({"explicit_rejections": "医学"})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_FIELD")

    def test_invalid_personality_tendency_warns(self):
        """非法的性格倾向值：产生 warning，不抛错。"""
        profile = {"personality_tendency": "极度外向"}
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("personality_tendency", warnings[0])

    def test_valid_personality_tendency_values(self):
        for val in ["偏稳定", "偏拼搏", "未定"]:
            warnings = validate_willingness_info({"personality_tendency": val})
            self.assertEqual(warnings, [])

    def test_invalid_family_economy_level_warns(self):
        profile = {"family_economy_level": "中产"}
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("family_economy_level", warnings[0])

    def test_valid_economy_levels(self):
        for val in ["宽裕", "普通", "紧张"]:
            warnings = validate_willingness_info({"family_economy_level": val})
            self.assertEqual(warnings, [])

    def test_family_has_industry_resources_non_bool_warns(self):
        """非布尔值：产生 warning，不抛错。"""
        profile = {"family_has_industry_resources": "有"}
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("family_has_industry_resources", warnings[0])

    def test_family_has_industry_resources_bool_valid(self):
        for val in [True, False]:
            warnings = validate_willingness_info({"family_has_industry_resources": val})
            self.assertEqual(warnings, [])

    def test_interest_source_parent_warns(self):
        """家长代述：应产生关于确认考生本人意愿的 warning。"""
        profile = {"interest_source": "家长代述"}
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("家长代述", warnings[0])

    def test_interest_source_child_no_warn(self):
        """考生本人表达：不产生 warning。"""
        profile = {"interest_source": "考生本人表达"}
        warnings = validate_willingness_info(profile)
        self.assertEqual(warnings, [])

    def test_invalid_interest_source_warns(self):
        profile = {"interest_source": "爷爷说的"}
        warnings = validate_willingness_info(profile)
        self.assertGreaterEqual(len(warnings), 1)

    def test_parent_child_consensus_not_dict_raises(self):
        """parent_child_consensus 不是对象：抛异常。"""
        with self.assertRaises(EvaluatorError) as ctx:
            validate_willingness_info({"parent_child_consensus": "有分歧"})
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_FIELD")

    def test_parent_child_consensus_valid(self):
        profile = {
            "parent_child_consensus": {
                "status": "一致",
                "notes": "家长和孩子都想学计算机"
            }
        }
        warnings = validate_willingness_info(profile)
        self.assertEqual(warnings, [])

    def test_parent_child_consensus_diverge_missing_detail_warns(self):
        """有分歧但缺少双方立场：产生 warning。"""
        profile = {
            "parent_child_consensus": {
                "status": "有分歧",
                "parent_preference": "",
                "child_preference": ""
            }
        }
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("有分歧", warnings[0])

    def test_parent_child_consensus_diverge_with_detail_no_warn(self):
        """有分歧且有双方立场：不产生 warning。"""
        profile = {
            "parent_child_consensus": {
                "status": "有分歧",
                "parent_preference": "医学",
                "child_preference": "计算机"
            }
        }
        warnings = validate_willingness_info(profile)
        self.assertEqual(warnings, [])

    def test_consensus_invalid_status_warns(self):
        """status 不在合法值中：产生 warning。"""
        profile = {"parent_child_consensus": {"status": "说不好"}}
        warnings = validate_willingness_info(profile)
        self.assertEqual(len(warnings), 1)
        self.assertIn("parent_child_consensus.status", warnings[0])


# ---------- v1.1 意愿信息可用性汇总 ----------

class TestSummarizeWillingnessAvailability(unittest.TestCase):

    def test_empty_profile_all_false(self):
        result = summarize_willingness_availability({})
        self.assertFalse(result["interest_directions"])
        self.assertFalse(result["explicit_rejections"])
        self.assertFalse(result["personality_tendency"])
        self.assertFalse(result["family_economy_level"])
        self.assertFalse(result["parent_child_consensus"])
        self.assertEqual(result["interest_source"], "未区分")

    def test_full_profile_all_true(self):
        profile = {
            "interest_directions": ["电力"],
            "explicit_rejections": ["医学"],
            "personality_tendency": "偏稳定",
            "family_economy_level": "普通",
            "family_has_industry_resources": False,
            "parent_child_consensus": {"status": "一致"},
            "interest_source": "考生本人表达",
        }
        result = summarize_willingness_availability(profile)
        self.assertTrue(result["interest_directions"])
        self.assertTrue(result["explicit_rejections"])
        self.assertTrue(result["personality_tendency"])
        self.assertTrue(result["family_economy_level"])
        self.assertTrue(result["parent_child_consensus"])
        self.assertEqual(result["interest_source"], "考生本人表达")


# ---------- validate_search_findings ----------

class TestValidateSearchFindings(unittest.TestCase):

    def _make_field(self, value, raw_text="原文片段", source_url="https://example.com"):
        return {"value": value, "raw_text": raw_text, "source_url": source_url}

    def _null_field(self):
        return {"value": None, "raw_text": None, "source_url": None}

    def _full_findings(self):
        """构造全字段有效的 findings。"""
        return {
            "s1": {
                "employment_rate": self._make_field("87%"),
                "top_industries": self._make_field(["电力系统", "新能源"]),
                "salary_range": self._make_field("6000-8000元/月"),
                "employment_quality_note": self._make_field("含灵活就业"),
            },
            "s2": {
                "civil_service_categories": self._make_field("自然资源类"),
                "degree_type": self._make_field("工学学士"),
                "state_enterprise_channels": self._make_field("国家电网定向"),
                "degree_exam_match_note": self._make_field("工学与考公要求一致"),
            },
            "s3": {
                "license_restriction": self._make_field("无排他性限制"),
                "similar_majors": self._make_field(["电子信息工程", "自动化"]),
                "license_name": self._make_field(["注册电气工程师"]),
                "discipline_category": self._make_field("工学"),
            },
            "s4": {
                "reputation_summary": self._make_field("整体口碑良好"),
                "hidden_risks": self._make_field("进不了电网差距大"),
                "supply_demand_trend": self._make_field("供需均衡"),
                "ordinary_family_reality": self._make_field("无背景可走通"),
            },
        }

    def test_full_findings_no_gaps(self):
        result = validate_search_findings(self._full_findings())
        self.assertFalse(result["has_gaps"])
        self.assertEqual(result["gaps"], [])
        for key in ["s1", "s2", "s3", "s4"]:
            self.assertEqual(result["coverage_summary"][key], "full")

    def test_missing_all_s1_critical_is_critical_gap(self):
        findings = self._full_findings()
        findings["s1"]["employment_rate"] = self._null_field()
        findings["s1"]["top_industries"] = self._null_field()
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        gap = next(g for g in result["gaps"] if g["search"] == "S1")
        self.assertEqual(gap["severity"], "critical")
        self.assertEqual(result["coverage_summary"]["s1"], "none")

    def test_missing_one_s1_critical_is_partial(self):
        findings = self._full_findings()
        findings["s1"]["employment_rate"] = self._null_field()
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        gap = next(g for g in result["gaps"] if g["search"] == "S1")
        self.assertEqual(gap["severity"], "critical")
        self.assertEqual(result["coverage_summary"]["s1"], "partial")
        self.assertIn("employment_rate", gap["missing_fields"])

    def test_missing_s2_critical_degree_type(self):
        findings = self._full_findings()
        findings["s2"]["degree_type"] = self._null_field()
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        gap = next(g for g in result["gaps"] if g["search"] == "S2")
        self.assertEqual(gap["severity"], "critical")
        self.assertIn("degree_type", gap["missing_fields"])

    def test_s4_all_null_is_optional_gap(self):
        findings = self._full_findings()
        for field in ["reputation_summary", "hidden_risks", "supply_demand_trend", "ordinary_family_reality"]:
            findings["s4"][field] = self._null_field()
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        gap = next(g for g in result["gaps"] if g["search"] == "S4")
        self.assertEqual(gap["severity"], "optional")
        self.assertEqual(result["coverage_summary"]["s4"], "none")

    def test_s4_partial_data_no_gap(self):
        """S4 有任意一个字段即视为有数据，不产生缺口。"""
        findings = self._full_findings()
        for field in ["hidden_risks", "supply_demand_trend", "ordinary_family_reality"]:
            findings["s4"][field] = self._null_field()
        result = validate_search_findings(findings)
        s4_gaps = [g for g in result["gaps"] if g["search"] == "S4"]
        self.assertEqual(s4_gaps, [])
        self.assertEqual(result["coverage_summary"]["s4"], "full")

    def test_non_dict_findings_raises(self):
        with self.assertRaises(EvaluatorError) as ctx:
            validate_search_findings("not a dict")
        self.assertEqual(ctx.exception.code, "INPUT_INVALID_FIELD")

    def test_missing_search_key_treated_as_empty(self):
        """findings 中缺少 s3 键，等同于 s3 全部字段为 null。"""
        findings = self._full_findings()
        del findings["s3"]
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        gap = next(g for g in result["gaps"] if g["search"] == "S3")
        self.assertEqual(gap["severity"], "critical")
        self.assertEqual(result["coverage_summary"]["s3"], "none")

    def test_has_critical_gaps_flag(self):
        """any critical gap → has_gaps True；gaps 列表非空。"""
        findings = self._full_findings()
        findings["s1"]["employment_rate"] = self._null_field()
        findings["s1"]["top_industries"] = self._null_field()
        result = validate_search_findings(findings)
        self.assertTrue(result["has_gaps"])
        critical = [g for g in result["gaps"] if g["severity"] == "critical"]
        self.assertTrue(len(critical) > 0)

    def test_suggested_action_present(self):
        findings = self._full_findings()
        findings["s2"]["civil_service_categories"] = self._null_field()
        findings["s2"]["degree_type"] = self._null_field()
        result = validate_search_findings(findings)
        gap = next(g for g in result["gaps"] if g["search"] == "S2")
        self.assertIn("suggested_action", gap)
        self.assertTrue(len(gap["suggested_action"]) > 0)


if __name__ == "__main__":
    unittest.main()
