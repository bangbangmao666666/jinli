"""评估输出格式化与校验。

职责：
  1. 校验 AI 产出的评估结果是否满足 output_schema 的必填字段要求
  2. 补全 evaluation_metadata（时间戳、版本号）
  3. 规范化字段值（如红绿灯 emoji、data_coverage 枚举值）
  4. 序列化为标准 JSON 字典（不做 dumps，由调用方决定是否序列化）

v1.1 变更：
  - 版本号升至 v1.1
  - 新增维度五 dimension_5_applicant_fit 的校验
  - traffic_light_reasons 同时接受字符串列表和对象列表
  - 新增 traffic_light_willingness_note 字段处理
  - make_unrated_card 增加 dimension_5 占位结构
  - format_batch_result 扩展 applicant_info_available 字段
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from .errors import runtime_output_schema_violation

# ---------- 常量 ----------

EVALUATOR_VERSION = "major-evaluator-skill-v1.1"

VALID_TRAFFIC_LIGHTS = {"🟢绿灯", "🟡黄灯", "🔴红灯", "⚪未评估"}
VALID_DATA_COVERAGE = {"full", "partial", "none"}
VALID_WIDTH_RATINGS = {"宽口径", "中等", "窄口径", "unknown"}
VALID_REGIONAL_STRENGTHS = {"强", "中", "弱", "unknown"}
VALID_SYSTEM_ARENAS = {"体制内为主", "体制外为主", "均衡", "unknown"}
VALID_MODES = {"pipeline", "single", "school_major"}

# v1.1 新增：维度五整体评级合法值
VALID_OVERALL_FIT_RATINGS = {"高度匹配", "基本匹配", "勉强匹配", "不匹配", "待补充"}

# ---------- 公开接口 ----------


def format_evaluation_card(
    card: Dict[str, Any],
    mode: str = "single",
) -> Dict[str, Any]:
    """校验并补全单张评估卡。

    Args:
        card: AI 产出的评估卡 dict
        mode: 触发模式（pipeline / single / school_major）

    Returns:
        规范化后的评估卡 dict

    Raises:
        EvaluatorError: 必填字段缺失或枚举值非法
    """
    _require_str(card, "major_name")
    _require_str(card, "traffic_light")

    # 红绿灯枚举校验
    tl = card["traffic_light"]
    if tl not in VALID_TRAFFIC_LIGHTS:
        raise runtime_output_schema_violation(
            "traffic_light",
            f"值 '{tl}' 不在合法枚举范围内：{VALID_TRAFFIC_LIGHTS}",
        )

    # traffic_light_reasons 必须是非空列表（接受字符串或对象列表）
    reasons = card.get("traffic_light_reasons")
    if not isinstance(reasons, list) or len(reasons) == 0:
        raise runtime_output_schema_violation(
            "traffic_light_reasons",
            "必须是非空数组（即使是⚪未评估，也需要说明原因）",
        )

    # data_coverage 枚举校验（可选字段）
    if "data_coverage" in card:
        dc = card["data_coverage"]
        if dc not in VALID_DATA_COVERAGE:
            raise runtime_output_schema_violation(
                "data_coverage",
                f"值 '{dc}' 不在合法枚举范围内：{VALID_DATA_COVERAGE}",
            )

    # 维度字段枚举校验（宽容模式：字段不存在则跳过）
    _check_dim_enum(card, "dimension_1_width", "rating", VALID_WIDTH_RATINGS)
    _check_dim_enum(card, "dimension_2_system_orientation", "primary_arena", VALID_SYSTEM_ARENAS)
    _check_dim_enum(card, "dimension_3_regional_dependency", "strength", VALID_REGIONAL_STRENGTHS)

    # v1.1 维度五校验（可选，字段存在时才校验）
    _validate_dimension_5(card)

    # 黄灯必须有 traffic_light_prerequisites（告知前提条件）
    if tl == "🟡黄灯":
        prereqs = card.get("traffic_light_prerequisites")
        if not isinstance(prereqs, list) or len(prereqs) == 0:
            # 警告级别，不抛错
            card.setdefault("_warnings", []).append(
                "⚠️ 黄灯专业应附带 'traffic_light_prerequisites' 字段，说明转绿灯的前提条件。"
            )

    # v1.1：如维度五未执行或全为待补充，补全 traffic_light_willingness_note
    _fill_willingness_note(card)

    # 补全 evaluation_metadata
    card["evaluation_metadata"] = {
        "evaluated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "evaluator": EVALUATOR_VERSION,
        "mode": mode if mode in VALID_MODES else "single",
    }

    return card


def format_batch_result(
    evaluations: List[Dict[str, Any]],
    input_summary: Dict[str, Any],
    global_warnings: Optional[List[str]] = None,
    urgent_todos: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """构建批量评估的完整输出结构（流水线模式）。

    Args:
        evaluations: 已格式化的单张评估卡列表
        input_summary: 输入摘要（专业数量、考生信息完整度等）
        global_warnings: 全局警告（非致命）
        urgent_todos: 需要考生重点关注的紧急事项

    Returns:
        完整的批量输出 dict
    """
    # 统计红绿灯分布
    tl_counts: Dict[str, int] = {"🟢绿灯": 0, "🟡黄灯": 0, "🔴红灯": 0, "⚪未评估": 0}
    for card in evaluations:
        tl = card.get("traffic_light", "⚪未评估")
        if tl in tl_counts:
            tl_counts[tl] += 1

    # 统计数据覆盖率
    full = sum(1 for c in evaluations if c.get("data_coverage") == "full")
    partial = sum(1 for c in evaluations if c.get("data_coverage") == "partial")
    no_cov = sum(1 for c in evaluations if c.get("data_coverage") == "none")

    return {
        "status": "success",
        "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "evaluator": EVALUATOR_VERSION,
        "input_summary": input_summary,
        "coverage_stats": {
            "full_coverage": full,
            "partial_coverage": partial,
            "no_coverage": no_cov,
            "coverage_rate": _coverage_rate(full, len(evaluations)),
        },
        "evaluations": evaluations,
        "traffic_light_summary": {
            "green": tl_counts["🟢绿灯"],
            "yellow": tl_counts["🟡黄灯"],
            "red": tl_counts["🔴红灯"],
            "unrated": tl_counts["⚪未评估"],
        },
        "global_warnings": global_warnings or [],
        "urgent_todos": urgent_todos or [],
    }


def make_unrated_card(major_name: str, major_code: str = "", reason: str = "") -> Dict[str, Any]:
    """为搜索失败或数据不足的专业生成一张空评估卡（⚪未评估）。"""
    default_reason = reason or (
        "搜索结果不足以支撑可靠评估。建议考生自行查阅："
        "1）教育部阳光高考平台该专业介绍；"
        "2）目标院校的培养方案；"
        "3）该专业近年就业质量报告。"
    )
    return {
        "major_name": major_name,
        "major_code": major_code,
        "data_coverage": "none",
        "search_quality": "insufficient",
        "dimension_1_width": {"rating": "unknown", "description": "数据不足，无法评估"},
        "dimension_2_system_orientation": {"primary_arena": "unknown", "description": "数据不足，无法评估"},
        "dimension_3_regional_dependency": {"strength": "unknown", "description": "数据不足，无法评估"},
        "dimension_4_name_trap": {"has_trap": "unknown", "description": "数据不足，无法评估"},
        # v1.1：维度五占位结构
        "dimension_5_applicant_fit": {
            "executed": False,
            "data_completeness": "none",
            "missing_fields": ["all"],
            "overall_fit_rating": "待补充",
        },
        "traffic_light": "⚪未评估",
        "traffic_light_reasons": [default_reason],
        "traffic_light_willingness_note": (
            "⚠️ 未经考生意愿校验，建议与考生沟通确认后再做最终决策。"
        ),
        "pitfall_summary": [],
        "evaluation_metadata": {
            "evaluated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "evaluator": EVALUATOR_VERSION,
            "mode": "pipeline",
        },
    }


# ---------- 内部工具 ----------

def _require_str(card: Dict[str, Any], field: str) -> None:
    value = card.get(field)
    if not isinstance(value, str) or not value.strip():
        raise runtime_output_schema_violation(field, "缺失或为空字符串")


def _check_dim_enum(
    card: Dict[str, Any],
    dim_key: str,
    sub_key: str,
    valid_set: set,
) -> None:
    dim = card.get(dim_key)
    if not isinstance(dim, dict):
        return  # 字段不存在，跳过
    value = dim.get(sub_key)
    if value is not None and value not in valid_set:
        raise runtime_output_schema_violation(
            f"{dim_key}.{sub_key}",
            f"值 '{value}' 不在合法枚举范围内：{valid_set}",
        )


def _validate_dimension_5(card: Dict[str, Any]) -> None:
    """校验维度五 dimension_5_applicant_fit（可选字段，存在时才校验）。"""
    dim5 = card.get("dimension_5_applicant_fit")
    if dim5 is None:
        return
    if not isinstance(dim5, dict):
        raise runtime_output_schema_violation(
            "dimension_5_applicant_fit",
            "必须是 JSON 对象",
        )
    # overall_fit_rating 如存在则校验枚举
    fit_rating = dim5.get("overall_fit_rating")
    if fit_rating is not None and fit_rating not in VALID_OVERALL_FIT_RATINGS:
        raise runtime_output_schema_violation(
            "dimension_5_applicant_fit.overall_fit_rating",
            f"值 '{fit_rating}' 不在合法枚举范围内：{VALID_OVERALL_FIT_RATINGS}",
        )
    # fit_adjustment_to_traffic_light 如存在则记录（不校验枚举，由 AI 自由填写）


def _fill_willingness_note(card: Dict[str, Any]) -> None:
    """如维度五未执行或全部待补充，自动填充 traffic_light_willingness_note。"""
    # 如果卡片中已经显式提供了 note，尊重 AI 的填写
    if "traffic_light_willingness_note" in card:
        return

    dim5 = card.get("dimension_5_applicant_fit")
    if dim5 is None:
        # 没有维度五字段
        card["traffic_light_willingness_note"] = (
            "⚠️ 未经考生意愿校验（意愿信息未提供），建议与考生沟通确认后再做最终决策。"
        )
        return

    executed = dim5.get("executed", True)
    overall = dim5.get("overall_fit_rating", "")
    if not executed or overall == "待补充":
        card["traffic_light_willingness_note"] = (
            "⚠️ 未经考生意愿校验（意愿信息未提供），建议与考生沟通确认后再做最终决策。"
        )
    else:
        card["traffic_light_willingness_note"] = None


def _coverage_rate(full: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{full / total * 100:.1f}%"
