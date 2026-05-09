"""数据校验层：对归一化结果做合理性检查，生成校验报告。

支持三种数据类型：
  - admission_plan      招生计划（校验 schools 树结构）
  - major_admission_scores  历年录取位次（校验 data 列表）
  - score_rank_table    一分一段表（校验 data 列表）

不抛异常，返回结构化报告让 模块 展示给用户确认。
"""
from __future__ import annotations

import re
from typing import Any


def validate(normalized: dict[str, Any]) -> dict[str, Any]:
    """根据 normalized 中的 type 字段分发到对应校验函数。"""
    data_type = normalized.get("type")  # None 表示招生计划
    if data_type == "major_admission_scores":
        return _validate_historical_ranks(normalized)
    if data_type == "score_rank_table":
        return _validate_score_rank_table(normalized)
    if data_type == "admission_filing":
        return _validate_admission_filing(normalized)
    return _validate_admission_plan(normalized)


# ── 招生计划校验 ──────────────────────────────────────────────────────────────

def _validate_admission_plan(normalized: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = list(normalized.get("_meta", {}).get("normalization_warnings", []))
    sample_issues: list[dict] = []

    schools = normalized.get("schools", [])
    valid_for_year = normalized.get("valid_for_year")
    province = normalized.get("province")

    if not province:
        errors.append("province（省份）未设置，无法写入 constraint-filter 数据目录")
    if not valid_for_year:
        errors.append("valid_for_year（招生年份）未设置，无法通过版本校验")
    if not schools:
        errors.append("schools 列表为空，文件可能未被正确解析")

    no_code_count = 0
    bad_code_count = 0
    bad_code_samples: list[str] = []
    no_subject_req_count = 0
    empty_major_group_count = 0
    total_majors = 0

    for school in schools:
        sc = school.get("school_code", "")
        sn = school.get("school_name", "")
        label = sn or sc or "（未知学校）"

        if not sc:
            no_code_count += 1
        elif not re.fullmatch(r"\d{5}", sc):
            bad_code_count += 1
            if len(bad_code_samples) < 3:
                bad_code_samples.append(sc)

        for group in school.get("major_groups", []):
            req = group.get("subject_requirement_raw")
            majors = group.get("majors", [])

            if not majors:
                empty_major_group_count += 1

            if req is None:
                no_subject_req_count += 1
                if len(sample_issues) < 10:
                    sample_issues.append({
                        "level": "warning",
                        "target": f"{label} · 专业组{group.get('group_code', '?')}",
                        "issue": "选科要求为空，constraint-filter 将无法处理该专业组",
                    })

            for major in majors:
                total_majors += 1
                if not major.get("major_name"):
                    if len(sample_issues) < 10:
                        sample_issues.append({
                            "level": "error",
                            "target": f"{label} · 专业代码{major.get('major_code', '?')}",
                            "issue": "专业名称为空",
                        })

    if no_code_count:
        warnings.append(f"{no_code_count} 所学校院校代码缺失，已用学校名称代替，入库后需手工补全")
    if bad_code_count:
        total = len(schools)
        sample_str = "、".join(f"'{c}'" for c in bad_code_samples)
        if bad_code_samples:
            sample_str += " 等"
        if bad_code_count == total:
            warnings.append(
                f"此文件院校代码使用内部格式（{sample_str}），"
                f"全部 {bad_code_count} 所学校均无教育部5位院校代码，"
                "入库后如需标准代码请手工补全"
            )
        else:
            warnings.append(
                f"{bad_code_count} 所学校的院校代码不是标准5位数字（示例：{sample_str}），请核实"
            )
    if no_subject_req_count:
        warnings.append(
            f"{no_subject_req_count} 个专业组缺少选科要求，"
            "constraint-filter 第三层（选科过滤）将无法处理这些专业"
        )
    if empty_major_group_count:
        warnings.append(f"{empty_major_group_count} 个专业组内没有专业，已忽略")

    _add_upload_warning(warnings)
    parse_warnings = normalized.get("_meta", {}).get("parse_warnings", [])
    _append_parse_warnings(warnings, parse_warnings)

    meta = normalized.get("_meta", {})
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "data_type":          "admission_plan",
            "total_schools":      meta.get("total_schools", len(schools)),
            "total_major_groups": meta.get("total_major_groups", 0),
            "total_majors":       meta.get("total_majors", total_majors),
            "province":           province,
            "valid_for_year":     valid_for_year,
            "source_type":        normalized.get("source_type"),
            "source_raw_filename": normalized.get("source_raw_filename"),
        },
        "sample_issues": sample_issues,
    }


# ── 历年录取位次校验 ──────────────────────────────────────────────────────────

