"""最终报告生成器。

按 PRD §3.1 的结构生成最终志愿填报报告。
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional


def generate(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    special_tags: List[str],
    special_tags_reason: str,
    adjustments: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    must_confirm_items: List[Dict[str, Any]],
    backup_plan: Optional[Dict[str, Any]],
    final_checklist: List[Dict[str, Any]],
    report_metadata: Dict[str, Any],
    eligible_pool: Optional[List[Dict[str, Any]]] = None,
    专业评估结果: Optional[Dict[str, Any]] = None,
    院校匹配_match_cards: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生成最终志愿填报报告。"""

    # 生成策略总结
    strategy_summary = _generate_strategy_summary(applicant, special_tags)

    # 构建调整后的志愿列表（在 填报策略模块 初稿基础上做微调）
    adjusted_volunteer_list = _build_adjusted_volunteers(draft_plan, adjustments, warnings)

    report = {
        "report_header": {
            "title": f"{applicant.get('exam_year', 2026)}年高考志愿填报最终报告",
            "generated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "disclaimer": (
                "本报告为智能辅助决策工具生成，仅供参考。"
                "最终填报请以各省教育考试院官方发布的招生计划和招生章程为准。"
            ),
            "version": "v1.0",
        },
        "applicant_profile_summary": {
            "province": applicant.get("province", ""),
            "total_score": applicant.get("total_score", 0),
            "provincial_rank": applicant.get("provincial_rank", 0),
            "subject_category": applicant.get("subject_category", ""),
            "selected_subjects": applicant.get("selected_subjects", []),
            "gender": applicant.get("gender", ""),
            "special_tags": special_tags,
            "special_tags_reason": special_tags_reason,
        },
        "strategy_summary": strategy_summary,
        "adjusted_volunteer_list": adjusted_volunteer_list,
        "special_adjustments": adjustments,
        "warnings": warnings,
        "must_confirm_items": must_confirm_items,
        "backup_plan": backup_plan or {
            "description": "如果考生对主方案中的某些选择不满意，可考虑以下替代",
            "alternatives": [],
        },
        "final_checklist": final_checklist,
        "report_metadata": report_metadata,
    }

    return report


def _generate_strategy_summary(applicant: Dict[str, Any], special_tags: List[str]) -> str:
    """根据考生画像生成策略总结。"""
    gender = applicant.get("gender", "")
    total_score = applicant.get("total_score", 0)
    target_system = applicant.get("target_system", "未定")

    parts = []
    if "女生" in special_tags:
        parts.append("优先推荐师范类和护理类方向，避开存在就业性别歧视的工科专业")
    if "数理基础薄弱" in special_tags:
        parts.append("避开硬核工科，选择对数理要求相对较低的应用型或文科方向")
    if "体制内目标" in special_tags:
        parts.append("专业向考公友好大类倾斜，院校向目标系统认可院校倾斜")
    if "低分段" in special_tags:
        parts.append("保本科与选好专科并行评估，确保兜底足够安全")

    if not parts:
        parts.append("综合考虑考生成绩、位次和选科，平衡学校层次与专业质量")

    strategy = "；".join(parts)
    return f"保专业为主，兼顾稳就业。{strategy}。"


def _build_adjusted_volunteers(
    draft_plan: Dict[str, Any],
    adjustments: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """在 填报策略模块 初稿基础上，叠加警告和调整信息。"""
    volunteer_list = draft_plan.get("volunteer_list", [])
    result = []

    for vol in volunteer_list:
        vol_copy = dict(vol)
        school_name = vol.get("school_name", "")
        group_name = vol.get("major_group", "")

        # 查找与该志愿相关的警告
        vol_warnings = []
        for w in warnings:
            content = w.get("content", "")
            if school_name in content and group_name in content:
                vol_warnings.append(w)

        # 查找与该志愿相关的隐藏门槛检查
        hidden_threshold_check = ""
        for w in vol_warnings:
            if "招生章程" in w.get("content", "") or "单科" in w.get("content", ""):
                hidden_threshold_check = f"⚠️ {w.get('content', '')}"
                break

        if not hidden_threshold_check:
            hidden_threshold_check = "⚠️ 请自行核查该校招生章程：是否有单科成绩要求、体检限制等"

        vol_copy["hidden_threshold_check"] = hidden_threshold_check
        vol_copy["attached_warnings"] = vol_warnings
        result.append(vol_copy)

    return result


def build_final_checklist(checker_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """根据检查结果生成最终检查清单。"""
    return [
        {
            "category": "安全性",
            "items": [
                "☐ 所有志愿都在硬约束过滤模块确认的基本盘范围内",
                "☐ 已核查每所院校的招生章程（单科要求、体检限制、专业级差）",
                "☐ 兜底志愿录取概率>95%，确保不滑档",
                "☐ 不干净的专业组已标记风险，未误勾服从调剂",
            ],
        },
        {
            "category": "适配性",
            "items": [
                "☐ 方案与考生的体制内/外偏好一致",
                "☐ 地域安排与考生的长期居住意愿一致",
                "☐ 经济承受力已考虑（学费在家庭预算内）",
                "☐ 性别相关的就业风险已标注",
            ],
        },
        {
            "category": "完整性",
            "items": [
                "☐ 冲/稳/保比例合理",
                "☐ 已了解备选方案",
                "☐ 已逐项确认所有'必须确认事项'",
                "☐ 关键风险已理解并接受",
            ],
        },
    ]


def build_must_confirm_items(applicant: Dict[str, Any], draft_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """生成必须确认事项列表。"""
    items = [
        {
            "item": "请确认考生位次为精确值（非估算值）",
            "reason": "位次是冲稳保判断的核心依据，估算位次可能导致判断偏差",
            "action": "如为估算值，请在官方一分一段表公布后重新运行",
        },
        {
            "item": "请核查每所志愿院校当年招生章程中的单科要求、体检限制、专业级差",
            "reason": "部分院校对特定专业有英语单科、数学单科、身高等隐藏门槛，不达标投档后可能被退档",
            "action": "确认考生条件是否满足，如不满足请移除该志愿",
        },
    ]

    # 根据考生情况增加个性化确认事项
    if applicant.get("gender") == "女":
        items.append({
            "item": "请确认已了解方案中各专业的女生就业实际情况",
            "reason": "部分专业招生不限性别但就业时存在性别偏好",
            "action": "如对某些专业有顾虑，请参考备选方案",
        })

    if applicant.get("target_system") in ("体制内", "考公", "考编"):
        items.append({
            "item": "请确认所选专业的学科大类与目标考公岗位要求一致",
            "reason": "'法学学位'不等于'法学类'、'管理学学位'不等于'管理学类'，考公报名时以学科代码为准",
            "action": "请对照当年公务员招录专业目录核实",
        })

    math_score = applicant.get("math_score")
    physics_score = applicant.get("physics_score")
    if (math_score is not None and math_score < 90) or (physics_score is not None and physics_score < 60):
        items.append({
            "item": "请确认考生已了解所选硬核工科专业的数理课程难度",
            "reason": "数理基础薄弱可能导致大学期间挂科甚至无法毕业",
            "action": "如坚持选择，建议提前了解该校转专业政策和补考制度",
        })

    return items
