"""T8.1 / T8.2 / T8.4 回归测试：面试复盘的生成、读取与画像写回。

覆盖：
1. 解析器容错（代码块包裹、字段缺失、全空）；
2. 生成复盘：落库 + 薄弱点合并进用户画像；
3. 重复生成按最新问答记录覆盖，不产生第二行；
4. 没有问答记录时 409；越权与不存在的面试记录都是 404；
5. 没生成过时读取返回 404。
"""

import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

from api_helpers import create_session, stub_chat_model, upload_file

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import Interview, InterviewEvaluation, UserProfile
from app.services import interview_evaluation_service
from app.services.interview_evaluation_service import (
    build_qa_transcript,
    parse_evaluation_payload,
)
from app.services.volc_speech.asr_client import resolve_audio_format

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

EVALUATION_JSON = json.dumps(
    {
        "summary": "整体处于中级偏下的水平。GIL 那道题答得不错，索引失效与并发模型两题明显没底。",
        "weak_topics": ["MySQL 索引优化", "GIL 与并发模型"],
        "suggestions": ["把 B+ 树索引结构与最左前缀原理过一遍", "用多进程/协程各写一个并发小例子"],
    },
    ensure_ascii=False,
)


def _read_evaluation(interview_id: int) -> InterviewEvaluation | None:
    db = SessionLocal()
    try:
        return (
            db.query(InterviewEvaluation)
            .filter(InterviewEvaluation.interview_id == interview_id)
            .first()
        )
    finally:
        db.close()


def _read_weak_topics(user_id: int) -> list[str] | None:
    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        return list(profile.weak_topics) if profile else None
    finally:
        db.close()


def _read_interview(interview_id: int) -> Interview | None:
    db = SessionLocal()
    try:
        return db.query(Interview).filter(Interview.id == interview_id).first()
    finally:
        db.close()


