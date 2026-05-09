"""归一化层：把 parser 输出的原始行列数据映射到 admission plan JSON schema。

设计原则：
- 基于列名关键词匹配（不用下标），抵抗列顺序变化
- 合并单元格（None 值）通过向上填充还原
- 找不到的字段留 null / 空列表，绝不编造
- 选科要求原文原封不动，不做任何修改
- 遇到无法处理的行记录到 parse_warnings，不中断
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import NormalizationError

# ── 列名关键词映射 ──────────────────────────────────────────────────────────
# 格式：schema字段名 → [候选关键词列表]（按优先级排列，第一个命中即用）
COLUMN_KEYWORDS: dict[str, list[str]] = {
    "school_code":          ["院校代码", "学校代码", "院校编号", "院校编码"],
    "school_name":          ["院校名称", "学校名称", "院校", "高校名称"],
    "school_city":          ["所在城市", "学校所在地", "城市"],
    "school_province_loc":  ["学校所在省", "所在省份", "所属省"],
    "group_code":           ["专业组代码", "组代码", "专业组号", "组号"],
    "group_name":           ["专业组名称", "专业组"],
    "major_code":           ["专业代码", "专业号", "专业编号"],
    "major_name":           ["专业名称", "专业"],
    "subject_req_raw":      ["选考科目要求", "选科要求", "科目要求", "报考要求",
                             "选考要求", "限选科目"],
    "quota":                ["计划人数", "招生计划", "招生人数", "计划数", "人数"],
    "gender_limit":         ["性别要求", "性别限制", "招生性别"],
    "physical_notes":       ["体检要求", "备注", "说明"],
}

# 省份名称正则（用于从文件标题/文字中提取）
_PROVINCE_RE = re.compile(
    r"(北京|天津|河北|山西|内蒙古|辽宁|吉林|黑龙江|上海|江苏|浙江|安徽|"
    r"福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|"
    r"西藏|陕西|甘肃|青海|宁夏|新疆)"
)

# 年份提取
_YEAR_RE = re.compile(r"(20[2-9]\d)\s*年")


def normalize_admission_plan(
    raw: dict[str, Any],
    user_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 parser 输出的 raw 归一化为 admission plan schema。

    user_hint 可提供：province、valid_for_year、source 等补充信息（用户口头说的）。
    """
    hint = user_hint or {}
    warnings: list[str] = []
    file_path = raw.get("file", "unknown")
    file_name = Path(file_path).name

    # 1. 从原始文件推断省份和年份
    province = hint.get("province") or _detect_province(raw, warnings)
    valid_for_year = hint.get("valid_for_year") or _detect_year(raw, warnings)

    # 2. 找最可能是招生计划的表格
    all_tables = raw.get("all_tables_flat") or _flatten_sheets(raw)
    if not all_tables:
        raise NormalizationError(
            "提取结果中没有任何表格，无法归一化",
            detail={"file": file_path},
        )

    # 3. 逐表尝试归一化，合并结果
    schools_map: dict[str, Any] = {}  # school_code → school dict
    parse_warnings: list[str] = []

    for table_entry in all_tables:
        rows = table_entry.get("rows", [])
        page = table_entry.get("page")
        sheet = table_entry.get("name", "")
        location = f"第{page}页" if page else (f"Sheet:{sheet}" if sheet else "?")

        if len(rows) < 2:
            continue  # 单行或空表，跳过

        col_map = _detect_column_map(rows[0])
        if not col_map:
            parse_warnings.append(f"{location}：无法识别表头，跳过此表（表头：{rows[0]}）")
            continue

        if "school_code" not in col_map and "school_name" not in col_map:
            parse_warnings.append(
                f"{location}：未找到院校代码或院校名称列，跳过（已识别列：{list(col_map.keys())}）"
            )
            continue

        _merge_rows_into_schools(rows[1:], col_map, schools_map, parse_warnings)

    if not schools_map:
        raise NormalizationError(
            "未能从任何表格中提取到院校信息，请确认文件是否为招生计划",
            detail={
                "file": file_path,
                "parse_warnings": parse_warnings,
                "hint": "如果文件格式特殊，请联系维护者",
            },
        )

    schools = list(schools_map.values())

    result = {
        "version": f"{valid_for_year}-招生计划-imported" if valid_for_year else "unknown-imported",
        "source": hint.get("source", f"用户上传：{file_name}"),
        "fetched_at": datetime.now().strftime("%Y-%m-%d"),
        "valid_for_year": valid_for_year,
        "province": province,
        "source_type": "user_upload",
        "source_raw_filename": file_name,
        "schools": schools,
        "_meta": {
            "total_schools": len(schools),
            "total_major_groups": sum(len(s["major_groups"]) for s in schools),
            "total_majors": sum(
                len(g["majors"])
                for s in schools
                for g in s["major_groups"]
            ),
            "parse_warnings": parse_warnings,
            "normalization_warnings": warnings,
        },
    }

    # 如果省份或年份缺失，加入 warnings
    if not province:
        warnings.append("未能从文件中自动识别省份，请在确认时手动指定")
    if not valid_for_year:
        warnings.append("未能从文件中自动识别招生年份，请在确认时手动指定")

    return result


