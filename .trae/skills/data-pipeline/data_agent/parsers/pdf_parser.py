"""PDF 解析器：用 pdfplumber 提取文字和表格。

设计原则：
- 只做提取，不做语义判断（那是 normalizer 的事）
- 提取失败直接报错，不跳过，不猜
- 每张表格保留原始行列结构，含 page 信息供追溯
- 如果文件是扫描件（无文字层），明确报 ParseError，引导用户换格式
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..errors import FileReadError, ParseError

# 判断是否为扫描件的启发式规则：
# 每页有表格但每格字符数都很少（< 2 字符），通常是扫描件 OCR 未识别
_SCAN_MIN_PAGE_RATIO = 0.8   # 超过 80% 的页面是空文字 → 可能是扫描件
_MIN_TEXT_LEN_PER_PAGE = 50  # 低于此字符数的页面算"空页"


def extract(file_path: str | Path) -> dict[str, Any]:
    """从 PDF 提取所有表格和文字，返回结构化原始数据。

    返回格式：
    {
        "file": "<path>",
        "total_pages": N,
        "is_likely_scanned": bool,
        "pages": [
            {
                "page": 1,
                "text_snippet": "<前200字>",
                "tables": [
                    {
                        "table_index": 0,
                        "rows": [["col1", "col2", ...], ...],
                        "row_count": N,
                        "col_count": N
                    }
                ]
            }
        ],
        "all_tables_flat": [  # 所有页面的表格拍平，方便 normalizer 遍历
            {
                "page": 1,
                "table_index": 0,
                "rows": [...]
            }
        ]
    }
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise FileReadError(
            "缺少依赖 pdfplumber，请先运行 pip install pdfplumber",
            detail={"hint": "cd 数据准备 && pip install -r requirements.txt"},
        ) from e

    path = Path(file_path)
    if not path.exists():
        raise FileReadError(
            f"文件不存在：{path}",
            detail={"path": str(path)},
        )
    if path.suffix.lower() != ".pdf":
        raise FileReadError(
            f"文件扩展名不是 .pdf：{path.name}",
            detail={"path": str(path)},
        )

    try:
        pdf = pdfplumber.open(str(path))
    except Exception as exc:
        raise FileReadError(
            f"无法打开 PDF 文件（可能已加密或损坏）：{exc}",
            detail={"path": str(path), "error": str(exc)},
        ) from exc

    pages_data = []
    all_tables_flat = []
    empty_page_count = 0

    with pdf:
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if len(text.strip()) < _MIN_TEXT_LEN_PER_PAGE:
                empty_page_count += 1

            tables_raw = page.extract_tables() or []
            tables = []
            for tidx, tbl in enumerate(tables_raw):
                # 过滤掉全空行
                cleaned_rows = [
                    [_clean_cell(c) for c in row]
                    for row in tbl
                    if any(c and str(c).strip() for c in row)
                ]
                if not cleaned_rows:
                    continue
                entry = {
                    "page": page_num,
                    "table_index": tidx,
                    "rows": cleaned_rows,
                    "row_count": len(cleaned_rows),
                    "col_count": max(len(r) for r in cleaned_rows) if cleaned_rows else 0,
                }
                tables.append(entry)
                all_tables_flat.append(entry)

            pages_data.append({
                "page": page_num,
                "text_snippet": text[:200].strip(),
                "tables": tables,
            })

    is_likely_scanned = (
        total_pages > 0 and (empty_page_count / total_pages) >= _SCAN_MIN_PAGE_RATIO
    )
    if is_likely_scanned:
        raise ParseError(
            f"此 PDF 可能是扫描件（{empty_page_count}/{total_pages} 页无可识别文字）。"
            "当前版本不支持 OCR，请向省考试院索取文字版 PDF 或 Excel 格式后重试。",
            detail={
                "total_pages": total_pages,
                "empty_pages": empty_page_count,
                "hint": "如确为扫描件，可尝试 Adobe Acrobat / 百度云 OCR 先转换后再上传",
            },
        )

    if not all_tables_flat:
        raise ParseError(
            f"此 PDF 未提取到任何表格（共 {total_pages} 页）。"
            "可能原因：①文件内容是纯文字说明而非表格；②表格是图片嵌入（扫描件）。",
            detail={
                "total_pages": total_pages,
                "text_preview": pages_data[0]["text_snippet"] if pages_data else "",
            },
        )

    return {
        "file": str(path),
        "total_pages": total_pages,
        "is_likely_scanned": False,
        "pages": pages_data,
        "all_tables_flat": all_tables_flat,
    }


def _clean_cell(value: Any) -> str | None:
    """把单元格值统一成字符串，去除多余空白，None 保持 None（表示空格/合并单元格）。"""
    if value is None:
        return None
    s = str(value).strip().replace("\n", " ").replace("\r", " ")
    # 多个空格合并为一个
    import re
    s = re.sub(r"\s+", " ", s)
    return s if s else None
