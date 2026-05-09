"""数据加载层。

所有数据都从磁盘文件读取；任何缺失、版本不匹配都必须抛错，
禁止用默认值或旧数据顶替（PRD §0.4 / §五）。

支持格式（按优先级）：
- CSV  (.csv)：主格式，每行一条记录，列标题为中文，Excel 可直接打开核对
- JSONL (.jsonl)：旧格式，向后兼容，逐行 JSON
- JSON  (.json)：旧格式，向后兼容，整体 JSON

小型配置文件（physical_restrictions、province_exam_mode 等）仍使用 JSON，
因为它们是系统内部规则文件，不需要人工核对。

历史数据（往年录取位次）可作为参考，但加载时必须在返回值中标注数据年份，
由上层调用方在输出中明确告知用户所用数据的年份。
"""
from __future__ import annotations

import csv as _csv
import json
import logging
import re as _re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# 去掉专业名括号注释，用于二级模糊匹配
# 只匹配不含嵌套括号的最内层括号，多次迭代直到稳定，处理任意嵌套深度
# 例："计算机(拔尖班(泰山学堂)、菁英班)" → "计算机"
_PAREN_INNER_RE = _re.compile(r"[（(][^（(）)]*[）)]")


def _strip_major_name(name: str) -> str:
    """去掉专业名中所有括号及其内容，从最内层向外迭代直到无括号残留。"""
    while True:
        stripped = _PAREN_INNER_RE.sub("", name).strip()
        if stripped == name:
            return stripped
        name = stripped

from .errors import (
    DataParseFailedError,
    DataSourceUnavailableError,
    DataVersionMismatchError,
)

DEFAULT_DATA_DIR = (
    Path(__file__).resolve().parent.parent  # constraint-filter/
    / "data"
)

# 生成数据目录：项目根目录下的 outputs/
# data_loader.py 路径：.trae/skills/constraint-filter/constraint_filter/data_loader.py
# parent×5 = jinli/（项目根）
DEFAULT_GENERATED_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "结果"
)


# ── 配置文件读取（JSON，内部规则，不需要人工核对）────────────────────────────