async def _run_interview_round(
    async_client: AsyncClient,
    headers: dict[str, str],
    session_id: int,
    text: str,
    reply: str,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    """发一条「模拟面试」消息，返回 done 事件（里面带 interview_id）。"""
    stub_chat_model(monkeypatch, content=reply)
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=1",
        json={"request_text": text, "select_model": 4},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    events = [
        json.loads(line[len("data:") :].strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    return next(e for e in events if e["type"] == "done")


# ---------------- 解析器 ----------------


def test_parse_evaluation_tolerates_code_fence() -> None:
    payload = parse_evaluation_payload(f"```json\n{EVALUATION_JSON}\n```")
    assert payload is not None
    assert "中级" in payload.summary
    assert payload.weak_topics == ["MySQL 索引优化", "GIL 与并发模型"]
    assert len(payload.suggestions) == 2


def test_parse_evaluation_tolerates_prose_and_dedupes() -> None:
    text = (
        f"复盘如下：{EVALUATION_JSON}\n希望有帮助。"
    ).replace("MySQL 索引优化\", \"GIL", "MySQL 索引优化\", \"MySQL 索引优化\", \"GIL")
    payload = parse_evaluation_payload(text)
    assert payload is not None
    assert payload.weak_topics.count("MySQL 索引优化") == 1


def test_parse_evaluation_rejects_empty_or_invalid() -> None:
    assert parse_evaluation_payload("") is None
    assert parse_evaluation_payload("不是 JSON") is None
    assert parse_evaluation_payload('{"summary": "", "weak_topics": [], "suggestions": []}') is None


def test_build_qa_transcript_marks_unanswered() -> None:
    interview = Interview(
        user_id=1, session_id=1, message_id=1, qa_object=[
            {"question": "GIL 是什么？", "answer": "全局解释器锁"},
            {"question": "索引为什么失效？", "answer": ""},
        ]
    )
    transcript = build_qa_transcript(interview)
    assert "第 1 题" in transcript
    assert "候选人：全局解释器锁" in transcript
    assert "候选人：（未作答）" in transcript


def test_resolve_audio_format() -> None:
    """录音格式由后缀推断，我们不做本地解码，交给服务端解。"""
    assert resolve_audio_format("面试录音.wav") == "wav"
    assert resolve_audio_format("interview.MP3") == "mp3"
    assert resolve_audio_format("a.m4a") == "m4a"
    assert resolve_audio_format("简历.pdf") is None
    assert resolve_audio_format("无后缀") is None


# ---------------- 接口 ----------------


@pytest.mark.anyio
async def test_generate_evaluation_persists_and_merges_profile(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生成复盘：落库、返回结构完整、薄弱点写进画像。"""
    headers = await register_and_login("evalgen")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        stub_chat_model(monkeypatch, content=EVALUATION_JSON)
        response = await async_client.post(
            f"/interviews/{interview_id}/evaluations", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["message"] == "复盘已生成"
        result = body["evaluation"]
        assert result["interview_id"] == interview_id
        assert "中级" in result["summary"]
        assert result["weak_topics"] == ["MySQL 索引优化", "GIL 与并发模型"]
        assert result["qa_count"] == 1

        # 落库
        row = _read_evaluation(interview_id)
        assert row is not None
        assert row.qa_count == 1

        # T8.4：薄弱点写回画像
        interview = _read_interview(interview_id)
        assert interview is not None
        assert _read_weak_topics(interview.user_id) == ["MySQL 索引优化", "GIL 与并发模型"]

        # 读取已生成的复盘
        fetched = await async_client.get(
            f"/interviews/{interview_id}/evaluations", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["evaluation"]["summary"] == result["summary"]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_regenerate_overwrites_single_row(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重复生成：按最新的问答记录覆盖，仍然只有一行。"""
    headers = await register_and_login("evalregen")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        stub_chat_model(monkeypatch, content=EVALUATION_JSON)
        await async_client.post(f"/interviews/{interview_id}/evaluations", headers=headers)

        # 再答一轮（这条消息会回填第一题答案并追加第二题）
        await _run_interview_round(
            async_client, headers, session_id, "GIL 是全局解释器锁", "第二题：索引为什么失效？", monkeypatch
        )

        revised = json.dumps(
            {"summary": "补答之后仍偏弱。", "weak_topics": ["索引失效"], "suggestions": ["练一遍最左前缀"]},
            ensure_ascii=False,
        )
        stub_chat_model(monkeypatch, content=revised)
        again = await async_client.post(
            f"/interviews/{interview_id}/evaluations", headers=headers
        )
        assert again.status_code == 200, again.text
        assert again.json()["evaluation"]["summary"] == "补答之后仍偏弱。"
        assert again.json()["evaluation"]["qa_count"] == 2

        db = SessionLocal()
        try:
            count = (
                db.query(InterviewEvaluation)
                .filter(InterviewEvaluation.interview_id == interview_id)
                .count()
            )
        finally:
            db.close()
        assert count == 1  # 覆盖而不是新增
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_read_before_generate_returns_null_not_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没生成过就读 → **200 + evaluation=null**，不是 404。

    用 404 表达「还没生成」会让前端每次打开面板都吃一个错误响应，
    而全局拦截器对 404 会弹「资源不存在」，用户会莫名看到红色报错（真机反馈）。
    """
    headers = await register_and_login("evalnone")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])
        response = await async_client.get(
            f"/interviews/{interview_id}/evaluations", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["evaluation"] is None
        assert "还没有生成" in body["message"]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_other_users_interview_is_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的面试记录：生成与读取都是 404。"""
    owner_headers = await register_and_login("evalowner")
    intruder_headers = await register_and_login("evalintruder")
    session_id = await create_session(async_client, owner_headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, owner_headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        gen = await async_client.post(
            f"/interviews/{interview_id}/evaluations", headers=intruder_headers
        )
        assert gen.status_code == 404
        read = await async_client.get(
            f"/interviews/{interview_id}/evaluations", headers=intruder_headers
        )
        assert read.status_code == 404
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=owner_headers
        )


# ---------------- T8.3 录音复盘 ----------------


@pytest.mark.anyio
async def test_finish_interview_is_idempotent(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """结束面试（T7.8）：状态置为已结束、时长冻结，重复调用幂等。"""
    headers = await register_and_login("finishitv")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        first = await async_client.post(
            f"/interviews/{interview_id}/finish", headers=headers
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["status"] == 1  # 已结束
        assert body["already_finished"] is False
        assert body["qa_count"] == 1
        assert body["interview_duration"] >= 0

        interview = _read_interview(interview_id)
        assert interview is not None
        assert interview.status == 1
        frozen = interview.interview_duration

        # 再点一次：不报错、不改数据
        second = await async_client.post(
            f"/interviews/{interview_id}/finish", headers=headers
        )
        assert second.status_code == 200
        assert second.json()["already_finished"] is True
        assert _read_interview(interview_id).interview_duration == frozen
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_finish_other_users_interview_is_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的面试不能被我结束。"""
    owner_headers = await register_and_login("finishowner")
    intruder_headers = await register_and_login("finishintruder")
    session_id = await create_session(async_client, owner_headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, owner_headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])
        response = await async_client.post(
            f"/interviews/{interview_id}/finish", headers=intruder_headers
        )
        assert response.status_code == 404
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=owner_headers
        )


FAKE_TRANSCRIPT = "面试官问我 GIL，我答了全局解释器锁。问索引失效，我说不太清楚。"


def _stub_transcription(monkeypatch: pytest.MonkeyPatch, text: str = FAKE_TRANSCRIPT) -> None:
    """把整段识别换成桩：真机会连火山，测试不能依赖它。"""

    async def fake_transcribe(data: bytes, **_kwargs) -> str:
        assert data, "录音字节应被完整取出来"
        return text

    monkeypatch.setattr(
        interview_evaluation_service, "transcribe_file_bytes", fake_transcribe
    )


@pytest.mark.anyio
async def test_evaluation_from_audio_persists_with_source(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上传录音复盘：转写 → 评测 → 落库（来源=录音，记下资源 ID），薄弱点写回画像。"""
    headers = await register_and_login("evalaudio")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        uploaded = await upload_file(
            async_client, headers, "面试录音.wav", b"RIFFfake-audio-bytes", "audio/wav"
        )
        resource_id = uploaded["resource_id"]

        _stub_transcription(monkeypatch)
        stub_chat_model(monkeypatch, content=EVALUATION_JSON)
        response = await async_client.post(
            f"/interviews/{interview_id}/evaluations/from-audio",
            json={"resource_id": resource_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["message"] == "已根据录音生成复盘"
        # 转写文本要回传，用户才能判断「AI 听到的是什么」
        assert body["transcript"] == FAKE_TRANSCRIPT

        result = body["evaluation"]
        assert result["source"] == 1  # 来源=录音
        assert result["resource_id"] == resource_id
        assert result["weak_topics"] == ["MySQL 索引优化", "GIL 与并发模型"]
        assert result["qa_count"] >= 1

        row = _read_evaluation(interview_id)
        assert row is not None
        assert row.source == 1
        assert row.resource_id == resource_id

        interview = _read_interview(interview_id)
        assert interview is not None
        assert _read_weak_topics(interview.user_id) == ["MySQL 索引优化", "GIL 与并发模型"]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_audio_evaluation_overrides_qa_evaluation(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一场面试先按问答复盘、再按录音复盘：覆盖同一行，来源随之切换。"""
    headers = await register_and_login("evalaudioover")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        stub_chat_model(monkeypatch, content=EVALUATION_JSON)
        first = await async_client.post(
            f"/interviews/{interview_id}/evaluations", headers=headers
        )
        assert first.json()["evaluation"]["source"] == 0

        uploaded = await upload_file(
            async_client, headers, "rec.mp3", b"ID3fake-mp3", "audio/mpeg"
        )
        _stub_transcription(monkeypatch)
        second = await async_client.post(
            f"/interviews/{interview_id}/evaluations/from-audio",
            json={"resource_id": uploaded["resource_id"]},
            headers=headers,
        )
        assert second.status_code == 200, second.text
        assert second.json()["evaluation"]["source"] == 1

        db = SessionLocal()
        try:
            count = (
                db.query(InterviewEvaluation)
                .filter(InterviewEvaluation.interview_id == interview_id)
                .count()
            )
        finally:
            db.close()
        assert count == 1  # 覆盖，不新增
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_audio_evaluation_rejects_unsupported_format(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """不是音频（比如误传简历）→ 400，而不是把它当音频硬解。"""
    headers = await register_and_login("evalaudiofmt")
    session_id = await create_session(async_client, headers, session_model=1)

    try:
        done = await _run_interview_round(
            async_client, headers, session_id, "开始面试", "第一题：说说 GIL。", monkeypatch
        )
        interview_id = int(done["interview_id"])

        uploaded = await upload_file(
            async_client, headers, "简历.txt", b"resume text", "text/plain"
        )
        response = await async_client.post(
            f"/interviews/{interview_id}/evaluations/from-audio",
            json={"resource_id": uploaded["resource_id"]},
            headers=headers,
        )
        assert response.status_code == 400
        assert "不支持的音频格式" in response.json()["message"]
    finally:
        await async_client.delete(f"/sessions/{session_id}?session_model=1", headers=headers)


@pytest.mark.anyio
async def test_audio_evaluation_rejects_other_users_resource(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人的录音：404（不能拿别人的录音给自己复盘）。"""
    owner_headers = await register_and_login("evalaudioowner")
    intruder_headers = await register_and_login("evalaudiointruder")
    session_id = await create_session(async_client, intruder_headers, session_model=1)

    try:
        uploaded = await upload_file(
            async_client, owner_headers, "owner.wav", b"RIFFowner", "audio/wav"
        )
        done = await _run_interview_round(
            async_client,
            intruder_headers,
            session_id,
            "开始面试",
            "第一题：说说 GIL。",
            monkeypatch,
        )
        interview_id = int(done["interview_id"])

        _stub_transcription(monkeypatch)
        response = await async_client.post(
            f"/interviews/{interview_id}/evaluations/from-audio",
            json={"resource_id": uploaded["resource_id"]},
            headers=intruder_headers,
        )
        assert response.status_code == 404
    finally:
        await async_client.delete(
            f"/sessions/{session_id}?session_model=1", headers=intruder_headers
        )
