
"""输入校验模块。

PRD原则：字段缺失就停下来要求用户补，不允许编造默认值。
"""
from .errors import (
    InputUpstreamEmptyError,
    InputMissingRequiredFieldError,
    InputInvalidFieldValueError,
)

# 流水线模式必填字段
PIPELINE_REQUIRED_FIELDS = [
    "eligible_pool",
    "passed_majors",
    "applicant_profile",
]

# 流水线模式可选字段
PIPELINE_OPTIONAL_FIELDS = [
    "selected_majors",  # 用户明确选择的3-5个专业名称列表
]

# 考生必填字段
APPLICANT_REQUIRED_FIELDS = [
    "province",
    "total_score",
    "provincial_rank",
]


def validate(data):
    """执行输入校验，返回非致命的warnings列表。

    致命错误直接抛异常（由上层转化为结构化error响应）；
    非致命（如数据年份警告）通过返回列表透传。
    """
    warnings = []

    # 检查是否为空数据
    if not data:
        raise InputUpstreamEmptyError(
            "输入数据为空，没有可评估的院校专业组合。",
            user_action="请确认上游模块正常执行或补充输入数据。",
        )

    # 流水线模式校验
    if "eligible_pool" in data or "passed_majors" in data:
        warnings.extend(_validate_pipeline_input(data))
    elif "major_name" in data or "school_name" in data:
        # 单校/专业查询模式
        warnings.extend(_validate_query_input(data))
    else:
        raise InputInvalidFieldValueError(
            "无法识别输入模式，请提供流水线输入或查询输入。",
            user_action="请确认输入数据格式。",
        )

    return warnings


def _validate_pipeline_input(data):
    warnings = []

    # 检查必填字段
    missing = [f for f in PIPELINE_REQUIRED_FIELDS if f not in data]
    if missing:
        raise InputMissingRequiredFieldError(
            "流水线模式缺失必填字段：{}".format(", ".join(missing)),
            user_action="请确认上游模块输出完整。",
            detail={"missing_fields": missing},
        )

    eligible_pool = data.get("eligible_pool", [])
    if not eligible_pool:
        raise InputUpstreamEmptyError(
            "可合法填报的院校专业基本盘为空，没有可评估的组合。",
            user_action="请放宽筛选条件或确认上游模块输出。",
        )

    # passed_majors 可以为空（表示直接评估基本盘中所有专业，不依赖 专业评估模块 输出）

    applicant_profile = data.get("applicant_profile", {})
    missing_applicant = [f for f in APPLICANT_REQUIRED_FIELDS if f not in applicant_profile]
    if missing_applicant:
        raise InputMissingRequiredFieldError(
            "考生信息缺失必填字段：{}".format(", ".join(missing_applicant)),
            user_action="请补充考生信息。",
            detail={"missing_fields": missing_applicant},
        )

    # 类型与范围校验
    total_score = applicant_profile.get("total_score")
    if not isinstance(total_score, (int, float)) or total_score < 0:
        raise InputInvalidFieldValueError(
            "total_score必须是非负数，实际：{}".format(repr(total_score)),
            user_action="请核对考生分数。",
            detail={"field": "total_score", "value": total_score},
        )

    provincial_rank = applicant_profile.get("provincial_rank")
    if not isinstance(provincial_rank, int) or provincial_rank < 1:
        raise InputInvalidFieldValueError(
            "provincial_rank必须是正整数，实际：{}".format(repr(provincial_rank)),
            user_action="请核对一分一段表查到的省内位次。",
            detail={"field": "provincial_rank", "value": provincial_rank},
        )

    return warnings


def _validate_query_input(data):
    warnings = []

    # 单校/专业查询至少有一个字段
    if not data.get("major_name") and not data.get("school_name"):
        raise InputMissingRequiredFieldError(
            "查询模式至少需要提供major_name或school_name之一。",
            user_action="请补充要查询的院校或专业。",
        )

    # 如果有考生信息，也要校验
    applicant_profile = data.get("applicant_profile", {})
    if applicant_profile:
        # 有考生信息时，校验必要字段
        if "province" in applicant_profile:
            if "total_score" in applicant_profile:
                total_score = applicant_profile.get("total_score")
                if not isinstance(total_score, (int, float)) or total_score < 0:
                    raise InputInvalidFieldValueError(
                        "total_score必须是非负数，实际：{}".format(repr(total_score)),
                        user_action="请核对考生分数。",
                        detail={"field": "total_score", "value": total_score},
                    )
            if "provincial_rank" in applicant_profile:
                provincial_rank = applicant_profile.get("provincial_rank")
                if not isinstance(provincial_rank, int) or provincial_rank < 1:
                    raise InputInvalidFieldValueError(
                        "provincial_rank必须是正整数，实际：{}".format(repr(provincial_rank)),
                        user_action="请核对一分一段表查到的省内位次。",
                        detail={"field": "provincial_rank", "value": provincial_rank},
                    )

    return warnings

