"""T7.6 回归测试：语音面试 WebSocket 端点的编排。

分工说明（避免自己验自己）：
- **协议与两个客户端**由 `test_volc_protocol.py` / `test_volc_speech_clients.py` 对着
  「按官方协议拼字节的假服务端」验证；
- **本文件**验证端点这一层的编排：鉴权与归属、控制消息、ASR→Agent→TTS 的串接、
  以及语音面试和文字面试**落进同一套数据**（消息 + 面试记录一问一答）。
  所以这里把 ASR / TTS 客户端换成轻量假实现，大模型用桩。
"""

import json
import sys
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import prompt_layer
from app.db.database import SessionLocal
from app.db.models import ChatMessage, Interview
from app.services import speech_stream_service, speech_turn_service
from app.services.volc_speech.tts_client import TtsSubtitleWord

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]

FAKE_TRANSCRIPT = "GIL 是全局解释器锁，同一时刻只有一个线程执行字节码"
FAKE_REPLY = "答得不错。那我接着问，多进程和 GIL 是什么关系？"

# 业务路径统一带 /api/v1（T10.1）。这个文件用的是 starlette 的 TestClient，
# 它的 base_url 合并只对 HTTP 生效、WebSocket 需要写完整路径，所以统一显式拼前缀。
API = "/api/v1"


class FakeAsrSession:
    """假 ASR：把收到的音频字节攒起来，收尾时吐一条最终识别结果。"""

    instances: list["FakeAsrSession"] = []

    def __init__(self, **_kwargs) -> None:
        self.chunks: list[bytes] = []
        self.closed = False
        # 真实 ASR 只有在收到音频之后才可能给出识别结果；假实现也要遵守这个时序，
        # 否则它会在音频到达之前就结束这一趟，测不出「音频是否真的转发了」。
        self._got_audio = asyncio.Event()
        FakeAsrSession.instances.append(self)

    async def connect(self) -> None:
        return None

    async def send_audio(self, chunk: bytes, *, is_last: bool = False) -> None:
        if chunk:
            self.chunks.append(chunk)
            self._got_audio.set()

    async def finish(self) -> None:
        return None

    async def close(self) -> None:
        self.closed = True

    async def responses(self) -> AsyncIterator:
        # 模拟服务端 VAD：收到音频后先给一个中间结果，再给最终分句
        from app.services.volc_speech.asr_client import AsrTranscript

        await self._got_audio.wait()
        yield AsrTranscript(text="GIL 是全局", is_final=False)
        yield AsrTranscript(text=FAKE_TRANSCRIPT, is_final=True)


class FakeTtsSession:
    """假 TTS：产出两段音频 + 一条带音素时间戳的字幕。"""

    instances: list["FakeTtsSession"] = []

    def __init__(self, **_kwargs) -> None:
        FakeTtsSession.instances.append(self)

    async def __aenter__(self) -> "FakeTtsSession":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def synthesize(self, _text: str) -> AsyncIterator:
        yield b"\x00\x01\x02\x03"
        yield TtsSubtitleWord(
            text="答得不错",
            start_ms=0,
            end_ms=300,
            phonemes=[{"text": "d", "start_time": 0.0, "end_time": 0.1}],
        )
        yield b"\x04\x05\x06\x07"


@pytest.fixture
def ws_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """把 ASR / TTS / 大模型都换掉，返回可建 WebSocket 的测试客户端。"""
    FakeAsrSession.instances.clear()
    FakeTtsSession.instances.clear()
    monkeypatch.setattr(speech_stream_service, "AsrSession", FakeAsrSession)
    monkeypatch.setattr(speech_stream_service, "TtsSession", FakeTtsSession)
    # 大模型：走文字链路同一套编排图，这里换成桩
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content=FAKE_REPLY)])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        speech_turn_service, "build_personalized_prompt", lambda **kwargs: None
    )

    from app.main import app

    with TestClient(app) as client:
        yield client


