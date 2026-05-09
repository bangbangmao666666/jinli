"""填报规则匹配模块。

根据考生省份匹配对应的志愿填报规则。
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from .data_loader import get_province_rule_or_default


def match_province_rules(province: str) -> Tuple[Dict[str, Any], bool]:
    """匹配省份填报规则。

    返回 (规则字典, 是否为默认规则)
    """
    return get_province_rule_or_default(province)


def get_max_volunteer_count(rules: Dict[str, Any]) -> int:
    """获取最大可填报志愿数。"""
    return rules.get("max_volunteer_count", 45)


def get_volunteer_mode(rules: Dict[str, Any]) -> str:
    """获取志愿模式（平行志愿/顺序志愿）。"""
    return rules.get("volunteer_mode", "平行志愿")


def get_admission_rule_desc(rules: Dict[str, Any]) -> str:
    """获取投档规则描述。"""
    return rules.get("admission_rule_desc", "分数优先、遵循志愿、一轮投档")