def _read_json(path: Path, *, kind: str) -> Dict[str, Any]:
    if not path.exists():
        raise DataSourceUnavailableError(
            f"无法找到{kind}数据文件：{path.name}",
            user_action="请确认数据文件存在；如缺失，请联系维护者补充。",
            detail={"missing_path": str(path), "kind": kind},
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise DataParseFailedError(
            f"{kind}数据文件解析失败：{exc.msg}",
            user_action="请联系维护者修复该数据文件。",
            detail={"path": str(path), "line": exc.lineno, "col": exc.colno},
        ) from exc


def load_province_exam_mode(data_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return _read_json(data_dir / "province_exam_mode.json", kind="省份高考模式")


def load_physical_restrictions(data_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return _read_json(data_dir / "physical_restrictions.json", kind="体检限制")


def load_subject_requirement_keywords(data_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return _read_json(data_dir / "subject_requirement_keywords.json", kind="选科要求解析规则")


# ── 省份映射 ──────────────────────────────────────────────────────────────────

PROVINCE_FILE_SLUG = {
    "北京": "beijing", "天津": "tianjin", "河北": "hebei", "山西": "shanxi",
    "内蒙古": "neimenggu", "辽宁": "liaoning", "吉林": "jilin", "黑龙江": "heilongjiang",
    "上海": "shanghai", "江苏": "jiangsu", "浙江": "zhejiang", "安徽": "anhui",
    "福建": "fujian", "江西": "jiangxi", "山东": "shandong", "河南": "henan",
    "湖北": "hubei", "湖南": "hunan", "广东": "guangdong", "广西": "guangxi",
    "海南": "hainan", "重庆": "chongqing", "四川": "sichuan", "贵州": "guizhou",
    "云南": "yunnan", "西藏": "xizang", "陕西": "shaanxi", "甘肃": "gansu",
    "青海": "qinghai", "宁夏": "ningxia", "新疆": "xinjiang",
}


# ── 通用文件路径解析（CSV 优先，兼容旧格式）──────────────────────────────────

def _resolve_data_path(data_dir: Path, stem: str, *, kind: str) -> tuple[Path, str]:
    """优先返回 .csv，其次 .jsonl，再次 .json，都不存在则抛错。返回 (path, fmt)。"""
    for ext, fmt in [(".csv", "csv"), (".jsonl", "jsonl"), (".json", "json")]:
        p = data_dir / f"{stem}{ext}"
        if p.exists():
            return p, fmt
    raise DataSourceUnavailableError(
        f"无法找到{kind}数据文件（已查找 {stem}.csv / .jsonl / .json）",
        user_action="请确认数据文件存在；如缺失，请使用 数据准备 导入。",
        detail={"missing_stem": stem, "data_dir": str(data_dir), "kind": kind},
    )


# ── CSV 迭代读取 ──────────────────────────────────────────────────────────────

def _iter_csv(path: Path, *, kind: str) -> Iterator[Dict[str, str]]:
    """逐行读取 CSV，yield 每行的 {列名: 值} 字典。"""
    if not path.exists():
        raise DataSourceUnavailableError(
            f"无法找到{kind}数据文件：{path.name}",
            user_action="请确认数据文件存在；如缺失，请使用 数据准备 重新导入。",
            detail={"missing_path": str(path), "kind": kind},
        )
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                yield dict(row)
    except OSError as exc:
        raise DataSourceUnavailableError(
            f"读取{kind}文件失败：{exc}",
            user_action="请确认文件权限正常。",
            detail={"path": str(path)},
        ) from exc


# ── 旧格式兼容：JSONL 迭代读取 ───────────────────────────────────────────────

def _iter_jsonl(path: Path, *, kind: str) -> Iterator[Dict[str, Any]]:
    """流式迭代 JSONL 文件，跳过 __meta__ 行，逐行 yield 记录。"""
    if not path.exists():
        raise DataSourceUnavailableError(
            f"无法找到{kind}数据文件：{path.name}",
            user_action="请确认数据文件存在；如缺失，请使用 数据准备 重新导入。",
            detail={"missing_path": str(path), "kind": kind},
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DataParseFailedError(
                        f"{kind} JSONL 第 {lineno} 行解析失败：{exc.msg}",
                        user_action="请联系维护者修复该数据文件。",
                        detail={"path": str(path), "line": lineno},
                    ) from exc
                if rec.get("__meta__"):
                    continue
                yield rec
    except DataParseFailedError:
        raise
    except OSError as exc:
        raise DataSourceUnavailableError(
            f"读取{kind}文件失败：{exc}",
            user_action="请确认文件权限正常。",
            detail={"path": str(path)},
        ) from exc


# ── 年份回退辅助 ───────────────────────────────────────────────────────────

def _find_fallback_year(
    province: str,
    slug: str,
    requested_year: int,
    generated_dir: Path,
    data_dir: Path,
    data_type: str,
) -> tuple[int, str]:
    """在精确年份找不到时，查找最近可用年份的数据文件。

    回退策略：
    1. 优先找 <= requested_year 的最近年份（过往数据更可靠）
    2. 如果没有过往数据，找最近的可用年份

    返回 (actual_year, warning_msg)。如果完全找不到，返回 (0, "")。
    """
    available_years: list[int] = []

    if data_type == "admission_plan":
        # 新格式: outputs/admission_plans/山东_2024_招生计划.csv
        pattern = _re.compile(rf"^{_re.escape(province)}_(\d+)_招生计划\.csv$")
        if generated_dir.exists():
            for f in (generated_dir / "admission_plans").glob("*.csv"):
                m = pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))
        # 旧格式: data/admission_plans/shandong_2024.csv
        old_pattern = _re.compile(rf"^{_re.escape(slug)}_(\d+)\.csv$")
        if data_dir.exists():
            for f in (data_dir / "admission_plans").glob("*.csv"):
                m = old_pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))
        # 旧 JSON 格式
        old_json_pattern = _re.compile(rf"^{_re.escape(slug)}_(\d+)\.json$")
        if data_dir.exists():
            for f in (data_dir / "admission_plans").glob("*.json"):
                m = old_json_pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))

    elif data_type == "historical_ranks":
        # 新格式: outputs/山东_2024_专业录取分数.csv
        pattern = _re.compile(rf"^{_re.escape(province)}_(\d+)_专业录取分数\.csv$")
        if generated_dir.exists():
            for f in generated_dir.glob("*.csv"):
                m = pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))
        # 旧格式
        old_pattern = _re.compile(rf"^{_re.escape(slug)}_(\d+)_major_admission_scores.*$")
        if data_dir.exists():
            for f in data_dir.glob(f"{slug}_*_major_admission_scores*"):
                m = old_pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))

    elif data_type == "score_rank_table":
        # 新格式: outputs/山东_2024_一分一段表.csv
        pattern = _re.compile(rf"^{_re.escape(province)}_(\d+)_一分一段表\.csv$")
        if generated_dir.exists():
            for f in generated_dir.glob("*.csv"):
                m = pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))
        # 旧格式
        old_pattern = _re.compile(rf"^{_re.escape(slug)}_(\d+)_score_rank_table.*$")
        if data_dir.exists():
            for f in data_dir.glob(f"{slug}_*_score_rank_table*"):
                m = old_pattern.match(f.name)
                if m:
                    available_years.append(int(m.group(1)))

    available_years = sorted(set(available_years), reverse=True)
    if not available_years:
        return 0, ""

    # 优先找 <= requested_year 的最近年份
    past_years = [y for y in available_years if y <= requested_year]
    if past_years:
        actual_year = past_years[0]
    else:
        # 没有过往数据，找最近的可用年份
        actual_year = available_years[0]

    if actual_year != requested_year:
        warning = (
            f"⚠️ 数据年份回退：系统中未找到 {province} {requested_year} 年的"
            f"{'招生计划' if data_type == 'admission_plan' else '历史录取位次' if data_type == 'historical_ranks' else '一分一段表'}，"
            f"自动回退到最近可用年份 {actual_year} 年的数据。"
            f"请知悉：招生专业、选科要求和计划人数每年可能变化，"
            f"{actual_year} 年数据仅供参考，最终以当年官方发布为准。"
        )
        return actual_year, warning

    return actual_year, ""


