
"""统一异常类型。

PRD原则：任何异常必须通过统一错误结构暴露给调用方，禁止降级为success。
因此所有分支都应该抛出MatcherError的子类，由入口捕获并转化为结构化error响应。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class MatcherError(Exception):
    """所有school-matcher抛出的异常的共同基类。

    子类通过error_code类属性声明错误码。构造时附带：
    - message: 给用户看的中文解释
    - user_action: 指引用户下一步做什么（而不是只留技术术语）
    - detail: 结构化上下文，便于开发者排查
    """

    error_code: str = "RUNTIME_UNEXPECTED_EXCEPTION"
    error_category: str = "runtime"  # input | data | runtime | external

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


# ---------- 输入类错误 ----------
class InputUpstreamEmptyError(MatcherError):
    error_code = "INPUT_UPSTREAM_EMPTY"
    error_category = "input"


class InputMissingRequiredFieldError(MatcherError):
    error_code = "INPUT_MISSING_REQUIRED_FIELD"
    error_category = "input"


class InputInvalidFieldValueError(MatcherError):
    error_code = "INPUT_INVALID_FIELD_VALUE"
    error_category = "input"


# ---------- 数据类错误 ----------
class DataSourceUnavailableError(MatcherError):
    error_code = "DATA_SOURCE_UNAVAILABLE"
    error_category = "data"


class DataVersionMismatchError(MatcherError):
    error_code = "DATA_VERSION_MISMATCH"
    error_category = "data"


class DataParseFailedError(MatcherError):
    error_code = "DATA_PARSE_FAILED"
    error_category = "data"


# ---------- 运行时类错误 ----------
class RuntimeEvaluationError(MatcherError):
    error_code = "RUNTIME_EVALUATION_ERROR"
    error_category = "runtime"

