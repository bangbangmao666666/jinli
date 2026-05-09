"""数据加载层。

加载特殊适配规则库和数据文件。规则库缺失时按 PRD 要求软降级并标注警告。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import DataParseFailedError, DataSourceUnavailableError

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_json(path: Path, *, kind: str, soft_fail: bool = False) -> Optional[Dict[str, Any]]:
    if not path.exists():
        if soft_fail:
            return None
        raise DataSourceUnavailableError(
            f"无法找到{kind}数据文件：{path.name}",
            user_action="请确认数据文件存在；如缺失，请联系维护者补充。",
            detail={"missing_path": str(path), "kind": kind},
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        if soft_fail:
            return None
        raise DataParseFailedError(
            f"{kind}数据文件解析失败：{exc.msg}",
            user_action="请联系维护者修复该数据文件。",
            detail={"path": str(path), "line": exc.lineno, "col": exc.colno},
        ) from exc


def load_female_risk_majors(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "female_risk_majors.json", kind="女生避坑规则", soft_fail=True)


def load_civil_service_major_catalog(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "civil_service_major_catalog.json", kind="公务员招录专业目录", soft_fail=True)


def load_selector_university_list(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "selector_university_list.json", kind="选调生资格院校名单", soft_fail=True)


def load_special_adjustment_rules(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "special_adjustment_rules.json", kind="特殊适配规则", soft_fail=True)


def load_hidden_threshold_rules(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "hidden_threshold_rules.json", kind="招生章程隐藏门槛", soft_fail=True)


def load_gender_employment_ratio(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "gender_employment_ratio.json", kind="专业就业性别比例", soft_fail=True)


def load_upgrade_to_bachelor_data(data_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data_dir = data_dir or DEFAULT_DATA_DIR
    return _read_json(data_dir / "upgrade_to_bachelor_data.json", kind="专升本录取数据", soft_fail=True)
