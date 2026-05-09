"""规则引擎：加载和执行各规则集。

根据考生画像自动匹配适用的规则集，并返回规则执行结果。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import data_loader
from .exceptions import DataSourceUnavailableError


class RuleEngine:
    """规则引擎：管理所有特殊适配规则的加载与执行。"""

    def __init__(self, data_dir: Optional[Any] = None) -> None:
        self.data_dir = data_dir
        self._rules: Dict[str, Any] = {}
        self._warnings: List[str] = []
        self._load_all()

    def _load_all(self) -> None:
        """加载所有规则库，缺失时记录警告但不报错。"""
        loaders = {
            "female_risk": data_loader.load_female_risk_majors,
            "civil_service": data_loader.load_civil_service_major_catalog,
            "selector_university": data_loader.load_selector_university_list,
            "special_adjustment": data_loader.load_special_adjustment_rules,
            "hidden_threshold": data_loader.load_hidden_threshold_rules,
            "gender_employment": data_loader.load_gender_employment_ratio,
            "upgrade_to_bachelor": data_loader.load_upgrade_to_bachelor_data,
        }
        for key, loader in loaders.items():
            try:
                self._rules[key] = loader(self.data_dir)
            except DataSourceUnavailableError:
                self._rules[key] = None
                self._warnings.append(f"规则库 '{key}' 缺失，相关适配规则将跳过")

    @property
    def warnings(self) -> List[str]:
        return self._warnings

    def get_rule(self, key: str) -> Optional[Dict[str, Any]]:
        return self._rules.get(key)

    def has_rule(self, key: str) -> bool:
        return self._rules.get(key) is not None

    def get_female_risk_majors(self) -> List[Dict[str, Any]]:
        rule = self._rules.get("female_risk")
        if not rule:
            return []
        return rule.get("high_risk_majors", [])

    def get_female_recommended_majors(self) -> List[Dict[str, Any]]:
        rule = self._rules.get("female_risk")
        if not rule:
            return []
        return rule.get("recommended_majors", [])

    def get_civil_service_friendly_categories(self) -> List[str]:
        rule = self._rules.get("special_adjustment")
        if not rule:
            return []
        rs = rule.get("rule_set_3_system_target", {})
        return rs.get("civil_service_friendly_categories", [])

    def get_math_threshold(self) -> int:
        rule = self._rules.get("special_adjustment")
        if not rule:
            return 90
        rs = rule.get("rule_set_2_math_physics_weak", {})
        return rs.get("math_threshold", 90)

    def get_physics_threshold(self) -> int:
        rule = self._rules.get("special_adjustment")
        if not rule:
            return 60
        rs = rule.get("rule_set_2_math_physics_weak", {})
        return rs.get("physics_threshold", 60)

    def get_high_math_majors(self) -> List[str]:
        rule = self._rules.get("special_adjustment")
        if not rule:
            return []
        rs = rule.get("rule_set_2_math_physics_weak", {})
        return rs.get("high_math_majors", [])

    def get_quality_vocational_directions(self) -> List[str]:
        rule = self._rules.get("special_adjustment")
        if not rule:
            return []
        rs = rule.get("rule_set_4_low_score", {})
        return rs.get("quality_vocational_directions", [])

    def is_female_high_risk_major(self, major_name: str) -> bool:
        """判断专业是否在女生高风险列表中（支持模糊匹配）。"""
        for item in self.get_female_risk_majors():
            if item.get("major_name") == major_name:
                return True
        # 内置兜底规则（PRD 明确列出的高风险专业）
        builtin_high_risk = [
            "土木工程", "道路桥梁与渡河工程", "港口航道与海岸工程",
            "采矿工程", "石油工程", "地质工程",
            "机械设计制造及其自动化", "冶金工程", "船舶与海洋工程",
        ]
        return any(risk in major_name for risk in builtin_high_risk)

    def is_high_math_demand_major(self, major_name: str) -> bool:
        """判断专业是否对数理要求极高。"""
        high_math_patterns = [
            "电子信息", "计算机", "自动化", "通信工程", "人工智能",
            "数学与应用数学", "物理学", "统计学", "信息与计算科学",
        ]
        return any(pat in major_name for pat in high_math_patterns)

    def is_civil_service_friendly_major(self, major_name: str, major_category: Optional[str] = None) -> bool:
        """判断专业是否属于考公友好大类。"""
        friendly_categories = self.get_civil_service_friendly_categories()
        if major_category and major_category in friendly_categories:
            return True
        friendly_keywords = ["法学", "财政", "会计", "汉语言", "中文", "工商管理", "计算机", "行政管理"]
        return any(kw in major_name for kw in friendly_keywords)
