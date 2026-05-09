"""专业组干净度检查模块。

检查每个专业组内是否包含红灯/天坑专业，评定干净度等级。
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

CLEANLINESS_CLEAN = "🟢 干净"
CLEANLINESS_BASIC = "🟡 基本干净"
CLEANLINESS_DIRTY = "🔴 不干净"


def check_major_group_cleanliness(
    group_majors: List[str],
    red_flag_majors: Set[str],
    yellow_flag_majors: Set[str],
) -> Tuple[str, List[str]]:
    """检查专业组干净度。

    Args:
        group_majors: 专业组内的所有专业列表
        red_flag_majors: 红灯专业集合
        yellow_flag_majors: 黄灯专业集合

    Returns:
        (干净度等级, 问题专业列表)
    """
    # 检查是否有红灯专业
    red_in_group = [m for m in group_majors if m in red_flag_majors]
    if red_in_group:
        return CLEANLINESS_DIRTY, red_in_group
    
    # 检查是否有黄灯专业
    yellow_in_group = [m for m in group_majors if m in yellow_flag_majors]
    if yellow_in_group:
        return CLEANLINESS_BASIC, yellow_in_group
    
    # 全是绿灯专业
    return CLEANLINESS_CLEAN, []


def extract_red_flag_majors(passed_majors: List[Dict[str, Any]]) -> Set[str]:
    """从 专业评估模块 输出中提取红灯专业列表。"""
    red_flags = set()
    for major in passed_majors:
        if major.get("traffic_light") == "红灯":
            red_flags.add(major.get("major_name", ""))
    return red_flags


def extract_yellow_flag_majors(passed_majors: List[Dict[str, Any]]) -> Set[str]:
    """从 专业评估模块 输出中提取黄灯专业列表。"""
    yellow_flags = set()
    for major in passed_majors:
        if major.get("traffic_light") == "黄灯":
            yellow_flags.add(major.get("major_name", ""))
    return yellow_flags


def check_all_groups(
    recommended_schools: List[Dict[str, Any]],
    red_flag_majors: Set[str],
    yellow_flag_majors: Set[str],
) -> List[Dict[str, Any]]:
    """检查所有推荐院校的专业组干净度。"""
    checked = []
    for school in recommended_schools:
        school_copy = dict(school)
        # 检查专业组
        if "major_groups" in school_copy:
            checked_groups = []
            for group in school_copy["major_groups"]:
                group_copy = dict(group)
                group_majors = group_copy.get("majors", [])
                cleanliness, issues = check_major_group_cleanliness(
                    group_majors, red_flag_majors, yellow_flag_majors
                )
                group_copy["cleanliness"] = cleanliness
                group_copy["issue_majors"] = issues
                checked_groups.append(group_copy)
            school_copy["major_groups"] = checked_groups
        else:
            # 单个专业的情况，创建虚拟专业组
            major_name = school_copy.get("major_name", "")
            group_majors = [major_name] if major_name else []
            cleanliness, issues = check_major_group_cleanliness(
                group_majors, red_flag_majors, yellow_flag_majors
            )
            school_copy["cleanliness"] = cleanliness
            school_copy["issue_majors"] = issues
        
        checked.append(school_copy)
    
    return checked


def get_cleanliness_desc(cleanliness: str) -> str:
    """获取干净度描述文本。"""
    if cleanliness == CLEANLINESS_CLEAN:
        return "组内所有专业均为绿灯/黄灯，均可接受"
    elif cleanliness == CLEANLINESS_BASIC:
        return "组内有个别黄灯专业但无红灯专业"
    elif cleanliness == CLEANLINESS_DIRTY:
        return "组内包含红灯/天坑专业"
    return "干净度未知"
