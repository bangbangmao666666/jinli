"""志愿顺序排列模块。

按照冲→稳→保的顺序排列志愿，同一档位内按优先级排序。
"""
from __future__ import annotations

from typing import Any, Dict, List


def rank_ratio_to_probability(ratio: float) -> float:
    """将 constraint-filter 的 rank_ratio_value 转换为录取概率估算值。

    rank_ratio = 考生位次 / 历史最低录取位次加权平均
    ratio 越小表示考生越强，录取概率越高。

    分段线性映射（与 rank_tier._classify 的档位边界对齐）：
      ≤ 0.70 (极保) → 0.97
      0.70–1.00 (保) → 0.97 ~ 0.80
      1.00–1.20 (稳) → 0.80 ~ 0.60
      1.20–1.50 (冲) → 0.60 ~ 0.30
      > 1.50  (极冲) → < 0.30
    """
    if ratio is None:
        return 0.50
    if ratio <= 0.70:
        return 0.97
    if ratio <= 1.00:
        return round(0.97 - (ratio - 0.70) / 0.30 * 0.17, 4)
    if ratio <= 1.20:
        return round(0.80 - (ratio - 1.00) / 0.20 * 0.20, 4)
    if ratio <= 1.50:
        return round(0.60 - (ratio - 1.20) / 0.30 * 0.30, 4)
    return max(0.05, round(0.30 - (ratio - 1.50) * 0.50, 4))


def sort_volunteers(
    volunteers: List[Dict[str, Any]],
    strategy_config: Dict[str, Any],
    target_sprint_schools: List[str] = None,
) -> List[Dict[str, Any]]:
    """排序志愿。

    Args:
        volunteers: 待排序的志愿列表
        strategy_config: 策略配置（包含冲稳保数量）
        target_sprint_schools: 用户指定的冲刺目标院校

    Returns:
        排序后的志愿列表
    """
    # 分类志愿
    sprint_volunteers = []
    stable_volunteers = []
    guarantee_volunteers = []
    unknown_volunteers = []

    for v in volunteers:
        positioning = v.get("positioning", "")
        if positioning == "冲":
            sprint_volunteers.append(v)
        elif positioning == "稳":
            stable_volunteers.append(v)
        elif positioning == "保":
            guarantee_volunteers.append(v)
        else:
            unknown_volunteers.append(v)

    # 对每类进行内部排序
    sorted_sprint = _sort_sprint_group(sprint_volunteers, target_sprint_schools or [])
    sorted_stable = _sort_stable_group(stable_volunteers)
    sorted_guarantee = _sort_guarantee_group(guarantee_volunteers)

    # 按策略配置截取对应数量
    # 当候选池总量小于系统按 max_volunteer_count 算出的目标数时，
    # 改为按实际池子大小重新推算各段数量，避免冲段比例虚高
    sprint_count = strategy_config.get("sprint_count", 5)
    stable_count = strategy_config.get("stable_count", 22)
    guarantee_count = strategy_config.get("guarantee_count", 18)

    total_pool = len(sorted_sprint) + len(sorted_stable) + len(sorted_guarantee)
    total_target = sprint_count + stable_count + guarantee_count
    if 0 < total_pool < total_target:
        # 从 strategy_config 反推比例字符串（如 "9%"）得到浮点数
        def _parse_ratio(key: str, fallback: float) -> float:
            raw = strategy_config.get(key, "")
            try:
                return int(str(raw).rstrip("%")) / 100
            except (ValueError, AttributeError):
                return fallback

        sprint_ratio = _parse_ratio("sprint_ratio", 0.1)
        stable_ratio = _parse_ratio("stable_ratio", 0.5)

        sprint_count = max(1, round(total_pool * sprint_ratio))
        stable_count = max(1, round(total_pool * stable_ratio))
        guarantee_count = max(1, total_pool - sprint_count - stable_count)

        # 冲档候选不足时，多余名额归到保段
        if sprint_count > len(sorted_sprint):
            guarantee_count += sprint_count - len(sorted_sprint)
            sprint_count = len(sorted_sprint)

    # 冲档候选过多时，超出部分降级到稳段（不丢弃）——无论 pool 大小均需执行
    if sprint_count < len(sorted_sprint):
        demoted = sorted_sprint[sprint_count:]
        sorted_sprint = sorted_sprint[:sprint_count]
        # 降级时更新 positioning 标记，避免后续分组错位
        for v in demoted:
            v["positioning"] = "稳"
        # 合并降级冲与原始稳后，必须重新统一排序，否则降级冲会全部挤在原始稳前面
        sorted_stable = _sort_stable_group(demoted + sorted_stable)
    
    final_sprint = sorted_sprint[:sprint_count]
    final_stable = sorted_stable[:stable_count]
    final_guarantee = sorted_guarantee[:guarantee_count]
    
    # 如果数量不够，从unknown补充
    if len(final_sprint) < sprint_count and unknown_volunteers:
        needed = sprint_count - len(final_sprint)
        final_sprint.extend(unknown_volunteers[:needed])
        unknown_volunteers = unknown_volunteers[needed:]
    
    if len(final_stable) < stable_count and unknown_volunteers:
        needed = stable_count - len(final_stable)
        final_stable.extend(unknown_volunteers[:needed])
        unknown_volunteers = unknown_volunteers[needed:]
    
    if len(final_guarantee) < guarantee_count and unknown_volunteers:
        needed = guarantee_count - len(final_guarantee)
        final_guarantee.extend(unknown_volunteers[:needed])
        unknown_volunteers = unknown_volunteers[needed:]
    
    # 合并并添加序号
    final = final_sprint + final_stable + final_guarantee
    result = []
    for idx, v in enumerate(final, 1):
        v_copy = dict(v)
        v_copy["serial_number"] = idx
        v_copy["sort_reason"] = _get_sort_reason(v_copy, idx)
        result.append(v_copy)
    
    return result


