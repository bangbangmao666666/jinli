"""错误码定义与错误响应构建。

错误分级：
  P0 - 立即停止，返回 error，不输出任何评估结果
  P1 - 单个专业评估异常，标记该专业为未评估，继续处理其余专业
  P2 - 警告，正常执行，记录在 warnings 中
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class EvaluatorError(Exception):
    """P0 级错误：立即停止整个评估流程。"""

    def __init__(
        self,
        code: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
        user_action: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}
        self.user_action = user_action or "请检查输入数据格式后重试。"

    def to_response(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.code,
            "error_category": _category(self.code),
            "error_message": self.message,
            "error_detail": self.detail,
            "user_action_required": self.user_action,
            "partial_result": None,
        }


# ---------- 输入类错误（INPUT_*） ----------

def input_upstream_format_error(detail: str) -> EvaluatorError:
    return EvaluatorError(
        code="INPUT_UPSTREAM_FORMAT_ERROR",
        message=f"硬约束过滤模块 输出格式不合规：{detail}",
        detail={"reason": detail},
        user_action="请确认 硬约束过滤模块（constraint-filter）已正常执行并输出合规的 JSON 格式。",
    )


def input_empty_pool() -> EvaluatorError:
    return EvaluatorError(
        code="INPUT_EMPTY_POOL",
        message="基本盘为空，无可评估专业。",
        detail={},
        user_action="请检查 硬约束过滤模块 的输出，eligible_pool 为空通常意味着没有专业通过硬约束过滤。"
        "可尝试放宽考生条件或联系 硬约束过滤模块 确认数据是否正常。",
    )


def input_invalid_score(field: str, value: Any) -> EvaluatorError:
    return EvaluatorError(
        code="INPUT_INVALID_SCORE",
        message=f"单科成绩字段 '{field}' 的值 {value!r} 不合法。",
        detail={"field": field, "value": value, "valid_range": "0~150 之间的整数"},
        user_action=f"请将 '{field}' 改为 0~150 之间的整数后重试。",
    )


def input_missing_field(field: str) -> EvaluatorError:
    return EvaluatorError(
        code="INPUT_MISSING_REQUIRED_FIELD",
        message=f"输入缺少必填字段：'{field}'。",
        detail={"missing_field": field},
        user_action=f"请补充字段 '{field}' 后重试。",
    )


def input_invalid_field(field: str, reason: str) -> EvaluatorError:
    return EvaluatorError(
        code="INPUT_INVALID_FIELD",
        message=f"输入字段 '{field}' 格式非法：{reason}。",
        detail={"field": field, "reason": reason},
        user_action=f"请检查字段 '{field}' 的格式后重试。",
    )


# ---------- 运行时类错误（RUNTIME_*） ----------

def runtime_output_schema_violation(field: str, reason: str) -> EvaluatorError:
    return EvaluatorError(
        code="RUNTIME_OUTPUT_SCHEMA_VIOLATION",
        message=f"评估输出不满足 schema 要求：字段 '{field}' {reason}。",
        detail={"field": field, "reason": reason},
        user_action="这通常是 skill 内部逻辑错误，请将完整错误信息反馈给维护者。",
    )


def runtime_unexpected(exc: Exception) -> Dict[str, Any]:
    """兜底：未预期异常，返回 error 响应 dict（不抛出）。"""
    import traceback

    return {
        "status": "error",
        "error_code": "RUNTIME_UNEXPECTED_EXCEPTION",
        "error_category": "runtime",
        "error_message": f"未预期异常：{exc}",
        "error_detail": {"traceback": traceback.format_exc()},
        "user_action_required": "请将完整错误信息反馈给维护者；此类错误通常意味着代码存在未覆盖的分支。",
        "partial_result": None,
    }


# ---------- 内部工具 ----------

def _category(code: str) -> str:
    if code.startswith("INPUT_"):
        return "input"
    if code.startswith("RUNTIME_"):
        return "runtime"
    return "unknown"