# ── 招生计划 ──────────────────────────────────────────────────────────────────

def load_admission_plan(
    province: str, year: int, data_dir: Optional[Path | str] = None
) -> Dict[str, Any]:
    """加载某省某年招生计划，返回树形结构（与旧 JSON 格式一致）。

    查找顺序：
    1. outputs/admission_plans/{省份}_{年份}_招生计划.csv（数据准备 生成）
    2. constraint-filter/data/admission_plans/{slug}_{year}.csv（旧格式）
    3. constraint-filter/data/admission_plans/{slug}_{year}.json（旧格式）
    4. 以上均找不到时，回退到最近可用年份的数据
    """
    generated_dir = DEFAULT_GENERATED_DIR
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    slug = PROVINCE_FILE_SLUG.get(province)
    if slug is None:
        raise DataSourceUnavailableError(
            f"省份 '{province}' 暂无对应招生计划文件映射",
            user_action="该省份数据尚未导入；请联系维护者补充，或改填已支持省份。",
            detail={"province": province, "supported": list(PROVINCE_FILE_SLUG.keys())},
        )

    # 1. 优先从 outputs/ 读取（数据准备 生成的新格式）
    csv_path = generated_dir / "admission_plans" / f"{province}_{year}_招生计划.csv"
    if csv_path.exists():
        return _load_admission_plan_csv(csv_path, province, year)

    # 2. 回退旧格式（data/ 目录）
    old_csv_path = data_dir / "admission_plans" / f"{slug}_{year}.csv"
    if old_csv_path.exists():
        return _load_admission_plan_csv(old_csv_path, province, year)

    json_path = data_dir / "admission_plans" / f"{slug}_{year}.json"
    if json_path.exists():
        plan = _read_json(json_path, kind=f"{province} {year} 年招生计划")
        valid_for = plan.get("valid_for_year")
        if valid_for != year:
            # 旧 JSON 格式：有年份标记但不匹配 → 尝试年份回退
            fallback_year, warning = _find_fallback_year(
                province, slug, year, generated_dir, data_dir, "admission_plan"
            )
            if fallback_year > 0:
                # 重新加载回退年份的数据
                fallback_csv = generated_dir / "admission_plans" / f"{province}_{fallback_year}_招生计划.csv"
                if fallback_csv.exists():
                    result = _load_admission_plan_csv(fallback_csv, province, fallback_year)
                    result["_warning"] = warning
                    return result
                fallback_old_csv = data_dir / "admission_plans" / f"{slug}_{fallback_year}.csv"
                if fallback_old_csv.exists():
                    result = _load_admission_plan_csv(fallback_old_csv, province, fallback_year)
                    result["_warning"] = warning
                    return result
        return plan

    # 3. 年份回退：查找最近可用年份
    fallback_year, warning = _find_fallback_year(
        province, slug, year, generated_dir, data_dir, "admission_plan"
    )
    if fallback_year > 0:
        fallback_csv = generated_dir / "admission_plans" / f"{province}_{fallback_year}_招生计划.csv"
        if fallback_csv.exists():
            result = _load_admission_plan_csv(fallback_csv, province, fallback_year)
            result["_warning"] = warning
            return result
        fallback_old_csv = data_dir / "admission_plans" / f"{slug}_{fallback_year}.csv"
        if fallback_old_csv.exists():
            result = _load_admission_plan_csv(fallback_old_csv, province, fallback_year)
            result["_warning"] = warning
            return result

    raise DataSourceUnavailableError(
        f"无法找到 {province} {year} 年招生计划"
        f"（已查找 outputs/admission_plans/ 和 data/admission_plans/）",
        user_action="请使用 数据准备 导入该省份该年度的招生计划文件。",
        detail={"province": province, "year": year,
                "generated_dir": str(generated_dir / "admission_plans"),
                "data_dir": str(data_dir / "admission_plans")},
    )


