"""规则集五：复读可能性评估。

不主动建议复读，但当考生主动提出或所有方案都不理想时，提供客观分析。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def apply(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    all_adjustments: List[Dict[str, Any]],
    all_warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """执行复读可能性评估。

    触发条件：考生主动提出复读，或方案中高危警告数量过多
    """
    user_asked_reboot = applicant.get("considering_reboot", False)
    high_risk_count = sum(1 for w in all_warnings if w.get("level") == "高危")

    if not user_asked_reboot and high_risk_count < 3:
        return {
            "applicable": False,
            "special_tags": [],
            "adjustments": [],
            "warnings": [],
            "reboot_assessment": None,
        }

    adjustments: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # 评估维度
    assessment = {
        "score_boost_potential": _assess_score_boost(applicant),
        "family_capacity": _assess_family_capacity(applicant),
        "policy_risk": _assess_policy_risk(applicant),
        "policy_restrictions": _assess_policy_restrictions(applicant),
    }

    overall_suitable = (
        assessment["score_boost_potential"]["suitable"] and
        assessment["family_capacity"]["suitable"]
    )

    reboot_assessment = {
        "overall_suitable": overall_suitable,
        "overall_recommendation": "谨慎考虑" if overall_suitable else "不建议复读",
        "dimensions": assessment,
        "note": "复读一年的结果具有高度不确定性，最终决策需考生和家长根据家庭实际情况自行判断。",
    }

    adjustments.append({
        "adjustment_content": "附复读可能性评估",
        "adjustment_reason": "考生主动询问复读，或当前方案高危风险较多",
        "rule_basis": "复读可能性评估规则",
        "original_source": "系统分析",
        "severity": "低",
    })

    return {
        "applicable": True,
        "special_tags": ["复读评估"],
        "adjustments": adjustments,
        "warnings": warnings,
        "reboot_assessment": reboot_assessment,
    }


def _assess_score_boost(applicant: Dict[str, Any]) -> Dict[str, Any]:
    """评估提分空间。"""
    abnormal_subjects = applicant.get("abnormal_subjects", [])
    total_score = applicant.get("total_score", 0)

    suitable = bool(abnormal_subjects)
    reason = ""
    if abnormal_subjects:
        reason = f"以下科目明显发挥失常：{', '.join(abnormal_subjects)}，存在明确的提分空间"
    else:
        reason = "未发现明显发挥失常的科目，复读提分空间不确定"

    return {
        "suitable": suitable,
        "reason": reason,
        "detail": "提分空间是复读决策中最重要的因素，没有明确提分空间的复读风险极高",
    }


def _assess_family_capacity(applicant: Dict[str, Any]) -> Dict[str, Any]:
    """评估家庭承受力。"""
    family_economy = applicant.get("family_economy_level", "普通")
    suitable = family_economy not in ("困难", "拮据")

    reason = ""
    if suitable:
        reason = f"家庭经济状况为'{family_economy}'，理论上可承受再一年的经济和心理压力"
    else:
        reason = f"家庭经济状况为'{family_economy}'，复读一年的经济压力可能较大"

    return {
        "suitable": suitable,
        "reason": reason,
        "detail": "复读不仅是经济成本，更是心理成本，需全家共同承受",
    }


def _assess_policy_risk(applicant: Dict[str, Any]) -> Dict[str, Any]:
    """评估政策风险（新高考改革等）。"""
    province = applicant.get("province", "")
    exam_year = applicant.get("exam_year", 2026)

    # 简化的政策风险判断：2024-2025 是多省新高考改革过渡期
    high_risk_provinces = ["河南", "陕西", "山西", "内蒙古", "四川", "云南", "宁夏", "青海"]
    is_high_risk = province in high_risk_provinces and exam_year <= 2026

    return {
        "suitable": not is_high_risk,
        "reason": f"{province}在{exam_year}年前后存在新高考改革过渡期的政策变动风险" if is_high_risk else f"{province}当前高考政策相对稳定",
        "detail": "政策变动可能导致考试内容、计分方式、录取规则发生变化，增加复读的不确定性",
    }


def _assess_policy_restrictions(applicant: Dict[str, Any]) -> Dict[str, Any]:
    """评估复读生政策限制。"""
    province = applicant.get("province", "")
    # 部分省份或院校对复读生有限制
    restricted_provinces = ["贵州", "云南", "四川"]  # 部分公办高中限制招收复读生
    has_restriction = province in restricted_provinces

    return {
        "has_restriction": has_restriction,
        "reason": f"{province}部分公办高中限制招收复读生，需提前确认复读渠道" if has_restriction else f"{province}复读生报考限制较少",
        "detail": "即使省份层面没有限制，个别院校（如部分军校、保送生项目）可能不招收复读生",
    }
