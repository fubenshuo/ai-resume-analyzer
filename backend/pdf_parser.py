"""
PDF 简历解析模块

使用 PyMuPDF (fitz) 作为主解析器，对中文 PDF 兼容性更好。
pdfplumber 作为备选方案。
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger("resume-api")


class PDFParseError(Exception):
    """PDF 解析异常"""
    pass


def parse_pdf(file_bytes: bytes, filename: str = "resume.pdf") -> str:
    """
    解析 PDF 文件，返回提取的纯文本。

    优先使用 PyMuPDF（中文兼容性好），失败时回退到 pdfplumber。

    Args:
        file_bytes: PDF 文件二进制内容
        filename: 原始文件名（用于日志）

    Returns:
        提取的全部文本（按页拼接）

    Raises:
        PDFParseError: 所有解析器均失败或内容为空
    """
    # ── 方式一：PyMuPDF（主解析器）──
    try:
        import fitz  # PyMuPDF
        text = _parse_with_fitz(file_bytes)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PyMuPDF 解析异常，尝试 pdfplumber 备选: {e}")

    # ── 方式二：pdfplumber（备选）──
    try:
        import pdfplumber
        text = _parse_with_pdfplumber(file_bytes)
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception:
        pass

    raise PDFParseError(
        "PDF 解析后文本为空。可能为扫描件/图片型简历，建议使用 OCR 预处理。"
    )


def _parse_with_fitz(file_bytes: bytes) -> str:
    """使用 PyMuPDF 提取文本。"""
    import fitz

    text_parts: list[str] = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = doc.page_count

    if total_pages == 0:
        doc.close()
        raise PDFParseError("PDF 文件不包含任何页面")

    try:
        for i in range(total_pages):
            page = doc[i]
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                cleaned = _clean_page_text(page_text)
                text_parts.append(cleaned)
            else:
                # 尝试 text blocks 模式
                blocks = page.get_text("blocks")
                block_texts = []
                # b[4] 是 block 的文本内容
                for b in blocks:
                    if len(b) > 4 and isinstance(b[4], str) and b[4].strip():
                        block_texts.append(b[4].strip())
                if block_texts:
                    text_parts.append("\n".join(block_texts))
                else:
                    text_parts.append(f"[第{i+1}页无可提取文本]")
    finally:
        doc.close()

    return _join_pages(text_parts)


def _parse_with_pdfplumber(file_bytes: bytes) -> str:
    """使用 pdfplumber 提取文本（备选）。"""
    import pdfplumber

    text_parts: list[str] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(_clean_page_text(page_text))
            else:
                text_parts.append(f"[第{i}页无可提取文本]")

    return _join_pages(text_parts)


def _clean_page_text(text: str) -> str:
    """清洗单页文本：合并断行、去除多余空白。"""
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
    return "\n".join(cleaned)


def _join_pages(text_parts: list[str]) -> str:
    """拼接多页文本。"""
    if not text_parts:
        return ""
    if len(text_parts) == 1:
        return text_parts[0]
    pages = [f"\n--- 第 {i} 页 ---\n{part}" for i, part in enumerate(text_parts, start=1)]
    return "\n".join(pages)
