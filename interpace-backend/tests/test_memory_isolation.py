"""T9.17：记忆隔离与清理的系统性验证。

三层记忆共用的硬要求，这里集中验一遍（前面的用例是零散覆盖的）：

1. **跨用户 ID 查询**：拿别人的条目 ID 去操作，一律 404（不区分「不存在」与「不是你的」）；
2. **检索不跨用户**：搜索、注入、画像都不返回别人的内容；
3. **级联清理**：删会话清掉该会话的摘要与检索索引；删用户清掉全部记忆数据。

隔离是长期记忆的地基：一旦串了，用户会看到别人的信息，属于最严重的一类缺陷。
所以这一组用例刻意写得直白，宁可重复一点也要把边界钉住。
"""

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_helpers import create_session, purge_user
from app.db.database import SessionLocal
from app.db.models import (
    SearchDocument,
    SessionSummary,
    User,
    UserMemory,
)
from app.services.user_memory_service import (
    CATEGORY_SKILL,
    SOURCE_SELF_REPORT,
    MemoryEntry,
    UserMemoryService,
)

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _latest_user_id() -> int:
    """取最近注册的用户 ID（register_and_login 不返回 ID，用这个代替）。"""
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        return user.id
    finally:
        db.close()


def _seed_memory(user_id: int, name: str) -> int:
    db = SessionLocal()
    try:
        UserMemoryService.ingest(
            db,
            user_id=user_id,
            entries=[MemoryEntry(category=CATEGORY_SKILL, name=name, mastery=70)],
            source=SOURCE_SELF_REPORT,
            commit=True,
        )
        row = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.name == name)
            .first()
        )
        assert row is not None
        return row.id
    finally:
        db.close()


# ---------------- 1. 跨用户 ID 查询 ---------------- 


@pytest.mark.anyio
async def test_cross_user_memory_id_is_rejected_everywhere(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """拿别人的记忆条目 ID 去读/改/删/批准/拒绝，全部 404。

    这是本任务点名要求的那类用例：**故意构造跨用户 ID 查询**。
    """
    await register_and_login("iso_owner")
    owner_id = _latest_user_id()
    intruder_headers = await register_and_login("iso_intruder")

    memory_id = _seed_memory(owner_id, "B 用户的私有技能")

    # 改
    patched = await async_client.put(
        f"/profile/memories/{memory_id}", json={"mastery": 10}, headers=intruder_headers
    )
    assert patched.status_code == 404
    # 删
    removed = await async_client.delete(
        f"/profile/memories/{memory_id}", headers=intruder_headers
    )
    assert removed.status_code == 404
    # 批准 / 拒绝
    approved = await async_client.post(
        f"/profile/memories/{memory_id}/approve", headers=intruder_headers
    )
    assert approved.status_code == 404
    rejected = await async_client.post(
        f"/profile/memories/{memory_id}/reject", headers=intruder_headers
    )
    assert rejected.status_code == 404

    # 侵入者自己的列表里看不到别人的条目
    listed = await async_client.get("/profile/memories", headers=intruder_headers)
    assert all(
        item["name"] != "B 用户的私有技能" for item in listed.json()
    ), "别人的记忆出现在了自己的列表里"


# ---------------- 2. 检索与画像不跨用户 ---------------- 


@pytest.mark.anyio
async def test_search_and_profile_are_isolated(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """A 的检索与画像里不能出现 B 的任何内容。"""
    owner_headers = await register_and_login("iso_search_owner")
    intruder_headers = await register_and_login("iso_search_intruder")

    created = await async_client.post(
        "/notes",
        json={"title": "私有笔记：紫罗兰协议", "content": "紫罗兰协议的细节只属于我。"},
        headers=owner_headers,
    )
    assert created.status_code == 201

    # 检索：换个用户搜同样的词，一条都不该有
    intruder_search = await async_client.get(
        "/search", params={"q": "紫罗兰"}, headers=intruder_headers
    )
    assert intruder_search.json()["total"] == 0

    # 画像：侵入者的技能列表是空的（没被别人的数据污染）
    profile = await async_client.get("/profile", headers=intruder_headers)
    assert profile.json()["target_skills"] == []
    assert profile.json()["weak_topics"] == []


# ---------------- 3. 级联清理 ---------------- 


@pytest.mark.anyio
async def test_delete_session_clears_summary_and_index(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """删会话要连带清掉该会话的检索索引与上下文摘要。

    两者都对 `sessions` 有外键 / 软引用：不清理不仅会留下「删掉的对话还能搜到」的脏数据，
    外键还会直接把删除请求挡下来（这个坑实现时真踩到了）。
    """
    headers = await register_and_login("iso_session")
    session_id = await create_session(async_client, headers)

    # 直接造数据：一条消息（会建索引）+ 一份摘要
    db = SessionLocal()
    try:
        from app.services.memory_search_service import (
            SOURCE_MESSAGE,
            MemorySearchService,
        )

        user_id = _latest_user_id()
        MemorySearchService.index_document(
            db,
            user_id=user_id,
            source_type=SOURCE_MESSAGE,
            source_id=999_001,
            session_id=session_id,
            title="会话内的消息",
            content="这条消息属于这个会话。",
            commit=True,
        )
        db.add(
            SessionSummary(
                user_id=user_id,
                session_id=session_id,
                summary="摘要",
                covered_message_id=1,
                covered_count=10,
            )
        )
        db.commit()
    finally:
        db.close()

    removed = await async_client.delete(
        f"/sessions/{session_id}?session_model=0", headers=headers
    )
    assert removed.status_code == 200, removed.text

    db = SessionLocal()
    try:
        assert (
            db.query(SearchDocument)
            .filter(SearchDocument.session_id == session_id)
            .count()
            == 0
        ), "删会话后还能搜到该会话的内容"
        assert (
            db.query(SessionSummary)
            .filter(SessionSummary.session_id == session_id)
            .count()
            == 0
        )
    finally:
        db.close()


def test_delete_user_clears_all_memory_tables() -> None:
    """删用户要清掉记忆相关的每一张表（泛化断言，加了新表也会被这条抓到）。"""
    from api_helpers import purge_user as _purge  # 与生产 delete_user 顺序一致的清理
    from app.db.base import Base
    from app.services.user_service import UserService

    db = SessionLocal()
    user = User(
        username="iso_del",
        password="x" * 12,
        avatar=None,
        create_time=1_700_000_000,
    )
    db.add(user)
    db.flush()
    user_id = user.id
    db.add(
        SearchDocument(
            user_id=user_id,
            source_type=0,
            source_id=1,
            title="t",
            content="c",
        )
    )
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        UserService.delete_user(db, user_id)
        leftover: list[str] = []
        for table in Base.metadata.sorted_tables:
            if "user_id" not in table.columns:
                continue
            if db.execute(table.select().where(table.c.user_id == user_id)).first():
                leftover.append(table.name)
        assert not leftover, f"删除用户后这些表还有残留: {leftover}"
    finally:
        db.rollback()
        db.close()
        _purge(user_id)
