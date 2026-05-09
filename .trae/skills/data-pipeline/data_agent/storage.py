"""写入层：把验证通过的 normalized 数据写到 constraint-filter 数据目录。

输出格式：全部改为 CSV（逗号分隔，UTF-8 BOM 编码，Excel 可直接双击打开）。

三种数据类型各对应一种 CSV 格式：
  - 招生计划（admission_plan）  → admission_plans/{slug}_{year}.csv
  - 历年录取位次               → {slug}_{year}_major_admission_scores.csv
  - 一分一段表                 → {slug}_{year}_score_rank_table.csv

target_dir 参数指向 constraint-filter 的 data/ 根目录。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .errors import StorageError

PROVINCE_FILE_SLUG = {
    "北京": "beijing",    "天津": "tianjin",   "河北": "hebei",
    "山西": "shanxi",     "内蒙古": "neimenggu","辽宁": "liaoning",
    "吉林": "jilin",      "黑龙江": "heilongjiang","上海": "shanghai",
    "江苏": "jiangsu",    "浙江": "zhejiang",   "安徽": "anhui",
    "福建": "fujian",     "江西": "jiangxi",    "山东": "shandong",
    "河南": "henan",      "湖北": "hubei",      "湖南": "hunan",
    "广东": "guangdong",  "广西": "guangxi",    "海南": "hainan",
    "重庆": "chongqing",  "四川": "sichuan",    "贵州": "guizhou",
    "云南": "yunnan",     "西藏": "xizang",     "陕西": "shaanxi",
    "甘肃": "gansu",      "青海": "qinghai",    "宁夏": "ningxia",
    "新疆": "xinjiang",
}

# 默认目标目录：项目根目录下的 outputs/
# storage.py 路径：.trae/skills/数据准备/data_模块/storage.py
# parent×5 = jinli/（项目根）
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "结果"

# 输出摘要目录（同 _DEFAULT_DATA_DIR，一并写入 outputs/）
_OUTPUTS_DIR = _DEFAULT_DATA_DIR


def store(
    normalized: dict[str, Any],
    *,
    target_dir: Path | str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """将 normalized 数据以 CSV 格式写到目标目录。

    返回 {
        "status": "success" | "error",
        "output_path": "<写入的文件路径>",
        "message": "...",
        "overwritten": bool
    }
    """
    province = normalized.get("province")
    year = normalized.get("valid_for_year")
    data_type = normalized.get("type")  # None=招生计划, "major_admission_scores", "score_rank_table"

    if not province:
        raise StorageError(
            "province 字段缺失，无法确定写入路径",
            detail={"hint": "请在确认环节补充省份信息"},
        )
    if not year:
        raise StorageError(
            "valid_for_year 字段缺失，无法确定写入路径",
            detail={"hint": "请在确认环节补充招生年份"},
        )

    slug = PROVINCE_FILE_SLUG.get(province)
    if slug is None:
        raise StorageError(
            f"省份 '{province}' 没有对应的文件名映射",
            detail={"province": province,
                    "hint": "请联系维护者在 storage.py 的 PROVINCE_FILE_SLUG 中添加此省"},
        )

    base_dir = Path(target_dir).resolve() if target_dir else _DEFAULT_DATA_DIR.resolve()

    if data_type == "major_admission_scores":
        tgt_dir = base_dir
        filename = f"{province}_{year}_专业录取分数.csv"
        writer_fn = _write_historical_ranks_csv
        type_label = "历年录取位次"
    elif data_type == "score_rank_table":
        tgt_dir = base_dir
        filename = f"{province}_{year}_一分一段表.csv"
        writer_fn = _write_score_rank_csv
        type_label = "一分一段表"
    elif data_type == "admission_filing":
        tgt_dir = base_dir
        round_num = normalized.get("round_number", "?")
        filename = f"{province}_{year}_第{round_num}次志愿投档.csv"
        writer_fn = _write_admission_filing_csv
        type_label = f"第{round_num}次志愿投档情况"
    else:
        tgt_dir = base_dir / "admission_plans"
        filename = f"{province}_{year}_招生计划.csv"
        writer_fn = _write_admission_plan_csv
        type_label = "招生计划"

    tgt_dir.mkdir(parents=True, exist_ok=True)
    output_path = tgt_dir / filename

    overwritten = False
    if output_path.exists():
        if not overwrite:
            raise StorageError(
                f"目标文件已存在：{output_path}\n"
                "若要覆盖，请在命令中加 --overwrite 标志。",
                detail={"existing_file": str(output_path),
                        "hint": "请先确认是否要覆盖已有数据"},
            )
        overwritten = True

    to_write = {k: v for k, v in normalized.items() if k != "_meta"}

    try:
        record_count = writer_fn(output_path, to_write)
    except OSError as exc:
        raise StorageError(
            f"写入文件失败：{exc}",
            detail={"output_path": str(output_path)},
        ) from exc

    _write_import_summary(province, year, type_label, filename, record_count, overwritten)

    return {
        "status": "success",
        "output_path": str(output_path),
        "format": "csv",
        "overwritten": overwritten,
        "message": (
            f"✅ 写入成功（CSV）：{output_path}\n"
            f"   类型：{type_label}，共 {record_count} 行数据\n"
            f"   适用年份：{year}  省份：{province}\n"
            f"   ⚠️ 来源：用户上传文件，请用 Excel 打开 CSV 核对关键数据后再使用。"
        ),
    }


def _write_import_summary(
    province: str,
    year: int | str,
    type_label: str,
    filename: str,
    record_count: int,
    overwritten: bool,
) -> None:
    """在 outputs/ 下写入或追加一条数据导入摘要 MD。

    每次成功 store 都在 outputs/数据导入记录_<省份>_<年份>.md 追加一条记录，
    方便用户在 outputs/ 统一查看所有中间产出。
    """
    from datetime import datetime

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = _OUTPUTS_DIR / f"0准备数据_数据导入记录_{province}_{year}.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_note = "（覆盖旧文件）" if overwritten else ""

    entry = (
        f"\n## {type_label} {status_note}\n"
        f"\n"
        f"- 写入时间：{now}\n"
        f"- 数据文件：`constraint-filter/data/{filename}`\n"
        f"- 记录数：{record_count} 条\n"
        f"- ⚠️ 来源：用户上传文件，请用 Excel 打开 CSV 核对关键数据后再使用\n"
    )

    if md_path.exists():
        md_path.open("a", encoding="utf-8").write(entry)
    else:
        header = (
            f"# 数据导入记录 — {province} {year}年\n"
            f"\n"
            f"本文件记录所有已导入 constraint-filter 的数据文件，供查阅和核对。\n"
        )
        md_path.write_text(header + entry, encoding="utf-8")


# ── CSV 写入函数 ──────────────────────────────────────────────────────────────

def _write_admission_plan_csv(path: Path, data: dict[str, Any]) -> int:
    """招生计划：树形结构 → 每行一个专业的 CSV。

    列：院校代码, 院校名称, 所在城市, 所属省份, 专业组代码, 专业组名称,
        选科要求, 专业代码, 专业名称, 专业类别, 是否军校, 是否公安,
        性别要求, 体检备注, [年份]最低分, [年份]最低位次（最近3年）
    """
    schools = data.get("schools", [])

    # 收集所有出现过的年份，取最近3年
    all_years: set[int] = set()
    for school in schools:
        for group in school.get("major_groups", []):
            for major in group.get("majors", []):
                for entry in major.get("yearly_admission_data", []):
                    try:
                        all_years.add(int(entry["year"]))
                    except (KeyError, ValueError, TypeError):
                        pass

    sorted_years = sorted(all_years, reverse=True)[:3]

    static_cols = [
        "院校代码", "院校名称", "所在城市", "所属省份",
        "专业组代码", "专业组名称", "选科要求",
        "专业代码", "专业名称", "专业类别",
        "是否军校", "是否公安", "性别要求", "体检备注",
    ]
    year_cols = []
    for y in sorted_years:
        year_cols += [f"{y}最低分", f"{y}最低位次"]

    headers = static_cols + year_cols
    row_count = 0

    # utf-8-sig = UTF-8 with BOM，Excel 双击可直接显示中文
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()

        for school in schools:
            for group in school.get("major_groups", []):
                for major in group.get("majors", []):
                    yearly = {
                        int(e["year"]): e
                        for e in major.get("yearly_admission_data", [])
                        if "year" in e
                    }
                    notes = major.get("physical_requirement_notes") or []

                    row: dict[str, Any] = {
                        "院校代码":   school.get("school_code", ""),
                        "院校名称":   school.get("school_name", ""),
                        "所在城市":   school.get("school_city") or "",
                        "所属省份":   school.get("school_province") or "",
                        "专业组代码": group.get("group_code", ""),
                        "专业组名称": group.get("group_name") or "",
                        "选科要求":   major.get("subject_req_raw") or group.get("subject_requirement_raw") or "",
                        "专业代码":   major.get("major_code", ""),
                        "专业名称":   major.get("major_name", ""),
                        "专业类别":   major.get("major_category") or "",
                        "是否军校":   "是" if school.get("is_military") else "否",
                        "是否公安":   "是" if school.get("is_police") else "否",
                        "性别要求":   major.get("gender_limit") or "",
                        "体检备注":   "；".join(notes),
                    }
                    for y in sorted_years:
                        entry = yearly.get(y, {})
                        row[f"{y}最低分"]   = entry.get("min_score", "")
                        row[f"{y}最低位次"] = entry.get("min_rank", "")

                    writer.writerow(row)
                    row_count += 1

    return row_count


def _write_historical_ranks_csv(path: Path, data: dict[str, Any]) -> int:
    """历年录取位次：每行一条学校×专业×年份记录。

    列：院校名称, 专业名称, 选科要求, 最低分, 最低位次, 平均分,
        年份, 批次, 是否985, 是否211, 是否双一流, 院校省份, 院校城市
    """
    records = data.get("data", [])

    headers = [
        "院校名称", "专业名称", "选科要求",
        "最低分", "最低位次", "平均分",
        "年份", "批次",
        "是否985", "是否211", "是否双一流",
        "院校省份", "院校城市",
    ]
    field_map = {
        "院校名称":   "school_name",
        "专业名称":   "major_name",
        "选科要求":   "subject_requirement",
        "最低分":     "min_score",
        "最低位次":   "min_rank",
        "平均分":     "avg_score",
        "年份":       "year",
        "批次":       "admission_batch",
        "是否985":    "is_985",
        "是否211":    "is_211",
        "是否双一流": "double_first_class",
        "院校省份":   "province",
        "院校城市":   "city",
    }

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow({ch: rec.get(en, "") for ch, en in field_map.items()})

    return len(records)


def _write_admission_filing_csv(path: Path, data: dict[str, Any]) -> int:
    """志愿投档情况：每行一条学校×专业的投档记录。

    列：院校代码, 院校名称, 专业代码, 专业名称, 投档计划数, 最低位次, 志愿轮次
    """
    records = data.get("data", [])
    headers = ["院校代码", "院校名称", "专业代码", "专业名称", "投档计划数", "最低位次", "志愿轮次"]

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)

    return len(records)


def _write_score_rank_csv(path: Path, data: dict[str, Any]) -> int:
    """一分一段表：每行一个分数段。

    列：分数, 合计本次, 合计累计, 物理本次, 物理累计,
        历史本次, 历史累计, 化学本次, 化学累计, 生物本次, 生物累计,
        政治本次, 政治累计, 地理本次, 地理累计
    """
    records = data.get("data", [])

    headers = [
        "分数",
        "合计本次", "合计累计",
        "物理本次", "物理累计",
        "历史本次", "历史累计",
        "化学本次", "化学累计",
        "生物本次", "生物累计",
        "政治本次", "政治累计",
        "地理本次", "地理累计",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow({
                "分数":     rec.get("score_range", ""),
                "合计本次": rec.get("total", {}).get("current", ""),
                "合计累计": rec.get("total", {}).get("cumulative", ""),
                "物理本次": rec.get("physics", {}).get("current", ""),
                "物理累计": rec.get("physics", {}).get("cumulative", ""),
                "历史本次": rec.get("history", {}).get("current", ""),
                "历史累计": rec.get("history", {}).get("cumulative", ""),
                "化学本次": rec.get("chemistry", {}).get("current", ""),
                "化学累计": rec.get("chemistry", {}).get("cumulative", ""),
                "生物本次": rec.get("biology", {}).get("current", ""),
                "生物累计": rec.get("biology", {}).get("cumulative", ""),
                "政治本次": rec.get("politics", {}).get("current", ""),
                "政治累计": rec.get("politics", {}).get("cumulative", ""),
                "地理本次": rec.get("geography", {}).get("current", ""),
                "地理累计": rec.get("geography", {}).get("cumulative", ""),
            })

    return len(records)
