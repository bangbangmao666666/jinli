"""规则集二：数理基础薄弱考生适配。

处理硬核工科红灯、推荐替代方向、风险明确告知。
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
    """执行数理基础薄弱适配规则。

    触发条件: math_score < 90 或 physics_score < 60
    """
    math_score = applicant.get("math_score")
    physics_score = applicant.get("physics_score")

    math_threshold = rule_engine.get_math_threshold()
    physics_threshold = rule_engine.get_physics_threshold()

    math_weak = math_score is not None and math_score < math_threshold
    physics_weak = physics_score is not None and physics_score < physics_threshold

    if not math_weak and not physics_weak:
        return {
            "applicable": False,
            "special_tags": [],
            "adjustments": [],
            "warnings": [],
            "alternative_recommendations": [],
        }

    adjustments: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    alternative_recommendations: List[str] = []

    weak_subjects = []
    if math_weak:
        weak_subjects.append(f"数学({math_score}分)")
    if physics_weak:
        weak_subjects.append(f"物理({physics_score}分)")

    volunteer_list = draft_plan.get("volunteer_list", [])
    for vol in volunteer_list:
        school_name = vol.get("school_name", "")
        group_name = vol.get("major_group", "")
        majors = vol.get("major_group_majors", [])

        for major_name in majors:
            if rule_engine.is_high_math_demand_major(major_name):
                warnings.append({
                    "level": "高危",
                    "icon": "⚠️",
                    "content": f"您的{'、'.join(weak_subjects)}，志愿'{school_name}·{group_name}'中的'{major_name}'核心课程对数理要求极高",
                    "suggestion": "如果选择该专业，大学期间需要付出大量额外精力补数理基础，且仍存在挂科风险。建议慎重考虑，或提前了解该校转专业政策。",
                    "rule_basis": "数理基础薄弱规则#1：硬核工科红灯",
                })
                adjustments.append({
                    "adjustment_content": f"对'{school_name}·{group_name}·{major_name}'加高危警告",
                    "adjustment_reason": f"考生{'、'.join(weak_subjects)}，低于阈值（数学<{math_threshold}或物理<{physics_threshold}），该专业核心课程对数理要求极高",
                    "rule_basis": "数理基础薄弱规则#1：硬核工科红灯",
                    "original_source": "填报策略模块 方案初稿",
                    "severity": "高",
                })

    # 4.2.2 推荐替代方向
    if math_weak or physics_weak:
        alternative_recommendations = [
            "护理学", "学前教育", "旅游管理", "社会工作",
            "汉语言文学", "新闻传播学类",
        ]
        if math_weak and not physics_weak:
            alternative_recommendations.extend(["食品科学", "园林", "建筑学（偏设计方向）"])

        adjustments.append({
            "adjustment_content": f"推荐对数理要求相对较低的方向：{', '.join(alternative_recommendations)}",
            "adjustment_reason": f"考生{'、'.join(weak_subjects)}，建议避开硬核工科，选择应用型或文科方向",
            "rule_basis": "数理基础薄弱规则#2：推荐替代方向",
            "original_source": "系统分析",
            "severity": "中",
        })

    return {
        "applicable": True,
        "special_tags": ["数理基础薄弱"],
        "adjustments": adjustments,
        "warnings": warnings,
        "alternative_recommendations": alternative_recommendations,
    }
