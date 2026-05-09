"""constraint-filter: 硬约束过滤模块 — 硬约束过滤。

对外仅暴露 `run(applicant, *, data_dir=None)` 一个入口。
"""
from .pipeline import run
from .errors import FilterError

__all__ = ["run", "FilterError"]
