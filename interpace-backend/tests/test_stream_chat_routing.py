"""stream-chat 接口的回归测试。

验证三件事：
1. 不传 agent_name / scene 时，按 select_model 查模式注册表；
2. 显式传入时以传入值优先（保持向后兼容）；
3. chat_messages.select_model 按原样落库，供历史回显区分模式。
4. 通过会话消息接口读回时也带 select_model（前端靠它回显模式标签）。
5. （T3.1）请求体里的附件段原样落库，非法类型被挡在 422。

模型与提示词构建都被替换掉：测试不打真实模型，也不依赖 prompt_templates 有没有数据。
"""

import sys
import time
import uuid
from collections.abc import Awaitable, Callable, Generator
from pathlib import Path

import pytest

from api_helpers import purge_user
from httpx import AsyncClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import prompt_layer
from app.db.database import SessionLocal
from app.db.models import ChatMessage, Interview, Session as SessionModel, User
from app.services import stream_chat_service
from app.services.chat_service import ChatService
from app.services.stream_chat_service import StreamChatService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """测试用数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _seed_conversation(db: Session, now: int) -> tuple[User, SessionModel]:
    """建一个用户 + 一个面试会话并提交（stream_chat 内部会 commit，没法靠回滚清理）。"""
    user = User(
        username=f"t12_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=now,
    )
    db.add(user)
    db.flush()
    conversation = SessionModel(
        user_id=user.id, session_model=1, title="t1_2_routing", created_at=now
    )
    db.add(conversation)
    db.commit()
    return user, conversation


def _cleanup(db: Session, user_id: int, session_id: int) -> None:
    """删掉本用例产生的数据，不给开发库留残留。"""
    db.rollback()
    # 面试记录先删：interviews.message_id 指向 chat_messages，
    # 自 T7.4 起「模拟面试」模式会真的写这张表（生产侧 delete_session 也是这个顺序）。
    db.query(Interview).filter(Interview.session_id == session_id).delete()
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.query(SessionModel).filter(SessionModel.id == session_id).delete()
    db.commit()
    # 统一走共享清理：顺序与外键依赖一致（检索索引 / 记忆日志 / 记忆 / 画像 / 用户）
    purge_user(user_id)


async def _drain(response) -> None:
    """把 SSE 响应体读完，触发生成器执行。"""
    async for _part in response.body_iterator:
        pass


@pytest.mark.anyio
async def test_stream_chat_routes_by_select_model(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """select_model 决定 agent / scene；显式传入时以传入值优先。"""
    now = int(time.time())
    user, conversation = _seed_conversation(db_session, now)
    captured: list[tuple[str, str]] = []

    def record_prompt(db: Session, user_id: int, agent_name: str, scene: str) -> None:
        captured.append((agent_name, scene))
        return None

    monkeypatch.setattr(stream_chat_service, "build_personalized_prompt", record_prompt)
    # 每次调用都要新建假模型，否则迭代器被第一次调用耗尽。
    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content="好的")])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")

    try:
        # 不传 agent / scene：按注册表解析
        cases = [(0, ("general_assistant", "chat")), (1, ("difficulty_learner", "study"))]
        for select_model, expected in cases:
            response = StreamChatService.stream_chat(
                db=db_session,
                user_id=user.id,
                session_id=conversation.id,
                session_model=1,
                request_text=f"问题 {select_model}",
                select_model=select_model,
            )
            await _drain(response)
            assert captured[-1] == expected

        # 显式传入：以传入值优先，select_model 仍然照常落库
        response = StreamChatService.stream_chat(
            db=db_session,
            user_id=user.id,
            session_id=conversation.id,
            session_model=1,
            request_text="显式指定",
            select_model=1,
            agent_name="interview_host",
            scene="interview",
        )
        await _drain(response)
        assert captured[-1] == ("interview_host", "interview")

        # 落库检查：三条消息的 select_model 应分别是 0 / 1 / 1
        rows = (
            db_session.query(ChatMessage)
            .filter(ChatMessage.session_id == conversation.id)
            .order_by(ChatMessage.id)
            .all()
        )
        assert [row.select_model for row in rows] == [0, 1, 1]
        assert all(row.response_text == "好的" for row in rows)

        # 消息接口读回时也要带 select_model，否则前端刷新后看不到模式标签。
        items, _has_more = ChatService.get_session_messages(
            db=db_session,
            user_id=user.id,
            session_id=conversation.id,
            page=1,
            page_size=20,
            session_model=1,
        )
        assert [item.select_model for item in items] == [0, 1, 1]
    finally:
        _cleanup(db_session, user.id, conversation.id)


@pytest.mark.anyio
async def test_stream_chat_persists_request_segments(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T3.1：请求体的附件段要原样落库，并能通过消息接口读回；非法类型挡在 422。"""
    headers = await register_and_login("seg")
    created = await async_client.post(
        "/sessions", json={"title": "附件测试", "session_model": 0}, headers=headers
    )
    # 注意：POST /sessions 返回的是 200 而不是 201（既有行为，与 AGENTS 的
    # 「创建 201」约定不符，/notes 与 /users 都是 201，只有 sessions 是 200）。
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]

    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content="收到")])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        stream_chat_service, "build_personalized_prompt", lambda **kwargs: None
    )

    try:
        # 非法附件类型：在进入业务逻辑之前就被 Pydantic 挡掉
        invalid = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "看看这个", "segments": [{"type": "hack"}]},
            headers=headers,
        )
        assert invalid.status_code == 422

        segment = {
            "type": "file",
            "name": "简历.pdf",
            "url": "minio://ai-resources/user_1/files/abc.pdf",
            "resource_id": 123,
        }
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "看看这份简历", "segments": [segment]},
            headers=headers,
        )
        assert response.status_code == 200
        assert "data:" in response.text  # 确实吐了 SSE 帧

        messages = await async_client.get(
            f"/sessions/{session_id}/messages?session_model=0", headers=headers
        )
        assert messages.status_code == 200
        items = messages.json()["messages"]
        assert len(items) == 1
        assert items[0]["request_segments"] == [segment]
    finally:
        # 删除会话会级联清掉消息，不给开发库留残留
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)