def _register_and_login(client: TestClient, prefix: str) -> str:
    """注册并登录，把 access token 写进 client 的头部（供后续 HTTP 调用使用）。"""
    import uuid

    username = f"{prefix[:10]}_{uuid.uuid4().hex[:8]}"
    password = "smoke123456"
    assert client.post(
        f"{API}/auth/register", json={"username": username, "password": password}
    ).status_code == 201
    login = client.post(
        f"{API}/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return token


def _create_interview_session(client: TestClient) -> int:
    created = client.post(f"{API}/sessions", json={"title": "语音面试", "session_model": 1})
    assert created.status_code == 200, created.text
    return int(created.json()["session"]["id"])


def test_speech_stream_runs_full_turn(ws_client: TestClient) -> None:
    """推音频 → 出识别结果 → 出面试官回复 → 出 TTS 音频与字幕 → 数据落库。"""
    token = _register_and_login(ws_client, "speech")
    session_id = _create_interview_session(ws_client)

    with ws_client.websocket_connect(
        f"{API}/sessions/{session_id}/speech/stream?session_model=1&token={token}"
    ) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["asr_sample_rate"] == 16000

        ws.send_json({"type": "start_utterance"})
        ws.send_bytes(b"\x00" * 640)
        ws.send_json({"type": "end_utterance"})

        events: list[dict] = []
        audio: list[bytes] = []
        # 收到 tts_end 代表这一轮结束
        while True:
            message = ws.receive()
            if message.get("bytes") is not None:
                audio.append(message["bytes"])
                continue
            payload = json.loads(message["text"])
            events.append(payload)
            if payload["type"] == "tts_end":
                break

    kinds = [item["type"] for item in events]
    assert "asr_partial" in kinds
    assert "asr_final" in kinds
    assert "reply" in kinds
    assert "tts_start" in kinds
    assert "tts_subtitle" in kinds

    final = next(item for item in events if item["type"] == "asr_final")
    assert final["text"] == FAKE_TRANSCRIPT
    reply = next(item for item in events if item["type"] == "reply")
    assert reply["text"] == FAKE_REPLY
    subtitle = next(item for item in events if item["type"] == "tts_subtitle")
    assert subtitle["end_ms"] == 300
    assert subtitle["phonemes"][0]["text"] == "d"
    # 两段音频都推给了前端
    assert audio == [b"\x00\x01\x02\x03", b"\x04\x05\x06\x07"]

    # 音频确实转发给了 ASR
    assert FakeAsrSession.instances
    assert FakeAsrSession.instances[0].chunks == [b"\x00" * 640]
    assert FakeAsrSession.instances[0].closed is True

    # 落库：一条消息 + 一条面试记录的一问一答
    db = SessionLocal()
    try:
        message = db.get(ChatMessage, int(reply["message_id"]))
        assert message is not None
        assert message.request_text == FAKE_TRANSCRIPT
        assert message.response_text == FAKE_REPLY
        assert message.select_model == 4  # 与文字链路一致

        interview = db.get(Interview, int(reply["interview_id"]))
        assert interview is not None
        assert interview.session_id == session_id
        assert interview.qa_object[0]["question"] == FAKE_REPLY
        assert interview.qa_object[0]["answer"] == ""
        assert interview.status == 0
    finally:
        db.close()

    ws_client.delete(f"{API}/sessions/{session_id}?session_model=1")


def test_speech_stream_requires_valid_token(ws_client: TestClient) -> None:
    """无效 token 必须在 accept 之前就被拒掉（不能给未授权连接开门）。"""
    token = _register_and_login(ws_client, "speechauth")
    session_id = _create_interview_session(ws_client)

    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect(
            f"{API}/sessions/{session_id}/speech/stream?session_model=1&token=bad-token"
        ):
            pass

    ws_client.delete(f"{API}/sessions/{session_id}?session_model=1")


def test_speech_stream_accepts_typed_text(ws_client: TestClient) -> None:
    """直接给文字（跳过 ASR）也要能跑通一轮——用于联调与降级。"""
    token = _register_and_login(ws_client, "speechtext")
    session_id = _create_interview_session(ws_client)

    with ws_client.websocket_connect(
        f"{API}/sessions/{session_id}/speech/stream?session_model=1&token={token}"
    ) as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "text", "text": "我用过 Redis 做缓存"})

        reply = None
        while True:
            message = ws.receive()
            if message.get("bytes") is not None:
                continue
            payload = json.loads(message["text"])
            if payload["type"] == "reply":
                reply = payload
            if payload["type"] == "tts_end":
                break

    assert reply is not None
    assert reply["text"] == FAKE_REPLY
    ws_client.delete(f"{API}/sessions/{session_id}?session_model=1")


