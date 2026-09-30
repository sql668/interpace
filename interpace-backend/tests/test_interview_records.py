"""T7.4 / T7.5 回归测试：模拟面试的记录创建与一问一答落库。

覆盖 T7.2 设计里的关键约定：
1. 首条消息建面试记录并把入口消息打标（status=1 + interview_id）；
2. 同一会话的后续轮次**不再新建**记录；
3. 提问来自面试官、回答来自候选人，回填到「最后一条没有答案」的提问上；
4. 用户连续发两条消息时，第二条不产生「空提问」条目；
5. 中途停止生成：答案保留、不追加问题、消息状态是「已停止」而不是面试入口；
6. 非面试模式不写面试记录；详情接口能按 interview_id 取回。
"""

import json
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

from api_helpers import create_session, stub_chat_model, purge_user

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import ChatMessage, Interview, Session as SessionModel, User
from app.services.interview_service import InterviewService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _read_interview(interview_id: int) -> Interview | None:
    db = SessionLocal()
    try:
        return db.query(Interview).filter(Interview.id == interview_id).first()
    finally:
        db.close()


def _read_message(message_id: int) -> ChatMessage | None:
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    finally:
        db.close()


async def _send_interview_message(
    async_client: AsyncClient,
    headers: dict[str, str],
    session_id: int,
    text: str,
    *,
    select_model: int = 4,
) -> tuple[dict, int]:
    """发一条面试间消息，返回 (done 事件, 消息 id)。"""
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=1",
        json={"request_text": text, "select_model": select_model},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[len("data:") :].strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    start = next(e for e in events if e["type"] == "start")
    done = next(e for e in events if e["type"] == "done")
    return done, int(start["message_id"])


