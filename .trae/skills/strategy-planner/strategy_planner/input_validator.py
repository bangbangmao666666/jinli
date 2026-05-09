"""输入校验。

PRD §2.4：检查必填字段完整性，缺失必填字段直接抛出异常。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .errors import (
    InputUpstreamEmptyError,
    MissingRequiredFieldError,
    InvalidFieldValueError,
)

REQUIRED_PIPELINE_FIELDS = [
    "applicant_profile",
    "recommended_schools",
]

# 这两个字段缺失时降级为 warning（如从 MD 解析时 专业评估模块 数据不可用）
OPTIONAL_PIPELINE_FIELDS = [
    "passed_majors",
    "eligible_pool",
]

REQUIRED_APPLICANT_FIELDS = [
    "province",
    "total_score",
    "provincial_rank",
]

RISK_PREFERENCE_OPTIONS = {"保守型", "适中型", "激进型"}
ACCEPT_ADJUSTMENT_OPTIONS = {"是", "否", "仅接受干净组调剂"}


def validate(input_data: Dict[str, Any]) -> List[str]:
    """执行输入校验，返回非致命的 warnings 列表。

    致命错误直接抛异常；非致命通过返回列表透传。
    """
    warnings: List[str] = []

    # 1. 检查上游输入是否为空
    if not input_data:
        raise InputUpstreamEmptyError(
            "上游输入为空",
            user_action="请提供完整的输入数据。",
        )

    # 2. 检查流水线必填字段
    missing_pipeline = [
        f for f in REQUIRED_PIPELINE_FIELDS
        if f not in input_data or input_data[f] in (None, "", [])
    ]
    if missing_pipeline:
        raise MissingRequiredFieldError(
            f"流水线必填字段缺失：{', '.join(missing_pipeline)}",
            user_action="请确保上游 模块 正常输出完整数据。",
            detail={"missing_fields": missing_pipeline},
        )

    # 2b. 可选字段为空时降级为 warning（如 MD 解析模式下 专业评估模块 数据不可用）
    for f in OPTIONAL_PIPELINE_FIELDS:
        if f not in input_data or input_data[f] in (None, "", []):
            warnings.append(
                f"⚠️ 上游字段 {f} 为空，相关功能将降级：passed_majors 为空则跳过专业组干净度检查；"
                "eligible_pool 为空则滑档预案无备选院校"
            )

    # 3. 检查考生信息必填字段
    applicant = input_data["applicant_profile"]
    missing_applicant = [
        f for f in REQUIRED_APPLICANT_FIELDS 
        if f not in applicant or applicant[f] in (None, "", [])
    ]
    if missing_applicant:
        raise MissingRequiredFieldError(
            f"考生信息必填字段缺失：{', '.join(missing_applicant)}",
            user_action="请补全考生省份、总分、位次信息。",
            detail={"missing_fields": missing_applicant},
        )

    # 4. 校验推荐院校数量
    recommended = input_data["recommended_schools"]
    if not recommended or len(recommended) == 0:
        raise InputUpstreamEmptyError(
            "推荐院校清单为空",
            user_action="请确保 院校匹配模块 正常输出推荐院校数据。",
        )

    # 5. 校验可选字段值（如果有）
    if "risk_preference" in input_data and input_data["risk_preference"]:
        if input_data["risk_preference"] not in RISK_PREFERENCE_OPTIONS:
            raise InvalidFieldValueError(
                f"risk_preference 必须是保守型/适中型/激进型之一，实际: {input_data['risk_preference']!r}",
                user_action="请使用：保守型 / 适中型 / 激进型 之一。",
                detail={"field": "risk_preference", "value": input_data["risk_preference"]},
            )

    if "accept_adjustment" in input_data and input_data["accept_adjustment"]:
        if input_data["accept_adjustment"] not in ACCEPT_ADJUSTMENT_OPTIONS:
            raise InvalidFieldValueError(
                f"accept_adjustment 必须是是/否/仅接受干净组调剂之一，实际: {input_data['accept_adjustment']!r}",
                user_action="请使用：是 / 否 / 仅接受干净组调剂 之一。",
                detail={"field": "accept_adjustment", "value": input_data["accept_adjustment"]},
            )

    # 6. 检查可填报基本盘是否足够
    eligible = input_data["eligible_pool"]
    if not eligible or len(eligible) < 10:
        warnings.append(
            f"可填报基本盘数量较少（仅 {len(eligible)} 个），可能影响兜底志愿不足。"
        )

    return warnings
