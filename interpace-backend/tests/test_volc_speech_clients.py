"""T7.6 回归测试：ASR / TTS 客户端对着「本地假火山服务」跑通完整会话。

**为什么用假服务**：真实火山服务需要付费凭证，CI 与开发机都不该依赖它。
这个假服务自己按官方协议拼字节（**不复用我们自己的编码器**，否则就是自己验自己），
能验到的东西是真实的：

- ASR：首帧带鉴权头与序号、音频包序号递增、**末包是负序号**、能让服务端结束会话；
- TTS：事件顺序 StartConnection → StartSession → TaskRequest → FinishSession →
  FinishConnection 全部走通，音频分片与音素时间戳都能取回。

真实服务的端到端验证需要凭证，另行进行。
"""

import asyncio
import gzip
import json
import struct
import sys
from pathlib import Path

import pytest
import websockets

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.volc_speech.asr_client import AsrSession, _extract_text, is_definite_end
from app.services.volc_speech.tts_client import (
    TtsSession,
    TtsSubtitleWord,
    _parse_subtitle,
)

# 假服务端用到的协议常量（独立写一遍，避免和被测代码共用同一份定义）
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_CLIENT = 0b0010
FULL_SERVER_RESPONSE = 0b1001
AUDIO_ONLY_SERVER = 0b1011

WITH_EVENT = 0b0100
NO_SEQ = 0b0000
POS_SEQ = 0b0001


def _read_frames(data: bytes) -> dict:
    """把客户端发来的帧解成便于断言的结构（独立实现，不用被测代码）。"""
    header_size = (data[0] & 0x0F) * 4
    msg_type = data[1] >> 4
    flags = data[1] & 0x0F
    compression = data[2] & 0x0F
    offset = header_size
    info = {"type": msg_type, "flags": flags, "event": None, "sequence": None}

    if msg_type in (FULL_CLIENT_REQUEST, AUDIO_ONLY_CLIENT) and flags in (POS_SEQ, 0b0011):
        info["sequence"] = struct.unpack(">i", data[offset : offset + 4])[0]
        offset += 4
    if flags == WITH_EVENT:
        info["event"] = struct.unpack(">i", data[offset : offset + 4])[0]
        offset += 4
        if info["event"] not in (1, 2, 50, 51, 52):
            size = struct.unpack(">I", data[offset : offset + 4])[0]
            offset += 4 + size
    payload_size = struct.unpack(">I", data[offset : offset + 4])[0]
    offset += 4
    payload = data[offset : offset + payload_size]
    if compression == 1 and payload:
        payload = gzip.decompress(payload)
    info["payload"] = payload
    return info


def _server_frame(
    msg_type: int,
    payload: bytes,
    *,
    flags: int = NO_SEQ,
    event: int | None = None,
    session_id: str = "",
    sequence: int | None = None,
    compression: int = 0,
) -> bytes:
    """按官方协议拼一帧服务端消息（独立实现）。"""
    header = bytes([(0b0001 << 4) | 1, (msg_type << 4) | flags, (0b0001 << 4) | compression, 0])
    body = bytearray()
    if sequence is not None:
        body.extend(struct.pack(">i", sequence))
    if event is not None:
        body.extend(struct.pack(">i", event))
        if event not in (1, 2, 50, 51, 52):
            encoded = session_id.encode("utf-8")
            body.extend(struct.pack(">I", len(encoded)))
            body.extend(encoded)
    if compression == 1 and payload:
        payload = gzip.compress(payload)
    body.extend(struct.pack(">I", len(payload)))
    body.extend(payload)
    return header + bytes(body)


async def _free_port() -> int:
    """拿一个空闲端口。"""
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


# ---------------- ASR ----------------


def test_extract_text_prefers_last_utterance() -> None:
    """分句优先于累计文本：`result.text` 会带上上一句，直接用会重复。

    这是**真机验证时发现的**：14 秒示例音频返回两句话，第二个事件里
    `result.text` 是两句拼接，而 `utterances[-1].text` 只有第二句。
    """
    payload = {
        "result": {
            "text": "第一句话。第二句话。",
            "utterances": [
                {"text": "第一句话。", "definite": True},
                {"text": "第二句话。", "definite": True},
            ],
        }
    }
    assert _extract_text(payload) == "第二句话。"


def test_extract_text_falls_back_to_cumulative() -> None:
    """没有分句信息（未开 show_utterances）时退回累计文本。"""
    assert _extract_text({"result": {"text": "只有累计文本"}}) == "只有累计文本"
    assert _extract_text({}) == ""
    assert _extract_text({"result": {"utterances": []}}) == ""