def _sort_sprint_group(volunteers: List[Dict[str, Any]], target_schools: List[str]) -> List[Dict[str, Any]]:
    """排序冲志愿组。"""
    # 优先级：用户指定的冲刺目标优先
    target_set = set(target_schools)
    target_volunteers = [v for v in volunteers if v.get("school_name", "") in target_set]
    other_volunteers = [v for v in volunteers if v.get("school_name", "") not in target_set]
    
    # 录取概率从高到低排序
    target_volunteers.sort(key=lambda x: x.get("admission_probability_num", 0), reverse=True)
    other_volunteers.sort(key=lambda x: x.get("admission_probability_num", 0), reverse=True)
    
    return target_volunteers + other_volunteers


def _sort_stable_group(volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """排序稳志愿组。"""
    # 优先级：专业匹配度高的优先
    # 其次：院校性价比高的优先
    # 其次：地域偏好优先
    # 最后：录取概率高的优先
    def sort_key(v):
        return (
            -v.get("major_match_score", 0),
            -v.get("cost_performance_score", 0),
            -v.get("location_preference_score", 0),
            -v.get("admission_probability_num", 0),
        )
    volunteers.sort(key=sort_key)
    return volunteers


def _sort_guarantee_group(volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """排序保志愿组。"""
    # 优先级：专业匹配度高的优先
    # 其次：录取概率低的在前（尽量录到更好的学校）
    # 最后：录取概率高的绝对兜底志愿（确保有学上
    # 将志愿分成两组：绝对兜底和其他
    absolute_guarantee = []
    other_guarantee = []
    
    for v in volunteers:
        prob = v.get("admission_probability_num", 0)
        if prob >= 0.95:  # 95%以上为绝对兜底
            absolute_guarantee.append(v)
        else:
            other_guarantee.append(v)
    
    # 其他保志愿按录取概率从低到高排序
    other_guarantee.sort(key=lambda x: x.get("admission_probability_num", 0))
    # 绝对兜底按录取概率从高到低排序
    absolute_guarantee.sort(key=lambda x: x.get("admission_probability_num", 0), reverse=True)
    
    return other_guarantee + absolute_guarantee


def _get_sort_reason(volunteer: Dict[str, Any], serial_number: int) -> str:
    """获取排序原因说明。"""
    positioning = volunteer.get("positioning", "")
    if positioning == "冲":
        return "为考生冲刺目标院校，录取概率较低，放在最前面不影响后续稳保志愿"
    elif positioning == "稳":
        return "录取概率较高，专业匹配度高，是核心目标志愿"
    elif positioning == "保":
        return "录取概率高，作为保底志愿"
    return "志愿"
