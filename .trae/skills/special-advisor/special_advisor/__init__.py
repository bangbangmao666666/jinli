"""special-advisor: 特殊适配与终审模块 — 特殊适配（最终审核与特殊群体适配）。

对外仅暴露 `run(input_data, *, data_dir=None)` 一个入口。
"""
from .pipeline import run
from .exceptions import SpecialAdvisorError

__all__ = ["run", "SpecialAdvisorError"]
