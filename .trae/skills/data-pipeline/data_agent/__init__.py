"""数据准备: 用户上传文件 → constraint-filter 可消费的 JSON。

对外暴露三个函数：
  detect(file_path)           → {"file_type": ..., "data_type": ..., "confidence": ...}
  extract(file_path)          → 原始提取结果 dict
  normalize(raw, data_type)   → 归一化后的 dict（符合 admission plan schema）
  validate(normalized)        → ValidationReport
  store(normalized, target_dir) → 写入文件并返回目标路径
"""
from .pipeline import detect, extract, normalize, validate, store

__all__ = ["detect", "extract", "normalize", "validate", "store"]
