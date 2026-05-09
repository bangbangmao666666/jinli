"""rank_ratio 计算与冲/稳/保分档（PRD §3.2）。

注意：本 skill 只打标签，不做排序取舍。取舍是 填报策略模块 的职责。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

WEIGHTS = [0.5, 0.3, 0.2]  # 最近一年 → 再上一年 → 再上一年


def compute(
    yearly_data: List[Dict[str, Any]], applicant_rank: int
) -> Tuple[float, str, bool, List[int]]:
    """
    返回 (rank_ratio, tier, data_incomplete, missing_years)。

    - yearly_data: [{"year": ..., "min_rank": ...}, ...]，期望为最近 3 年，年份降序或升序都可
    - 若全部缺失或 min_rank 缺失，返回 (None, "unknown", True, [...])
    - 数据不足 3 年，使用可得年份按现有权重的归一化加权平均，data_incomplete=True
    """
    # 只保留含有 min_rank 的记录，按年份降序
    records = [r for r in yearly_data if isinstance(r.get("min_rank"), int)]
    records.sort(key=lambda r: r["year"], reverse=True)

    available_years = [r["year"] for r in records]
    if not records:
        return None, "unknown", True, []

    weights = WEIGHTS[: len(records)]
    weight_sum = sum(weights)
    weighted_avg = sum(r["min_rank"] * w for r, w in zip(records, weights)) / weight_sum

    if weighted_avg <= 0:
        return None, "unknown", True, []

    ratio = applicant_rank / weighted_avg
    tier = _classify(ratio)
    incomplete = len(records) < 3
    # missing_years 计算：以最近3年为参照，把缺失年份返回（如只提供 2025/2023，缺 2024）
    missing_years: List[int] = []
    if records:
        latest = records[0]["year"]
        expected = {latest - i for i in range(3)}
        missing_years = sorted(expected - set(available_years), reverse=True)
    return round(ratio, 4), tier, incomplete, missing_years


def _classify(ratio: float) -> str:
    """
    ratio = 考生位次 / 历史最低录取位次加权平均

    位次数字越小成绩越好，因此：
    - ratio < 1：考生位次 < 历史最低位次 → 考生比历史最低线好 → 保底有余
    - ratio ≈ 1：考生与历史最低线相当 → 稳线附近
    - ratio > 1：考生位次 > 历史最低位次 → 考生比历史最低线差 → 有风险

    档位映射（与 PRD §3.2 志愿策略对应）：
      ratio ≤ 0.70  → 极保（远超分数线，用作兜底）
      0.70 < ratio ≤ 1.00 → 保（稳定录取概率高）
      1.00 < ratio ≤ 1.20 → 稳（分数线附近，大概率可录）
      1.20 < ratio ≤ 1.50 → 冲（有一定风险，值得尝试）
      ratio > 1.50  → 极冲（明显超出分数线，概率较低）
    """
    if ratio <= 0.70:
        return "极保"
    if ratio <= 1.00:
        return "保"
    if ratio <= 1.20:
        return "稳"
    if ratio <= 1.50:
        return "冲"
    return "极冲"


def should_include(tier: str, aggressive_mode: bool) -> bool:
    """默认模式下过滤掉极冲（明显录不上）和极保（远超分数线，通常不是目标院校）。"""
    if aggressive_mode:
        return tier != "unknown"  # 激进模式下 unknown 也保留，由 warnings 提示
    if tier in ("极冲", "极保"):
        return False
    if tier == "unknown":
        # unknown 的专业：保留但在输出中标记 data_incomplete。PRD §四第二层规定保留。
        return True
    return True
