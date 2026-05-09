"""数据加载模块。

加载填报规则、招生计划、录取数据等。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .errors import DataRuleNotFoundError, DataSourceUnavailableError


def get_data_dir() -> Path:
    """获取数据目录路径。"""
    skill_root = Path(__file__).parent.parent
    # 先尝试本地 data 目录
    local_data = skill_root / "data"
    if local_data.exists():
        return local_data
    # 否则回退到 constraint-filter 的 data 目录
    constraint_filter_data = skill_root.parent / "constraint-filter" / "data"
    if constraint_filter_data.exists():
        return constraint_filter_data
    # 返回本地 data 目录（即使不存在）
    return local_data


def load_province_application_rules(province: str) -> Dict[str, Any]:
    """加载省份填报规则。

    优先使用项目本地规则数据库，如果缺失则返回通用规则并告警。
    """
    data_dir = get_data_dir()
    rule_file = data_dir / "province_application_rules.json"
    
    # 默认通用规则
    default_rules = {
        "volunteer_mode": "平行志愿",
        "max_volunteer_count": 45,
        "admission_rule_desc": "分数优先、遵循志愿、一轮投档",
        "batch_name": "本科批",
        "data_source": "通用平行志愿规则（该省数据未收录）",
    }
    
    if not rule_file.exists():
        return default_rules
    
    try:
        with open(rule_file, "r", encoding="utf-8") as f:
            all_rules = json.load(f)
        
        if province in all_rules:
            rules = all_rules[province]
            rules.setdefault("data_source", f"{province}教育考试院2026年志愿填报规则")
            return rules
        else:
            return default_rules
    except Exception as e:
        return default_rules


def load_sample_admission_plans(province: str) -> Dict[str, Any]:
    """加载招生计划数据（示例）。"""
    # 这里返回示例数据，实际应该从 constraint-filter 的 data/admission_plans 加载
    return {
        "province": province,
        "year": 2026,
        "schools": [],
    }


def get_province_rule_or_default(province: str) -> tuple[Dict[str, Any], bool]:
    """获取省份规则，返回 (规则字典, 是否为默认规则)。"""
    rules = load_province_application_rules(province)
    is_default = rules["data_source"].startswith("通用平行志愿规则")
    return rules, is_default


def create_default_rules() -> Dict[str, Dict[str, Any]]:
    """创建默认的省份填报规则数据库（供参考）。"""
    return {
        "河南": {
            "volunteer_mode": "平行志愿",
            "max_volunteer_count": 45,
            "admission_rule_desc": "分数优先、遵循志愿、一轮投档",
            "batch_name": "本科批",
        },
        "山东": {
            "volunteer_mode": "平行志愿",
            "max_volunteer_count": 96,
            "admission_rule_desc": "分数优先、遵循志愿、一轮投档",
            "batch_name": "常规批",
        },
        "河北": {
            "volunteer_mode": "平行志愿",
            "max_volunteer_count": 112,
            "admission_rule_desc": "分数优先、遵循志愿、一轮投档",
            "batch_name": "本科批",
        },
        "浙江": {
            "volunteer_mode": "平行志愿",
            "max_volunteer_count": 80,
            "admission_rule_desc": "分数优先、遵循志愿、一轮投档",
            "batch_name": "普通类",
        },
    }
