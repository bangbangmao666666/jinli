"""顶层 pipeline：串联 detect → extract → normalize → validate → store。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import DataPipelineError, UnsupportedFileTypeError
from .parsers import pdf_parser, excel_parser
from .normalizer import (
    normalize_admission_plan, normalize_historical_ranks,
    normalize_score_rank_table, normalize_admission_filing,
)
from .validator import validate as validate_plan
from .storage import store as store_plan


_SUPPORTED_EXTENSIONS = {
    ".pdf", ".xlsx", ".xlsm", ".xls", ".csv"
    # .docx 暂不支持招生计划格式（招生章程留后续版本）
}


def detect(file_path: str | Path) -> dict[str, Any]:
    """识别文件类型 + 猜测数据类型。"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in _SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"不支持的文件类型：{suffix}",
            detail={
                "file": str(path),
                "supported": sorted(_SUPPORTED_EXTENSIONS),
                "hint": "请提供 PDF 或 Excel 格式的文件",
            },
        )

    # 从文件名启发式猜数据类型
    name_lower = path.name.lower()
    data_type = "unknown"
    confidence = "low"

    if any(kw in name_lower for kw in ["招生计划", "zhaosjh", "plan", "厚本"]):
        data_type = "admission_plan"
        confidence = "high"
    elif any(kw in name_lower for kw in ["投档情况", "志愿投档"]):
        data_type = "admission_filing"
        confidence = "high"
    elif any(kw in name_lower for kw in ["分数线", "录取位次", "录取分数", "投档", "lishi", "历年"]):
        data_type = "historical_ranks"
        confidence = "medium"
    elif any(kw in name_lower for kw in ["一分一段", "成绩分布", "位次表"]):
        data_type = "score_rank_table"
        confidence = "medium"
    elif any(kw in name_lower for kw in ["招生章程", "章程"]):
        data_type = "enrollment_charter"
        confidence = "medium"
    else:
        data_type = "admission_plan"  # 默认猜招生计划，后续让用户确认
        confidence = "low"

    return {
        "file": str(path),
        "file_name": path.name,
        "file_type": suffix.lstrip("."),
        "data_type": data_type,
        "data_type_confidence": confidence,
        "message": _detect_message(data_type, confidence, path.name),
    }


def extract(file_path: str | Path) -> dict[str, Any]:
    """提取文件原始数据。"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return pdf_parser.extract(file_path)
    if suffix in (".xlsx", ".xlsm", ".xltx", ".xls", ".csv"):
        return excel_parser.extract(file_path)
    raise UnsupportedFileTypeError(
        f"extract 不支持 {suffix}",
        detail={"supported": [".pdf", ".xlsx", ".xls", ".csv"]},
    )


def normalize(
    raw: dict[str, Any],
    data_type: str = "admission_plan",
    user_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """归一化 raw 到目标 schema。

    data_type 取值：
      - admission_plan      招生计划（院校→专业组→专业树）
      - historical_ranks    历年录取位次/分数线（扁平列表）
      - score_rank_table    一分一段表（分数→位次映射）
    """
    if data_type == "admission_plan":
        return normalize_admission_plan(raw, user_hint=user_hint)
    if data_type == "historical_ranks":
        return normalize_historical_ranks(raw, user_hint=user_hint)
    if data_type == "score_rank_table":
        return normalize_score_rank_table(raw, user_hint=user_hint)
    if data_type == "admission_filing":
        return normalize_admission_filing(raw, user_hint=user_hint)
    raise UnsupportedFileTypeError(
        f"不支持的 data_type='{data_type}'",
        detail={"supported": ["admission_plan", "historical_ranks", "score_rank_table", "admission_filing"]},
    )


def validate(normalized: dict[str, Any]) -> dict[str, Any]:
    return validate_plan(normalized)


def store(
    normalized: dict[str, Any],
    *,
    target_dir: Path | str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    return store_plan(normalized, target_dir=target_dir, overwrite=overwrite)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def run_full_pipeline(
    file_path: str | Path,
    *,
    user_hint: dict[str, Any] | None = None,
    target_dir: Path | str | None = None,
    overwrite: bool = False,
    save_intermediate: Path | str | None = None,
) -> dict[str, Any]:
    """一次性跑完 detect→extract→normalize→validate，等待确认后 store。

    返回 {
        "detect": ...,
        "validation_report": ...,
        "normalized": ...,      # 供用户确认的归一化结果
        "ready_to_store": bool  # 是否可以入库
    }
    注意：store 步骤不在这里执行，需要用户确认后手动调用 store()。
    """
    try:
        det = detect(file_path)
        raw = extract(file_path)
        data_type = det.get("data_type", "admission_plan")
        normalized = normalize(raw, data_type=data_type, user_hint=user_hint)
        report = validate(normalized)

        actual_path: Path | None = None
        if save_intermediate and normalized:
            p = Path(save_intermediate).with_suffix(".jsonl")  # 统一存 .jsonl
            p.parent.mkdir(parents=True, exist_ok=True)
            _write_jsonl_intermediate(p, normalized)
            actual_path = p

        return {
            "detect": det,
            "validation_report": report,
            "normalized": normalized,
            "ready_to_store": report["passed"],
            "saved_path": str(actual_path) if actual_path else None,
        }
    except DataPipelineError as exc:
        return {"status": "error", **exc.to_dict()}


def _write_jsonl_intermediate(path: Path, data: dict[str, Any]) -> None:
    """将归一化结果写为 JSONL 中间文件：第一行 __meta__，后续每行一条记录。"""
    records = data.get("data") or data.get("schools", [])
    meta = {k: v for k, v in data.items() if k not in ("data", "schools", "_meta")}
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"__meta__": True, **meta}, ensure_ascii=False) + "\n")
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _detect_message(data_type: str, confidence: str, filename: str) -> str:
    type_labels = {
        "admission_plan": "招生计划（大厚本）",
        "historical_ranks": "历史录取位次/分数线",
        "score_rank_table": "一分一段表",
        "enrollment_charter": "招生章程",
        "unknown": "未知类型",
    }
    label = type_labels.get(data_type, data_type)
    conf_label = {"high": "较确定", "medium": "猜测", "low": "不确定"}.get(confidence, "")
    return f"识别为【{label}】（{conf_label}）。如果识别有误，请告诉我实际是什么类型。"
