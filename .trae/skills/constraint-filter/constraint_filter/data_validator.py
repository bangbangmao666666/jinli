"""数据完整性校验层。

在 pipeline 正式使用各类数据之前，对关键字段做快速抽样校验，
发现明显异常立即抛出 DataIntegrityViolatedError，避免静默输出误导结果。

校验原则（PRD §0.4）：
- 只检测「明显错误」，误报率要低
- 致命问题 → 硬停，抛 DataIntegrityViolatedError，附带可操作的用户提示
- 可疑但不确定 → 写入 warnings 列表，继续运行
- 不依赖外部网络或文件，只检查内存中已加载的数据结构

当前支持的数据源校验：
  validate_admission_plan()    —— 招生计划
  validate_historical_ranks()  —— 历史录取位次
  validate_score_rank_table()  —— 一分一段表（供将来调用方使用）
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .errors import DataIntegrityViolatedError

# 4 位纯数字：几乎不可能是专业名称，但极可能是列对调后残留的年份值
_FOUR_DIGIT_RE = re.compile(r"^\d{4}$")

# 专业名称合理最短长度：短于 2 个字符的通常是解析残骸（如 "-"、"/"）
_MIN_MAJOR_NAME_LEN = 2

# 抽样上限：避免对超大文件做全量遍历
_SAMPLE_LIMIT = 200


# ── 招生计划校验 ──────────────────────────────────────────────────────────────

def validate_admission_plan(
    plan: Dict[str, Any],
    exam_year: int,
) -> List[str]:
    """校验招生计划数据的基本合理性。

    Fatal（抛 DataIntegrityViolatedError）：
      - schools 列表为空
      - 所有专业总数为 0
      - 抽样专业名称中，空值或纯数字（年份格式）超过 20%

    返回 warning 字符串列表（非致命问题）。
    """
    warnings: List[str] = []
    schools = plan.get("schools") or []
    source = plan.get("source", "未知来源")

    # ① schools 不为空
    if not schools:
        raise DataIntegrityViolatedError(
            "招生计划数据为空：schools 列表中没有任何院校记录",
            user_action=(
                "请确认数据文件已正确导入；"
                "重新运行 数据准备 并检查原始文件内容是否包含院校信息。"
            ),
            detail={"source": source, "valid_for_year": plan.get("valid_for_year")},
        )

    # 展开所有专业（最多 _SAMPLE_LIMIT 条用于抽样，但总数要全量统计）
    all_majors = [
        major
        for school in schools
        for group in school.get("major_groups", [])
        for major in group.get("majors", [])
    ]

    # ② 专业总数不为 0
    if not all_majors:
        raise DataIntegrityViolatedError(
            f"招生计划中没有任何专业记录（共 {len(schools)} 所院校，但专业数为 0）",
            user_action=(
                "请检查原始文件格式，可能存在表头识别错误或数据在非标准位置；"
                "重新运行 数据准备，并手动确认 Excel 中包含专业列。"
            ),
            detail={"school_count": len(schools), "source": source},
        )

    # ③ 抽样专业名称，检查空值和年份格式
    sample = all_majors[:_SAMPLE_LIMIT]
    n = len(sample)

    empty_count = 0
    year_like_count = 0
    for major in sample:
        name = (major.get("major_name") or "").strip()
        if not name or len(name) < _MIN_MAJOR_NAME_LEN:
            empty_count += 1
        elif _FOUR_DIGIT_RE.match(name):
            year_like_count += 1

    if year_like_count / n > 0.20:
        raise DataIntegrityViolatedError(
            f"招生计划专业名称异常：抽样 {n} 条中 {year_like_count} 条值为纯数字"
            f"（占 {year_like_count / n:.0%}），疑似列映射错误导致年份写入了专业名称列",
            user_action=(
                "这是数据导入时列对调的典型症状。"
                "请重新运行 数据准备，导入原始文件，并核对列名映射是否正确。"
            ),
            detail={
                "sample_size": n,
                "year_like_count": year_like_count,
                "examples": [
                    (m.get("major_name"), m.get("major_code"))
                    for m in sample
                    if _FOUR_DIGIT_RE.match((m.get("major_name") or "").strip())
                ][:5],
            },
        )

    if empty_count / n > 0.20:
        raise DataIntegrityViolatedError(
            f"招生计划专业名称异常：抽样 {n} 条中 {empty_count} 条为空或过短"
            f"（占 {empty_count / n:.0%}）",
            user_action=(
                "专业名称大量缺失，通常是原始文件中【专业名称】列未被正确识别。"
                "请重新运行 数据准备 并核对原始文件中的列名。"
            ),
            detail={"sample_size": n, "empty_count": empty_count},
        )

    # 非致命 warnings
    if empty_count > 0:
        warnings.append(
            f"招生计划：抽样发现 {empty_count}/{n} 条专业名称为空或过短，"
            "已保留这些条目，请核对原始数据。"
        )

    return warnings


# ── 历史录取位次校验 ──────────────────────────────────────────────────────────

def validate_historical_ranks(
    ranks: Dict[Tuple[str, str], list],
    province: str,
    year: int,
) -> List[str]:
    """校验历史录取位次查找表的基本合理性。

    ranks 格式：{(school_name, major_name): [{year, min_rank, min_score, ...}]}

    Fatal：
      - major_name 中超过 10% 为纯数字（年份格式）——捕获列对调 bug
      - major_name 中超过 20% 为空
      - min_rank 为 0 的比例超过 30%（位次不可能为 0）

    返回 warning 列表。
    """
    if not ranks:
        return []  # 空表是允许的，pipeline 会软降级到 unknown

    warnings: List[str] = []
    keys = list(ranks.keys())
    sample_keys = keys[:_SAMPLE_LIMIT]
    n = len(sample_keys)

    # ① 检查 major_name 字段
    empty_major_count = 0
    year_like_major_count = 0
    year_like_examples: List[str] = []

    for school_name, major_name in sample_keys:
        name = (major_name or "").strip()
        if not name or len(name) < _MIN_MAJOR_NAME_LEN:
            empty_major_count += 1
        elif _FOUR_DIGIT_RE.match(name):
            year_like_major_count += 1
            if len(year_like_examples) < 5:
                year_like_examples.append(f"{school_name}·{major_name}")

    if year_like_major_count / n > 0.10:
        raise DataIntegrityViolatedError(
            f"{province} {year} 年历史录取位次数据异常："
            f"抽样 {n} 条中 {year_like_major_count} 条专业名称为纯数字"
            f"（占 {year_like_major_count / n:.0%}），疑似列映射错误",
            user_action=(
                f"专业名称列被错误写入了年份值（如 '{year}'），"
                "这是数据导入时列对调的典型症状。"
                f"请删除 {province}_{year}_专业录取分数.csv，"
                "重新运行 数据准备 导入原始文件，"
                "并确认 数据准备 代码已更新至最新版本。"
            ),
            detail={
                "province": province,
                "year": year,
                "sample_size": n,
                "year_like_count": year_like_major_count,
                "examples": year_like_examples,
            },
        )

    if empty_major_count / n > 0.20:
        raise DataIntegrityViolatedError(
            f"{province} {year} 年历史录取位次数据异常："
            f"专业名称字段大量为空（抽样 {n} 条中 {empty_major_count} 条，"
            f"占 {empty_major_count / n:.0%}）",
            user_action=(
                "请重新运行 数据准备 导入原始文件，"
                "并检查原始文件中是否存在【专业名称】或【专业】列。"
            ),
            detail={"sample_size": n, "empty_count": empty_major_count},
        )

    # ② 检查 min_rank 合理性（抽样 key 对应的所有录取条目）
    sampled_ranks: List[int] = []
    for key in sample_keys:
        for entry in ranks[key]:
            sampled_ranks.append(entry.get("min_rank", 0))

    if sampled_ranks:
        zero_count = sum(1 for r in sampled_ranks if r == 0)
        if zero_count / len(sampled_ranks) > 0.30:
            raise DataIntegrityViolatedError(
                f"{province} {year} 年历史录取位次数据异常："
                f"超过 30% 的记录 min_rank 为 0"
                f"（抽样 {len(sampled_ranks)} 条中 {zero_count} 条）",
                user_action=(
                    "位次为 0 表示该字段解析失败。"
                    "请重新运行 数据准备，并检查原始文件中【最低位次】列的数据格式。"
                ),
                detail={
                    "sample_rank_count": len(sampled_ranks),
                    "zero_count": zero_count,
                },
            )

    # 非致命 warnings
    if empty_major_count > 0:
        warnings.append(
            f"历史录取位次（{province} {year}）：发现 {empty_major_count} 条专业名称为空，"
            "这些条目在位次匹配时将被忽略。"
        )

    return warnings


# ── 一分一段表校验 ────────────────────────────────────────────────────────────

def validate_score_rank_table(
    table: Dict[str, Any],
    province: str,
    year: int,
) -> List[str]:
    """校验一分一段表的基本合理性。

    Fatal：
      - 记录数 < 30（明显不完整，正常应有 400–600 条）
      - 超过 30% 的分数不在 [100, 750] 合理区间

    返回 warning 列表。
    """
    if not table:
        return []  # 空表允许，pipeline 不强依赖此数据

    warnings: List[str] = []

    # ① 记录数下限
    if len(table) < 30:
        raise DataIntegrityViolatedError(
            f"{province} {year} 年一分一段表记录数过少（仅 {len(table)} 条），数据明显不完整",
            user_action=(
                "一分一段表通常应有 400–600 条分数段记录。"
                "请重新导入完整的一分一段表文件。"
            ),
            detail={"province": province, "year": year, "record_count": len(table)},
        )

    # ② 分数区间校验
    out_of_range = 0
    for score_str in table:
        try:
            score = int(score_str)
            if not (100 <= score <= 750):
                out_of_range += 1
        except (ValueError, TypeError):
            out_of_range += 1

    if out_of_range / len(table) > 0.30:
        raise DataIntegrityViolatedError(
            f"{province} {year} 年一分一段表分数值异常：超过 30% 的记录分数不在 [100, 750] 区间内",
            user_action=(
                "请检查原始文件中的【分数】列是否被正确解析；"
                "重新运行 数据准备 后重新导入。"
            ),
            detail={
                "total": len(table),
                "out_of_range": out_of_range,
                "ratio": f"{out_of_range / len(table):.0%}",
            },
        )

    if out_of_range > 0:
        warnings.append(
            f"一分一段表（{province} {year}）：发现 {out_of_range} 条分数超出合理区间 [100, 750]，"
            "已忽略这些条目。"
        )

    return warnings
