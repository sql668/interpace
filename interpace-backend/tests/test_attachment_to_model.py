"""T3.6 回归测试：附件内容真的进入模型调用。

只断言「解析成功」不够——重点是证明**模型收到了**这些内容：
- 文档附件 → 正文作为文本内容块；
- 图片附件 → image_url 多模态内容块（base64 data URL）；
- 扫描件 PDF → 渲染成图片后同样作为 image_url 内容块。

做法：用一个会记录「收到的消息」的假模型替换真模型，然后走真实 HTTP 接口发消息。
"""

import base64
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from api_helpers import create_session, stub_chat_model, upload_file
from document_fixtures import make_docx, make_scanned_pdf

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import ChatMessage

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _text_of(message: Any) -> str:
    """把人类消息里的文本内容块拼起来（内容可能是字符串，也可能是内容块数组）。"""
    content = message.content
    if isinstance(content, str):
        return content
    return "\n".join(block.get("text", "") for block in content if block.get("type") == "text")


@pytest.mark.anyio
async def test_image_attachment_becomes_multimodal_block(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """图片附件要以 data URL 形式进入模型调用。"""
    headers = await register_and_login("attimg")
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"fake-image-content"
    uploaded = await upload_file(
        async_client, headers, "shot.png", image_bytes, "image/png"
    )
    resource_id = uploaded["resource_id"]
    session_id = await create_session(async_client, headers)

    captured: list[list[Any]] = []
    stub_chat_model(monkeypatch, captured)

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={
                "request_text": "这张图里是什么？",
                "segments": [
                    {"type": "image", "name": "shot.png", "resource_id": resource_id}
                ],
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert captured, "模型似乎没有被调用"

        human_content = captured[-1][-1].content
        assert isinstance(human_content, list), "人类消息应该是多模态内容块数组"
        image_blocks = [b for b in human_content if b.get("type") == "image_url"]
        assert len(image_blocks) == 1
        expected_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
        assert image_blocks[0]["image_url"]["url"] == expected_url
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )


@pytest.mark.anyio
async def test_document_attachment_text_reaches_model(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Word 附件要解析成文本进入模型，并写进 file_extracted_text 留档。"""
    headers = await register_and_login("attdoc")
    uploaded = await upload_file(
        async_client,
        headers,
        "resume.docx",
        make_docx(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resource_id = uploaded["resource_id"]
    session_id = await create_session(async_client, headers)

    captured: list[list[Any]] = []
    stub_chat_model(monkeypatch, captured)

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={
                "request_text": "看看我的简历",
                "segments": [
                    {"type": "file", "name": "resume.docx", "resource_id": resource_id}
                ],
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert captured, "模型似乎没有被调用"

        # 简历正文（含表格内容）应出现在发给模型的文本里
        assert "FastAPI、MySQL" in _text_of(captured[-1][-1])

        # 同时留档到 chat_messages.file_extracted_text
        db = SessionLocal()
        try:
            row = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .first()
            )
            assert row is not None
            assert "FastAPI、MySQL" in (row.file_extracted_text or "")
        finally:
            db.close()
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )


@pytest.mark.anyio
async def test_scanned_pdf_becomes_images(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描件 PDF 要渲染成图片进入模型，而不是静默变成空文本。"""
    headers = await register_and_login("attscan")
    uploaded = await upload_file(
        async_client,
        headers,
        "scan.pdf",
        make_scanned_pdf("SCANNED RESUME"),
        "application/pdf",
    )
    resource_id = uploaded["resource_id"]
    session_id = await create_session(async_client, headers)

    captured: list[list[Any]] = []
    stub_chat_model(monkeypatch, captured)

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={
                "request_text": "看看我的简历",
                "segments": [
                    {"type": "file", "name": "scan.pdf", "resource_id": resource_id}
                ],
            },
            headers=headers,
        )
        assert response.status_code == 200
        assert captured, "模型似乎没有被调用"

        human_content = captured[-1][-1].content
        image_blocks = [b for b in human_content if b.get("type") == "image_url"]
        assert len(image_blocks) == 1, "扫描件应该渲染成 1 页图片"
        assert image_blocks[0]["image_url"]["url"].startswith("data:image/png;base64,")
        # 同时要告诉模型这是什么，否则它只会看到一张没有说明的图
        assert "扫描件" in _text_of(captured[-1][-1])
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )
