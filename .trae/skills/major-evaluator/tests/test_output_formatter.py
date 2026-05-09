"""输出格式化器单元测试（v1.1）。

运行方式：
    cd .trae/skills/major-evaluator
    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from major_evaluator.errors import EvaluatorError
from major_evaluator.output_formatter import (
    EVALUATOR_VERSION,
    format_batch_result,
    format_evaluation_card,
    make_unrated_card,
)


def _minimal_card(**kwargs):
    """构造最小合法评估卡。"""
    card = {
        "major_name": "电气工程及其自动化",
        "traffic_light": "🟡黄灯",
        "traffic_light_reasons": ["进电网前景好，但必须确认学校在电网招聘名单内"],
        "traffic_light_prerequisites": ["确认目标院校在电网招聘名单内"],
    }
    card.update(kwargs)
    return card


# ---------- format_evaluation_card ----------

class TestFormatEvaluationCard(unittest.TestCase):

    def test_valid_card_adds_metadata(self):
        card = _minimal_card()
        result = format_evaluation_card(card)
        self.assertIn("evaluation_metadata", result)
        self.assertIn("evaluated_at", result["evaluation_metadata"])
        # v1.1 版本号
        self.assertEqual(result["evaluation_metadata"]["evaluator"], "major-evaluator-skill-v1.1")

    def test_version_is_v1_1(self):
        """确认版本常量已更新为 v1.1。"""
        self.assertIn("v1.1", EVALUATOR_VERSION)

    def test_missing_major_name_raises(self):
        card = _minimal_card()
        del card["major_name"]
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_missing_traffic_light_raises(self):
        card = _minimal_card()
        del card["traffic_light"]
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_invalid_traffic_light_value_raises(self):
        card = _minimal_card(traffic_light="推荐")
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_empty_reasons_raises(self):
        card = _minimal_card(traffic_light_reasons=[])
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_all_traffic_light_values_accepted(self):
        for tl in ["🟢绿灯", "🟡黄灯", "🔴红灯", "⚪未评估"]:
            card = _minimal_card(traffic_light=tl)
            result = format_evaluation_card(card)
            self.assertEqual(result["traffic_light"], tl)

    def test_invalid_data_coverage_raises(self):
        card = _minimal_card(data_coverage="unknown_value")
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_valid_data_coverage_values(self):
        for cov in ["full", "partial", "none"]:
            card = _minimal_card(data_coverage=cov)
            result = format_evaluation_card(card)
            self.assertEqual(result["data_coverage"], cov)

    def test_invalid_dimension_rating_raises(self):
        card = _minimal_card(
            dimension_1_width={"rating": "超宽", "description": "test"}
        )
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_yellow_light_without_prerequisites_adds_warning(self):
        """黄灯缺 prerequisites：不抛错，但 card 内加 warning。"""
        card = _minimal_card(traffic_light="🟡黄灯")
        del card["traffic_light_prerequisites"]
        result = format_evaluation_card(card)
        self.assertIn("_warnings", result)

    def test_mode_written_to_metadata(self):
        card = _minimal_card()
        result = format_evaluation_card(card, mode="pipeline")
        self.assertEqual(result["evaluation_metadata"]["mode"], "pipeline")

    def test_reasons_as_list_of_dicts(self):
        """v1.1：traffic_light_reasons 支持对象列表格式。"""
        reasons = [
            {"factor": "客观评价良好", "detail": "维度1-4均通过", "source": "综合维度1-4"},
            {"factor": "考生意愿匹配", "detail": "兴趣高，性格适配", "source": "dimension_5"},
        ]
        card = _minimal_card(traffic_light_reasons=reasons)
        result = format_evaluation_card(card)
        self.assertEqual(result["traffic_light_reasons"], reasons)

    def test_willingness_note_added_when_no_dimension5(self):
        """无维度五字段时，自动填充 traffic_light_willingness_note。"""
        card = _minimal_card()
        result = format_evaluation_card(card)
        self.assertIn("traffic_light_willingness_note", result)
        self.assertIsNotNone(result["traffic_light_willingness_note"])

    def test_willingness_note_null_when_dimension5_executed(self):
        """维度五已执行且非待补充时，note 为 None。"""
        card = _minimal_card(
            dimension_5_applicant_fit={
                "executed": True,
                "overall_fit_rating": "高度匹配",
                "data_completeness": "full",
            }
        )
        result = format_evaluation_card(card)
        self.assertIsNone(result["traffic_light_willingness_note"])

    def test_willingness_note_set_when_dimension5_pending(self):
        """维度五 overall_fit_rating 为待补充时，自动填充 note。"""
        card = _minimal_card(
            dimension_5_applicant_fit={
                "executed": True,
                "overall_fit_rating": "待补充",
                "data_completeness": "none",
            }
        )
        result = format_evaluation_card(card)
        self.assertIsNotNone(result["traffic_light_willingness_note"])
        self.assertIn("未经考生意愿校验", result["traffic_light_willingness_note"])

    def test_dimension5_not_dict_raises(self):
        """dimension_5_applicant_fit 不是对象：抛异常。"""
        card = _minimal_card(dimension_5_applicant_fit="高度匹配")
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_dimension5_invalid_overall_fit_rating_raises(self):
        """overall_fit_rating 不在合法枚举范围：抛异常。"""
        card = _minimal_card(
            dimension_5_applicant_fit={
                "executed": True,
                "overall_fit_rating": "超级匹配",
            }
        )
        with self.assertRaises(EvaluatorError) as ctx:
            format_evaluation_card(card)
        self.assertEqual(ctx.exception.code, "RUNTIME_OUTPUT_SCHEMA_VIOLATION")

    def test_dimension5_valid_overall_fit_ratings(self):
        """所有合法的 overall_fit_rating 枚举值应被接受。"""
        for rating in ["高度匹配", "基本匹配", "勉强匹配", "不匹配", "待补充"]:
            card = _minimal_card(
                dimension_5_applicant_fit={
                    "executed": True,
                    "overall_fit_rating": rating,
                }
            )
            result = format_evaluation_card(card)
            self.assertEqual(result["dimension_5_applicant_fit"]["overall_fit_rating"], rating)


# ---------- make_unrated_card ----------

class TestMakeUnratedCard(unittest.TestCase):

    def test_returns_unrated_traffic_light(self):
        card = make_unrated_card("基础医学", "100100")
        self.assertEqual(card["traffic_light"], "⚪未评估")

    def test_contains_major_name(self):
        card = make_unrated_card("基础医学")
        self.assertEqual(card["major_name"], "基础医学")

    def test_all_dimensions_unknown(self):
        card = make_unrated_card("基础医学")
        self.assertEqual(card["dimension_1_width"]["rating"], "unknown")
        self.assertEqual(card["dimension_2_system_orientation"]["primary_arena"], "unknown")
        self.assertEqual(card["dimension_3_regional_dependency"]["strength"], "unknown")

    def test_custom_reason(self):
        card = make_unrated_card("基础医学", reason="测试原因")
        self.assertIn("测试原因", card["traffic_light_reasons"][0])

    def test_dimension5_stub_present(self):
        """v1.1：未评估卡应包含维度五占位结构。"""
        card = make_unrated_card("基础医学")
        self.assertIn("dimension_5_applicant_fit", card)
        dim5 = card["dimension_5_applicant_fit"]
        self.assertFalse(dim5["executed"])
        self.assertEqual(dim5["overall_fit_rating"], "待补充")

    def test_willingness_note_present(self):
        """v1.1：未评估卡应有 traffic_light_willingness_note。"""
        card = make_unrated_card("基础医学")
        self.assertIn("traffic_light_willingness_note", card)
        self.assertIsNotNone(card["traffic_light_willingness_note"])

    def test_evaluator_version_is_v1_1(self):
        """v1.1：未评估卡的 evaluator 应为 v1.1。"""
        card = make_unrated_card("基础医学")
        self.assertIn("v1.1", card["evaluation_metadata"]["evaluator"])


# ---------- format_batch_result ----------

class TestFormatBatchResult(unittest.TestCase):

    def _make_cards(self):
        return [
            _minimal_card(traffic_light="🟢绿灯", data_coverage="full",
                          major_name="计算机科学与技术"),
            _minimal_card(traffic_light="🟡黄灯", data_coverage="partial",
                          major_name="电气工程及其自动化"),
            _minimal_card(traffic_light="🔴红灯", data_coverage="none",
                          major_name="机械工程"),
            make_unrated_card("基础医学"),
        ]

    def test_traffic_light_counts(self):
        cards = self._make_cards()
        result = format_batch_result(cards, input_summary={})
        summary = result["traffic_light_summary"]
        self.assertEqual(summary["green"], 1)
        self.assertEqual(summary["yellow"], 1)
        self.assertEqual(summary["red"], 1)
        self.assertEqual(summary["unrated"], 1)

    def test_coverage_stats(self):
        cards = self._make_cards()
        result = format_batch_result(cards, input_summary={})
        stats = result["coverage_stats"]
        self.assertEqual(stats["full_coverage"], 1)
        self.assertEqual(stats["partial_coverage"], 1)
        self.assertEqual(stats["no_coverage"], 2)

    def test_status_is_success(self):
        result = format_batch_result([], input_summary={})
        self.assertEqual(result["status"], "success")

    def test_global_warnings_included(self):
        result = format_batch_result(
            [], input_summary={}, global_warnings=["警告1", "警告2"]
        )
        self.assertEqual(result["global_warnings"], ["警告1", "警告2"])

    def test_empty_evaluations(self):
        result = format_batch_result([], input_summary={"unique_majors_after_dedup": 0})
        self.assertEqual(result["traffic_light_summary"]["green"], 0)
        self.assertEqual(result["coverage_stats"]["coverage_rate"], "0.0%")

    def test_evaluator_version_is_v1_1(self):
        """v1.1：批量结果的 evaluator 字段应为 v1.1。"""
        result = format_batch_result([], input_summary={})
        self.assertIn("v1.1", result["evaluator"])

    def test_input_summary_with_willingness_fields(self):
        """v1.1：input_summary 可包含意愿字段可用性信息。"""
        summary = {
            "total_majors_in_pool": 10,
            "unique_majors_after_dedup": 5,
            "applicant_info_available": {
                "math_score": True,
                "interest_directions": True,
                "explicit_rejections": False,
                "personality_tendency": True,
                "interest_source": "考生本人表达",
            }
        }
        result = format_batch_result([], input_summary=summary)
        self.assertEqual(
            result["input_summary"]["applicant_info_available"]["interest_source"],
            "考生本人表达"
        )


if __name__ == "__main__":
    unittest.main()
