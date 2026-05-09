"""数据准备 专用异常类。"""
from __future__ import annotations


class DataPipelineError(Exception):
    """基类。"""
    error_code: str = "PIPELINE_ERROR"

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict:
        return {
            "status": "error",
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


class UnsupportedFileTypeError(DataPipelineError):
    error_code = "UNSUPPORTED_FILE_TYPE"


class FileReadError(DataPipelineError):
    error_code = "FILE_READ_ERROR"


class ParseError(DataPipelineError):
    error_code = "PARSE_ERROR"


class NormalizationError(DataPipelineError):
    error_code = "NORMALIZATION_ERROR"


class StorageError(DataPipelineError):
    error_code = "STORAGE_ERROR"
