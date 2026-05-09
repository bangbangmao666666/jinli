"""调剂策略生成模块。

针对每个专业组给出是否建议勾选服从调剂的明确建议。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .cleanliness_checker import CLEANLINESS_CLEAN, CLEANLINESS_BASIC, CLEANLINESS_DIRTY


def generate_adjustment_advice(
    volunteer: Dict[str, Any],
    accept_adjustment_preference: str = "仅接受干净组调剂",
) -> Dict[str, Any]:
    """生成单个志愿的调剂建议。"""
    cleanliness = volunteer.get("cleanliness", "")
    school_name = volunteer.get("school_name", "")
    major_group = volunteer.get("major_group", "")
    
    advice = {
        "serial_number": volunteer.get("serial_number", 0),
        "school_name": school_name,
        "major_group": major_group,
        "suggestion": "",
        "reason": "",
    }
    
    # 根据专业组干净度和用户偏好给出建议
    if cleanliness == CLEANLINESS_CLEAN:
        if accept_adjustment_preference in ["是", "仅接受干净组调剂"]:
            advice["suggestion"] = "建议勾选服从调剂"
            advice["reason"] = "专业组干净，即使调剂也可接受，勾选后可以增加录取概率，避免退档"
        else:
            advice["suggestion"] = "不勾选服从调剂"
            advice["reason"] = "根据您的偏好，不勾选服从调剂"
    
    elif cleanliness == CLEANLINESS_BASIC:
        # 检查分数优势
        score_advantage = volunteer.get("score_advantage", 0)
        if score_advantage >= 5:
            if accept_adjustment_preference in ["是", "仅接受干净组调剂"]:
                advice["suggestion"] = "建议勾选服从调剂"
                advice["reason"] = "分数优势较大，大概率录到目标专业，即使调剂也可接受"
            else:
                advice["suggestion"] = "不勾选服从调剂"
                advice["reason"] = "根据您的偏好，不勾选服从调剂"
        else:
            if accept_adjustment_preference == "是":
                advice["suggestion"] = "谨慎勾选服从调剂"
                advice["reason"] = "分数优势不足，可能被调剂到黄灯专业，请确认是否可接受"
            else:
                advice["suggestion"] = "不勾选服从调剂"
                advice["reason"] = "根据您的偏好，不勾选服从调剂"
    
    elif cleanliness == CLEANLINESS_DIRTY:
        score_advantage = volunteer.get("score_advantage", 0)
        if score_advantage >= 10:
            advice["suggestion"] = "可考虑不勾选服从调剂"
            advice["reason"] = "分数优势极大，大概率录到目标专业，不勾选避免被调剂到红灯专业"
        else:
            advice["suggestion"] = "不建议填报该组"
            advice["reason"] = "要么录不到目标专业，要么被调剂到红灯专业，风险太大"
    
    else:
        advice["suggestion"] = "请自行决定是否勾选服从调剂"
        advice["reason"] = "专业组信息不足，无法判断干净度"
    
    return advice


def generate_all_adjustment_advice(
    volunteers: List[Dict[str, Any]],
    accept_adjustment_preference: str = "仅接受干净组调剂",
) -> Dict[str, Any]:
    """生成所有志愿的调剂建议。"""
    suggestions = []
    for v in volunteers:
        advice = generate_adjustment_advice(v, accept_adjustment_preference)
        suggestions.append(advice)
    
    return {
        "general_principle": "只在干净的专业组勾选服从调剂；不干净的专业组除非分数有绝对优势（超过专业最低分10分以上），否则不要勾选服从调剂",
        "adjustment_suggestion_list": suggestions,
    }