# ── historical_ranks normalizer ───────────────────────────────────────────────

# 列名关键词：历年录取位次/分数线表
_RANK_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "school_name":      ["院校名称", "学校名称", "院校", "学校"],
    "major_name":       ["专业名称", "专业"],
    "subject_req":      ["选考科目要求", "选科要求", "科目要求", "报考要求", "选科"],
    "min_score":        ["最低分", "录取最低分", "投档最低分", "分数线", "最低录取分"],
    "min_rank":         ["最低位次", "录取最低位次", "投档位次", "位次"],
    "avg_score":        ["平均分", "录取平均分"],
    "year":             ["年份", "录取年份", "年度"],
    "batch":            ["批次", "录取批次"],
    "school_province":  ["院校省份", "所在省", "学校所在地"],
    "school_city":      ["院校城市", "所在城市"],
    "is_985":           ["985", "是否985"],
    "is_211":           ["211", "是否211"],
    "double_first":     ["双一流", "是否双一流"],
}


def normalize_historical_ranks(
    raw: dict[str, Any],
    user_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 parser 输出的 raw 归一化为历年录取位次扁平列表。

    输出格式（与 shandong_2024_major_admission_scores.json 一致）：
    {
        "province": "山东",
        "year": 2024,
        "type": "major_admission_scores",
        "source": "...",
        "data": [
            {"school_name": ..., "major_name": ..., "min_score": ..., "min_rank": ..., ...}
        ]
    }
    """
    hint = user_hint or {}
    warnings: list[str] = []
    file_path = raw.get("file", "unknown")
    file_name = Path(file_path).name

    province = hint.get("province") or _detect_province(raw, warnings)
    year = hint.get("valid_for_year") or _detect_year(raw, warnings)

    all_tables = raw.get("all_tables_flat") or _flatten_sheets(raw)
    if not all_tables:
        raise NormalizationError("提取结果中没有任何表格", detail={"file": file_path})

    records: list[dict[str, Any]] = []

    for table_entry in all_tables:
        rows = table_entry.get("rows", [])
        if len(rows) < 2:
            continue

        # 自动查找真正的表头行（前5行，至少命中2列才算有效表头，排除大标题行）
        header_idx, col_map = _find_header_row(rows, _RANK_COLUMN_KEYWORDS, max_scan=5)
        if header_idx < 0 or ("min_rank" not in col_map and "min_score" not in col_map):
            warnings.append(f"表格未找到位次/分数列，跳过（已扫描前5行）")
            continue
        if "major_name" not in col_map:
            warnings.append(f"表格未找到专业名称列，跳过（表头行：{rows[header_idx]}）")
            continue

        prev: dict[str, Any] = {}
        for row in rows[header_idx + 1:]:
            def get(field: str) -> Any:
                ci = col_map.get(field)
                if ci is None or ci >= len(row):
                    return None
                val = row[ci]
                if val is None:
                    return prev.get(field)
                prev[field] = val
                return val

            major_name = get("major_name")
            if not major_name:
                continue

            rec: dict[str, Any] = {
                "school_name":       get("school_name") or "",
                "year":              str(get("year") or year or ""),
                "major_name":        str(major_name),
                "subject_requirement": get("subject_req") or "",
                "min_score":         _to_str(get("min_score")),
                "min_rank":          _to_str(get("min_rank")),
                "avg_score":         _to_str(get("avg_score")),
                "admission_batch":   get("batch") or "",
                "school_nature":     "公办",   # 默认，来源文件通常没有此列
                "province":          get("school_province") or province or "",
                "city":              get("school_city") or "",
                "is_985":            _bool_flag(get("is_985")),
                "is_211":            _bool_flag(get("is_211")),
                "double_first_class": _bool_flag(get("double_first")),
            }
            records.append(rec)

    if not records:
        raise NormalizationError(
            "未能提取到任何录取记录，请确认文件是历年录取位次/分数线表",
            detail={"file": file_path, "warnings": warnings},
        )

    return {
        "province":        province,
        "year":            year,
        "valid_for_year":  year,          # storage.py 需要此字段确定写入路径
        "type":            "major_admission_scores",
        "source":          hint.get("source", f"用户上传：{file_name}"),
        "fetched_at":      datetime.now().strftime("%Y-%m-%d"),
        "source_type":     "user_upload",
        "source_raw_filename": file_name,
        "data": records,
        "_meta": {
            "total_records": len(records),
            "normalization_warnings": warnings,
        },
    }


# ── admission_filing normalizer ────────────────────────────────────────────────

_FILING_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "major_code_name":  ["专业代号及名称", "专业代号", "专业名称"],
    "school_code_name": ["院校代号及名称", "院校代号", "院校名称"],
    "quota":            ["投档计划数", "计划数", "投档人数", "录取计划"],
    "min_rank":         ["最低位次", "投档最低位次", "最低录取位次"],
}

_FILING_CODE_RE = re.compile(r"^([A-Za-z0-9]+)\s*(.+)$")


def _parse_code_name(combined: str) -> tuple[str, str]:
    """将"A001北京大学"或"17文科试验班类(...)"拆成(代码, 名称)。"""
    s = (combined or "").strip()
    if not s:
        return "", ""
    m = _FILING_CODE_RE.match(s)
    if m:
        return m.group(1), m.group(2).strip()
    return "", s


def normalize_admission_filing(
    raw: dict[str, Any],
    user_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将投档情况表归一化为扁平记录列表。

    输出格式：
    {
        "province": "山东",
        "year": 2024,
        "type": "admission_filing",
        "round_number": 1,
        "data": [
            {"院校代码": "A001", "院校名称": "北京大学",
             "专业代码": "17", "专业名称": "文科试验班类(...)",
             "投档计划数": "22", "最低位次": "157", "志愿轮次": 1}
        ]
    }
    """
    hint = user_hint or {}
    warnings: list[str] = []
    file_path = raw.get("file", "unknown")
    file_name = Path(file_path).name

    province = hint.get("province") or _detect_province(raw, warnings)
    year = hint.get("valid_for_year") or _detect_year(raw, warnings)

    # 从文件名提取志愿轮次（第1次/第2次/第3次）
    round_match = re.search(r"第(\d+)次", file_name)
    round_number = int(round_match.group(1)) if round_match else hint.get("round_number", 0)

    all_tables = raw.get("all_tables_flat") or _flatten_sheets(raw)
    if not all_tables:
        raise NormalizationError("提取结果中没有任何表格", detail={"file": file_path})

    records: list[dict[str, Any]] = []

    for table_entry in all_tables:
        rows = table_entry.get("rows", [])
        if len(rows) < 2:
            continue

        header_idx, col_map = _find_header_row(rows, _FILING_COLUMN_KEYWORDS, max_scan=5)
        if header_idx < 0 or "min_rank" not in col_map:
            warnings.append("未找到最低位次列，跳过此表")
            continue

        for row in rows[header_idx + 1:]:
            def get(field: str) -> str:
                ci = col_map.get(field)
                if ci is None or ci >= len(row):
                    return ""
                v = row[ci]
                return "" if v is None else str(v).strip()

            school_code, school_name = _parse_code_name(get("school_code_name"))
            major_code, major_name   = _parse_code_name(get("major_code_name"))
            min_rank = _to_str(get("min_rank"))

            if not school_name or not min_rank:
                continue

            records.append({
                "院校代码":   school_code,
                "院校名称":   school_name,
                "专业代码":   major_code,
                "专业名称":   major_name,
                "投档计划数": _to_str(get("quota")),
                "最低位次":   min_rank,
                "志愿轮次":   round_number,
            })

    if not records:
        raise NormalizationError(
            "未能提取到任何投档记录，请确认文件是志愿投档情况表",
            detail={"file": file_path, "warnings": warnings},
        )

    return {
        "province":        province,
        "year":            year,
        "valid_for_year":  year,
        "type":            "admission_filing",
        "round_number":    round_number,
        "source":          hint.get("source", f"用户上传：{file_name}"),
        "fetched_at":      datetime.now().strftime("%Y-%m-%d"),
        "source_type":     "user_upload",
        "source_raw_filename": file_name,
        "data": records,
        "_meta": {
            "total_records":          len(records),
            "round_number":           round_number,
            "normalization_warnings": warnings,
        },
    }


# ── score_rank_table normalizer ────────────────────────────────────────────────

_SCORE_RANK_COLUMN_KEYWORDS: dict[str, list[str]] = {
    # 分数列
    "score":        ["分数", "总分", "成绩", "分数段"],
    # 合计 / 全体
    "total_cur":    ["合计本次", "本次人数", "当分人数",
                     "全体 本段人数", "全体 当次", "全体本次"],
    "total_cum":    ["合计累计", "全体 累计人数", "全体 累计",
                     "合计 累计"],
    # 物理
    "physics_cur":  ["物理本次", "物理当次", "物理选考本次",
                     "选考物理 本段人数", "物理 本段人数"],
    "physics_cum":  ["物理累计", "物理选考累计",
                     "选考物理 累计人数", "物理 累计人数"],
    # 历史
    "history_cur":  ["历史本次", "历史当次",
                     "选考历史 本段人数", "历史 本段人数"],
    "history_cum":  ["历史累计",
                     "选考历史 累计人数", "历史 累计人数"],
    # 化学
    "chemistry_cur":["化学本次",
                     "选考化学 本段人数", "化学 本段人数"],
    "chemistry_cum":["化学累计",
                     "选考化学 累计人数", "化学 累计人数"],
    # 生物
    "biology_cur":  ["生物本次",
                     "选考生物 本段人数", "生物 本段人数"],
    "biology_cum":  ["生物累计",
                     "选考生物 累计人数", "生物 累计人数"],
    # 政治 / 思想政治
    "politics_cur": ["政治本次", "思想政治本次",
                     "选考思想政治 本段人数", "思想政治 本段人数"],
    "politics_cum": ["政治累计", "思想政治累计",
                     "选考思想政治 累计人数", "思想政治 累计人数"],
    # 地理
    "geography_cur":["地理本次",
                     "选考地理 本段人数", "地理 本段人数"],
    "geography_cum":["地理累计",
                     "选考地理 累计人数", "地理 累计人数"],
}


def normalize_score_rank_table(
    raw: dict[str, Any],
    user_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 parser 输出的 raw 归一化为一分一段表。

    输出格式（与 shandong_2024_score_rank_table.json 一致）：
    {
        "province": "山东",
        "year": 2024,
        "type": "score_rank_table",
        "data": [
            {
                "score_range": "566",
                "total": {"current": "1231", "cumulative": "54147"},
                "physics": {"current": "800", "cumulative": "40491"},
                ...
            }
        ]
    }
    """
    hint = user_hint or {}
    warnings: list[str] = []
    file_path = raw.get("file", "unknown")
    file_name = Path(file_path).name

    province = hint.get("province") or _detect_province(raw, warnings)
    year = hint.get("valid_for_year") or _detect_year(raw, warnings)

    all_tables = raw.get("all_tables_flat") or _flatten_sheets(raw)
    if not all_tables:
        raise NormalizationError("提取结果中没有任何表格", detail={"file": file_path})

    records: list[dict[str, Any]] = []

    for table_entry in all_tables:
        rows = table_entry.get("rows", [])
        if len(rows) < 2:
            continue

        header_idx, col_map = _find_header_row(rows, _SCORE_RANK_COLUMN_KEYWORDS, max_scan=5)
        if header_idx < 0 or "score" not in col_map:
            warnings.append(f"未找到分数列，跳过（已扫描前5行）")
            continue

        def _col(row: list, field: str) -> str:
            ci = col_map.get(field)
            if ci is None or ci >= len(row):
                return ""
            v = row[ci]
            return "" if v is None else str(v).strip()

        for row in rows[header_idx + 1:]:
            score = _col(row, "score")
            if not score or not score.replace(".", "").isdigit():
                continue
            # 只取整数分数（省略小数行）
            score_int = str(int(float(score)))

            records.append({
                "score_range": score_int,
                "total":     {"current": _col(row, "total_cur"),    "cumulative": _col(row, "total_cum")},
                "physics":   {"current": _col(row, "physics_cur"),  "cumulative": _col(row, "physics_cum")},
                "history":   {"current": _col(row, "history_cur"),  "cumulative": _col(row, "history_cum")},
                "chemistry": {"current": _col(row, "chemistry_cur"),"cumulative": _col(row, "chemistry_cum")},
                "biology":   {"current": _col(row, "biology_cur"),  "cumulative": _col(row, "biology_cum")},
                "politics":  {"current": _col(row, "politics_cur"), "cumulative": _col(row, "politics_cum")},
                "geography": {"current": _col(row, "geography_cur"),"cumulative": _col(row, "geography_cum")},
            })

    if not records:
        raise NormalizationError(
            "未能提取到任何一分一段记录，请确认文件是一分一段表",
            detail={"file": file_path, "warnings": warnings},
        )

    return {
        "province":        province,
        "year":            year,
        "valid_for_year":  year,          # storage.py 需要此字段确定写入路径
        "type":            "score_rank_table",
        "source":          hint.get("source", f"用户上传：{file_name}"),
        "fetched_at":      datetime.now().strftime("%Y-%m-%d"),
        "source_type":     "user_upload",
        "source_raw_filename": file_name,
        "data": records,
        "_meta": {
            "total_records": len(records),
            "normalization_warnings": warnings,
        },
    }


# ── 通用列名检测（兼容多种关键词映射表）────────────────────────────────────────

def _detect_column_map_generic(
    header_row: list, keywords: dict[str, list[str]]
) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for ci, cell in enumerate(header_row):
        if not cell:
            continue
        cell_str = str(cell)
        for field, kws in keywords.items():
            if field in col_map:
                continue
            if any(kw in cell_str for kw in kws):
                col_map[field] = ci
                break
    return col_map


def _to_str(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    # 去掉 openpyxl 读出的 .0 后缀
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s


def _bool_flag(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s in ("是", "Y", "y", "yes", "Yes", "YES", "1", "True", "true"):
        return "是"
    if s in ("否", "N", "n", "no", "No", "NO", "0", "False", "false"):
        return "否"
    return s


# ── 内部辅助函数 ──────────────────────────────────────────────────────────────

def _detect_province(raw: dict, warnings: list) -> str | None:
    """从文件名、文字片段中尝试识别省份名。"""
    candidates = [raw.get("file", "")]
    for page in raw.get("pages", []):
        candidates.append(page.get("text_snippet", ""))
    for sheet in raw.get("sheets", []):
        candidates.append(sheet.get("name", ""))
        rows = sheet.get("rows", [])
        if rows:
            candidates.append(" ".join(str(c) for c in rows[0] if c))

    for text in candidates:
        m = _PROVINCE_RE.search(text)
        if m:
            return m.group(1)
    warnings.append("未能自动识别省份，可能需要用户补充")
    return None


def _detect_year(raw: dict, warnings: list) -> int | None:
    """从文件名、文字片段中尝试识别年份。"""
    candidates = [raw.get("file", "")]
    for page in raw.get("pages", []):
        candidates.append(page.get("text_snippet", ""))
    for sheet in raw.get("sheets", []):
        candidates.append(sheet.get("name", ""))

    for text in candidates:
        m = _YEAR_RE.search(text)
        if m:
            y = int(m.group(1))
            if 2020 <= y <= 2035:
                return y
    # 尝试不带"年"的4位数字年份（文件名里常见，如 henan_2026.pdf）
    for text in candidates:
        m = re.search(r"(20[2-9]\d)", text)
        if m:
            y = int(m.group(1))
            if 2020 <= y <= 2035:
                return y
    warnings.append("未能自动识别招生年份，可能需要用户补充")
    return None


def _detect_column_map(header_row: list) -> dict[str, int]:
    """把表头行映射成 {schema字段名: 列下标}。"""
    col_map: dict[str, int] = {}
    for ci, cell in enumerate(header_row):
        if not cell:
            continue
        cell_str = str(cell)
        for field, keywords in COLUMN_KEYWORDS.items():
            if field in col_map:
                continue
            if any(kw in cell_str for kw in keywords):
                col_map[field] = ci
                break
    return col_map


def _merge_rows_into_schools(
    rows: list,
    col_map: dict[str, int],
    schools_map: dict,
    warnings: list,
) -> None:
    """逐行处理，合并单元格（前向填充），累积到 schools_map。

    选科要求策略：
    - 每个专业行都记录自己的选科要求（subject_req_raw），存在 major 级别
    - 专业组级别仅保留"代表值"（第一个非空值），供无专业级数据时回退使用
    - 如果一个专业组内各专业选科要求不同，只在组级别记录一条汇总 warning，不逐行警告
    """

    # 前向填充状态（模拟合并单元格）
    prev: dict[str, str | None] = {}
    # 记录院校代码缺失（每所学校只警告一次）
    warned_missing_code: set = set()
    # 记录专业组内选科要求不一致（每组只警告一次）
    warned_mixed_req: set = set()

    for ri, row in enumerate(rows):
        def get(field: str) -> str | None:
            ci = col_map.get(field)
            if ci is None or ci >= len(row):
                return None
            val = row[ci]
            if val is None:
                # 合并单元格：用上一行同字段的值
                return prev.get(field)
            prev[field] = val
            return val

        school_code = _normalize_code(get("school_code"))
        school_name = get("school_name")

        if not school_code and not school_name:
            continue  # 空行

        # 容忍：学校代码缺失时用名称作 key
        key = school_code or f"name:{school_name}"

        if key not in schools_map:
            schools_map[key] = {
                "school_code": school_code or "",
                "school_name": school_name or "",
                "school_city": get("school_city"),
                "school_province": get("school_province_loc"),
                "school_tier": [],
                "is_public": True,
                "is_military": _is_military(school_name),
                "is_police": _is_police(school_name),
                "major_groups": [],
            }
            if not school_code and school_name not in warned_missing_code:
                warned_missing_code.add(school_name)
                warnings.append(
                    f"院校代码缺失，已用院校名称 '{school_name}' 代替，请手工补全"
                )

        school = schools_map[key]

        group_code = get("group_code") or ""
        group_name = get("group_name") or ""
        subject_req_raw = get("subject_req_raw")  # 原文，不改
        major_code = _normalize_code(get("major_code"))
        major_name = get("major_name")

        if not major_name:
            continue  # 没有专业名的行跳过

        # 找或新建专业组
        group = _find_or_create_group(school["major_groups"], group_code, group_name)
        # 组级别只记录第一个出现的选科要求（作为回退值）
        if group["subject_requirement_raw"] is None and subject_req_raw:
            group["subject_requirement_raw"] = subject_req_raw
        elif subject_req_raw and group["subject_requirement_raw"] != subject_req_raw:
            # 同组内出现了不同的选科要求——每组只警告一次
            group_key = f"{school_code or school_name}_{group_code}"
            if group_key not in warned_mixed_req:
                warned_mixed_req.add(group_key)
                warnings.append(
                    f"学校 '{school_name}' 专业组 '{group_code or group_name}' "
                    f"内各专业选科要求不同（首条：'{group['subject_requirement_raw']}'），"
                    f"各专业已单独记录选科要求，组级别保留首条值"
                )

        group["majors"].append({
            "major_code": major_code or "",
            "major_name": major_name,
            "major_category": None,
            "yearly_admission_data": [],
            "subject_req_raw": subject_req_raw or "",   # 专业级别选科要求（最准确）
            "single_subject_requirement": None,
            "gender_limit": get("gender_limit"),
            "physical_requirement_notes": _parse_physical_notes(get("physical_notes")),
        })


def _find_or_create_group(groups: list, group_code: str, group_name: str) -> dict:
    code_key = group_code or group_name
    for g in groups:
        if (g["group_code"] or g["group_name"]) == code_key:
            return g
    new_group = {
        "group_code": group_code,
        "group_name": group_name,
        "subject_requirement_raw": None,
        "majors": [],
    }
    groups.append(new_group)
    return new_group


def _normalize_code(raw: str | None) -> str | None:
    """去除前导零、小数点、空格，确保纯数字。"""
    if not raw:
        return None
    s = str(raw).strip()
    # 去掉 openpyxl 读出的 .0 后缀
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s if s else None


def _is_military(name: str | None) -> bool:
    if not name:
        return False
    return any(kw in name for kw in ["军", "国防科技", "海军", "空军", "陆军", "火箭军", "战略支援"])


def _is_police(name: str | None) -> bool:
    if not name:
        return False
    return any(kw in name for kw in ["公安", "警察", "警官", "政法", "司法警官"])


def _parse_physical_notes(raw: str | None) -> list[str]:
    if not raw or raw.strip() in ("-", "—", "无", ""):
        return []
    return [raw.strip()]


def _find_header_row(
    rows: list,
    keywords: dict[str, list[str]],
    max_scan: int = 5,
    required: set[str] | None = None,
) -> tuple[int, dict[str, int]]:
    """在前 max_scan 行中找第一个满足 required 字段要求的表头行。

    required：必须同时命中的字段名集合，防止标题行被误判为表头。
              未指定时要求命中 >= 2 个字段。
    返回 (header_row_index, col_map)；找不到则返回 (-1, {})。
    多行表头（如一分一段表用两行标注"本段人数/累计人数"）会把连续两行合并后再匹配。

    策略：先逐行扫描单行表头（优先级高），全部失败后再尝试两行合并（处理跨行表头）。
    这样可以避免标题行（如"山东省2024高考专业录取分数"）因包含"专业"等关键词而
    在 merged 模式下把字段错误地映射到相邻列（如把 major_name 映射到年份列）。
    """
    def _is_valid(col_map: dict) -> bool:
        if required:
            return all(f in col_map for f in required)
        return len(col_map) >= 2  # 至少命中2列才算真正的表头

    scan = min(max_scan, len(rows))

    # 第一遍：只尝试单行，优先级最高
    for i in range(scan):
        col_map = _detect_column_map_generic(rows[i], keywords)
        if _is_valid(col_map):
            return i, col_map

    # 第二遍：回退到两行合并（处理跨两行的表头，如一分一段表）
    for i in range(min(scan - 1, len(rows) - 1)):
        merged = _merge_two_header_rows(rows[i], rows[i + 1])
        col_map = _detect_column_map_generic(merged, keywords)
        if _is_valid(col_map):
            # 数据行从 i+2 开始，返回 i+1 让调用方用 header_idx+1 跳过两行
            return i + 1, col_map

    return -1, {}


def _merge_two_header_rows(row_a: list, row_b: list) -> list:
    """把两行合并成一行字符串列表，用于识别跨两行的表头。

    关键逻辑：row_a 中的 None 表示合并单元格，向右继承最近一个非空值。
    例如：
      row_a = ["分数段", "全体", None, "选考物理", None, ...]
      row_b = [None, "本段人数", "累计人数", "本段人数", "累计人数", ...]
    合并后：
      ["分数段", "全体 本段人数", "全体 累计人数", "选考物理 本段人数", "选考物理 累计人数", ...]
    这样每列都带有科目前缀，关键词匹配才能区分不同科目的本段/累计列。
    """
    length = max(len(row_a), len(row_b))
    merged = []
    last_a = ""  # 继承上一列的科目名
    for i in range(length):
        a = row_a[i] if i < len(row_a) else None
        b = row_b[i] if i < len(row_b) else None
        a_str = str(a).strip() if a is not None else ""
        b_str = str(b).strip() if b is not None else ""
        if a_str:
            last_a = a_str  # 更新继承值
        effective_a = a_str if a_str else last_a  # None 时用继承值
        merged.append((effective_a + " " + b_str).strip() or None)
    return merged


def _flatten_sheets(raw: dict) -> list[dict]:
    """将 Excel parser 输出的 sheets 转为 all_tables_flat 格式。"""
    result = []
    for sheet in raw.get("sheets", []):
        rows = sheet.get("rows", [])
        if rows:
            result.append({
                "page": None,
                "name": sheet.get("name", ""),
                "table_index": 0,
                "rows": rows,
            })
    return result