def _validate_historical_ranks(normalized: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = list(normalized.get("_meta", {}).get("normalization_warnings", []))
    sample_issues: list[dict] = []

    province = normalized.get("province")
    valid_for_year = normalized.get("valid_for_year")
    records: list[dict] = normalized.get("data", [])

    if not province:
        errors.append("province（省份）未设置")
    if not valid_for_year:
        errors.append("valid_for_year（年份）未设置")
    if not records:
        errors.append("data 列表为空，文件可能未被正确解析")

    missing_school = 0
    missing_major = 0
    missing_rank = 0

    for i, rec in enumerate(records[:200]):   # 抽查前 200 条
        if not rec.get("school_name"):
            missing_school += 1
        if not rec.get("major_name"):
            missing_major += 1
        if not rec.get("min_rank"):
            missing_rank += 1
            if len(sample_issues) < 5:
                sample_issues.append({
                    "level": "warning",
                    "target": f"{rec.get('school_name', '?')} · {rec.get('major_name', '?')}",
                    "issue": "最低位次为空",
                })

    if missing_school > 10:
        warnings.append(f"前 200 条中有 {missing_school} 条院校名称为空，请检查解析结果")
    if missing_major > 10:
        warnings.append(f"前 200 条中有 {missing_major} 条专业名称为空，请检查解析结果")
    if missing_rank > 20:
        warnings.append(f"前 200 条中有 {missing_rank} 条最低位次为空，请检查解析结果")

    _add_upload_warning(warnings)

    meta = normalized.get("_meta", {})
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "data_type":       "major_admission_scores",
            "total_records":   meta.get("total_records", len(records)),
            "province":        province,
            "valid_for_year":  valid_for_year,
            "source_type":     normalized.get("source_type"),
            "source_raw_filename": normalized.get("source_raw_filename"),
        },
        "sample_issues": sample_issues,
    }


# ── 一分一段表校验 ────────────────────────────────────────────────────────────

def _validate_score_rank_table(normalized: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = list(normalized.get("_meta", {}).get("normalization_warnings", []))
    sample_issues: list[dict] = []

    province = normalized.get("province")
    valid_for_year = normalized.get("valid_for_year")
    records: list[dict] = normalized.get("data", [])

    if not province:
        errors.append("province（省份）未设置")
    if not valid_for_year:
        errors.append("valid_for_year（年份）未设置")
    if not records:
        errors.append("data 列表为空，文件可能未被正确解析")

    # 检查分数段是否连续（简单抽查）
    if len(records) > 1:
        scores = []
        for rec in records:
            try:
                scores.append(int(rec.get("score_range", 0)))
            except (ValueError, TypeError):
                pass
        if scores:
            max_s, min_s = max(scores), min(scores)
            expected_count = max_s - min_s + 1
            if abs(len(scores) - expected_count) > 5:
                warnings.append(
                    f"分数段数量（{len(scores)}）与预期（{expected_count}，"
                    f"从 {min_s} 到 {max_s}）不符，可能有缺失行"
                )

    _add_upload_warning(warnings)

    meta = normalized.get("_meta", {})
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "data_type":      "score_rank_table",
            "total_records":  meta.get("total_records", len(records)),
            "province":       province,
            "valid_for_year": valid_for_year,
            "source_type":    normalized.get("source_type"),
            "source_raw_filename": normalized.get("source_raw_filename"),
        },
        "sample_issues": sample_issues,
    }


# ── 志愿投档情况校验 ──────────────────────────────────────────────────────────

def _validate_admission_filing(normalized: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = list(normalized.get("_meta", {}).get("normalization_warnings", []))
    sample_issues: list[dict] = []

    province     = normalized.get("province")
    valid_for_year = normalized.get("valid_for_year")
    round_number = normalized.get("round_number", 0)
    records      = normalized.get("data", [])

    if not province:
        errors.append("province（省份）未设置")
    if not valid_for_year:
        errors.append("valid_for_year（年份）未设置")
    if not round_number:
        warnings.append("未能从文件名中识别出志愿轮次（第几次），请确认文件名含【第X次】字样")
    if not records:
        errors.append("data 列表为空，文件可能未被正确解析")

    missing_school = sum(1 for r in records[:200] if not r.get("院校名称"))
    missing_rank   = sum(1 for r in records[:200] if not r.get("最低位次"))
    if missing_school > 10:
        warnings.append(f"前200条中有 {missing_school} 条院校名称为空，请检查")
    if missing_rank > 10:
        warnings.append(f"前200条中有 {missing_rank} 条最低位次为空，请检查")

    _add_upload_warning(warnings)

    meta = normalized.get("_meta", {})
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "data_type":      "admission_filing",
            "round_number":   round_number,
            "total_records":  meta.get("total_records", len(records)),
            "province":       province,
            "valid_for_year": valid_for_year,
            "source_type":    normalized.get("source_type"),
            "source_raw_filename": normalized.get("source_raw_filename"),
        },
        "sample_issues": sample_issues,
    }


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _add_upload_warning(warnings: list[str]) -> None:
    warnings.append(
        "此数据来自用户上传文件，系统未与官方数据库做交叉验证。"
        "constraint-filter 使用时会在结果中标注【来源：用户上传】，请自行核对关键信息。"
    )


def _append_parse_warnings(warnings: list[str], parse_warnings: list[str]) -> None:
    """折叠重复类型的解析警告，避免大文件输出淹没关键信息。"""
    MIXED_REQ_PATTERN = "内各专业选科要求不同"
    mixed_req: list[str] = []
    others: list[str] = []
    for w in parse_warnings:
        if MIXED_REQ_PATTERN in w:
            mixed_req.append(w)
        else:
            others.append(w)

    if mixed_req:
        first = mixed_req[0]
        if len(mixed_req) == 1:
            warnings.append(f"[解析阶段] {first}")
        else:
            warnings.append(
                f"[解析阶段] {len(mixed_req)} 所院校存在组内选科不一致，"
                "各专业已单独记录选科要求，组级别保留首条值。"
                f"（示例：{first}）"
            )

    for w in others:
        warnings.append(f"[解析阶段] {w}")
