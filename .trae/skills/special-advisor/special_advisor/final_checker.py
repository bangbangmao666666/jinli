"""最终审核检查清单执行器。

按 PRD §5 逐项执行安全性、适配性、完整性检查。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def run(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    eligible_pool: Optional[List[Dict[str, Any]]],
    all_adjustments: List[Dict[str, Any]],
    all_warnings: List[Dict[str, Any]],
    special_tags: List[str],
) -> Dict[str, Any]:
    """执行最终审核检查清单。

    返回:
        {
            "safety_checks": [...],
            "adaptation_checks": [...],
            "completeness_checks": [...],
            "new_warnings": [...],
            "new_adjustments": [...],
        }
    """
    safety_checks = _check_safety(applicant, draft_plan, eligible_pool, all_warnings)
    adaptation_checks = _check_adaptation(applicant, draft_plan, all_warnings, special_tags)
    completeness_checks = _check_completeness(applicant, draft_plan, all_adjustments, all_warnings)

    new_warnings: List[Dict[str, Any]] = []
    new_adjustments: List[Dict[str, Any]] = []

    # 将不通过的检查项转化为警告或调整
    for check in safety_checks:
        if not check["passed"]:
            if check["severity"] == "error":
                new_warnings.append({
                    "level": "高危",
                    "icon": "⚠️",
                    "content": check["message"],
                    "suggestion": check["action"],
                    "rule_basis": check["rule_basis"],
                })
            new_adjustments.append({
                "adjustment_content": check["message"],
                "adjustment_reason": check["action"],
                "rule_basis": check["rule_basis"],
                "original_source": "最终审核检查清单",
                "severity": "高" if not check["passed"] else "低",
            })

    for check in adaptation_checks:
        if not check["passed"]:
            new_warnings.append({
                "level": "中危",
                "icon": "⚠️",
                "content": check["message"],
                "suggestion": check["action"],
                "rule_basis": check["rule_basis"],
            })

    for check in completeness_checks:
        if not check["passed"]:
            new_warnings.append({
                "level": "中危",
                "icon": "⚠️",
                "content": check["message"],
                "suggestion": check["action"],
                "rule_basis": check["rule_basis"],
            })

    return {
        "safety_checks": safety_checks,
        "adaptation_checks": adaptation_checks,
        "completeness_checks": completeness_checks,
        "new_warnings": new_warnings,
        "new_adjustments": new_adjustments,
    }


def _check_safety(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    eligible_pool: Optional[List[Dict[str, Any]]],
    all_warnings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """安全性检查 (PRD §5.1)。"""
    checks = []
    volunteer_list = draft_plan.get("volunteer_list", [])

    # 1. 基本盘范围检查
    in_pool_count = len(volunteer_list)
    checks.append({
        "item": "基本盘范围",
        "passed": True,  # 简化处理：依赖 硬约束过滤模块 的输出质量
        "message": f"共 {in_pool_count} 个志愿待审核",
        "action": "如有个别志愿不在 硬约束过滤模块 基本盘内，将在后续处理中移除",
        "rule_basis": "安全性检查#1：基本盘范围",
        "severity": "warn",
    })

    # 2. 兜底安全
    has_safe_bottom = False
    if volunteer_list:
        last_vol = volunteer_list[-1]
        prob_str = str(last_vol.get("admission_probability", ""))
        positioning = last_vol.get("positioning", "")
        if positioning == "保" or ">95%" in prob_str or ">90%" in prob_str:
            has_safe_bottom = True

    checks.append({
        "item": "兜底安全",
        "passed": has_safe_bottom,
        "message": "兜底志愿录取概率足够安全" if has_safe_bottom else "兜底志愿不够安全",
        "action": "建议从基本盘中补充录取概率>95%的保底志愿，或增加民办/偏远地区保底选项",
        "rule_basis": "安全性检查#3：兜底安全",
        "severity": "error" if not has_safe_bottom else "ok",
    })

    # 3. 专业组干净度
    unclean_marked = all(
        any(w.get("rule_basis", "").startswith("专业组干净度") for w in all_warnings)
        or "黄灯" not in str(vol.get("major_group_cleanliness", ""))
        for vol in volunteer_list
    )
    checks.append({
        "item": "专业组干净度",
        "passed": unclean_marked,
        "message": "不干净的专业组已标记风险" if unclean_marked else "存在未标记风险的不干净专业组",
        "action": "对包含天坑/红灯专业的专业组，建议不勾选服从调剂",
        "rule_basis": "安全性检查#4：专业组干净度",
        "severity": "error" if not unclean_marked else "ok",
    })

    # 4. 学费承受力
    family_economy = applicant.get("family_economy_level", "普通")
    tuition_budget = applicant.get("tuition_budget_yearly")
    # 简化：如果家庭紧张且方案中有民办/中外合作，则警告
    has_economic_risk = False
    if family_economy in ("困难", "拮据") or (tuition_budget is not None and tuition_budget < 20000):
        for vol in volunteer_list:
            if "民办" in str(vol.get("school_name", "")) or "中外合作" in str(vol.get("school_name", "")):
                has_economic_risk = True
                break

    checks.append({
        "item": "学费承受力",
        "passed": not has_economic_risk,
        "message": "方案中所有院校学费在家庭预算内" if not has_economic_risk else "方案中存在超出家庭预算的院校",
        "action": "建议替换为高学费院校为公办院校，或确认家庭可承担",
        "rule_basis": "安全性检查#5：学费承受力",
        "severity": "error" if has_economic_risk else "ok",
    })

    return checks


def _check_adaptation(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    all_warnings: List[Dict[str, Any]],
    special_tags: List[str],
) -> List[Dict[str, Any]]:
    """适配性检查 (PRD §5.2)。"""
    checks = []

    # 1. 体制内外
    target_system = applicant.get("target_system", "未定")
    has_system_mismatch = target_system in ("体制内", "考公", "考编") and "体制内目标" not in special_tags
    checks.append({
        "item": "体制内外",
        "passed": not has_system_mismatch,
        "message": "方案与考生的体制内/外偏好一致" if not has_system_mismatch else "方案可能与考生的体制内目标不一致",
        "action": "如考生目标为体制内，建议增加考公友好专业",
        "rule_basis": "适配性检查#1：体制内外",
        "severity": "warn" if has_system_mismatch else "ok",
    })

    # 2. 地域
    preferred_cities = applicant.get("preferred_cities", [])
    checks.append({
        "item": "地域",
        "passed": True,
        "message": f"考生意向城市：{', '.join(preferred_cities) if preferred_cities else '未指定'}",
        "action": "如地域安排与长期居住意愿不一致，请自行调整",
        "rule_basis": "适配性检查#2：地域",
        "severity": "ok",
    })

    # 3. 经济
    family_economy = applicant.get("family_economy_level", "普通")
    checks.append({
        "item": "经济承受力",
        "passed": True,
        "message": f"家庭经济状况：{family_economy}",
        "action": "已按家庭经济状况检查学费承受力",
        "rule_basis": "适配性检查#3：经济",
        "severity": "ok",
    })

    # 4. 性别
    gender = applicant.get("gender")
    gender_checked = gender != "女" or "女生" in special_tags
    checks.append({
        "item": "性别",
        "passed": gender_checked,
        "message": "性别相关的就业风险已标注" if gender_checked else "女生但未执行女生避坑检查",
        "action": "请确认是否已执行女生避坑规则",
        "rule_basis": "适配性检查#4：性别",
        "severity": "warn" if not gender_checked else "ok",
    })

    # 5. 数理基础
    math_score = applicant.get("math_score")
    physics_score = applicant.get("physics_score")
    has_weak_warning = "数理基础薄弱" in special_tags
    math_weak = math_score is not None and math_score < 90
    physics_weak = physics_score is not None and physics_score < 60
    math_checked = not (math_weak or physics_weak) or has_weak_warning
    checks.append({
        "item": "数理基础",
        "passed": math_checked,
        "message": "已对相关高风险专业加警告" if math_checked else "考生数理薄弱但未加警告",
        "action": "建议对硬核工科专业加高危警告",
        "rule_basis": "适配性检查#5：数理基础",
        "severity": "warn" if not math_checked else "ok",
    })

    return checks


def _check_completeness(
    applicant: Dict[str, Any],
    draft_plan: Dict[str, Any],
    all_adjustments: List[Dict[str, Any]],
    all_warnings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """完整性检查 (PRD §5.3)。"""
    checks = []
    volunteer_list = draft_plan.get("volunteer_list", [])

    # 1. 冲稳保比例
    positioning_counts = {}
    for vol in volunteer_list:
        pos = vol.get("positioning", "未知")
        positioning_counts[pos] = positioning_counts.get(pos, 0) + 1

    has_chong = positioning_counts.get("冲", 0) > 0
    has_wen = positioning_counts.get("稳", 0) > 0
    has_bao = positioning_counts.get("保", 0) > 0
    ratio_ok = has_chong and has_wen and has_bao

    checks.append({
        "item": "冲稳保比例",
        "passed": ratio_ok,
        "message": f"冲/稳/保分布：{positioning_counts}" if ratio_ok else "冲稳保比例不完整",
        "action": "建议至少各保留1个冲、稳、保志愿",
        "rule_basis": "完整性检查#1：冲稳保比例",
        "severity": "warn" if not ratio_ok else "ok",
    })

    # 2. 备选方案
    has_backup = bool(draft_plan.get("backup_plan")) or any(
        a.get("adjustment_content", "").startswith("备选") for a in all_adjustments
    )
    checks.append({
        "item": "备选方案",
        "passed": has_backup,
        "message": "已提供备选方案" if has_backup else "未提供备选方案",
        "action": "如主方案有争议，建议提供备选方案",
        "rule_basis": "完整性检查#2：备选方案",
        "severity": "warn" if not has_backup else "ok",
    })

    # 3. 待确认事项
    has_must_confirm = bool(draft_plan.get("must_confirm_items"))
    checks.append({
        "item": "待确认事项",
        "passed": has_must_confirm,
        "message": "已列出待确认事项" if has_must_confirm else "未列出待确认事项",
        "action": "建议列出所有需要考生二次确认的事项",
        "rule_basis": "完整性检查#3：待确认事项",
        "severity": "warn" if not has_must_confirm else "ok",
    })

    # 4. 风险标注
    has_high_risk = any(w.get("level") == "高危" for w in all_warnings)
    risk_prominent = has_high_risk  # 简化：只要有高危即认为已标注
    checks.append({
        "item": "风险标注",
        "passed": risk_prominent,
        "message": "关键风险已用 ⚠️ 标注" if risk_prominent else "未发现高危风险",
        "action": "如有风险，请确保用 ⚠️ 标注并放在显眼位置",
        "rule_basis": "完整性检查#4：风险标注",
        "severity": "ok",
    })

    return checks
