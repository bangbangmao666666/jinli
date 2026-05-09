"""体检限制过滤（第四层）。

核心原则：以 physical_restrictions.json 为唯一依据。
映射表未覆盖 → physical_check = not_verified + warnings，绝不自行推断。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def evaluate(
    major: Dict[str, Any],
    physical_exam: Optional[Dict[str, Any]],
    gender: str,
    rules_table: Dict[str, Any],
) -> Tuple[bool, Optional[str], bool]:
    """判定某个专业是否被体检维度排除。

    返回 (kept, exclude_reason, verified)：
    - kept:           是否保留该专业
    - exclude_reason: 若被排除，说明原因
    - verified:       映射表是否覆盖了该专业的体检要求（False → warnings）
    """
    # 无体检信息 → 全部保留，verified=False
    if not physical_exam:
        return True, None, False

    rules = rules_table.get("rules", [])
    applicable_rules: List[Dict[str, Any]] = []

    for rule in rules:
        if _rule_matches_applicant(rule, physical_exam, gender):
            if _rule_matches_major(rule, major):
                applicable_rules.append(rule)

    if applicable_rules:
        # 取第一条作为排除理由即可（多条同时命中时合并）
        reasons = [f"[{r['rule_id']}] {r['reason']}" for r in applicable_rules]
        return False, "体检维度：" + "；".join(reasons), True

    # 判断该专业是否"显式声明了体检限制但映射表未登记"
    # → 这是 L2 数据缺失（PRD §五 5.3），标记 not_verified
    notes = major.get("physical_requirement_notes") or []
    note_mentions_limit = any(
        kw in note for note in notes for kw in ["色盲", "色弱", "视力", "身高", "听力"]
    )
    if note_mentions_limit:
        # 专业原文有限制，但我们没有规则兜底
        return True, None, False
    return True, None, True


def _rule_matches_applicant(rule: Dict[str, Any], pe: Dict[str, Any], gender: str) -> bool:
    cond = rule.get("condition", {})
    field = cond.get("field")
    value = cond.get("value")

    if field == "color_blindness":
        actual = pe.get("color_blindness")
        if actual in (None, "未知"):
            return False
        if value == "色盲":
            return actual == "色盲"
        if value == "色弱":
            # 色弱规则对色盲者同样适用（色盲 ⊇ 色弱）
            return actual in ("色弱", "色盲")
        return False

    if field == "vision_any_lt":
        l, r = pe.get("vision_left"), pe.get("vision_right")
        if l is None and r is None:
            return False
        worst = min(x for x in (l, r) if x is not None)
        return worst < value

    if field == "height_cm_lt":
        h = pe.get("height_cm")
        if h is None:
            return False
        rule_gender = cond.get("gender")
        if rule_gender and rule_gender != gender:
            return False
        return h < value

    if field == "hearing_normal":
        actual = pe.get("hearing_normal")
        if actual is None:
            return False
        return actual == value  # value 通常为 False

    # 未识别的 field → 不触发规则（更严谨的做法是抛错，但体检字段类型较多，
    # 保持保守：未识别规则不生效即可，等同于"数据缺失"的处理）
    return False


def _rule_matches_major(rule: Dict[str, Any], major: Dict[str, Any]) -> bool:
    name = major.get("major_name", "")
    category = major.get("major_category", "")
    if name and name in rule.get("affected_major_names", []):
        return True
    for cat in rule.get("affected_major_categories", []):
        # 容忍"X类" <-> "X"的包含关系；以规则字符串为子串匹配
        if cat and (cat in name or cat == category or (category and cat in category)):
            return True
    return False


def collect_missing_fields_warning(physical_exam: Optional[Dict[str, Any]]) -> List[str]:
    """检查哪些体检字段未提供，生成 warnings。"""
    if not physical_exam:
        return [
            "体检维度未过滤，结果可能包含该考生体检不符合的专业，请自行核对。"
        ]
    warnings: List[str] = []
    if physical_exam.get("color_blindness") in (None, "未知"):
        warnings.append("体检字段 color_blindness 为'未知'，色觉维度未过滤，化学/医学等相关专业请自行核对。")
    if physical_exam.get("vision_left") is None and physical_exam.get("vision_right") is None:
        warnings.append("体检字段视力为空，飞行/航海等视力敏感专业已保留在池中，请自行核实。")
    if physical_exam.get("height_cm") is None:
        warnings.append("体检字段 height_cm 为空，部分有身高要求的专业（如空乘、国防生）已保留在池中，请自行核实。")
    if physical_exam.get("hearing_normal") is None:
        warnings.append("体检字段 hearing_normal 为空，听力敏感专业已保留在池中，请自行核实。")
    return warnings
