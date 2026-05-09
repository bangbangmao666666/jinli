"""major-evaluator: 专业评估模块 专业深度评估 skill。

公开接口：
  run(data, mode=None) -> dict
    - data: 硬约束过滤模块 输出的 dict（流水线模式）
            或 {"major_name": ..., "school_name": ..., "applicant_profile": ...}（查询模式）
    - mode: "pipeline" | "single" | "school_major" | None（自动推断）
    - 返回：标准化评估结果 dict，status 为 "success" 或 "error"

v1.1 变更：
  - 新增维度五（考生意愿匹配）的信息采集与传递
  - 流水线模式输出 applicant_info_available 扩展意愿字段
  - 意愿信息缺失时生成对应 global_warnings

Python 层只负责输入校验与输出结构化。
五维评估逻辑由 Trae Solo AI 依据 SKILL.md 框架执行。
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from .errors import EvaluatorError, runtime_unexpected
from .input_validator import (
    summarize_willingness_availability,
    validate_applicant_scores,
    validate_pipeline_input,
    validate_search_findings,
    validate_single_input,
    validate_willingness_info,
)
from .output_formatter import format_batch_result, format_evaluation_card, make_unrated_card


def run(
    data: Dict[str, Any],
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """skill 主入口。

    自动判断运行模式（如未显式指定）：
      - data 含 "eligible_pool" → 流水线模式
      - data 含 "major_name"   → 单专业/学校+专业查询模式
    """
    try:
        return _run_inner(data, mode)
    except EvaluatorError as exc:
        return exc.to_response()
    except Exception as exc:  # noqa: BLE001
        return runtime_unexpected(exc)


def _run_inner(data: Dict[str, Any], mode: Optional[str]) -> Dict[str, Any]:
    # findings 验证模式：模块 提交搜索提取结果，校验是否满足评估需要
    if "findings" in data:
        return _run_validate_findings(data["findings"])

    # 自动推断模式
    if mode is None:
        if "eligible_pool" in data:
            mode = "pipeline"
        elif "major_name" in data:
            mode = "school_major" if data.get("school_name") else "single"
        else:
            from .errors import input_upstream_format_error
            raise input_upstream_format_error(
                "无法推断运行模式：输入既不含 'eligible_pool'，也不含 'major_name'。"
            )

    if mode == "pipeline":
        return _run_pipeline(data)
    else:
        return _run_single(data, mode)


def _run_validate_findings(findings: Dict[str, Any]) -> Dict[str, Any]:
    """findings 验证模式：模块 完成 WebFetch 提取后，提交结果校验数据完整性。

    如存在缺口，返回 data_gaps 让 模块 补全；否则返回 ready_to_evaluate 继续评估。
    """
    result = validate_search_findings(findings)

    if result["has_gaps"]:
        critical_gaps = [g for g in result["gaps"] if g["severity"] == "critical"]
        return {
            "status": "data_gaps",
            "coverage_summary": result["coverage_summary"],
            "gaps": result["gaps"],
            "has_critical_gaps": bool(critical_gaps),
            "instructions": (
                "搜索提取结果存在数据缺口，请按 gaps 列表中的 suggested_action 重新获取缺失字段。"
                "critical 级别的缺口必须补全后再评估；optional 级别可在补全后或标注'数据不足'后继续。"
                "补全后请再次提交 findings 校验。最多重试 2 次，超过后以现有数据继续评估。"
            ),
        }

    return {
        "status": "ready_to_evaluate",
        "coverage_summary": result["coverage_summary"],
        "findings": findings,
        "instructions": (
            "数据完整性校验通过，请依据 SKILL.md 的五维评估框架执行评估。"
            "每个维度的结论必须引用 findings 中对应字段的 value 和 raw_text，不得使用训练知识补全。"
        ),
    }


def _run_pipeline(data: Dict[str, Any]) -> Dict[str, Any]:
    """流水线模式：处理 硬约束过滤模块 的完整输出。"""
    unique_majors, applicant_profile = validate_pipeline_input(data)
    warnings = validate_applicant_scores(applicant_profile)

    # v1.1：校验意愿信息字段
    willingness_warnings = validate_willingness_info(applicant_profile)
    warnings.extend(willingness_warnings)

    # 硬件信息可用性
    hardware_available = {
        "math_score": applicant_profile.get("math_score") is not None,
        "physics_score": applicant_profile.get("physics_score") is not None,
        "system_preference": applicant_profile.get("system_preference") is not None,
        "preferred_region": applicant_profile.get("preferred_region") is not None,
    }

    # v1.1：意愿信息可用性
    willingness_available = summarize_willingness_availability(applicant_profile)

    # 合并 applicant_info_available
    applicant_info_available = {**hardware_available, **willingness_available}

    # 缺失提示
    if not hardware_available["math_score"] and not hardware_available["physics_score"]:
        warnings.append("考生未提供单科成绩，涉及数理基础的适配检查将跳过。")
    if not hardware_available["system_preference"]:
        warnings.append("考生未提供体制内外偏好，体制偏好适配检查将跳过。")

    # v1.1：意愿信息缺失汇总
    missing_willingness = [
        k for k, v in willingness_available.items()
        if k != "interest_source" and not v
    ]
    if missing_willingness:
        warnings.append(
            f"⚠️ 考生意愿信息中有 {len(missing_willingness)} 个字段未提供"
            f"（{', '.join(missing_willingness)}），维度五的部分子项标注为'待补充'。"
        )

    # 统计排斥方向影响的专业（排斥列表非空时给出提醒）
    rejections = applicant_profile.get("explicit_rejections") or []
    if rejections:
        warnings.append(
            f"⚠️ 考生明确排斥以下方向：{rejections}，"
            "涉及相关专业的红绿灯将按规则降级，请 AI 在评估时特别注意。"
        )

    # 家长与考生分歧提醒
    consensus = applicant_profile.get("parent_child_consensus")
    if isinstance(consensus, dict) and consensus.get("status") == "有分歧":
        warnings.append(
            "⚠️ 家长与考生在专业方向上存在分歧，相关专业的评估卡已标记冲突风险。"
        )

    input_summary = {
        "total_majors_in_pool": sum(
            len(m.get("majors", []))
            for school in data.get("eligible_pool", [])
            for m in school.get("major_groups", [])
        ),
        "unique_majors_after_dedup": len(unique_majors),
        "applicant_info_available": applicant_info_available,
    }

    # 注意：实际评估由 Trae Solo AI 依据 SKILL.md 执行。
    return {
        "status": "pending_evaluation",
        "mode": "pipeline",
        "input_summary": input_summary,
        "majors_to_evaluate": unique_majors,
        "applicant_profile": applicant_profile,
        "warnings": warnings,
        "instructions": (
            "请依据 SKILL.md 的五维评估框架，对 majors_to_evaluate 中的每个专业执行评估。"
            "维度1-4执行 S1-S4 四条定向搜索；"
            "维度5（考生意愿匹配）依据 applicant_profile 中的意愿信息执行，"
            "兴趣必须经过维度四名称陷阱校验后才能采信，考生明确排斥的方向红绿灯必须降级。"
            "完成所有专业评估后，调用 format_batch_result 输出标准化结果。"
        ),
    }


def _run_single(data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """单专业/学校+专业查询模式。"""
    major_name, school_name, applicant_profile = validate_single_input(data)
    warnings = validate_applicant_scores(applicant_profile)

    # v1.1：校验意愿信息字段
    willingness_warnings = validate_willingness_info(applicant_profile)
    warnings.extend(willingness_warnings)

    search_mode = "school_major" if school_name else "single"

    # v1.1：意愿信息缺失说明
    willingness_available = summarize_willingness_availability(applicant_profile)
    missing_willingness = [
        k for k, v in willingness_available.items()
        if k != "interest_source" and not v
    ]
    if missing_willingness:
        warnings.append(
            f"⚠️ 考生意愿信息中有 {len(missing_willingness)} 个字段未提供，"
            "维度五的部分子项将标注为'待补充'，红绿灯将注明'未经考生意愿校验'。"
        )

    return {
        "status": "pending_evaluation",
        "mode": search_mode,
        "major_name": major_name,
        "school_name": school_name,
        "applicant_profile": applicant_profile,
        "warnings": warnings,
        "instructions": (
            f"请依据 SKILL.md 的五维评估框架，对专业「{major_name}」执行评估。"
            + (f"需同时搜索「{school_name}」该专业的具体情况（S5 搜索）。" if school_name else "")
            + "维度1-4执行 S1-S4 定向搜索；"
            + "维度5（考生意愿匹配）依据 applicant_profile 中的意愿信息执行，"
            + "兴趣必须先过维度四名称陷阱校验，考生明确排斥则红绿灯必须降级。"
        ),
    }
