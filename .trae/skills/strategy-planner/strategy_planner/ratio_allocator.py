"""冲稳保比例分配模块。

根据考生风险偏好和可填志愿数，计算冲稳保的具体数量。
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

# 基础比例表
BASIC_RATIOS = {
    "保守型": {"sprint": 0.1, "stable": 0.5, "guarantee": 0.4},
    "适中型": {"sprint": 0.2, "stable": 0.5, "guarantee": 0.3},
    "激进型": {"sprint": 0.3, "stable": 0.45, "guarantee": 0.25},
}

# 保底志愿最低数量
MIN_GUARANTEE_COUNT = 10
# 可填志愿数极少时的冲志愿上限
MIN_VOLUNTEER_THRESHOLD = 20
SPRINT_LIMIT_WHEN_LOW = 3
GUARANTEE_MIN_WHEN_LOW = 8
# 绝对兜底志愿数量
ABSOLUTE_GUARANTEE_COUNT = 3


def allocate_ratio(
    risk_preference: str,
    max_volunteer_count: int,
) -> Dict[str, Any]:
    """分配冲稳保比例。

    Args:
        risk_preference: 风险偏好（保守型/适中型/激进型）
        max_volunteer_count: 该省最大可填志愿数

    Returns:
        包含比例和数量的字典
    """
    # 获取基础比例
    ratios = BASIC_RATIOS.get(risk_preference, BASIC_RATIOS["保守型"])
    
    # 计算基础数量
    sprint_count = int(max_volunteer_count * ratios["sprint"])
    stable_count = int(max_volunteer_count * ratios["stable"])
    guarantee_count = max_volunteer_count - sprint_count - stable_count
    
    # 应用调整规则
    sprint_count, stable_count, guarantee_count = _adjust_counts(
        sprint_count, stable_count, guarantee_count, max_volunteer_count, risk_preference
    )
    
    # 重新计算比例（取整后）
    total = sprint_count + stable_count + guarantee_count
    sprint_ratio = round(sprint_count / total, 2) if total > 0 else 0
    stable_ratio = round(stable_count / total, 2) if total > 0 else 0
    guarantee_ratio = round(guarantee_count / total, 2) if total > 0 else 0
    
    return {
        "risk_preference": risk_preference,
        "sprint_ratio": f"{int(sprint_ratio * 100)}%",
        "stable_ratio": f"{int(stable_ratio * 100)}%",
        "guarantee_ratio": f"{int(guarantee_ratio * 100)}%",
        "sprint_count": sprint_count,
        "stable_count": stable_count,
        "guarantee_count": guarantee_count,
    }


def _adjust_counts(
    sprint_count: int,
    stable_count: int,
    guarantee_count: int,
    max_volunteer_count: int,
    risk_preference: str,
) -> Tuple[int, int, int]:
    """调整冲稳保数量，确保满足约束条件。"""
    # 规则1：保志愿数量不得低于最低值
    if guarantee_count < MIN_GUARANTEE_COUNT:
        # 从冲志愿扣除，补充到保志愿
        needed = MIN_GUARANTEE_COUNT - guarantee_count
        if sprint_count >= needed:
            sprint_count -= needed
            guarantee_count = MIN_GUARANTEE_COUNT
        else:
            # 冲志愿不够，再从稳志愿扣
            needed -= sprint_count
            sprint_count = 0
            if stable_count >= needed:
                stable_count -= needed
                guarantee_count = MIN_GUARANTEE_COUNT
            else:
                guarantee_count = sprint_count + stable_count + guarantee_count
                sprint_count = 0
                stable_count = 0
    
    # 规则2：可填志愿数极少时的特殊处理
    if max_volunteer_count < MIN_VOLUNTEER_THRESHOLD:
        if sprint_count > SPRINT_LIMIT_WHEN_LOW:
            excess = sprint_count - SPRINT_LIMIT_WHEN_LOW
            sprint_count = SPRINT_LIMIT_WHEN_LOW
            guarantee_count += excess
        if guarantee_count < GUARANTEE_MIN_WHEN_LOW:
            needed = GUARANTEE_MIN_WHEN_LOW - guarantee_count
            if stable_count >= needed:
                stable_count -= needed
                guarantee_count = GUARANTEE_MIN_WHEN_LOW
    
    # 规则3：确保保志愿中有足够的绝对兜底志愿
    if guarantee_count < ABSOLUTE_GUARANTEE_COUNT:
        # 从稳志愿调过来
        needed = ABSOLUTE_GUARANTEE_COUNT - guarantee_count
        if stable_count >= needed:
            stable_count -= needed
            guarantee_count = ABSOLUTE_GUARANTEE_COUNT
        elif sprint_count + stable_count >= needed:
            # 先从稳志愿扣，再从冲志愿扣
            needed -= stable_count
            stable_count = 0
            sprint_count -= needed
            guarantee_count = ABSOLUTE_GUARANTEE_COUNT
    
    # 确保总数正确
    total = sprint_count + stable_count + guarantee_count
    if total != max_volunteer_count:
        diff = max_volunteer_count - total
        # 差异补充到保志愿
        guarantee_count += diff
    
    return sprint_count, stable_count, guarantee_count
