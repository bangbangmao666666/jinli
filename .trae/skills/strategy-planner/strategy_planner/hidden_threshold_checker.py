"""隐藏门槛核查模块。

核查每个院校专业的隐藏报考门槛，提示用户自行确认。
"""
from __future__ import annotations

from typing import Any, Dict, List


def check_hidden_thresholds(
    school_major: Dict[str, Any],
    applicant_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """核查单个院校专业的隐藏门槛。

    由于招生章程解析复杂，这里主要生成提示信息，
    具体核查由用户对照招生章程完成。
    """
    threshold_info = {
        "needs_check": True,
        "check_items": [
            "单科成绩要求",
            "专业级差",
            "体检限制",
            "外语语种限制",
            "男女比例限制",
        ],
        "prompt": "请自行核查该校招生章程中的报考条件",
        "school_name": school_major.get("school_name", ""),
        "major_name": school_major.get("major_name", ""),
    }
    
    # 如果已有部分信息，补充进去
    if "single_subject_requirements" in school_major:
        threshold_info["single_subject_requirements"] = school_major["single_subject_requirements"]
    
    if "physical_requirements" in school_major:
        threshold_info["physical_requirements"] = school_major["physical_requirements"]
    
    return threshold_info


def check_all_thresholds(
    recommended_schools: List[Dict[str, Any]],
    applicant_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """核查所有推荐院校的隐藏门槛。"""
    checked = []
    for school in recommended_schools:
        school_copy = dict(school)
        threshold_info = check_hidden_thresholds(school_copy, applicant_profile)
        school_copy["hidden_thresholds"] = threshold_info
        checked.append(school_copy)
    return checked


def get_threshold_prompt(threshold_info: Dict[str, Any]) -> str:
    """获取门槛核查提示文本。"""
    base_prompt = threshold_info.get("prompt", "请核查该校招生章程")
    check_items = threshold_info.get("check_items", [])
    if check_items:
        items_str = "、".join(check_items)
        return f"⚠️ {base_prompt}：{items_str}"
    return f"⚠️ {base_prompt}"