def test_is_definite_end_requires_definite_flag() -> None:
    """判「一句话说完了」要看 definite，不能只看有没有 utterances。

    真机实测：快速推流时中间结果同样带 utterances，但 definite=False；
    只看「有 utterances」会把 3 句话判成 9 次最终结果。
    """
    assert is_definite_end({"result": {"utterances": [{"text": "第一句", "definite": False}]}}) is False
    assert is_definite_end({"result": {"utterances": [{"text": "第一句", "definite": True}]}}) is True
    assert is_definite_end({"result": {"utterances": [{"definite": True}, {"definite": False}]}}) is False
    assert is_definite_end({"result": {}}) is False
    assert is_definite_end({}) is False


@pytest.mark.anyio
async def test_asr_session_against_fake_server() -> None:
    """ASR：首帧带鉴权头、音频序号递增、末包负序号，最终拿到识别文本。"""
    port = await _free_port()
    seen: dict = {"sequences": [], "headers": None, "texts": []}

    async def handler(websocket) -> None:
        seen["headers"] = {k.lower(): v for k, v in websocket.request.headers.items()}
        # 1) 首帧：full client request，序号 1
        first = _read_frames(await websocket.recv())
        assert first["type"] == FULL_CLIENT_REQUEST
        assert first["sequence"] == 1
        payload = json.loads(first["payload"])
        assert payload["audio"]["rate"] == 16000
        seen["texts"].append(payload["request"]["model_name"])

        # 2) 音频帧：序号 2、3，末包是负序号
        while True:
            frame = _read_frames(await websocket.recv())
            seen["sequences"].append(frame["sequence"])
            if frame["sequence"] < 0:
                break

        # 3) 回识别结果：带序号的 full server response，最后一包置 bit1
        body = json.dumps(
            {"result": {"text": "我说的是 Python 后端开发"}}, ensure_ascii=False
        ).encode("utf-8")
        await websocket.send(
            _server_frame(
                FULL_SERVER_RESPONSE, body, flags=POS_SEQ, sequence=1, compression=1
            )
        )
        await websocket.send(
            _server_frame(
                FULL_SERVER_RESPONSE,
                body,
                flags=0b0011,  # bit0=带序号，bit1=末包
                sequence=-2,
                compression=1,
            )
        )

    async with websockets.serve(handler, "127.0.0.1", port):
        async with AsrSession(
            url=f"ws://127.0.0.1:{port}",
            api_key="fake-key",
            resource_id="volc.seedasr.sauc.duration",
        ) as session:
            transcripts = [
                item async for item in session.stream_audio([b"a" * 320, b"b" * 320])
            ]

    assert seen["headers"]["x-api-key"] == "fake-key"
    assert seen["headers"]["x-api-resource-id"] == "volc.seedasr.sauc.duration"
    assert "x-api-request-id" in seen["headers"]
    # 序号：2、3 是音频包，末包必须是负的
    assert seen["sequences"] == [2, 3, -4]
    assert any("Python 后端开发" in item.text for item in transcripts)


# ---------------- TTS ----------------


def test_parse_subtitle_keeps_words_for_lip_sync() -> None:
    """字级别时间戳挂在句子结束事件的 payload 里，必须原样保留（T7.9 口型要用）。"""
    result = _parse_subtitle(
        {
            "text": "你好",
            "words": [
                {"word": "你", "startTime": 0.0, "endTime": 0.12, "confidence": 0.91},
                {"word": "好", "startTime": 0.12, "endTime": 0.3, "confidence": 0.88},
            ],
            "phonemes": [{"text": "n", "startTime": 0.0, "endTime": 0.05}],
        }
    )
    assert result.text == "你好"
    assert len(result.words) == 2
    assert result.words[0]["word"] == "你"
    assert result.start_ms == 0
    assert result.end_ms == 120  # 秒 → 毫秒
    assert result.phonemes[0]["text"] == "n"


def test_parse_subtitle_tolerates_empty_arrays() -> None:
    """真机实测当前音色返回的就是空数组，不能因此报错。"""
    result = _parse_subtitle({"text": "你好", "words": [], "phonemes": []})
    assert result.text == "你好"
    assert result.words == []
    assert result.phonemes == []
    assert result.start_ms is None


