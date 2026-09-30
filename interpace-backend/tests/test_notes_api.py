"""T2.3 回归测试：笔记 CRUD 接口与用户隔离。

覆盖每个路由的正常路径与错误路径：
- 正常路径：创建 → 列表 → 详情 → 更新 → 删除；
- 错误路径：未登录 401、参数校验 422、越权与他人笔记一律 404。

共享的 async_client / register_and_login 夹具见 tests/conftest.py。
"""

import base64
import json
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.db.database import SessionLocal
from app.db.models import ChatMessage, Session as SessionModel

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _current_user_id(headers: dict[str, str]) -> int:
    """从鉴权头里的 JWT 解出用户 ID（只解码不验签，测试够用）。"""
    token = headers["Authorization"].split(" ", 1)[1]
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    return int(json.loads(base64.urlsafe_b64decode(payload + padding))["sub"])


def _seed_chat_message(user_id: int, question: str, answer: str) -> int:
    """直接写库造一条对话消息，供「一键存入」用例使用，返回消息 ID。"""
    db = SessionLocal()
    try:
        now = int(time.time())
        conversation = SessionModel(
            user_id=user_id, session_model=1, title="t2_6_import", created_at=now
        )
        db.add(conversation)
        db.flush()
        message = ChatMessage(
            user_id=user_id,
            session_id=conversation.id,
            select_model=4,
            request_id=uuid4().hex,
            request_text=question,
            response_text=answer,
            request_segments=[],
            response_segments=[],
            status=0,
            interview_id=None,
            file_extracted_text="",
            created_at=now,
        )
        db.add(message)
        db.commit()
        return message.id
    finally:
        db.close()


