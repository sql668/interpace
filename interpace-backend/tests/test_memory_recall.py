"""T9.15 回归测试：跨会话记忆检索接入对话链路。

三个重点：
1. **触发条件**：只有带回溯指代的提问才去检索，普通提问不查（省一次全文检索）；
2. **隔离**：检索结果必须全是当前用户的——这是三层记忆的硬要求；
3. **真的进了提示词**：检索到的历史要出现在模型收到的消息里，而不只是查出来丢掉。
"""

import sys
import time
import uuid
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.memory import (
    build_memory_context,
    should_recall,
)
from app.db.database import SessionLocal
from app.db.models import SearchDocument
from app.services.memory_search_service import (
    SOURCE_MESSAGE,
    SOURCE_NOTE,
    MemorySearchService,
)


def _seed(db, *, user_id: int, source_id: int, title: str, content: str) -> None:
    MemorySearchService.index_document(
        db,
        user_id=user_id,
        source_type=SOURCE_MESSAGE,
        source_id=source_id,
        title=title,
        content=content,
        commit=False,
    )
    db.commit()


def _make_users(count: int = 2) -> list[int]:
    """造 count 个真实用户（索引表对 users 有外键，不能随手编 ID）。"""
    from app.db.models import User

    db = SessionLocal()
    try:
        ids: list[int] = []
        for _ in range(count):
            user = User(
                username=f"recall_{uuid.uuid4().hex[:8]}",
                password="x" * 12,
                avatar=None,
                create_time=int(time.time()),
            )
            db.add(user)
            db.flush()
            ids.append(user.id)
        db.commit()
        return ids
    finally:
        db.close()


def _drop_users(user_ids: list[int]) -> None:
    """清理：先索引后用户（顺序错就撞外键）。"""
    from api_helpers import purge_user

    db = SessionLocal()
    try:
        for user_id in user_ids:
            db.query(SearchDocument).filter(SearchDocument.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()
    for user_id in user_ids:
        purge_user(user_id)


def test_should_recall_by_keywords() -> None:
    """回溯指代才触发检索；普通提问不触发。"""
    assert should_recall("上次那道 MySQL 索引的题我没答好，再讲讲")
    assert should_recall("我们之前聊过 GIL 吧")
    assert should_recall("回顾一下你说过的缓存三兄弟")
    assert not should_recall("讲讲 Python 的装饰器")
    assert not should_recall("")


def test_build_memory_context_is_scoped_to_user() -> None:
    """检索到的历史必须全是当前用户的，别人的内容一个字都不能进来。"""
    user_a, user_b = _make_users()
    db = SessionLocal()
    try:
        _seed(
            db,
            user_id=user_a,
            source_id=1,
            title="上次那道索引题",
            content="我上次问过 MySQL 索引失效，你说是函数包裹列导致的。",
        )
        _seed(
            db,
            user_id=user_b,
            source_id=2,
            title="别人的索引题",
            content="B 用户的私有内容：索引下推的条件必须写进我的回答里才算串扰。",
        )

        context = ""
        for _ in range(10):  # InnoDB 全文索引对新写入行有短暂可见性延迟
            context = build_memory_context(
                db, user_id=user_a, query="上次那道索引题讲的是什么"
            )
            if context:
                break
            time.sleep(0.05)
            db.expire_all()

        assert context, "检索不到自己的历史"
        assert "索引失效" in context
        assert "[历史对话]" in context
        # 关键断言：别人的内容一个字都没有
        assert "B 用户的私有内容" not in context
    finally:
        db.close()
        _drop_users([user_a, user_b])


def test_build_memory_context_returns_empty_without_hits() -> None:
    """搜不到就返回空串，调用方据此什么都不注入。"""
    db = SessionLocal()
    try:
        assert (
            build_memory_context(
                db, user_id=999, query="一个不存在的历史话题完全无关的关键词"
            )
            == ""
        )
    finally:
        db.close()


def test_build_memory_context_truncates_long_content() -> None:
    """注入提示词的历史要限长（接口返回全文，注入必须限长，否则提示词会被顶爆）。"""
    (user_a,) = _make_users(1)
    db = SessionLocal()
    try:
        long_text = "缓存击穿" + "补充说明" * 400
        _seed(
            db,
            user_id=user_a,
            source_id=11,
            title="很长的历史",
            content=long_text,
        )
        context = ""
        for _ in range(10):
            context = build_memory_context(db, user_id=user_a, query="缓存击穿")
            if context:
                break
            time.sleep(0.05)
            db.expire_all()
        assert context
        assert "已截断" in context
        assert len(context) < len(long_text)
    finally:
        db.close()
        _drop_users([user_a])


@pytest.mark.anyio
async def test_recalled_history_reaches_the_model(
    async_client, register_and_login, monkeypatch
) -> None:
    """检索到的历史要真的出现在模型收到的消息里，而不是查出来丢掉。"""
    from api_helpers import create_session, make_recording_model
    from app.agent import prompt_layer

    headers = await register_and_login("recall")
    session_id = await create_session(async_client, headers)

    db = SessionLocal()
    try:
        from app.db.models import User

        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        _seed(
            db,
            user_id=user.id,
            source_id=101,
            title="上次聊的缓存穿透",
            content="我上次问的是缓存穿透，你建议用布隆过滤器。",
        )
        user_id = user.id
    finally:
        db.close()

    captured: list[list] = []
    monkeypatch.setattr(
        prompt_layer, "get_chat_model", lambda provider="deepseek": make_recording_model(captured)
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        prompt_layer,
        "build_personalized_prompt",
        lambda **kwargs: "你是助手",
    )

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "上次聊的缓存穿透再讲一遍"},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        # 组装后的消息里应当带上检索到的历史
        flattened = str(captured)
        assert "缓存穿透" in flattened, "检索到的历史没有进到模型输入里"

        # 普通提问不该触发检索（不注入历史块）
        captured.clear()
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "讲讲 Python 装饰器"},
            headers=headers,
        )
        assert response.status_code == 200
        assert "检索到的该用户的历史记录" not in str(captured)
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)
        db = SessionLocal()
        try:
            db.query(SearchDocument).filter(SearchDocument.user_id == user_id).delete()
            db.commit()
        finally:
            db.close()
