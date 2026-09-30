"""T6.4 回归测试：简历 Word 导出（决策 D12）。

覆盖：
1. 小节提取（只取「优化后的简历」，不把「不足 / 改进建议」塞进 Word）；
2. 生成的 `.docx` 能**被重新打开**且正文与源文本一致；
3. 导出接口落成资源，下载走 `GET /resources/{id}/content` 能拿到真实 Word 字节；
4. 越权 / 空内容 / 不存在的消息分别返回 404 与 409。
"""

import io
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from httpx import AsyncClient

from api_helpers import create_session, stub_chat_model

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import Resource
from app.services.resume_export_service import (
    build_resume_docx,
    extract_resume_section,
)

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

RESUME_REPLY = """## 简历诊断
整体匹配度中等，量化不足。

## 亮点
- **订单系统**接口日均 300 万请求

## 不足
1. 项目成果没有量化

## 改进建议
- 把「接口变快了」改成具体数字

## 优化后的简历
# 张伟
Python 后端开发工程师

## 技能
- Python / FastAPI / MySQL
- **Redis** 缓存设计

## 工作经历
某电商公司 · 后端开发（2021.07-2025.06）
- 负责订单系统接口开发，日均请求 300 万

## 下一步
可以进入模拟面试。
"""


def _read_resource(resource_id: int) -> Resource | None:
    db = SessionLocal()
    try:
        return db.query(Resource).filter(Resource.id == resource_id).first()
    finally:
        db.close()


async def _send_resume_message(
    async_client: AsyncClient, headers: dict[str, str], session_id: int
) -> int:
    """发一条简历优化消息，返回入口消息 ID。"""
    sent = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=1",
        json={"request_text": "帮我优化简历", "select_model": 3},
        headers=headers,
    )
    assert sent.status_code == 200, sent.text
    events = [
        json.loads(line[len("data:") :].strip())
        for line in sent.text.splitlines()
        if line.startswith("data:")
    ]
    return int(next(e for e in events if e["type"] == "start")["message_id"])


def test_extract_resume_section_stops_at_next_heading() -> None:
    """只截取「优化后的简历」这一节，遇到下一个二级标题就停。"""
    section = extract_resume_section(RESUME_REPLY)
    assert "# 张伟" in section
    assert "Redis" in section
    # 前后小节都不能混进来
    assert "量化不足" not in section
    assert "模拟面试" not in section


def test_extract_resume_section_falls_back_to_whole_text() -> None:
    """模型没按小节输出时退回全文，而不是产出空文档。"""
    assert extract_resume_section("张伟\nPython 后端\n") == "张伟\nPython 后端"


def test_build_resume_docx_is_openable_and_matches_content() -> None:
    """生成的 docx 是合法 OOXML，能被重新打开，正文与源文本一致。"""
    data = build_resume_docx("优化后的简历", "# 张伟\n\n## 技能\n- Python / FastAPI\n")

    # 1) 结构上是合法 docx（zip + 必备部件）
    with ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names

    # 2) 能被 python-docx 重新打开，且内容对得上
    document = Document(io.BytesIO(data))
    texts = [paragraph.text for paragraph in document.paragraphs]
    joined = "\n".join(texts)
    assert "优化后的简历" in joined
    assert "张伟" in joined
    assert "Python / FastAPI" in joined
    # 加粗标记不能以原文形式残留
    assert "**" not in joined
    # 列表项走了 List Bullet 样式
    assert any(p.style.name == "List Bullet" for p in document.paragraphs)


@pytest.mark.anyio
async def test_export_endpoint_returns_downloadable_docx(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """导出接口：落资源 → 用返回的 download_path 能取到真实 Word 字节。"""
    headers = await register_and_login("resumeexp")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content=RESUME_REPLY)

    try:
        message_id = await _send_resume_message(async_client, headers, session_id)

        exported = await async_client.post(
            "/resumes/export", json={"message_id": message_id}, headers=headers
        )
        assert exported.status_code == 200, exported.text
        body = exported.json()
        assert body["resource_id"] > 0
        assert body["file_name"].endswith(".docx")
        assert body["download_path"] == f"/resources/{body['resource_id']}/content"

        # 资源记录确实落库了
        resource = _read_resource(body["resource_id"])
        assert resource is not None
        assert resource.storage_path.startswith("minio://")
        assert resource.expire_time is not None  # 会被过期清理一并回收

        # 下载路径能拿到真实 Word 字节
        downloaded = await async_client.get(body["download_path"], headers=headers)
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content[:2] == b"PK"  # docx 是 zip 容器
        document = Document(io.BytesIO(downloaded.content))
        joined = "\n".join(p.text for p in document.paragraphs)
        assert "张伟" in joined
        # 「不足」那一节不该被导出
        assert "项目成果没有量化" not in joined
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_export_rejects_other_users_message(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的消息一律 404；这条消息没有可导出的内容时 409。"""
    owner_headers = await register_and_login("resumeexpowner")
    intruder_headers = await register_and_login("resumeexpintruder")
    session_id = await create_session(async_client, owner_headers, session_model=1)
    stub_chat_model(monkeypatch, content=RESUME_REPLY)

    try:
        message_id = await _send_resume_message(async_client, owner_headers, session_id)

        forbidden = await async_client.post(
            "/resumes/export", json={"message_id": message_id}, headers=intruder_headers
        )
        assert forbidden.status_code == 404

        missing = await async_client.post(
            "/resumes/export", json={"message_id": 99999999}, headers=owner_headers
        )
        assert missing.status_code == 404
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=owner_headers
        )


@pytest.mark.anyio
async def test_export_empty_message_returns_409(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """助手消息正文为空时返回 409，而不是生成一个空 Word。"""
    headers = await register_and_login("resumeexpempty")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content="")

    try:
        message_id = await _send_resume_message(async_client, headers, session_id)

        exported = await async_client.post(
            "/resumes/export", json={"message_id": message_id}, headers=headers
        )
        assert exported.status_code == 409
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)
