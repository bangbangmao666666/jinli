"""统一异常类型。

PRD 原则：任何异常必须通过统一错误结构暴露给调用方，禁止降级为 success。
因此所有分支都应该抛出 SpecialAdvisorError 的子类，由入口 pipeline.run 捕获并转
成结构化 error 响应。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class SpecialAdvisorError(Exception):
    """所有 special-advisor 抛出的异常的共同基类。

    子类通过 error_code 类属性声明错误码。构造时附带:
    - message: 给用户看的中文解释
    - user_action: 指引用户下一步做什么
    - detail: 结构化上下文，便于开发者排查
    """

    error_code: str = "RUNTIME_UNEXPECTED_EXCEPTION"
    error_category: str = "runtime"

    def __init__(
        self,
        message: str,
        *,
        user_action: str = "请将错误信息反馈给维护者。",
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.user_action = user_action
        self.detail: Dict[str, Any] = detail or {}

    def to_response(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.error_code,
            "error_category": self.error_category,
            "error_message": self.message,
            "error_detail": self.detail,
            "user_action_required": self.user_action,
            "partial_result": None,
        }


# ---- 输入类 ----
class InputUpstreamEmptyError(SpecialAdvisorError):
    error_code = "INPUT_UPSTREAM_EMPTY"
    error_category = "input"


class InputDraftIncompleteError(SpecialAdvisorError):
    error_code = "INPUT_DRAFT_INCOMPLETE"
    error_category = "input"


class InputMissingRequiredFieldError(SpecialAdvisorError):
    error_code = "INPUT_MISSING_REQUIRED_FIELD"
    error_category = "input"


# ---- 数据类 ----
class DataSourceUnavailableError(SpecialAdvisorError):
    error_code = "DATA_SOURCE_UNAVAILABLE"
    error_category = "data"


class DataParseFailedError(SpecialAdvisorError):
    error_code = "DATA_PARSE_FAILED"
    error_category = "data"
