"""T5.5 回归测试：刷题场景的回复能解析并落库成题库。

三条路径：
1. 刷题模式 + 回复是题库 JSON → 落 `quiz_papers` / `quiz_questions`，入口消息标记 status=3；
2. 刷题模式 + 回复还在确认参数 → 什么都不落，status 保持 0；
3. 其它模式 + 回复是题库 JSON → 不落库（只有 quiz 场景才解析）。
"""

import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

from api_helpers import create_session, stub_chat_model

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import ChatMessage, QuizPaper, QuizQuestion

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

QUIZ_JSON = json.dumps(
    {
        "target_job": "Python 后端",
        "difficulty": "中级",
        "question_count": 2,
        "questions": [
            {"question": "什么是 GIL？", "reference_answer": "全局解释器锁"},
            {
                "question": "B+ 树为什么适合做索引？",
                "reference_answer": "树矮、范围扫描快",
            },
        ],
    },
    ensure_ascii=False,
)


def _read_paper(message_id: int) -> QuizPaper | None:
    """直接查库看卷子落没落，不看接口。"""
    db = SessionLocal()
    try:
        return db.query(QuizPaper).filter(QuizPaper.message_id == message_id).first()
    finally:
        db.close()


def _read_questions(paper_id: int) -> list[QuizQuestion]:
    db = SessionLocal()
    try:
        return (
            db.query(QuizQuestion)
            .filter(QuizQuestion.paper_id == paper_id)
            .order_by(QuizQuestion.order_index)
            .all()
        )
    finally:
        db.close()


def _read_message(message_id: int) -> ChatMessage | None:
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    finally:
        db.close()


async def _send(
    async_client: AsyncClient,
    headers: dict[str, str],
    session_id: int,
    select_model: int,
) -> tuple[list[dict], int]:
    """发一条消息，返回 (SSE 事件列表, 本轮入口消息 id)。"""
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=0",
        json={"request_text": "试试", "select_model": select_model},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    events = [
        json.loads(line[len("data:") :].strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    start = next(e for e in events if e["type"] == "start")
    return events, int(start["message_id"])


@pytest.mark.anyio
async def test_quiz_scene_persists_paper(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """刷题模式 + 题库 JSON：卷子与题目都落库，入口消息标记为 3。"""
    headers = await register_and_login("quizok")
    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch, content=QUIZ_JSON)

    try:
        events, message_id = await _send(
            async_client, headers, session_id, select_model=2
        )
        done = next(e for e in events if e["type"] == "done")
        assert done["quiz_paper_id"] is not None

        paper = _read_paper(message_id)
        assert paper is not None
        assert paper.id == done["quiz_paper_id"]
        assert paper.target_job == "Python 后端"
        assert paper.difficulty == "中级"
        assert paper.question_count == 2
        assert paper.status == 0  # 待作答

        questions = _read_questions(paper.id)
        assert [q.order_index for q in questions] == [1, 2]
        assert questions[0].question == "什么是 GIL？"
        assert questions[0].reference_answer == "全局解释器锁"
        assert questions[0].score is None

        message = _read_message(message_id)
        assert message is not None
        assert message.status == 3  # 题库入口
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )


@pytest.mark.anyio
async def test_quiz_scene_without_quiz_reply_persists_nothing(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """刷题模式 + 还在确认参数：不落库，消息状态保持 0。"""
    headers = await register_and_login("quizno")
    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch, content="请确认一下参数：目标岗位、难度、题量？")

    try:
        events, message_id = await _send(
            async_client, headers, session_id, select_model=2
        )
        done = next(e for e in events if e["type"] == "done")
        assert done["quiz_paper_id"] is None

        assert _read_paper(message_id) is None
        message = _read_message(message_id)
        assert message is not None
        assert message.status == 0
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )


@pytest.mark.anyio
async def test_non_quiz_scene_does_not_persist_paper(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """其它模式即使吐出题库 JSON 也不落库：只有 quiz 场景才解析。"""
    headers = await register_and_login("quizother")
    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch, content=QUIZ_JSON)

    try:
        events, message_id = await _send(
            async_client, headers, session_id, select_model=0
        )
        done = next(e for e in events if e["type"] == "done")
        assert done["quiz_paper_id"] is None

        assert _read_paper(message_id) is None
        message = _read_message(message_id)
        assert message is not None
        assert message.status == 0
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=headers
        )