def test_speech_stream_refused_when_demo_disables_voice(
    ws_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """演示环境关掉语音面试后，后端要拒绝连接（T12.4）。

    前端不显示按钮只是界面。绕过界面直接连 WebSocket 一样能烧 ASR/TTS——
    语音是双计费里最贵的一条链路，所以这一层必须在**服务端**判。
    """
    import app.services.usage_quota_service as service_module
    from app.core.quota_config import DemoLimits
    from app.services.usage_quota_service import UsageQuotaService

    class _FakeSettings:
        app_env = "demo"

    monkeypatch.setattr(service_module, "settings", _FakeSettings())
    monkeypatch.setattr(
        UsageQuotaService,
        "limits",
        staticmethod(
            lambda: DemoLimits.from_dict(
                {
                    "enabled": True,
                    "environments": ["demo"],
                    "cost_reduction": {"disable_voice_interview": True},
                }
            )
        ),
    )

    # 注意：这里用的是**合法 token 与合法会话**——拒绝的唯一原因是环境开关，
    # 不是鉴权。否则这条用例就测不出"开关生效"了。
    token = _register_and_login(ws_client, "speechoff")
    session_id = _create_interview_session(ws_client)

    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect(
            f"{API}/sessions/{session_id}/speech/stream?session_model=1&token={token}"
        ):
            pass

    ws_client.delete(f"{API}/sessions/{session_id}?session_model=1")


def test_speech_stream_ends_at_demo_time_limit(
    ws_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """演示环境单场面试 3 分钟：到点由**服务端**主动结束，而不是等用户挂断（T12.4）。

    这是语音链路和文字链路的关键差别：文字可以"下一轮不回答"，语音必须自己掐断——
    否则用户只要不挂断，麦克风就一直开着、TTS 就一直烧着。
    """
    import time

    import app.services.usage_quota_service as service_module
    from app.core.quota_config import DemoLimits
    from app.services.usage_quota_service import UsageQuotaService

    class _FakeSettings:
        app_env = "demo"

    monkeypatch.setattr(service_module, "settings", _FakeSettings())
    monkeypatch.setattr(
        UsageQuotaService,
        "limits",
        staticmethod(
            lambda: DemoLimits.from_dict(
                {
                    "enabled": True,
                    "environments": ["demo"],
                    "interview": {"max_minutes": 3},
                    "notice": {"interview_timeout_message": "已达演示环境 {minutes} 分钟上限"},
                }
            )
        ),
    )

    token = _register_and_login(ws_client, "speechcap")
    session_id = _create_interview_session(ws_client)

    with ws_client.websocket_connect(
        f"{API}/sessions/{session_id}/speech/stream?session_model=1&token={token}"
    ) as ws:
        assert ws.receive_json()["type"] == "ready"

        # 第一轮：这一轮会创建面试记录
        ws.send_json({"type": "text", "text": "我用过 Redis 做缓存"})
        while True:
            message = ws.receive()
            if message.get("bytes") is not None:
                continue
            if json.loads(message["text"])["type"] == "tts_end":
                break

        # 把这场面试的创建时间往前推 5 分钟，模拟"已经聊超时了"
        db = SessionLocal()
        try:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .order_by(Interview.id.desc())
                .first()
            )
            assert interview is not None, "第一轮应该建立面试记录"
            interview_id = interview.id
            interview.created_at = int(time.time()) - 300
            db.add(interview)
            db.commit()
        finally:
            db.close()

        # 第二轮：这轮跑完后服务端应发现已超时，主动结束并发 interview_timeout
        ws.send_json({"type": "text", "text": "再问我一题"})
        timeout_event = None
        for _ in range(200):  # 上界保护：避免用例卡死
            message = ws.receive()
            if message.get("bytes") is not None:
                continue
            payload = json.loads(message["text"])
            if payload["type"] == "interview_timeout":
                timeout_event = payload
                break
        assert timeout_event is not None, "到点后必须下发 interview_timeout"
        assert timeout_event["max_minutes"] == 3
        assert "3 分钟上限" in timeout_event["message"]
        assert timeout_event["interview_id"] == interview_id

    # 面试记录要被结束掉（时长冻结），否则前端会一直显示"进行中"
    db = SessionLocal()
    try:
        interview = db.get(Interview, interview_id)
        assert interview.status == 1
        assert interview.interview_duration >= 300
    finally:
        db.close()

    ws_client.delete(f"{API}/sessions/{session_id}?session_model=1")
