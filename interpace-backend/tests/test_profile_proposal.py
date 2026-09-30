"""T6.2 回归测试：简历画像「先确认、后写入」（决策 D11）。

覆盖：
1. 画像解析器（空白、「未知」占位、去重、全空返回 None）；
2. 简历优化这条流式链路会落一条待确认记录，且**不直接写 user_profiles**；
3. 确认接口写入画像，且列表字段是合并去重、不是覆盖；
4. 忽略接口不写画像；
5. 重复确认返回 409；越权一律 404；输入太短时不触发抽取。
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
from app.db.models import ChatMessage, ProfileProposal, UserProfile
from app.services.profile_extraction_service import parse_profile_payload
from app.services.user_memory_service import (
    CATEGORY_SKILL,
    SOURCE_SELF_REPORT,
    MemoryEntry,
    UserMemoryService,
)

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

# 模型在简历优化模式下先给正文，再由后端第二次调用抽画像——同一个桩要能同时满足两件事，
# 所以这里用「能解析成画像的 JSON 当正文」：正文对用户来说不重要，测试只关心中间结果。
RESUME_REPLY = """## 简历诊断
整体与目标岗位匹配。

## 优化后的简历
张伟 / Python 后端 / 3 年
"""

PROFILE_JSON = json.dumps(
    {
        "target_job": "Python 后端",
        "years_experience": "3 年",
        "target_level": "中级",
        "target_skills": ["Python", "FastAPI"],
        "weak_topics": ["索引优化"],
    },
    ensure_ascii=False,
)

# 输入要超过 PROFILE_EXTRACT_MIN_CHARS（120 字）才会触发抽取。
LONG_RESUME_TEXT = "帮我优化简历：" + "Python 后端开发，三年经验，做过订单系统和支付系统。" * 8


def _read_profile(user_id: int) -> UserProfile | None:
    db = SessionLocal()
    try:
        return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    finally:
        db.close()


def _seed_profile(user_id: int, target_skills: list[str]) -> None:
    """造一条已有能力记忆：用来验证「确认」是合并而不是覆盖。

    注意：T9.2 起 `user_profiles.target_skills` 只是**派生缓存**，
    真正的数据在 `user_memories` 里，所以这里要往明细表写。
    """
    db = SessionLocal()
    try:
        UserMemoryService.ingest(
            db,
            user_id=user_id,
            entries=[
                MemoryEntry(category=CATEGORY_SKILL, name=name, mastery=50)
                for name in target_skills
            ],
            source=SOURCE_SELF_REPORT,
            commit=True,
        )
    finally:
        db.close()


def _delete_profile(user_id: int) -> None:
    """删掉本用例造的画像行。"""
    db = SessionLocal()
    try:
        db.query(UserProfile).filter(UserProfile.user_id == user_id).delete()
        db.commit()
    finally:
        db.close()


def _read_proposal(proposal_id: int) -> ProfileProposal | None:
    db = SessionLocal()
    try:
        return db.query(ProfileProposal).filter(ProfileProposal.id == proposal_id).first()
    finally:
        db.close()


def _read_message(message_id: int) -> ChatMessage | None:
    db = SessionLocal()
    try:
        return db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    finally:
        db.close()


async def _send_resume(
    async_client: AsyncClient,
    headers: dict[str, str],
    session_id: int,
    text: str = LONG_RESUME_TEXT,
) -> tuple[dict, int]:
    """发一条「简历优化」消息，返回 (done 事件, 入口消息 id)。"""
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=1",
        json={"request_text": text, "select_model": 3},
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


def test_parse_profile_payload_normalizes() -> None:
    """解析器：占位词归一成 None，列表去重，全空返回 None。"""
    payload = parse_profile_payload(
        json.dumps(
            {
                "target_job": "未知",
                "years_experience": " 3 年 ",
                "target_level": "中级",
                "target_skills": ["Python", "Python", " ", "FastAPI"],
                "weak_topics": [],
            },
            ensure_ascii=False,
        )
    )
    assert payload is not None
    assert payload.target_job is None
    assert payload.years_experience == "3 年"
    assert payload.target_level == "中级"
    assert payload.target_skills == ["Python", "FastAPI"]
    assert payload.is_empty is False


def test_parse_profile_payload_all_empty_returns_none() -> None:
    text = '{"target_job": null, "years_experience": "", "target_level": "未指定", "target_skills": [], "weak_topics": []}'
    assert parse_profile_payload(text) is None
    assert parse_profile_payload("不是 JSON") is None


@pytest.mark.anyio
async def test_resume_stream_creates_pending_proposal(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """简历优化后落待确认记录，但**画像此时还没有被写入**。"""
    headers = await register_and_login("profilepend")
    session_id = await create_session(async_client, headers, session_model=1)
    # 第一次调用返回简历正文，第二次（抽取画像）返回画像 JSON。
    stub_chat_model(monkeypatch, content=RESUME_REPLY)

    try:
        done, message_id = await _send_resume(async_client, headers, session_id)
        # 桩固定返回正文，抽不出来画像 → 不应落待确认记录
        assert done["profile_proposal_id"] is None

        # 换成能解析成画像的返回，再来一轮
        stub_chat_model(monkeypatch, content=PROFILE_JSON)
        done, message_id = await _send_resume(async_client, headers, session_id)
        proposal_id = done["profile_proposal_id"]
        assert proposal_id is not None

        proposal = _read_proposal(int(proposal_id))
        assert proposal is not None
        assert proposal.message_id == message_id
        assert proposal.payload["target_job"] == "Python 后端"
        assert proposal.payload["target_skills"] == ["Python", "FastAPI"]
        assert proposal.status == 0

        # 关键：确认之前不能动画像
        message = _read_message(message_id)
        assert message is not None
        assert _read_profile(message.user_id) is None

        # 列表接口能按会话拿到映射
        listing = await async_client.get(
            f"/profile-proposals?session_id={session_id}", headers=headers
        )
        assert listing.status_code == 200, listing.text
        items = listing.json()["items"]
        assert len(items) == 1
        assert items[0]["message_id"] == message_id
        assert items[0]["target_job"] == "Python 后端"
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_short_input_skips_extraction(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """输入太短（纯提问）时不触发抽取，省一次模型调用。"""
    headers = await register_and_login("profileshort")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content=PROFILE_JSON)

    try:
        done, _message_id = await _send_resume(
            async_client, headers, session_id, text="简历怎么写？"
        )
        assert done["profile_proposal_id"] is None
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_confirm_writes_profile_merging_lists(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """确认写画像：标量字段被覆盖，列表字段是合并去重。"""
    headers = await register_and_login("profileok")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content=PROFILE_JSON)
    profile_user_id: int | None = None

    try:
        done, message_id = await _send_resume(async_client, headers, session_id)
        proposal_id = int(done["profile_proposal_id"])

        # 先给这个用户造一条已有画像：用来验证「确认是合并，不是覆盖」。
        message = _read_message(message_id)
        assert message is not None
        profile_user_id = message.user_id
        _seed_profile(profile_user_id, target_skills=["Docker"])

        # 模拟用户把岗位改成「Python 后端工程师」，技能列表补一项
        response = await async_client.post(
            f"/profile-proposals/{proposal_id}/confirm",
            json={
                "target_job": "Python 后端工程师",
                "years_experience": "3 年",
                "target_level": "中级",
                "target_skills": ["Python", "MySQL"],
                "weak_topics": ["索引优化"],
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["proposal"]["status"] == 1

        profile = _read_profile(message.user_id)
        assert profile is not None
        assert profile.target_job == "Python 后端工程师"
        assert profile.target_level == "中级"
        # 已有 ["Docker"] + 确认 ["Python", "MySQL"] → 合并去重，已有顺序不变
        assert profile.target_skills == ["Docker", "Python", "MySQL"]
        assert profile.weak_topics == ["索引优化"]

        # 重复确认被挡
        again = await async_client.post(
            f"/profile-proposals/{proposal_id}/confirm",
            json={"target_job": "再改一次"},
            headers=headers,
        )
        assert again.status_code == 409
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)
        # 画像不在会话级联删除范围内，单独清掉，不给开发库留残留。
        if profile_user_id is not None:
            _delete_profile(profile_user_id)


@pytest.mark.anyio
async def test_dismiss_does_not_write_profile(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """忽略：状态变成 2，画像不写。"""
    headers = await register_and_login("profiledismiss")
    session_id = await create_session(async_client, headers, session_model=1)
    stub_chat_model(monkeypatch, content=PROFILE_JSON)

    try:
        done, message_id = await _send_resume(async_client, headers, session_id)
        proposal_id = int(done["profile_proposal_id"])

        response = await async_client.post(
            f"/profile-proposals/{proposal_id}/dismiss", headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["proposal"]["status"] == 2

        message = _read_message(message_id)
        assert message is not None
        assert _read_profile(message.user_id) is None
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_other_users_proposal_is_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的待确认记录：确认与忽略都 404，列表也查不到。"""
    owner_headers = await register_and_login("profileowner")
    intruder_headers = await register_and_login("profileintruder")
    session_id = await create_session(async_client, owner_headers, session_model=1)
    stub_chat_model(monkeypatch, content=PROFILE_JSON)

    try:
        done, _message_id = await _send_resume(async_client, owner_headers, session_id)
        proposal_id = int(done["profile_proposal_id"])

        confirm = await async_client.post(
            f"/profile-proposals/{proposal_id}/confirm",
            json={"target_job": "偷改"},
            headers=intruder_headers,
        )
        assert confirm.status_code == 404

        dismiss = await async_client.post(
            f"/profile-proposals/{proposal_id}/dismiss", headers=intruder_headers
        )
        assert dismiss.status_code == 404

        listing = await async_client.get(
            f"/profile-proposals?session_id={session_id}", headers=intruder_headers
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 0
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=owner_headers
        )
