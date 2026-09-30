"""T12.4 回归测试：演示环境的「单场模拟面试 3 分钟」上限。

时长从**面试记录创建**算起，语音与文字共用同一个时钟。这里覆盖文字链路
（语音链路的到点自动结束在 `test_speech_stream.py` 里，那边才有 WebSocket 夹具）：

- 到点后不再回答新问题，**也不再调用模型**（这是最省钱的一道闸）；
- 到点会把面试记录结束掉，而不是一直停在「进行中」；
- 上限只在演示环境生效，开发环境完全不受影响。
"""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from api_helpers import create_session, stub_chat_model
from app.core.quota_config import DemoLimits
from app.db.database import SessionLocal
from app.db.models import Interview, UsageRecord
from app.services.usage_quota_service import UsageQuotaService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

TEST_IP = "203.0.113.77"


class _FakeSettings:
    """把当前环境伪装成演示环境（settings 是 frozen dataclass，只能换模块级引用）。"""

    app_env = "demo"


def _limits(max_minutes: int = 3) -> DemoLimits:
    return DemoLimits.from_dict(
        {
            "enabled": True,
            "environments": ["demo"],
            "interview": {"max_minutes": max_minutes},
            "notice": {"interview_timeout_message": "已达 {minutes} 分钟上限"},
        }
    )


@pytest.fixture(autouse=True)
def clean_usage() -> None:
    _purge()
    yield
    _purge()


def _purge() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(UsageRecord).where(UsageRecord.client_ip == TEST_IP))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def demo_env(monkeypatch: pytest.MonkeyPatch):
    """把「当前环境 = demo」和「配额配置」一起替换掉。"""
    import app.services.usage_quota_service as service_module

    def _apply(max_minutes: int = 3) -> None:
        monkeypatch.setattr(service_module, "settings", _FakeSettings())
        monkeypatch.setattr(
            UsageQuotaService, "limits", staticmethod(lambda: _limits(max_minutes))
        )

    _apply()
    return _apply


# ---------------- 时长计算 ----------------


def test_remaining_seconds_uses_interview_start(demo_env) -> None:
    """剩余时间按面试记录的创建时间算；超时返回负数（日志里能看到超了多少）。"""
    import time

    now = int(time.time())
    assert UsageQuotaService.interview_max_minutes() == 3
    assert UsageQuotaService.interview_remaining_seconds(now) == pytest.approx(180, abs=3)
    assert UsageQuotaService.interview_remaining_seconds(now - 60) == pytest.approx(120, abs=3)
    assert UsageQuotaService.interview_remaining_seconds(now - 300) < 0

    # 拿不到创建时间时按"刚开始"处理，不要因为查不到就判超时
    assert UsageQuotaService.interview_remaining_seconds(None) == 180
    assert UsageQuotaService.interview_remaining_seconds(0) == 180


def test_no_limit_when_disabled(demo_env) -> None:
    """上限为 0 表示不限：返回 None，调用方据此跳过所有判断。"""
    demo_env(max_minutes=0)
    assert UsageQuotaService.interview_max_minutes() == 0
    assert UsageQuotaService.interview_remaining_seconds(1) is None


def test_dev_environment_has_no_interview_limit() -> None:
    """开发环境不受这条限制（当前测试进程就是 development）。"""
    assert UsageQuotaService.interview_max_minutes() == 0
    assert UsageQuotaService.interview_remaining_seconds(1) is None


# ---------------- 文字模拟面试到点后不再回答 ----------------


async def _start_interview(
    async_client: AsyncClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[int, int]:
    """开一场文字模拟面试，返回 (session_id, interview_id)。"""
    captured: list[list[Any]] = []
    stub_chat_model(monkeypatch, captured, content="请介绍一下你的项目经验。")
    session_id = await create_session(async_client, headers, session_model=1)
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=1",
        json={"request_text": "我准备好了，开始吧", "select_model": 4},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .order_by(Interview.id.desc())
            .first()
        )
        assert interview is not None, "第一轮应该建立面试记录"
        return session_id, interview.id
    finally:
        db.close()


def _backdate_interview(interview_id: int, seconds: int) -> None:
    """把面试记录的创建时间往前推，用来模拟"这场面试已经进行了 N 秒"。"""
    import time

    db = SessionLocal()
    try:
        interview = db.get(Interview, interview_id)
        interview.created_at = int(time.time()) - seconds
        db.add(interview)
        db.commit()
    finally:
        db.close()


@pytest.mark.anyio
async def test_text_interview_stops_after_limit(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
    demo_env,
) -> None:
    """超过 3 分钟后：给提示、结束面试记录、**不再调用模型**。"""
    headers = await register_and_login("intvcap")
    session_id, interview_id = await _start_interview(async_client, headers, monkeypatch)

    try:
        # 模拟这场面试已经进行了 5 分钟
        _backdate_interview(interview_id, 300)

        # 换一个会记录调用的桩：用来断言"超时后模型没被调用"
        calls: list[list[Any]] = []
        stub_chat_model(monkeypatch, calls, content="这段不应该出现")

        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=1",
            json={"request_text": "再问我一题", "select_model": 4},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert "3 分钟上限" in response.text
        assert calls == [], "超时后不应该再调用模型（这是省钱的关键）"

        # `done` 事件里要带上完整正文，前端照常渲染成一条回答
        assert '"type": "done"' in response.text
        assert '"stopped": true' in response.text

        # 面试记录应该被结束掉，而不是停在「进行中」
        db = SessionLocal()
        try:
            interview = db.get(Interview, interview_id)
            assert interview.status == 1, "超时后面试记录应标记为已结束"
            assert interview.interview_duration >= 300
        finally:
            db.close()
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=headers
        )


@pytest.mark.anyio
async def test_text_interview_within_limit_still_answers(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
    demo_env,
) -> None:
    """没到上限时要正常回答——限制不能误伤正常使用。"""
    headers = await register_and_login("intvok")
    session_id, interview_id = await _start_interview(async_client, headers, monkeypatch)

    try:
        _backdate_interview(interview_id, 60)  # 才过 1 分钟

        calls: list[list[Any]] = []
        stub_chat_model(monkeypatch, calls, content="那我们聊聊 Redis 的持久化。")

        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=1",
            json={"request_text": "好的", "select_model": 4},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert calls, "未超时的情况下应该照常调用模型"
        assert "3 分钟上限" not in response.text
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=headers
        )


@pytest.mark.anyio
async def test_first_interview_round_is_allowed(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
    demo_env,
) -> None:
    """还没开始面试时不能判超时——这一轮就是"开始面试"，必须放行。

    否则演示环境会出现「连第一句都问不出去」的离谱行为。
    """
    headers = await register_and_login("intvfirst")
    calls: list[list[Any]] = []
    stub_chat_model(monkeypatch, calls, content="我们开始吧，先自我介绍一下。")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        response = await async_client.post(
            f"/sessions/{session_id}/stream-chat?session_model=1",
            json={"request_text": "开始面试", "select_model": 4},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert calls, "第一轮必须正常调用模型"
        assert "上限" not in response.text
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=headers
        )
