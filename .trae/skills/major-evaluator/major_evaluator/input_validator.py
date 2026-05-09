"""输入格式校验。

支持两种输入模式：
  - 流水线模式：来自 硬约束过滤模块 的完整输出（含 eligible_pool）
  - 单专业/学校+专业查询模式：直接指定专业名称

v1.1 新增：
  - validate_willingness_info: 校验考生意愿信息（维度五所需字段）
  - summarize_willingness_availability: 汇总意愿信息的可用性

校验失败立即抛出 EvaluatorError，不继续执行。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .errors import (
    input_empty_pool,
    input_invalid_field,
    input_invalid_score,
    input_missing_field,
    input_upstream_format_error,
)

# 单科成绩的合法范围
_SCORE_MIN = 0
_SCORE_MAX = 150

# 单科成绩字段名
_SCORE_FIELDS = ("math_score", "physics_score")

# 体制偏好合法值
_SYSTEM_PREFERENCE_VALID = {"体制内", "体制外", "未定"}

# v1.1 意愿信息合法值
_PERSONALITY_VALID = {"偏稳定", "偏拼搏", "未定"}
_ECONOMY_VALID = {"宽裕", "普通", "紧张"}
_INTEREST_SOURCE_VALID = {"考生本人表达", "家长代述", "未区分"}
_CONSENSUS_STATUS_VALID = {"一致", "有分歧", "未沟通"}


def validate_pipeline_input(data: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """校验流水线模式的输入（硬约束过滤模块 输出格式）。

    Returns:
        (unique_majors, applicant_profile)
        unique_majors: 去重后的专业列表，每项为 {"major_name": ..., "major_code": ...}
        applicant_profile: 考生信息 dict（来自 硬约束过滤模块 输出）

    Raises:
        EvaluatorError: 任何格式问题
    """
    if not isinstance(data, dict):
        raise input_upstream_format_error("输入必须是 JSON 对象，当前类型为：" + type(data).__name__)

    status = data.get("status")
    if status != "success":
        raise input_upstream_format_error(
            f"硬约束过滤模块 输出 status 为 '{status}'，期望 'success'。"
            "请先确保 硬约束过滤模块 正常运行后再调用 专业评估模块。"
        )

    eligible_pool = data.get("eligible_pool")
    if eligible_pool is None:
        raise input_upstream_format_error("缺少 'eligible_pool' 字段。")
    if not isinstance(eligible_pool, list):
        raise input_upstream_format_error("'eligible_pool' 必须是数组类型。")
    if len(eligible_pool) == 0:
        raise input_empty_pool()

    applicant_profile = data.get("applicant_profile", {})
    if not isinstance(applicant_profile, dict):
        raise input_upstream_format_error("'applicant_profile' 必须是 JSON 对象。")

    # 提取去重专业列表
    unique_majors = _extract_unique_majors(eligible_pool)
    if not unique_majors:
        raise input_empty_pool()

    return unique_majors, applicant_profile


def validate_single_input(data: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """校验单专业/学校+专业查询模式的输入。

    Returns:
        (major_name, school_name, applicant_profile)
        school_name 为空字符串时表示纯专业查询（不含学校）

    Raises:
        EvaluatorError: 任何格式问题
    """
    if not isinstance(data, dict):
        raise input_upstream_format_error("输入必须是 JSON 对象。")

    major_name = data.get("major_name", "").strip()
    if not major_name:
        raise input_missing_field("major_name")

    school_name = data.get("school_name", "").strip()
    applicant_profile = data.get("applicant_profile", {})

    if not isinstance(applicant_profile, dict):
        raise input_upstream_format_error("'applicant_profile' 必须是 JSON 对象。")

    return major_name, school_name, applicant_profile


def validate_applicant_scores(applicant_profile: Dict[str, Any]) -> List[str]:
    """校验考生单科成绩的合法性。

    Returns:
        warnings 列表（分数合法但有提示的情况）

    Raises:
        EvaluatorError: 分数明显非法（负数、超界）
    """
    warnings: List[str] = []

    for field in _SCORE_FIELDS:
        value = applicant_profile.get(field)
        if value is None:
            continue  # 未提供，跳过

        if not isinstance(value, (int, float)):
            raise input_invalid_score(field, value)

        score = int(value)
        if score < _SCORE_MIN or score > _SCORE_MAX:
            raise input_invalid_score(field, value)

    # 检查体制偏好值
    system_pref = applicant_profile.get("system_preference")
    if system_pref is not None and system_pref not in _SYSTEM_PREFERENCE_VALID:
        warnings.append(
            f"'system_preference' 的值 '{system_pref}' 不在合法范围内 "
            f"（合法值：{sorted(_SYSTEM_PREFERENCE_VALID)}），将忽略该字段。"
        )

    return warnings


def validate_willingness_info(applicant_profile: Dict[str, Any]) -> List[str]:
    """校验考生意愿信息字段（v1.1 新增，维度五所需）。

    所有字段均为可选。字段缺失时不报错，只在 warnings 中说明。
    字段存在但格式非法时，枚举类字段产生 warning，结构类字段（数组/对象）类型错误则抛异常。

    Returns:
        warnings 列表

    Raises:
        EvaluatorError: 字段类型明显非法（如数组字段传了字符串）
    """
    warnings: List[str] = []

    # interest_directions: 字符串数组
    interest_dirs = applicant_profile.get("interest_directions")
    if interest_dirs is not None:
        if not isinstance(interest_dirs, list) or not all(
            isinstance(x, str) for x in interest_dirs
        ):
            raise input_invalid_field("interest_directions", "必须是字符串数组，例如 [\"电力相关\", \"稳定工作\"]")

    # explicit_rejections: 字符串数组
    rejections = applicant_profile.get("explicit_rejections")
    if rejections is not None:
        if not isinstance(rejections, list) or not all(
            isinstance(x, str) for x in rejections
        ):
            raise input_invalid_field("explicit_rejections", "必须是字符串数组，例如 [\"医学\", \"化学\"]")

    # personality_tendency: 枚举
    personality = applicant_profile.get("personality_tendency")
    if personality is not None and personality not in _PERSONALITY_VALID:
        warnings.append(
            f"'personality_tendency' 的值 '{personality}' 不在合法范围内 "
            f"（合法值：{sorted(_PERSONALITY_VALID)}），将忽略该字段。"
        )

    # family_economy_level: 枚举
    economy = applicant_profile.get("family_economy_level")
    if economy is not None and economy not in _ECONOMY_VALID:
        warnings.append(
            f"'family_economy_level' 的值 '{economy}' 不在合法范围内 "
            f"（合法值：{sorted(_ECONOMY_VALID)}），将忽略该字段。"
        )

    # family_has_industry_resources: 布尔
    resources = applicant_profile.get("family_has_industry_resources")
    if resources is not None and not isinstance(resources, bool):
        warnings.append(
            f"'family_has_industry_resources' 的值 {resources!r} 应为布尔型（true/false），将忽略该字段。"
        )

    # interest_source: 枚举
    source = applicant_profile.get("interest_source")
    if source is not None and source not in _INTEREST_SOURCE_VALID:
        warnings.append(
            f"'interest_source' 的值 '{source}' 不在合法范围内 "
            f"（合法值：{sorted(_INTEREST_SOURCE_VALID)}），将标注为'未区分'。"
        )
    # 家长代述时给出提醒
    if source == "家长代述":
        warnings.append(
            "⚠️ 意愿偏好由家长代述（非考生本人），建议确认考生本人意愿后再做最终决策。"
        )

    # parent_child_consensus: 对象
    consensus = applicant_profile.get("parent_child_consensus")
    if consensus is not None:
        if not isinstance(consensus, dict):
            raise input_invalid_field(
                "parent_child_consensus",
                "必须是 JSON 对象，含 status / parent_preference / child_preference 字段",
            )
        status = consensus.get("status")
        if status not in _CONSENSUS_STATUS_VALID:
            warnings.append(
                f"'parent_child_consensus.status' 的值 '{status}' 不在合法范围内 "
                f"（合法值：{sorted(_CONSENSUS_STATUS_VALID)}），共识度检查将跳过。"
            )
        elif status == "有分歧":
            parent_pref = (consensus.get("parent_preference") or "").strip()
            child_pref = (consensus.get("child_preference") or "").strip()
            if not parent_pref or not child_pref:
                warnings.append(
                    "⚠️ 家长与考生存在分歧（parent_child_consensus.status='有分歧'），"
                    "但 parent_preference 或 child_preference 为空，分歧详情将无法记录在评估卡中。"
                )

    return warnings


def summarize_willingness_availability(applicant_profile: Dict[str, Any]) -> Dict[str, Any]:
    """汇总意愿信息各字段的可用性，用于 input_summary 和 global_warnings 生成。

    Returns:
        dict，key 为字段名，value 为 True/False（是否已提供），
        interest_source 例外，直接返回其字符串值。
    """
    consensus = applicant_profile.get("parent_child_consensus")
    return {
        "interest_directions": applicant_profile.get("interest_directions") is not None,
        "explicit_rejections": applicant_profile.get("explicit_rejections") is not None,
        "personality_tendency": applicant_profile.get("personality_tendency") is not None,
        "family_economy_level": applicant_profile.get("family_economy_level") is not None,
        "parent_child_consensus": isinstance(consensus, dict),
        "interest_source": applicant_profile.get("interest_source", "未区分"),
    }


# ---- 搜索结果字段定义（critical = 至少一个非 null 才能评估该维度）----

_SEARCH_DEFINITIONS: Dict[str, Any] = {
    "s1": {
        "critical": {"employment_rate", "top_industries"},
        "optional": {"salary_range", "employment_quality_note"},
        "dimension_affected": "dimension_1_width",
        "suggested_action": (
            "重新执行 S1 搜索（[专业名] 就业率 薪资 就业去向 2023 2024），"
            "用 WebFetch 优先读取就业质量报告、麦可思报告等权威来源页面"
        ),
    },
    "s2": {
        "critical": {"civil_service_categories", "degree_type"},
        "optional": {"state_enterprise_channels", "degree_exam_match_note"},
        "dimension_affected": "dimension_2_system_orientation",
        "suggested_action": (
            "重新执行 S2 搜索（[专业名] 考公 国家公务员 专业目录 对口岗位），"
            "用 WebFetch 优先读取国家公务员局或各省人社厅官方页面"
        ),
    },
    "s3": {
        "critical": {"license_restriction", "similar_majors"},
        "optional": {"license_name", "discipline_category"},
        "dimension_affected": "dimension_4_name_trap",
        "suggested_action": (
            "重新执行 S3 搜索（[专业名] 执业资格证 学位类型 和近似专业名 区别），"
            "用 WebFetch 优先读取教育部专业目录或执业资格考试官网"
        ),
    },
    "s4": {
        "critical": set(),  # S4 全部可选，但至少需要一个字段有数据
        "optional": {"reputation_summary", "hidden_risks", "supply_demand_trend", "ordinary_family_reality"},
        "dimension_affected": "dimension_1_width（口碑补充）",
        "suggested_action": (
            "重新执行 S4 搜索（[专业名] 就业 坑 值不值得报 论坛 知乎 2024），"
            "用 WebFetch 读取知乎问答或论坛帖子获取真实口碑"
        ),
    },
}


def validate_search_findings(findings: Dict[str, Any]) -> Dict[str, Any]:
    """校验 模块 提取的搜索结果是否满足五维评估的最低数据要求。

    模块 在完成 WebSearch + WebFetch + 结构化提取后，将 findings 传入此函数。
    函数检查每个搜索的关键字段是否有效（value 和 raw_text 均非 None）。

    Args:
        findings: 结构化提取结果，格式：
            {
                "s1": {
                    "employment_rate": {"value": "87%", "raw_text": "原文片段", "source_url": "..."},
                    "top_industries":  {"value": None, "raw_text": None, "source_url": None},
                    ...
                },
                "s2": {...},
                "s3": {...},
                "s4": {...}
            }

    Returns:
        {
            "has_gaps": bool,
            "gaps": [
                {
                    "search": "S1",
                    "missing_fields": ["employment_rate", "top_industries"],
                    "dimension_affected": "dimension_1_width",
                    "severity": "critical | optional",
                    "suggested_action": "具体补救措施"
                }
            ],
            "coverage_summary": {"s1": "full | partial | none", ...}
        }

    Raises:
        EvaluatorError: findings 不是合法对象
    """
    if not isinstance(findings, dict):
        raise input_invalid_field("findings", "必须是 JSON 对象，含 s1/s2/s3/s4 子对象")

    gaps: List[Dict[str, Any]] = []
    coverage_summary: Dict[str, str] = {}

    for search_key, definition in _SEARCH_DEFINITIONS.items():
        search_data = findings.get(search_key)
        if not isinstance(search_data, dict):
            search_data = {}

        critical_fields: set = definition["critical"]
        optional_fields: set = definition["optional"]
        all_fields = critical_fields | optional_fields

        # 找出有效字段（value 和 raw_text 均非 None）
        available: set = set()
        for field in all_fields:
            field_data = search_data.get(field)
            if isinstance(field_data, dict):
                if field_data.get("value") is not None and field_data.get("raw_text") is not None:
                    available.add(field)

        missing_critical = critical_fields - available

        # 覆盖度评级
        if not critical_fields:
            # S4：无 critical 字段，有任何数据即为 full
            coverage = "full" if available else "none"
        elif missing_critical == critical_fields:
            coverage = "none"
        elif missing_critical:
            coverage = "partial"
        else:
            coverage = "full"

        coverage_summary[search_key] = coverage

        # 需要补全的字段
        if coverage == "none":
            missing = sorted(missing_critical | (optional_fields - available))
            severity = "optional" if not critical_fields else "critical"
            gaps.append({
                "search": search_key.upper(),
                "missing_fields": missing,
                "dimension_affected": definition["dimension_affected"],
                "severity": severity,
                "suggested_action": definition["suggested_action"],
            })
        elif coverage == "partial" and missing_critical:
            gaps.append({
                "search": search_key.upper(),
                "missing_fields": sorted(missing_critical),
                "dimension_affected": definition["dimension_affected"],
                "severity": "critical",
                "suggested_action": definition["suggested_action"],
            })

    return {
        "has_gaps": bool(gaps),
        "gaps": gaps,
        "coverage_summary": coverage_summary,
    }


def _extract_unique_majors(eligible_pool: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """从 硬约束过滤模块 的 eligible_pool 中提取去重后的专业列表。

    硬约束过滤模块 的结构：eligible_pool -> [school] -> major_groups -> [group] -> majors -> [major]
    按 major_code + major_name 去重。
    """
    seen: set = set()
    result: List[Dict[str, str]] = []

    for school in eligible_pool:
        if not isinstance(school, dict):
            continue
        for group in school.get("major_groups", []):
            if not isinstance(group, dict):
                continue
            for major in group.get("majors", []):
                if not isinstance(major, dict):
                    continue
                code = str(major.get("major_code", "")).strip()
                name = str(major.get("major_name", "")).strip()
                if not name:
                    continue
                key = (code, name)
                if key not in seen:
                    seen.add(key)
                    result.append({"major_code": code, "major_name": name})

    return result