@pytest.mark.anyio
async def test_tts_session_against_fake_server() -> None:
    """TTS：事件顺序全走通，音频分片与音素时间戳都能取回。"""
    port = await _free_port()
    seen: dict = {"events": [], "speaker": None, "subtitle_enabled": None}

    async def handler(websocket) -> None:
        # StartConnection → ConnectionStarted
        start = _read_frames(await websocket.recv())
        seen["events"].append(start["event"])
        await websocket.send(_server_frame(FULL_SERVER_RESPONSE, b"{}", flags=WITH_EVENT, event=50))

        # StartSession → SessionStarted：**音色等会话级参数必须带在这里**
        session_frame = _read_frames(await websocket.recv())
        seen["events"].append(session_frame["event"])
        session_params = json.loads(session_frame["payload"])["req_params"]
        seen["speaker"] = session_params["speaker"]
        seen["subtitle_enabled"] = session_params["enable_subtitle"]
        assert session_params["audio_params"]["format"] == "pcm"
        await websocket.send(
            _server_frame(FULL_SERVER_RESPONSE, b"{}", flags=WITH_EVENT, event=150)
        )

        # TaskRequest → 音频分片 + 字幕 + 句子结束（只带文本）
        task = _read_frames(await websocket.recv())
        seen["events"].append(task["event"])
        task_params = json.loads(task["payload"])["req_params"]
        seen["task_text"] = task_params["text"]
        assert "speaker" not in task_params, "音色不该出现在 TaskRequest（实测会报资源不匹配）"

        await websocket.send(
            # 官方示例：音频是 AudioOnlyServer + EventType=TTSResponse，并带 session_id
            _server_frame(
                AUDIO_ONLY_SERVER,
                b"\x01\x02\x03\x04",
                flags=WITH_EVENT,
                event=352,
                session_id="sess",
            )
        )
        subtitle = json.dumps(
            {
                "text": "你好",
                "words": [{"text": "你好", "start_time": 0.0, "end_time": 0.3}],
                "phonemes": [{"text": "n", "start_time": 0.0, "end_time": 0.1}],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await websocket.send(
            _server_frame(FULL_SERVER_RESPONSE, subtitle, flags=WITH_EVENT, event=364)
        )
        await websocket.send(
            _server_frame(FULL_SERVER_RESPONSE, b"{}", flags=WITH_EVENT, event=351)
        )

        # FinishSession → SessionFinished，然后 FinishConnection
        finish = _read_frames(await websocket.recv())
        seen["events"].append(finish["event"])
        await websocket.send(
            _server_frame(FULL_SERVER_RESPONSE, b"{}", flags=WITH_EVENT, event=152)
        )
        end = _read_frames(await websocket.recv())
        seen["events"].append(end["event"])

    async with websockets.serve(handler, "127.0.0.1", port):
        async with TtsSession(
            url=f"ws://127.0.0.1:{port}",
            api_key="fake-key",
            resource_id="seed-tts-2.0",
            speaker="zh_female_vv_uranus_bigtts",
        ) as session:
            audio: list[bytes] = []
            subtitles: list[TtsSubtitleWord] = []
            async for item in session.synthesize("你好"):
                if isinstance(item, bytes):
                    audio.append(item)
                else:
                    subtitles.append(item)

    # 事件顺序：1=StartConnection 100=StartSession 200=TaskRequest
    #          102=FinishSession 2=FinishConnection
    assert seen["events"] == [1, 100, 200, 102, 2]
    assert seen["speaker"] == "zh_female_vv_uranus_bigtts"
    assert seen["subtitle_enabled"] is True
    assert seen["task_text"] == "你好"
    assert audio == [b"\x01\x02\x03\x04"]
    assert len(subtitles) == 1
    assert subtitles[0].text == "你好"
    assert subtitles[0].phonemes[0]["text"] == "n"
    assert subtitles[0].end_ms == 300


@pytest.mark.anyio
async def test_tts_close_does_not_hang_when_server_silent() -> None:
    """建会话失败后服务端不再回事件时，close() 必须超时返回而不是永久挂住。

    **真机踩到的**：一次失败的合成让连接一直等到调用方被强制超时（180 秒）才结束。
    """
    import app.services.volc_speech.tts_client as tts_module

    port = await _free_port()

    async def handler(websocket) -> None:
        # 只回 ConnectionStarted；收到 StartSession 后保持沉默，模拟「建会话失败被吊住」
        _read_frames(await websocket.recv())
        await websocket.send(
            _server_frame(FULL_SERVER_RESPONSE, b"{}", flags=WITH_EVENT, event=50)
        )
        _read_frames(await websocket.recv())
        # 沉默够久让 0.5s 的超时先触发即可，不必真的挂 30 秒（会让用例变慢）
        await asyncio.sleep(2)

    original_timeout = tts_module.EVENT_TIMEOUT_SECONDS
    tts_module.EVENT_TIMEOUT_SECONDS = 0.5
    try:
        async with websockets.serve(handler, "127.0.0.1", port):
            session = TtsSession(
                url=f"ws://127.0.0.1:{port}",
                api_key="fake-key",
                resource_id="seed-tts-2.0",
                speaker="zh_male_liufei_uranus_bigtts",
            )
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(session.connect(), timeout=5)
            # 关键断言：连接失败之后 close() 也必须能返回
            await asyncio.wait_for(session.close(), timeout=5)
    finally:
        tts_module.EVENT_TIMEOUT_SECONDS = original_timeout
