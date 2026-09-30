"""T5.6 回归测试：题库读取接口。

重点验两件事：
1. 卷子详情里的题目**不含参考答案**（答题阶段泄露等于送答案）；
2. 越权访问别人的卷子一律 404，不区分「不存在」与「不是你的」。
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

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

QUIZ_JSON = json.dumps(
    {
        "target_job": "Python 后端",
        "difficulty": "中级",
        "question_count": 2,
        "questions": [
            {"question": "什么是 GIL？", "reference_answer": "全局解释器锁"},
            {"question": "索引为什么失效？", "reference_answer": "函数包裹列"},
        ],
    },
    ensure_ascii=False,
)


async def _create_paper(
    async_client: AsyncClient, headers: dict[str, str]
) -> tuple[int, int, int]:
    """跑一次刷题出题，返回 (session_id, message_id, paper_id)。"""
    session_id = await create_session(async_client, headers)
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=0",
        json={"request_text": "出题", "select_model": 2},
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
    assert done["quiz_paper_id"] is not None
    return session_id, int(start["message_id"]), int(done["quiz_paper_id"])


@pytest.mark.anyio
async def test_get_quiz_paper_hides_reference_answer(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """卷子详情返回题目与序号，但不返回参考答案。"""
    headers = await register_and_login("quizget")
    stub_chat_model(monkeypatch, content=QUIZ_JSON)

    session_id, message_id, paper_id = await _create_paper(async_client, headers)
    try:
        response = await async_client.get(f"/quiz-papers/{paper_id}", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["id"] == paper_id
        assert body["session_id"] == session_id
        assert body["message_id"] == message_id
        assert body["target_job"] == "Python 后端"
        assert body["difficulty"] == "中级"
        assert body["question_count"] == 2
        assert body["status"] == 0

        questions = body["questions"]
        assert [q["order_index"] for q in questions] == [1, 2]
        assert questions[0]["question"] == "什么是 GIL？"
        # 关键：不能把参考答案发出去
        assert all("reference_answer" not in q for q in questions)
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)


@pytest.mark.anyio
async def test_list_quiz_papers_by_session(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """按会话列出卷子，给出 message_id → paper_id 的映射。"""
    headers = await register_and_login("quizlist")
    stub_chat_model(monkeypatch, content=QUIZ_JSON)

    session_id, message_id, paper_id = await _create_paper(async_client, headers)
    try:
        response = await async_client.get(
            f"/quiz-papers?session_id={session_id}", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == paper_id
        assert body["items"][0]["message_id"] == message_id
        assert "questions" not in body["items"][0]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)


@pytest.mark.anyio
async def test_other_users_paper_is_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的卷子：详情 404，列表也查不到。"""
    owner_headers = await register_and_login("quizowner")
    intruder_headers = await register_and_login("quizintruder")
    stub_chat_model(monkeypatch, content=QUIZ_JSON)

    session_id, _message_id, paper_id = await _create_paper(async_client, owner_headers)
    try:
        detail = await async_client.get(
            f"/quiz-papers/{paper_id}", headers=intruder_headers
        )
        assert detail.status_code == 404

        listing = await async_client.get(
            f"/quiz-papers?session_id={session_id}", headers=intruder_headers
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 0
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=owner_headers
        )


@pytest.mark.anyio
async def test_missing_paper_is_404(
    async_client: AsyncClient, register_and_login: RegisterAndLogin
) -> None:
    """不存在的卷子返回 404。"""
    headers = await register_and_login("quizmiss")
    response = await async_client.get("/quiz-papers/99999999", headers=headers)
    assert response.status_code == 404