def _cleanup_chat_message(message_id: int) -> None:
    """删掉造出来的消息与其会话，不给开发库留残留。"""
    db = SessionLocal()
    try:
        message = db.get(ChatMessage, message_id)
        if message is None:
            return
        session_id = message.session_id
        # 必须先删消息再删会话：chat_messages.session_id 上有外键，顺序反了会撞约束
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(SessionModel).filter(SessionModel.id == session_id).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_notes_crud_lifecycle(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """创建 → 列表 → 详情 → 更新 → 删除的完整链路。"""
    headers = await register_and_login("note")

    created = await async_client.post(
        "/notes",
        json={"title": "MySQL 笔记", "content": "<p>聚簇索引</p>"},
        headers=headers,
    )
    assert created.status_code == 201
    note = created.json()
    note_id = note["id"]
    assert note["title"] == "MySQL 笔记"
    assert note["source_type"] == 0
    assert note["content"] == "<p>聚簇索引</p>"

    listed = await async_client.get("/notes", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == note_id
    # 列表项不含正文，避免列表接口返回大字段
    assert "content" not in body["items"][0]

    detail = await async_client.get(f"/notes/{note_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["content"] == "<p>聚簇索引</p>"

    # 只传标题：正文应保持不变
    updated = await async_client.put(
        f"/notes/{note_id}", json={"title": "MySQL 索引笔记"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "MySQL 索引笔记"
    assert updated.json()["content"] == "<p>聚簇索引</p>"

    deleted = await async_client.delete(f"/notes/{note_id}", headers=headers)
    assert deleted.status_code == 204

    assert (await async_client.get(f"/notes/{note_id}", headers=headers)).status_code == 404


@pytest.mark.anyio
async def test_notes_are_isolated_between_users(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """别人的笔记在读/改/删上都应等价于「不存在」。"""
    owner = await register_and_login("owner")
    other = await register_and_login("other")

    created = await async_client.post(
        "/notes", json={"title": "私有笔记", "content": "<p>secret</p>"}, headers=owner
    )
    assert created.status_code == 201
    note_id = created.json()["id"]

    assert (await async_client.get(f"/notes/{note_id}", headers=other)).status_code == 404
    assert (
        await async_client.put(
            f"/notes/{note_id}", json={"title": "篡改"}, headers=other
        )
    ).status_code == 404
    assert (await async_client.delete(f"/notes/{note_id}", headers=other)).status_code == 404

    # 对方的列表里也不该出现
    assert (await async_client.get("/notes", headers=other)).json()["total"] == 0
    # 原主人一切正常
    assert (await async_client.get(f"/notes/{note_id}", headers=owner)).status_code == 200

    # 收尾：删掉这条，不给开发库留残留
    assert (await async_client.delete(f"/notes/{note_id}", headers=owner)).status_code == 204


@pytest.mark.anyio
async def test_notes_require_auth(async_client: AsyncClient) -> None:
    """未登录访问笔记接口一律 401。"""
    assert (await async_client.get("/notes")).status_code == 401
    assert (await async_client.post("/notes", json={"title": "x"})).status_code == 401


@pytest.mark.anyio
async def test_notes_validation_errors(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """参数校验失败返回 422。"""
    headers = await register_and_login("notev")

    # 标题不能为空
    empty_title = await async_client.post("/notes", json={"title": ""}, headers=headers)
    assert empty_title.status_code == 422
    # 分页参数越界
    bad_limit = await async_client.get("/notes", params={"limit": 0}, headers=headers)
    assert bad_limit.status_code == 422
    # note_id 必须大于 0
    bad_id = await async_client.get("/notes/0", headers=headers)
    assert bad_id.status_code == 422


@pytest.mark.anyio
async def test_import_note_from_message(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """一键存入：生成笔记并记录来源；重复调用幂等，且不覆盖用户改过的内容。"""
    headers = await register_and_login("import")
    user_id = _current_user_id(headers)
    message_id = _seed_chat_message(
        user_id,
        "什么是覆盖索引？",
        "## 一句话回答\n\n它是**索引与查询匹配**的一种状态。",
    )
    note_id: int | None = None
    try:
        first = await async_client.post(
            "/notes/import", json={"message_id": message_id}, headers=headers
        )
        assert first.status_code == 200
        body = first.json()
        assert body["created"] is True
        note = body["note"]
        note_id = note["id"]
        # 来源被记录下来，标题取自问题文本，正文含问与答
        assert note["source_type"] == 1
        assert note["source_message_id"] == message_id
        assert note["title"] == "什么是覆盖索引？"
        assert "什么是覆盖索引？" in note["content"]
        # Markdown 的标题与加粗被转成富文本，而不是原样留着 ## 和 **
        assert "<h2>一句话回答</h2>" in note["content"]
        assert "<strong>索引与查询匹配</strong>" in note["content"]
        assert "**" not in note["content"]

        # 用户改过内容后再点一次：返回同一条，且不覆盖编辑
        await async_client.put(
            f"/notes/{note_id}", json={"content": "<p>我自己改的</p>"}, headers=headers
        )
        second = await async_client.post(
            "/notes/import", json={"message_id": message_id}, headers=headers
        )
        assert second.status_code == 200
        assert second.json()["created"] is False
        assert second.json()["note"]["id"] == note_id
        detail = await async_client.get(f"/notes/{note_id}", headers=headers)
        assert detail.json()["content"] == "<p>我自己改的</p>"
    finally:
        if note_id is not None:
            await async_client.delete(f"/notes/{note_id}", headers=headers)
        _cleanup_chat_message(message_id)


@pytest.mark.anyio
async def test_import_note_rejects_foreign_or_missing_message(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """存入别人的消息或根本不存在的消息，一律 404。"""
    owner = await register_and_login("owner1")
    other = await register_and_login("other1")
    message_id = _seed_chat_message(_current_user_id(owner), "私密问题", "私密回答")
    try:
        foreign = await async_client.post(
            "/notes/import", json={"message_id": message_id}, headers=other
        )
        assert foreign.status_code == 404

        missing = await async_client.post(
            "/notes/import", json={"message_id": 999_999_999}, headers=other
        )
        assert missing.status_code == 404
    finally:
        _cleanup_chat_message(message_id)