def _load_admission_plan_csv(path: Path, province: str, year: int) -> Dict[str, Any]:
    """从招生计划 CSV 重建树形结构。

    CSV 列名约定（storage.py 写入时保证）：
      院校代码, 院校名称, 所在城市, 所属省份, 专业组代码, 专业组名称, 选科要求,
      专业代码, 专业名称, 专业类别, 是否军校, 是否公安, 性别要求, 体检备注,
      {年份}最低分, {年份}最低位次（最多3年）
    """
    # 检测年份列：列名形如 "2025最低分"
    _year_col_re = _re.compile(r"^(\d{4})最低分$")

    rows: List[Dict[str, str]] = list(_iter_csv(path, kind=f"{province} {year} 年招生计划"))
    if not rows:
        raise DataParseFailedError(
            f"{province} {year} 年招生计划 CSV 为空：{path.name}",
            user_action="请重新运行 数据准备 生成该文件。",
            detail={"path": str(path)},
        )

    # 从表头检测有哪些年份列
    data_years: List[int] = sorted(
        [int(m.group(1)) for col in rows[0] if (m := _year_col_re.match(col))],
        reverse=True,
    )

    schools_map: Dict[str, Any] = {}

    for row in rows:
        school_code = row.get("院校代码", "").strip()
        school_name = row.get("院校名称", "").strip()
        key = school_code or f"name:{school_name}"
        if not key or key == "name:":
            continue

        if key not in schools_map:
            schools_map[key] = {
                "school_code":    school_code,
                "school_name":    school_name,
                "school_city":    row.get("所在城市", "").strip() or None,
                "school_province": row.get("所属省份", "").strip() or None,
                "school_tier":    [],
                "is_public":      True,
                "is_military":    row.get("是否军校", "").strip() == "是",
                "is_police":      row.get("是否公安", "").strip() == "是",
                "major_groups":   [],
            }

        school = schools_map[key]
        group_code = row.get("专业组代码", "").strip()
        group_name = row.get("专业组名称", "").strip()
        subject_req = row.get("选科要求", "").strip() or None

        # 找或新建专业组
        group = next(
            (g for g in school["major_groups"] if g["group_code"] == group_code),
            None,
        )
        if group is None:
            group = {
                "group_code":             group_code,
                "group_name":             group_name,
                "subject_requirement_raw": subject_req,
                "majors":                 [],
            }
            school["major_groups"].append(group)

        # 重建 yearly_admission_data
        yearly: List[Dict[str, Any]] = []
        for y in data_years:
            min_score = row.get(f"{y}最低分", "").strip()
            min_rank  = row.get(f"{y}最低位次", "").strip()
            if not min_score and not min_rank:
                continue
            entry: Dict[str, Any] = {"year": y}
            if min_score:
                entry["min_score"] = min_score
            if min_rank:
                try:
                    entry["min_rank"] = int(min_rank)
                except ValueError:
                    entry["min_rank"] = min_rank
            yearly.append(entry)

        notes_raw = row.get("体检备注", "").strip()
        notes = [n.strip() for n in notes_raw.split("；") if n.strip()] if notes_raw else []

        group["majors"].append({
            "major_code":                row.get("专业代码", "").strip(),
            "major_name":                row.get("专业名称", "").strip(),
            "major_category":            row.get("专业类别", "").strip() or None,
            "yearly_admission_data":     yearly,
            "single_subject_requirement": None,
            "gender_limit":              row.get("性别要求", "").strip() or None,
            "physical_requirement_notes": notes,
        })

    return {
        "version":       f"{year}-招生计划-csv",
        "source":        path.name,
        "valid_for_year": year,
        "province":      province,
        "source_type":   "csv",
        "schools":       list(schools_map.values()),
    }


