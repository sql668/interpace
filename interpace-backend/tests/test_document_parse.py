"""T3.2 回归测试：文档解析与扫描件识别。

纯函数测试，不依赖数据库。测试用的 PDF 现场生成：
- 文字版：直接 `insert_text`；
- 扫描件：先把文字页渲染成位图，再把位图插进一张新 PDF——这样文件里
  **有图片对象、没有文字层**，正好对应扫描件的特征。
"""

import sys
from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from httpx import AsyncClient

from document_fixtures import make_docx, make_scanned_pdf, make_text_pdf

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.document_parse_service import DocumentParseService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def test_parse_plain_text_and_markdown() -> None:
    """纯文本与 Markdown 直接读取。"""
    text_result = DocumentParseService.parse("你好，世界".encode(), "note.txt")
    assert text_result.ok
    assert text_result.text == "你好，世界"
    assert not text_result.suspected_scanned

    md_result = DocumentParseService.parse(b"# Title\nbody", "note.md")
    assert md_result.ok
    assert "Title" in md_result.text


def test_parse_docx_includes_table_content() -> None:
    """Word 文档要连表格一起取，否则简历里的经历会整段丢失。"""
    result = DocumentParseService.parse(make_docx(), "resume.docx")
    assert result.ok
    assert "张三" in result.text
    assert "FastAPI、MySQL" in result.text


def test_parse_text_pdf() -> None:
    """有文字层的 PDF 正常解析，不应被误判为扫描件。"""
    result = DocumentParseService.parse(
        make_text_pdf("Python backend engineer with FastAPI experience"), "resume.pdf"
    )
    assert result.ok
    assert "FastAPI" in result.text
    assert not result.suspected_scanned


def test_short_text_pdf_is_not_treated_as_scan() -> None:
    """文字少但页面里没有图片——那是短文档，不是扫描件。"""
    result = DocumentParseService.parse(make_text_pdf("hi"), "short.pdf")
    assert result.ok
    assert not result.suspected_scanned


def test_scanned_pdf_is_detected() -> None:
    """有图片、没文字层 → 判定为疑似扫描件，并给出明确说明。"""
    result = DocumentParseService.parse(
        make_scanned_pdf("SCANNED RESUME CONTENT"), "scan.pdf"
    )
    assert not result.ok
    assert result.suspected_scanned
    assert "图片识别" in result.message


def test_render_pdf_pages_returns_png() -> None:
    """扫描件可以被渲染成 PNG，交给多模态模型（T3.6 用）。"""
    pages = DocumentParseService.render_pdf_pages(make_scanned_pdf("PAGE ONE"))
    assert len(pages) == 1
    assert pages[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pdf_pages_respects_max_pages() -> None:
    """页数上限要生效——图片 token 很贵。"""
    document = pymupdf.open()
    for _ in range(3):
        document.new_page().insert_text((72, 120), "PAGE", fontsize=14)
    data = document.tobytes()
    document.close()

    assert len(DocumentParseService.render_pdf_pages(data, max_pages=2)) == 2
    assert len(DocumentParseService.render_pdf_pages(data, max_pages=10)) == 3


def test_unsupported_suffix_reports_clearly() -> None:
    """不支持的类型要说明白，而不是静默返回空。"""
    result = DocumentParseService.parse(b"whatever", "sheet.xlsx")
    assert not result.ok
    assert not result.suspected_scanned
    assert "暂不支持" in result.message
    assert not DocumentParseService.is_supported_document("sheet.xlsx")
    assert DocumentParseService.is_supported_document("resume.pdf")


@pytest.mark.anyio
async def test_upload_document_returns_parse_info(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """T3.2 集成：上传时响应里就带解析结果，用户不用等发消息才知道读没读到。"""
    headers = await register_and_login("doc")

    docx_response = await async_client.post(
        "/upload/file",
        files={
            "file": (
                "resume.docx",
                BytesIO(make_docx()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert docx_response.status_code == 201
    docx_parse = docx_response.json()["parse"]
    assert docx_parse["ok"] is True
    assert docx_parse["char_count"] > 0
    assert docx_parse["suspected_scanned"] is False

    scan_response = await async_client.post(
        "/upload/file",
        files={
            "file": (
                "scan.pdf",
                BytesIO(make_scanned_pdf("SCANNED RESUME")),
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert scan_response.status_code == 201
    scan_parse = scan_response.json()["parse"]
    assert scan_parse["ok"] is False
    assert scan_parse["suspected_scanned"] is True
    assert "图片识别" in scan_parse["message"]

    # 图片不是文档，不带解析结果
    image_response = await async_client.post(
        "/upload/file",
        files={"file": ("avatar.png", BytesIO(b"fake-png-bytes"), "image/png")},
        headers=headers,
    )
    assert image_response.status_code == 201
    assert image_response.json()["parse"] is None