@pytest.mark.anyio
async def test_first_message_creates_interview_and_marks_entry(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """首条消息：建记录 + 入口消息打标 + 第一道题落进 qa_object。"""
    headers = await register_and_login("itvfirst")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content="你好，我们先从 Python 基础开始，说说 GIL 是什么？")

    try:
        done, message_id = await _send_interview_message(
            async_client, headers, session_id, "开始面试吧"
        )
        interview_id = done["interview_id"]
        assert interview_id is not None

        interview = _read_interview(int(interview_id))
        assert interview is not None
        assert interview.session_id == session_id
        assert interview.message_id == message_id
        assert interview.status == 0  # 进行中
        assert len(interview.qa_object) == 1
        assert "GIL" in interview.qa_object[0]["question"]
        assert interview.qa_object[0]["answer"] == ""  # 还没有回答

        # 入口消息：前端「查看面试记录详情」卡片靠这两个字段亮起来
        message = _read_message(message_id)
        assert message is not None
        assert message.status == 1
        assert message.interview_id == int(interview_id)

        # 详情接口能取回（越权/不存在由 session_service 已有逻辑兜底）
        detail = await async_client.get(f"/interviews/{interview_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["message_id"] == message_id
        assert len(body["qa_object"]) == 1
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_second_round_fills_answer_and_appends_question(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第二轮：上一题的答案被回填，同时追加这一轮的新问题，且不新建记录。"""
    headers = await register_and_login("itvround")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        stub_chat_model(monkeypatch, content="第一个问题：说说 GIL 是什么？")
        done, message_id = await _send_interview_message(
            async_client, headers, session_id, "开始面试"
        )
        interview_id = int(done["interview_id"])

        stub_chat_model(monkeypatch, content="答得不错。第二个问题：索引为什么会失效？")
        done2, message_id2 = await _send_interview_message(
            async_client, headers, session_id, "GIL 是全局解释器锁，同一时刻只有一个线程跑字节码"
        )
        # 同一场面试：不新建记录
        assert done2["interview_id"] == interview_id

        interview = _read_interview(interview_id)
        assert interview is not None
        assert len(interview.qa_object) == 2
        assert interview.qa_object[0]["question"] == "第一个问题：说说 GIL 是什么？"
        assert "全局解释器锁" in interview.qa_object[0]["answer"]
        assert interview.qa_object[1]["question"] == "答得不错。第二个问题：索引为什么会失效？"
        assert interview.qa_object[1]["answer"] == ""
        # 第二轮的消息不该是入口消息
        assert _read_message(message_id2).interview_id is None
        # 时长有更新
        assert interview.interview_duration >= 0
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_consecutive_user_messages_do_not_create_empty_question(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用户连续发两条消息：第二条不产生空提问条目。"""
    headers = await register_and_login("itvdouble")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        stub_chat_model(monkeypatch, content="问题一：什么是 B+ 树？")
        done, _mid = await _send_interview_message(
            async_client, headers, session_id, "开始"
        )
        interview_id = int(done["interview_id"])

        # 第二条仍然是一轮「问答」：它会回填问题一的答案，并追加问题二
        stub_chat_model(monkeypatch, content="问题二：说说索引覆盖？")
        await _send_interview_message(async_client, headers, session_id, "B+ 树是平衡树")
        # 第三条：此时没有待回答的提问，应当被忽略
        stub_chat_model(monkeypatch, content="问题三：讲讲事务隔离级别？")
        await _send_interview_message(async_client, headers, session_id, "补充一句")

        interview = _read_interview(interview_id)
        assert interview is not None
        # 三条消息 = 三个问题，但只有前两个问题拿到了答案，且不存在空提问
        assert all(str(item["question"]).strip() for item in interview.qa_object)
        answers = [item["answer"] for item in interview.qa_object]
        assert answers[0] == "B+ 树是平衡树"
        assert answers[1] == "补充一句"
        assert answers[2] == ""
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_non_interview_mode_writes_nothing(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非模拟面试模式（快速回答）不写面试记录。"""
    headers = await register_and_login("itvother")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content="这是一段普通回答")

    try:
        done, _mid = await _send_interview_message(
            async_client, headers, session_id, "你好", select_model=0
        )
        assert done["interview_id"] is None

        db = SessionLocal()
        try:
            count = db.query(Interview).filter(Interview.session_id == session_id).count()
        finally:
            db.close()
        assert count == 0
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


# ---------- 中途停止的两条路径：直接测服务层，避开流式时序抖动 ----------


def _seed_rows(db) -> tuple[User, SessionModel, ChatMessage]:
    """造一条最简的 用户 + 会话 + 消息，供服务层直测使用。"""
    now = int(time.time())
    user = User(
        username=f"t74_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=now,
    )
    db.add(user)
    db.flush()
    session = SessionModel(user_id=user.id, session_model=1, title="t7_4", created_at=now)
    db.add(session)
    db.flush()
    message = ChatMessage(
        user_id=user.id,
        session_id=session.id,
        select_model=4,
        request_id=uuid.uuid4().hex,
        request_text="开始面试",
        response_text="",
        status=0,
    )
    db.add(message)
    db.commit()
    return user, session, message


def _cleanup_rows(db, user_id: int, session_id: int) -> None:
    db.rollback()
    db.query(Interview).filter(Interview.session_id == session_id).delete()
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.query(SessionModel).filter(SessionModel.id == session_id).delete()
    db.commit()
    # 统一走共享清理：顺序与外键依赖一致（检索索引 / 记忆日志 / 记忆 / 画像 / 用户）
    purge_user(user_id)


def test_stopped_first_message_creates_no_interview() -> None:
    """首条消息就被停止：这场面试什么都没有，不建记录（否则会留下空面试）。"""
    db = SessionLocal()
    user_id = session_id = None
    try:
        user, session, message = _seed_rows(db)
        user_id, session_id = user.id, session.id
        interview_id = InterviewService.record_round(
            db=db,
            user_id=user.id,
            session_id=session.id,
            message_id=message.id,
            request_text="开始面试",
            response_text="半截回答",
            response_ok=False,
        )
        assert interview_id is None
        assert db.query(Interview).filter(Interview.session_id == session.id).count() == 0
    finally:
        if user_id is not None and session_id is not None:
            _cleanup_rows(db, user_id, session_id)
        db.close()


def test_stopped_later_message_keeps_answer_but_adds_no_question() -> None:
    """后续轮次被停止：用户的回答要留下，半截回答不能变成面试题。"""
    db = SessionLocal()
    user_id = session_id = None
    try:
        user, session, message = _seed_rows(db)
        user_id, session_id = user.id, session.id
        # 先正常问一题
        interview_id = InterviewService.record_round(
            db=db,
            user_id=user.id,
            session_id=session.id,
            message_id=message.id,
            request_text="开始面试",
            response_text="第一个问题：GIL 是什么？",
            response_ok=True,
        )
        db.commit()
        assert interview_id is not None

        # 第二轮：用户答了话，但生成被停止
        second = ChatMessage(
            user_id=user.id,
            session_id=session.id,
            select_model=4,
            request_id=uuid.uuid4().hex,
            request_text="GIL 是全局解释器锁",
            response_text="半截的下一题",
            status=2,
        )
        db.add(second)
        db.commit()
        InterviewService.record_round(
            db=db,
            user_id=user.id,
            session_id=session.id,
            message_id=second.id,
            request_text="GIL 是全局解释器锁",
            response_text="半截的下一题",
            response_ok=False,
        )
        db.commit()

        interview = _read_interview(interview_id)
        assert interview is not None
        assert len(interview.qa_object) == 1  # 半截回答没有变成第二题
        assert interview.qa_object[0]["answer"] == "GIL 是全局解释器锁"
        assert interview.status == 0  # 停止不等于面试异常
    finally:
        if user_id is not None and session_id is not None:
            _cleanup_rows(db, user_id, session_id)
        db.close()
