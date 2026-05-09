"""输出格式化模块。

格式化最终输出结果。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .cleanliness_checker import get_cleanliness_desc
from .hidden_threshold_checker import get_threshold_prompt


def format_volunteer_list(volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化志愿列表。"""
    formatted = []
    for v in volunteers:
        # 优先使用具体专业名称，如果没有则用专业组中的专业
        major_name = v.get("major_name", "")
        if not major_name:
            major_group_majors = v.get("major_group_majors", [])
            if major_group_majors:
                major_name = major_group_majors[0]
        
        formatted_v = {
            "serial_number": v.get("serial_number", 0),
            "school_name": v.get("school_name", ""),
            "major_name": major_name,
            "school_major_line": f"{v.get('school_name', '')} - {major_name}",
            "major_group": v.get("major_group", ""),
            "major_group_majors": v.get("major_group_majors", []),
            "major_group_cleanliness": v.get("cleanliness", ""),
            "major_group_cleanliness_desc": get_cleanliness_desc(v.get("cleanliness", "")),
            "positioning": v.get("positioning", ""),
            "rank_ratio": v.get("rank_ratio_value"),
            "admission_probability": v.get("admission_probability", "未知"),
            "risk_desc": v.get("risk_desc", ""),
            "hidden_threshold_check": get_threshold_prompt(v.get("hidden_thresholds", {})),
            "sort_reason": v.get("sort_reason", ""),
        }
        formatted.append(formatted_v)
    return formatted


