"""T9.16 回归测试：长会话的上下文压缩。

重点：
1. **触发节流**：攒够一批才压一次，不是每轮都压（否则长会话每轮都在烧模型）；
2. **渐进覆盖**：第二次只压新增的那批，不重压整段历史；
3. **真的进了提示词**：摘要出现在模型收到的消息里；
4. 摘要生成失败时降级成「没有摘要」，不打断正常回答。
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

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.db.database import SessionLocal
from app.db.models import ChatMessage, Session as SessionModel, SessionSummary, User
from app.services import session_summary_service
from app.services.session_summary_service import SessionSummaryService


def _make_session(message_count: int) -> tuple[int, int, int]:
    """造一个用户 + 会话 + N 条消息，返回 (user_id, session_id, last_message_id)。"""
    now = int(time.time())
    db = SessionLocal()
    try:
        user = User(
            username=f"sum_{uuid.uuid4().hex[:8]}",
            password="x" * 12,
            avatar=None,
            create_time=now,
        )
        db.add(user)
        db.flush()
        session = SessionModel(
            user_id=user.id, session_model=0, title="长会话", created_at=now
        )
        db.add(session)
        db.flush()
        last_id = 0
        for index in range(1, message_count + 1):
            row = ChatMessage(
                user_id=user.id,
                session_id=session.id,
                select_model=0,
                request_id=uuid.uuid4().hex,
                request_text=f"第 {index} 轮问题：暗号是 CODE-{index}",
                response_text=f"第 {index} 轮回答",
                status=0,
            )
            db.add(row)
            db.flush()
            last_id = row.id
        db.commit()
        return user.id, session.id, last_id
    finally:
        db.close()


def _drop(user_id: int, session_id: int) -> None:
    from api_helpers import purge_user

    db = SessionLocal()
    try:
        db.query(SessionSummary).filter(SessionSummary.session_id == session_id).delete()
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        db.query(SessionModel).filter(SessionModel.id == session_id).delete()
        db.commit()
    finally:
        db.close()
    purge_user(user_id)


def _stub_summarizer(monkeypatch: pytest.MonkeyPatch, text: str = "早期对话摘要") -> list[int]:
    """替换摘要模型，返回一个「被调用次数」的可观察列表。"""
    calls: list[int] = []

    class CountingModel(GenericFakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            calls.append(1)
            return super()._generate(messages, stop, run_manager, **kwargs)

    monkeypatch.setattr(
        session_summary_service,
        "get_chat_model",
        lambda provider="deepseek": CountingModel(messages=iter([AIMessage(content=text)])),
    )
    return calls


def test_short_session_needs_no_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """消息条数不超过保留窗口时不压缩（也不调模型）。"""
    user_id, session_id, _ = _make_session(5)
    calls = _stub_summarizer(monkeypatch)
    db = SessionLocal()
    try:
        assert (
            SessionSummaryService.ensure_summary(
                db, user_id=user_id, session_id=session_id
            )
            == ""
        )
        assert calls == []
    finally:
        db.close()
        _drop(user_id, session_id)


def test_first_crossing_summarizes_older_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次超出保留窗口就先压一次——否则早期内容一直是丢的。"""
    user_id, session_id, _ = _make_session(15)
    calls = _stub_summarizer(monkeypatch, "用户在前几轮提到了暗号 CODE-1")
    db = SessionLocal()
    try:
        summary = SessionSummaryService.ensure_summary(
            db, user_id=user_id, session_id=session_id
        )
        assert "CODE-1" in summary
        assert len(calls) == 1

        row = SessionSummaryService.get_summary(db, session_id=session_id)
        assert row is not None
        assert row.covered_count == 5  # 15 条里保留最近 10 条，压掉 5 条
    finally:
        db.close()
        _drop(user_id, session_id)


def test_incremental_summary_only_covers_new_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第二次只在攒够新的一批时才压，且覆盖数只增加新压的那批。"""
    user_id, session_id, _ = _make_session(15)
    calls = _stub_summarizer(monkeypatch)
    db = SessionLocal()
    try:
        SessionSummaryService.ensure_summary(db, user_id=user_id, session_id=session_id)
        assert len(calls) == 1
        first = SessionSummaryService.get_summary(db, session_id=session_id)
        assert first is not None
        first_covered = first.covered_count

        # 立刻再调一次：没有新的一批，不该再调模型
        SessionSummaryService.ensure_summary(db, user_id=user_id, session_id=session_id)
        assert len(calls) == 1, "没有新增消息时不该重复压缩"

        # 再加 10 条消息（共 25 条）→ 未覆盖的攒到 10 条，触发一次压缩
        now = int(time.time())
        for index in range(16, 26):
            db.add(
                ChatMessage(
                    user_id=user_id,
                    session_id=session_id,
                    select_model=0,
                    request_id=uuid.uuid4().hex,
                    request_text=f"第 {index} 轮问题",
                    response_text=f"第 {index} 轮回答",
                    status=0,
                )
            )
        db.commit()

        SessionSummaryService.ensure_summary(db, user_id=user_id, session_id=session_id)
        assert len(calls) == 2
        second = SessionSummaryService.get_summary(db, session_id=session_id)
        assert second is not None
        # 25 条消息 → 保留最近 10 条 → 应覆盖前 15 条；首轮已覆盖 5 条，因此本轮只压 10 条
        assert second.covered_count == first_covered + 10
    finally:
        db.close()
        _drop(user_id, session_id)


def test_summary_failure_degrades_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """摘要生成失败时返回空串（或旧摘要），不抛异常——不能把正常回答带崩。"""
    user_id, session_id, _ = _make_session(15)

    def boom(*_args, **_kwargs):
        raise RuntimeError("模型不可用")

    monkeypatch.setattr(session_summary_service, "get_chat_model", boom)
    db = SessionLocal()
    try:
        assert (
            SessionSummaryService.ensure_summary(
                db, user_id=user_id, session_id=session_id
            )
            == ""
        )
    finally:
        db.close()
        _drop(user_id, session_id)


@pytest.mark.anyio
async def test_summary_reaches_the_model(
    async_client, register_and_login, monkeypatch
) -> None:
    """摘要要真的出现在模型收到的消息里。"""
    from api_helpers import create_session, make_recording_model
    from app.agent import prompt_layer

    headers = await register_and_login("sumctx")
    session_id = await create_session(async_client, headers)

    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        user_id = user.id
    finally:
        db.close()

    # 造 30 条历史消息 + 一条摘要（直接写库，省掉压缩调用）
    db = SessionLocal()
    try:
        for index in range(1, 31):
            db.add(
                ChatMessage(
                    user_id=user_id,
                    session_id=session_id,
                    select_model=0,
                    request_id=uuid.uuid4().hex,
                    request_text=f"历史第 {index} 轮",
                    response_text="历史回答",
                    status=0,
                )
            )
        db.add(
            SessionSummary(
                user_id=user_id,
                session_id=session_id,
                summary="早期对话里用户说过他的目标岗位是 Python 后端。",
                covered_message_id=999,
                covered_count=20,
            )
        )
        db.commit()
    finally:
        db.close()

    captured: list[list] = []
    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": make_recording_model(captured),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        prompt_layer, "build_personalized_prompt", lambda **kwargs: "你是助手"
    )

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=0",
            json={"request_text": "继续"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        flattened = str(captured)
        assert "Python 后端" in flattened, "摘要没有进到模型输入里"
        assert "更早内容的摘要" in flattened
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)
        _drop(user_id, session_id)
