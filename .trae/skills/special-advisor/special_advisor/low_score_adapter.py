"""规则集四：低分段考生（专科线附近）适配。

处理保本科 vs 选好专科、专科方向推荐倾斜、升本通道评估。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .rule_engine import RuleEngine


def apply(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    eligible_pool: Optional[List[Dict[str, Any]]],
    rule_engine: RuleEngine,
) -> Dict[str, Any]:
    """执行低分段考生适配规则。

    触发条件：总分接近或略高于本科线（由 caller 根据省份本科线判断）
    """
    total_score = applicant.get("total_score", 0)
    provincial_rank = applicant.get("provincial_rank", 0)

    # 低分段判定：由调用方根据省份本科线传入，或在此做保守估计
    is_low_score = applicant.get("is_low_score", False)
    if not is_low_score:
        # 如果未显式标记，尝试根据 rank 粗略判断（需要省份本科线数据，此处保守处理）
        # 建议由外部传入明确的 is_low_score 标记
        return {
            "applicable": False,
            "special_tags": [],
            "adjustments": [],
            "warnings": [],
            "vocational_alternatives": [],
        }

    adjustments: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    vocational_alternatives: List[str] = []

    quality_directions = rule_engine.get_quality_vocational_directions()
    if not quality_directions:
        quality_directions = [
            "医学类专科（护理、口腔医学技术）",
            "铁路/航空类专科",
            "计算机/软件类专科",
            "电力类专科",
        ]

    # 4.4.1 保本科 vs 选好专科
    volunteer_list = draft_plan.get("volunteer_list", [])
    if volunteer_list:
        last_vol = volunteer_list[-1]
        last_positioning = last_vol.get("positioning", "")
        if last_positioning != "保":
            warnings.append({
                "level": "高危",
                "icon": "⚠️",
                "content": "低分段考生兜底志愿定位不够保守，存在滑档风险",
                "suggestion": "建议增加录取概率>95%的保底志愿，或评估优质专科作为兜底",
                "rule_basis": "低分段考生适配规则#1：保本科 vs 选好专科",
            })

    adjustments.append({
        "adjustment_content": f"低分段考生建议同步关注优质专科方向：{', '.join(quality_directions)}",
        "adjustment_reason": "如果勉强够本科线但只能上末流本科的冷门专业，优质专科的热门对口专业可能就业更好",
        "rule_basis": "低分段考生适配规则#1：保本科 vs 选好专科",
        "original_source": "系统分析",
        "severity": "中",
    })

    vocational_alternatives = quality_directions

    # 4.4.2 升本通道评估
    if not rule_engine.has_rule("upgrade_to_bachelor"):
        warnings.append({
            "level": "中危",
            "icon": "⚠️",
            "content": "专升本录取数据缺失，无法评估升本通道",
            "suggestion": "如选择专科，请自行核实该校该专业的专升本录取率和对口本科院校质量",
            "rule_basis": "低分段考生适配规则#2：升本通道评估",
        })

    return {
        "applicable": True,
        "special_tags": ["低分段"],
        "adjustments": adjustments,
        "warnings": warnings,
        "vocational_alternatives": vocational_alternatives,
    }
