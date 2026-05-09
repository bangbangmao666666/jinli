"""规则集一：中低分段女生适配。

处理就业性别歧视预警、推荐倾斜方向、地域倾斜、专业组干净度加严。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rule_engine import RuleEngine


def apply(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    专业评估结果: Optional[Dict[str, Any]],
    rule_engine: RuleEngine,
) -> Dict[str, Any]:
    """执行女生适配规则。

    返回:
        {
            "applicable": bool,
            "special_tags": ["女生"],
            "adjustments": [...],
            "warnings": [...],
            "recommendation_boosts": [...],  # 建议提升优先级的专业
            "removed_volunteers": [...],     # 建议移除的志愿
        }
    """
    gender = applicant.get("gender")
    if gender != "女":
        return {
            "applicable": False,
            "special_tags": [],
            "adjustments": [],
            "warnings": [],
            "recommendation_boosts": [],
            "removed_volunteers": [],
        }

    adjustments: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    recommendation_boosts: List[str] = []
    removed_volunteers: List[Dict[str, Any]] = []

    if not rule_engine.has_rule("female_risk"):
        warnings.append({
            "level": "中危",
            "icon": "⚠️",
            "content": "女生避坑规则库缺失，未执行性别就业风险检查",
            "suggestion": "请人工复核方案中是否存在对女生就业不友好的专业",
            "rule_basis": "规则库可用性检查",
        })

    volunteer_list = draft_plan.get("volunteer_list", [])
    for vol in volunteer_list:
        school_name = vol.get("school_name", "")
        group_name = vol.get("major_group", "")
        majors = vol.get("major_group_majors", [])
        positioning = vol.get("positioning", "")

        # 4.1.1 隐形性别歧视预警：检查专业组内是否有高风险专业
        has_high_risk = False
        high_risk_major_names = []
        for major_name in majors:
            if rule_engine.is_female_high_risk_major(major_name):
                has_high_risk = True
                high_risk_major_names.append(major_name)

        if has_high_risk:
            # 检查是否是考生明确要求保留的（通过 applicant 中的 preferred_majors 或特殊标记判断）
            preferred = applicant.get("preferred_majors", [])
            explicitly_wanted = any(m in preferred for m in high_risk_major_names)

            if explicitly_wanted:
                warnings.append({
                    "level": "高危",
                    "icon": "⚠️",
                    "content": f"志愿'{school_name}·{group_name}'包含女生高风险专业：{', '.join(high_risk_major_names)}，该专业对女生就业存在显著性别歧视",
                    "suggestion": "如坚持选择，请做好就业困难的心理准备，建议提前了解行业实际情况",
                    "rule_basis": "女生避坑规则#1：隐形性别歧视预警（考生明确要求保留）",
                })
            else:
                removed_volunteers.append({
                    "serial_number": vol.get("serial_number"),
                    "school_name": school_name,
                    "major_group": group_name,
                    "removed_majors": high_risk_major_names,
                })
                adjustments.append({
                    "adjustment_content": f"将'{school_name}·{group_name}'从推荐列表中移除（含高风险专业：{', '.join(high_risk_major_names)}）",
                    "adjustment_reason": "该专业组包含对女生就业存在显著性别歧视的专业，施工单位/现场岗位普遍不招女生",
                    "rule_basis": "女生避坑规则#1：隐形性别歧视预警",
                    "original_source": "填报策略模块 方案初稿",
                    "severity": "高",
                })

        # 4.1.4 专业组干净度加严：黄灯按红灯处理
        cleanliness = vol.get("major_group_cleanliness", "")
        if "黄灯" in str(cleanliness) or "⚠️" in str(cleanliness):
            warnings.append({
                "level": "高危",
                "icon": "⚠️",
                "content": f"志愿'{school_name}·{group_name}'专业组干净度为黄灯，对女生而言调剂风险更高",
                "suggestion": "建议不勾选该专业组的服从调剂，或放弃该志愿",
                "rule_basis": "女生避坑规则#4：专业组干净度加严",
            })

    # 4.1.2 推荐倾斜方向：在现有方案中标记值得提升优先级的专业
    female_friendly_keywords = [
        "师范", "护理", "小学教育", "学前教育",
        "财务管理", "会计学", "汉语言文学",
    ]
    for vol in volunteer_list:
        majors = vol.get("major_group_majors", [])
        for major in majors:
            if any(kw in major for kw in female_friendly_keywords):
                recommendation_boosts.append(major)

    if recommendation_boosts:
        adjustments.append({
            "adjustment_content": f"建议提升以下女生友好专业的优先级：{', '.join(set(recommendation_boosts))}",
            "adjustment_reason": "师范类有编制保障、护理学就业率极高且女生友好、财会类适合考公",
            "rule_basis": "女生避坑规则#2：推荐倾斜方向",
            "original_source": "填报策略模块 方案初稿",
            "severity": "低",
        })

    return {
        "applicable": True,
        "special_tags": ["女生"],
        "adjustments": adjustments,
        "warnings": warnings,
        "recommendation_boosts": list(set(recommendation_boosts)),
        "removed_volunteers": removed_volunteers,
    }