# ── 历史录取位次 ──────────────────────────────────────────────────────────────

def load_historical_ranks(
    province: str, year: int, data_dir: Optional[Path | str] = None
) -> Dict[tuple, list]:
    """加载历史录取位次，返回 {(school_name, major_name): [yearly_data]} 查找表。

    查找顺序：outputs/{省份}_{年份}_专业录取分数.csv → data/{slug}_{year}_major_admission_scores.*

    文件不存在时返回空字典（软降级），位次过滤退化为 unknown，不报错。
    """
    generated_dir = DEFAULT_GENERATED_DIR
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    slug = PROVINCE_FILE_SLUG.get(province)
    if slug is None:
        return {}

    # 1. 优先从 outputs/ 读取（数据准备 生成的新格式）
    new_csv = generated_dir / f"{province}_{year}_专业录取分数.csv"
    if new_csv.exists():
        path, fmt = new_csv, "csv"
    else:
        # 2. 回退旧文件名（data/ 目录）
        old_csv = data_dir / f"{province}_{year}_专业录取分数.csv"
        if old_csv.exists():
            path, fmt = old_csv, "csv"
        else:
            stem = f"{slug}_{year}_major_admission_scores"
            try:
                path, fmt = _resolve_data_path(data_dir, stem, kind=f"{province} {year} 年历史录取位次")
            except DataSourceUnavailableError:
                # 3. 年份回退
                fallback_year, _ = _find_fallback_year(
                    province, slug, year, generated_dir, data_dir, "historical_ranks"
                )
                if fallback_year > 0:
                    return load_historical_ranks(province, fallback_year, data_dir)
                return {}

    lookup: Dict[tuple, list] = {}

    def _process(school: str, major: str, min_rank_raw: str,
                 min_score_raw: str, rec_year_raw: str) -> None:
        if not school or not major:
            return
        try:
            entry = {
                "year":      int(rec_year_raw) if rec_year_raw else year,
                "min_rank":  int(min_rank_raw) if min_rank_raw else 0,
                "min_score": min_score_raw,
                "data_year": year,
            }
        except (ValueError, TypeError):
            return
        lookup.setdefault((school, major), []).append(entry)

    if fmt == "csv":
        for row in _iter_csv(path, kind=f"{province} {year} 年历史录取位次"):
            _process(
                row.get("院校名称", "").strip(),
                row.get("专业名称", "").strip(),
                row.get("最低位次", row.get("最低录取位次", "")).strip(),
                row.get("最低分", row.get("最低录取分", "")).strip(),
                row.get("年份", "").strip(),
            )
    elif fmt == "jsonl":
        for rec in _iter_jsonl(path, kind=f"{province} {year} 年历史录取位次"):
            try:
                _process(
                    rec.get("school_name", ""),
                    rec.get("major_name", ""),
                    str(rec.get("min_rank", "")),
                    str(rec.get("min_score", "")),
                    str(rec.get("year", "")),
                )
            except Exception:
                continue
    else:
        raw = _read_json(path, kind=f"{province} {year} 年历史录取位次")
        for rec in raw.get("data", []):
            try:
                _process(
                    rec.get("school_name", ""),
                    rec.get("major_name", ""),
                    str(rec.get("min_rank", "")),
                    str(rec.get("min_score", "")),
                    str(rec.get("year", "")),
                )
            except Exception:
                continue

    for key in lookup:
        lookup[key].sort(key=lambda r: r["year"], reverse=True)

    logger.debug(
        "历史录取位次加载完成：共 %d 条 (school, major) 组合",
        len(lookup),
    )

    return lookup


def lookup_historical_rank(
    ranks: Dict[tuple, list],
    school_name: str,
    major_name: str,
) -> list:
    """按 (school_name, major_name) 查找历史录取位次，支持二级回退匹配。

    查找策略（依次尝试，命中即返回）：
    1. 精确匹配：(school_name, major_name)
    2. 去掉招生计划专业名中的括号注释后匹配
       例："计算机科学与技术(含拔尖班)" → "计算机科学与技术"
    """
    # 第一级：精确匹配
    data = ranks.get((school_name, major_name))
    if data is not None:
        return data

    # 第二级：递归去掉嵌套括号后匹配（招生计划专业名常带多层注释，历史表只有基础名）
    base = _strip_major_name(major_name)
    if base != major_name:
        data = ranks.get((school_name, base))
        if data is not None:
            logger.debug(
                "位次二级匹配命中：%s · %r → 基础名 %r",
                school_name, major_name, base,
            )
            return data

    return []


