"""T5.7 回归测试：提交答案与评分。

用假模型返回约定的评分 JSON，验四件事：
1. 评分写回题目行（得分 + 解析），卷子状态推到 2；
2. 用户作答先落库——即便评分失败也不会丢；
3. 已评分的卷子再提交返回 409；
4. 评分输出解析不出来时返回 502，且卷子停在「已提交」可重试。
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
from app.db.models import QuizPaper, QuizQuestion, UserProfile

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

EVALUATION_JSON = json.dumps(
    {
        "total_score": 60,
        "weak_topics": ["GIL", "索引失效"],
        "questions": [
            {"order_index": 1, "score": 40, "analysis": "只说了名字，没讲作用"},
            {"order_index": 2, "score": 80, "analysis": "思路对，例子不够"},
        ],
    },
    ensure_ascii=False,
)


def _read_paper(paper_id: int) -> QuizPaper | None:
    db = SessionLocal()
    try:
        return db.query(QuizPaper).filter(QuizPaper.id == paper_id).first()
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


def _read_weak_topics(user_id: int) -> list[str] | None:
    db = SessionLocal()
    try:
        profile = (
            db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        )
        return list(profile.weak_topics) if profile else None
    finally:
        db.close()


async def _create_paper(
    async_client: AsyncClient,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, int]:
    """跑一次出题，返回 (session_id, paper_id)。

    出题这一步用题库 JSON 当假模型输出；调用方随后可以再用
    `stub_chat_model(monkeypatch, content=...)` 覆盖成评分输出。
    """
    stub_chat_model(monkeypatch, content=QUIZ_JSON)
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
    done = next(e for e in events if e["type"] == "done")
    assert done["quiz_paper_id"] is not None
    return session_id, int(done["quiz_paper_id"])


@pytest.mark.anyio
async def test_submit_scores_and_persists(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常提交：返回总分与薄弱点，题目得分与解析落库，卷子变成已评分。"""
    headers = await register_and_login("quizsub")
    session_id, paper_id = await _create_paper(async_client, headers, monkeypatch)
    stub_chat_model(monkeypatch, content=EVALUATION_JSON)

    try:
        response = await async_client.post(
            f"/quiz-papers/{paper_id}/submissions",
            json={
                "answers": [
                    {"order_index": 1, "answer": "GIL 是全局解释器锁"},
                    {"order_index": 2, "answer": "没答上来"},
                ]
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["paper_id"] == paper_id
        assert body["status"] == 2
        assert body["total_score"] == 60
        assert body["weak_topics"] == ["GIL", "索引失效"]
        assert [q["score"] for q in body["questions"]] == [40, 80]
        # 响应里可以带用户自己的作答，但依然不能带参考答案
        assert all("reference_answer" not in q for q in body["questions"])

        paper = _read_paper(paper_id)
        assert paper is not None
        assert paper.status == 2

        questions = _read_questions(paper_id)
        assert [q.score for q in questions] == [40, 80]
        assert questions[0].user_answer == "GIL 是全局解释器锁"
        assert questions[0].analysis == "只说了名字，没讲作用"

        # T5.8：薄弱点写回用户画像
        assert paper.user_id is not None
        assert _read_weak_topics(paper.user_id) == ["GIL", "索引失效"]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)


@pytest.mark.anyio
async def test_second_submission_is_rejected(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """一份卷子只评分一次：第二次提交返回 409。"""
    headers = await register_and_login("quizdup")
    session_id, paper_id = await _create_paper(async_client, headers, monkeypatch)
    stub_chat_model(monkeypatch, content=EVALUATION_JSON)

    try:
        payload = {"answers": [{"order_index": 1, "answer": "答案"}]}
        first = await async_client.post(
            f"/quiz-papers/{paper_id}/submissions", json=payload, headers=headers
        )
        assert first.status_code == 200, first.text

        second = await async_client.post(
            f"/quiz-papers/{paper_id}/submissions", json=payload, headers=headers
        )
        assert second.status_code == 409
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)


@pytest.mark.anyio
async def test_answers_survive_grading_failure(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """评分输出解析不出来时返回 502，但用户答案已经保住，卷子可重试。"""
    headers = await register_and_login("quizfail")
    session_id, paper_id = await _create_paper(async_client, headers, monkeypatch)
    stub_chat_model(monkeypatch, content="这次我不输出 JSON 了")

    try:
        response = await async_client.post(
            f"/quiz-papers/{paper_id}/submissions",
            json={"answers": [{"order_index": 1, "answer": "我的答案"}]},
            headers=headers,
        )
        assert response.status_code == 502, response.text

        paper = _read_paper(paper_id)
        assert paper is not None
        assert paper.status == 1  # 已提交、未评分，可重试
        questions = _read_questions(paper_id)
        assert questions[0].user_answer == "我的答案"
        assert questions[0].score is None
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=0", headers=headers)


@pytest.mark.anyio
async def test_other_users_paper_cannot_be_submitted(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的卷子提交一律 404。"""
    owner_headers = await register_and_login("quizsubowner")
    intruder_headers = await register_and_login("quizsubintruder")
    session_id, paper_id = await _create_paper(async_client, owner_headers, monkeypatch)
    stub_chat_model(monkeypatch, content=EVALUATION_JSON)

    try:
        response = await async_client.post(
            f"/quiz-papers/{paper_id}/submissions",
            json={"answers": [{"order_index": 1, "answer": "答案"}]},
            headers=intruder_headers,
        )
        assert response.status_code == 404
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=0", headers=owner_headers
        )
