"""T1.8 回归测试：手动停止流式回答。

验证五件事：
1. 登记停止后生成器提前跳出，不再产出后续 delta；
2. 已生成的部分内容被保留，消息状态置为 2（用户主动停止）；
3. done 事件带 stopped=true；
4. 重复停止是幂等的——不报错，且第二次反馈 first_request=false；
5. 停止不属于当前用户 / 当前会话的消息时抛 404。
"""

import json
import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

from api_helpers import purge_user
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import prompt_layer
from app.core.exceptions import AppException
from app.db.database import SessionLocal
from app.db.models import ChatMessage, Session as SessionModel, User
from app.services import stream_chat_service
from app.services.stream_chat_service import MESSAGE_STATUS_STOPPED, StreamChatService

# 假模型会按空格切成多块，保证「读到第一块之后再停止」是可复现的。
FULL_ANSWER = "一 二 三 四 五 六 七 八 九 十"


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
        username=f"t18_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=now,
    )
    db.add(user)
    db.flush()
    conversation = SessionModel(
        user_id=user.id, session_model=1, title="t1_8_stop", created_at=now
    )
    db.add(conversation)
    db.commit()
    return user, conversation


def _cleanup(db: Session, user_id: int, session_id: int) -> None:
    """删掉本用例产生的数据，不给开发库留残留。"""
    db.rollback()
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.query(SessionModel).filter(SessionModel.id == session_id).delete()
    db.commit()
    # 统一走共享清理：顺序与外键依赖一致（检索索引 / 记忆日志 / 记忆 / 画像 / 用户）
    purge_user(user_id)


def _parse_frame(raw: str) -> dict | None:
    """从一帧 SSE 文本里解析出事件 payload。"""
    for line in raw.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return None


def _stub_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """替换掉真实模型与提示词构建，让测试确定且不产生外部调用。"""
    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content=FULL_ANSWER)])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        stream_chat_service, "build_personalized_prompt", lambda **kwargs: None
    )


@pytest.mark.anyio
async def test_stop_stream_chat_keeps_partial_text_and_marks_status(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """读到第一块增量的中途停止：内容保留、状态置 2、事件流立刻收尾。"""
    now = int(time.time())
    user, conversation = _seed_conversation(db_session, now)
    _stub_agent(monkeypatch)

    try:
        response = StreamChatService.stream_chat(
            db=db_session,
            user_id=user.id,
            session_id=conversation.id,
            session_model=1,
            request_text="测试停止",
            select_model=1,
        )
        iterator = response.body_iterator.__aiter__()

        start_event = _parse_frame(await anext(iterator))
        assert start_event is not None and start_event["type"] == "start"
        message_id = start_event["message_id"]

        first_delta = _parse_frame(await anext(iterator))
        assert first_delta is not None and first_delta["type"] == "delta"

        # 模拟用户点「停止」；再点一次应保持幂等。
        assert (
            StreamChatService.stop_stream(
                db=db_session,
                user_id=user.id,
                session_id=conversation.id,
                message_id=message_id,
            )
            is True
        )
        assert (
            StreamChatService.stop_stream(
                db=db_session,
                user_id=user.id,
                session_id=conversation.id,
                message_id=message_id,
            )
            is False
        )

        deltas = [first_delta["text"]]
        events: list[dict] = []
        async for part in iterator:
            parsed = _parse_frame(part)
            if not parsed:
                continue
            events.append(parsed)
            if parsed["type"] == "delta":
                deltas.append(parsed["text"])

        # 停止后不应再有新的 delta，事件流以 done 收尾。
        assert len(deltas) == 1
        assert events[-1]["type"] == "done"
        assert events[-1]["stopped"] is True

        partial_text = "".join(deltas)
        # 部分内容：既不是空的，也确实比完整回答短。
        assert 0 < len(partial_text) < len(FULL_ANSWER)
        assert events[-1]["response_text"] == partial_text

        row = db_session.query(ChatMessage).filter(ChatMessage.id == message_id).one()
        assert row.status == MESSAGE_STATUS_STOPPED
        assert row.response_text == partial_text
    finally:
        _cleanup(db_session, user.id, conversation.id)


def test_stop_stream_rejects_unknown_message(db_session: Session) -> None:
    """停止不存在（或不属于自己）的消息应抛 404。"""
    now = int(time.time())
    user, conversation = _seed_conversation(db_session, now)
    try:
        with pytest.raises(AppException) as exc_info:
            StreamChatService.stop_stream(
                db=db_session,
                user_id=user.id,
                session_id=conversation.id,
                message_id=999_999_999,
            )
        assert exc_info.value.code == 404
    finally:
        _cleanup(db_session, user.id, conversation.id)