# ── 一分一段表 ────────────────────────────────────────────────────────────────

def load_score_rank_table(
    province: str, year: int, data_dir: Optional[Path | str] = None
) -> Dict[str, Any]:
    """加载一分一段表，返回 {score_str: record} 查找表。

    查找顺序：outputs/{省份}_{年份}_一分一段表.csv → data/{slug}_{year}_score_rank_table.*
    """
    generated_dir = DEFAULT_GENERATED_DIR
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    slug = PROVINCE_FILE_SLUG.get(province)
    if slug is None:
        return {}

    # 1. 优先从 outputs/ 读取（数据准备 生成的新格式）
    new_csv = generated_dir / f"{province}_{year}_一分一段表.csv"
    if new_csv.exists():
        path, fmt = new_csv, "csv"
    else:
        # 2. 回退旧文件名（data/ 目录）
        old_csv = data_dir / f"{province}_{year}_一分一段表.csv"
        if old_csv.exists():
            path, fmt = old_csv, "csv"
        else:
            stem = f"{slug}_{year}_score_rank_table"
            try:
                path, fmt = _resolve_data_path(data_dir, stem, kind=f"{province} {year} 年一分一段表")
            except DataSourceUnavailableError:
                # 3. 年份回退
                fallback_year, _ = _find_fallback_year(
                    province, slug, year, generated_dir, data_dir, "score_rank_table"
                )
                if fallback_year > 0:
                    return load_score_rank_table(province, fallback_year, data_dir)
                return {}

    lookup: Dict[str, Any] = {}


    if fmt == "csv":
        for row in _iter_csv(path, kind=f"{province} {year} 年一分一段表"):
            score = row.get("分数", "").strip()
            if not score:
                continue
            lookup[score] = {
                "score_range": score,
                "total":     {"current": row.get("合计本次", ""), "cumulative": row.get("合计累计", "")},
                "physics":   {"current": row.get("物理本次", ""), "cumulative": row.get("物理累计", "")},
                "history":   {"current": row.get("历史本次", ""), "cumulative": row.get("历史累计", "")},
                "chemistry": {"current": row.get("化学本次", ""), "cumulative": row.get("化学累计", "")},
                "biology":   {"current": row.get("生物本次", ""), "cumulative": row.get("生物累计", "")},
                "politics":  {"current": row.get("政治本次", ""), "cumulative": row.get("政治累计", "")},
                "geography": {"current": row.get("地理本次", ""), "cumulative": row.get("地理累计", "")},
            }
    elif fmt == "jsonl":
        for rec in _iter_jsonl(path, kind=f"{province} {year} 年一分一段表"):
            score = rec.get("score_range")
            if score:
                lookup[str(score)] = rec
    else:
        raw = _read_json(path, kind=f"{province} {year} 年一分一段表")
        for rec in raw.get("data", []):
            score = rec.get("score_range")
            if score:
                lookup[str(score)] = rec

    return lookup


# ── 分数 → 位次自动换算 ──────────────────────────────────────────────────────

def lookup_rank_from_score(
    score: int,
    province: str,
    exam_year: int,
    exam_mode: str,
    subject_category: str,
    data_dir: Optional[Path] = None,
) -> Optional[int]:
    """根据总分从一分一段表反查全省累计位次。

    返回的位次用于 rank_ratio 计算，与历史录取数据的位次体系保持一致：
    - 综合改革省份（3+3 / 3+1+2）：使用"合计累计"（全省所有考生排名）
      历史录取数据中的最低位次也基于此全省排名，两侧一致。
    - 传统文理省份：同样使用"合计累计"作为近似。

    如果一分一段表不存在或分数不在表中，返回 None（调用方应加 warning，不中断流水线）。
    """
    table = load_score_rank_table(province, exam_year, data_dir)
    if not table:
        return None

    row = table.get(str(score))
    if not row:
        # 分数刚好不在表中（极值），取偏差最小的相邻分数
        for offset in range(1, 10):
            row = table.get(str(score + offset)) or table.get(str(score - offset))
            if row:
                break
    if not row:
        return None

    try:
        return int(row["total"]["cumulative"])
    except (KeyError, ValueError, TypeError):
        return None