def format_volunteer_table(volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """生成志愿填报表格格式，用于清晰展示。"""
    table = []
    for v in volunteers:
        # 优先使用具体专业名称，如果没有则用专业组中的专业
        major_name = v.get("major_name", "")
        if not major_name:
            major_group_majors = v.get("major_group_majors", [])
            if major_group_majors:
                major_name = major_group_majors[0]
        
        school_name = v.get("school_name", "")
        
        table.append({
            "序号": v.get("serial_number", 0),
            "学校名称": school_name,
            "专业名称": major_name,
            "学校+专业": f"{school_name} - {major_name}",
            "志愿类型": v.get("positioning", ""),
            "rank_ratio": v.get("rank_ratio_value"),
            "录取概率": v.get("admission_probability", "未知"),
            "专业组干净度": v.get("cleanliness", ""),
        })
    return table


def format_warnings(
    input_warnings: List[str],
    is_default_rule: bool,
    is_radical: bool,
) -> List[str]:
    """格式化警告信息。"""
    warnings = []
    
    # 输入警告
    warnings.extend(input_warnings)
    
    # 省份规则警告
    if is_default_rule:
        warnings.append("⚠️ 该省填报规则未收录，以下方案基于通用平行志愿规则生成，请您根据该省实际可填志愿数和规则调整")
    
    # 激进策略警告
    if is_radical:
        warnings.append("⚠️ 您选择了激进型策略，冲志愿比例较高，滑档风险也相应增加，请谨慎考虑。普通家庭建议优先选择保守型或适中型策略")
    
    # 通用警告
    warnings.append("⚠️ 本方案基于历史录取数据生成，当年录取情况可能有变化，仅供参考")
    warnings.append("⚠️ 平行志愿只有一次投档机会，一旦被投档后又被退档，将直接落入征集志愿或下一批次，请谨慎选择是否服从调剂")
    warnings.append("⚠️ 请务必在官方填报系统截止前至少1小时提交，避免网络拥堵导致提交失败")
    
    return warnings


def format_basic_info(
    applicant_profile: Dict[str, Any],
    application_rules: Dict[str, Any],
    strategy_tone: str,
) -> Dict[str, Any]:
    """格式化基本信息。"""
    return {
        "applicant_summary": {
            "province": applicant_profile.get("province", ""),
            "total_score": applicant_profile.get("total_score", 0),
            "provincial_rank": applicant_profile.get("provincial_rank", 0),
            "subject_category": applicant_profile.get("subject_category", ""),
            "selected_subjects": applicant_profile.get("selected_subjects", []),
        },
        "application_rule": {
            "volunteer_mode": application_rules.get("volunteer_mode", "平行志愿"),
            "max_volunteer_count": application_rules.get("max_volunteer_count", 45),
            "admission_rule_desc": application_rules.get("admission_rule_desc", ""),
            "batch_name": application_rules.get("batch_name", "本科批"),
            "data_source": application_rules.get("data_source", ""),
        },
        "strategy_tone": strategy_tone,
        "strategy_reason": "考生为普通家庭，试错成本高，优先确保录取到好就业的专业，兼顾适度冲好学校",
        "risk_warning": "⚠️ 高考志愿填报窗口极短，通常出分后仅有3~7天，请立即开始行动，不要等待。本方案为辅助参考，最终填报请以官方招生计划和招生章程为准。",
    }


def format_volunteer_segments(
    volunteers: List[Dict[str, Any]],
    strategy_config: Dict[str, Any],
) -> Dict[str, Any]:
    """按冲稳保分段格式化志愿。
    
    Args:
        volunteers: 完整的志愿列表（已排序）
        strategy_config: 策略配置
        
    Returns:
        分段展示的志愿数据
    """
    # 按志愿类型分类
    sprint_volunteers = []
    stable_volunteers = []
    guarantee_volunteers = []
    
    for v in volunteers:
        positioning = v.get("positioning", "")
        if positioning == "冲":
            sprint_volunteers.append(v)
        elif positioning == "稳":
            stable_volunteers.append(v)
        elif positioning == "保":
            guarantee_volunteers.append(v)
    
    # 创建分段表格
    sprint_table = _create_segment_table(sprint_volunteers)
    stable_table = _create_segment_table(stable_volunteers)
    guarantee_table = _create_segment_table(guarantee_volunteers)
    
    return {
        "冲段": {
            "志愿数量": len(sprint_table),
            "录取概率范围": "约30%-60%",
            "方向说明": "冲刺更好的院校和专业，即使录取概率较低，放在前面不影响后续稳保志愿",
            "参考院校": _extract_school_list(sprint_volunteers),
            "志愿表格": sprint_table,
        },
        "稳段": {
            "志愿数量": len(stable_table),
            "录取概率范围": "约60%-90%",
            "方向说明": "核心目标志愿，录取概率较高，专业匹配度高",
            "参考院校": _extract_school_list(stable_volunteers),
            "志愿表格": stable_table,
        },
        "保段": {
            "志愿数量": len(guarantee_table),
            "录取概率范围": "安全兜底 (80%以上，rank_ratio 越低概率越高)",
            "方向说明": "保底志愿，确保不滑档",
            "参考院校": _extract_school_list(guarantee_volunteers),
            "志愿表格": guarantee_table,
        },
    }


def _create_segment_table(volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为一段志愿创建表格。"""
    table = []
    for v in volunteers:
        major_name = v.get("major_name", "")
        if not major_name:
            major_group_majors = v.get("major_group_majors", [])
            if major_group_majors:
                major_name = major_group_majors[0]
        
        school_name = v.get("school_name", "")
        
        table.append({
            "序号": v.get("serial_number", 0),
            "学校名称": school_name,
            "专业名称": major_name,
            "学校+专业": f"{school_name} - {major_name}",
            "志愿类型": v.get("positioning", ""),
            "rank_ratio": v.get("rank_ratio_value"),
            "录取概率": v.get("admission_probability", "未知"),
            "专业组干净度": v.get("cleanliness", ""),
        })
    return table


def _extract_school_list(volunteers: List[Dict[str, Any]]) -> List[str]:
    """从志愿列表中提取学校名称列表（去重）。"""
    schools = set()
    for v in volunteers:
        school = v.get("school_name", "")
        if school:
            schools.add(school)
    return sorted(list(schools))


def format_strategy_summary_table(
    volunteer_segments: Dict[str, Any],
    strategy_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """生成二、各段志愿配置细则表格。"""
    summary_table = []
    
    risk_preference = strategy_config.get("risk_preference", "保守型")
    
    # 确定数量占比
    ratio_map = {
        "保守型": {"冲段": "10%", "稳段": "50%", "保段": "40%"},
        "适中型": {"冲段": "20%", "稳段": "50%", "保段": "30%"},
        "激进型": {"冲段": "30%", "稳段": "45%", "保段": "25%"},
    }
    ratio_config = ratio_map.get(risk_preference, ratio_map["保守型"])
    
    # 冲段
    sprint_info = volunteer_segments.get("冲段", {})
    if sprint_info:
        summary_table.append({
            "志愿段": "冲段",
            "数量占比": ratio_config.get("冲段", "20%"),
            "对应志愿数": f"{sprint_info.get('志愿数量', 0)}个",
            "录取概率区间": sprint_info.get("录取概率范围", "30%-60%"),
            "核心报考方向": sprint_info.get("方向说明", ""),
            "参考院校举例": "、".join(sprint_info.get("参考院校", [])),
        })
    
    # 稳段
    stable_info = volunteer_segments.get("稳段", {})
    if stable_info:
        summary_table.append({
            "志愿段": "稳段",
            "数量占比": ratio_config.get("稳段", "50%"),
            "对应志愿数": f"{stable_info.get('志愿数量', 0)}个",
            "录取概率区间": stable_info.get("录取概率范围", "60%-90%"),
            "核心报考方向": stable_info.get("方向说明", ""),
            "参考院校举例": "、".join(stable_info.get("参考院校", [])),
        })
    
    # 保段
    guarantee_info = volunteer_segments.get("保段", {})
    if guarantee_info:
        ref_schools = "、".join(guarantee_info.get("参考院校", []))
        summary_table.append({
            "志愿段": "保段",
            "数量占比": ratio_config.get("保段", "40%"),
            "对应志愿数": f"{guarantee_info.get('志愿数量', 0)}个",
            "录取概率区间": guarantee_info.get("录取概率范围", "90%以上"),
            "核心报考方向": guarantee_info.get("方向说明", ""),
            "参考院校举例": ref_schools,
        })
    
    return summary_table
