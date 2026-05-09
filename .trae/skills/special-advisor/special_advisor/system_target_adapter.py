"""规则集三：有明确体制内目标的考生适配。

处理专业选择向考公目录倾斜、学位类型核查、院校选择倾斜、地域绑定。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rule_engine import RuleEngine


def apply(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    院校匹配_match_cards: Optional[Dict[str, Any]],
    rule_engine: RuleEngine,
) -> Dict[str, Any]:
    """执行体制内目标适配规则。"""
    target_system = applicant.get("target_system", "未定")
    if target_system not in ("体制内", "考公", "考编", "国企", True):
        return {
            "applicable": False,
            "special_tags": [],
            "adjustments": [],
            "warnings": [],
            "civil_service_friendly_majors": [],
        }

    adjustments: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    civil_service_friendly_majors: List[str] = []

    if not rule_engine.has_rule("civil_service") and not rule_engine.has_rule("special_adjustment"):
        warnings.append({
            "level": "中危",
            "icon": "⚠️",
            "content": "公务员招录目录缺失，体制内目标考生的专业大类适配未执行",
            "suggestion": "请人工核对所选专业是否属于目标岗位要求的学科大类，特别注意'法学学位≠法学类'、'管理学学位≠管理学类'等常见误区",
            "rule_basis": "规则库可用性检查",
        })

    friendly_categories = rule_engine.get_civil_service_friendly_categories()
    if not friendly_categories:
        friendly_categories = ["法学类", "财政学类", "计算机类", "中国语言文学类", "工商管理类"]

    volunteer_list = draft_plan.get("volunteer_list", [])
    for vol in volunteer_list:
        school_name = vol.get("school_name", "")
        group_name = vol.get("major_group", "")
        majors = vol.get("major_group_majors", [])

        for major_name in majors:
            if rule_engine.is_civil_service_friendly_major(major_name):
                civil_service_friendly_majors.append(f"{school_name}·{major_name}")
            else:
                # 标记非考公友好专业
                warnings.append({
                    "level": "中危",
                    "icon": "⚠️",
                    "content": f"'{school_name}·{group_name}·{major_name}'不属于考公岗位数量多的专业大类",
                    "suggestion": f"体制内目标考生建议优先选择以下大类：{', '.join(friendly_categories)}",
                    "rule_basis": "体制内目标适配规则#1：专业选择向考公目录倾斜",
                })

    if civil_service_friendly_majors:
        adjustments.append({
            "adjustment_content": f"已标记以下考公友好专业：{', '.join(civil_service_friendly_majors)}",
            "adjustment_reason": "考生目标为体制内，优先选择岗位数量多的专业大类",
            "rule_basis": "体制内目标适配规则#1：专业选择向考公目录倾斜",
            "original_source": "填报策略模块 方案初稿",
            "severity": "低",
        })

    # 4.3.2 院校选择向目标系统倾斜
    preferred_cities = applicant.get("preferred_cities", [])
    if preferred_cities:
        adjustments.append({
            "adjustment_content": f"体制内就业地域性极强，建议优先选择目标地区（{', '.join(preferred_cities)}）的院校",
            "adjustment_reason": "考公/考编存在明显的地域偏好，本地院校在信息获取、实习、人脉等方面更有优势",
            "rule_basis": "体制内目标适配规则#3：地域与目标岗位绑定",
            "original_source": "考生信息",
            "severity": "中",
        })

    return {
        "applicable": True,
        "special_tags": ["体制内目标"],
        "adjustments": adjustments,
        "warnings": warnings,
        "civil_service_friendly_majors": civil_service_friendly_majors,
    }
