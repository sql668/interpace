"""T7.6 回归测试：火山引擎语音帧协议的编解码。

纯函数测试，不连网络。重点守住官方排查清单里最容易踩的两条：
① `payload_size` 必须写压缩后的长度；② 末包必须是负序号 + NEG_WITH_SEQUENCE。
"""

import gzip
import struct
import sys
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.volc_speech.protocol import (
    CompressionType,
    EventType,
    Frame,
    FrameBuilder,
    MessageFlag,
    MessageType,
    SerializationType,
    encode_json_payload,
)


def test_asr_full_request_round_trip() -> None:
    """ASR 首帧：序号、类型、flags、payload 都要能原样解回来。"""
    payload = encode_json_payload({"user": {"uid": "x"}}, CompressionType.GZIP)
    frame = FrameBuilder(compression=CompressionType.GZIP).full_request(payload)

    decoded = Frame.from_bytes(frame.to_bytes())
    assert decoded.message_type == MessageType.FULL_CLIENT_REQUEST
    assert decoded.flags == MessageFlag.POSITIVE_SEQUENCE
    assert decoded.sequence == 1
    assert decoded.json_payload() == {"user": {"uid": "x"}}


def test_payload_size_is_compressed_length() -> None:
    """帧里写的 payload 长度必须是 gzip 之后的长度（写原始长度会导致服务端读帧错位）。"""
    raw = ("重复内容" * 200).encode("utf-8")
    compressed = gzip.compress(raw)
    frame = FrameBuilder(compression=CompressionType.GZIP).full_request(
        encode_json_payload({"text": "x" * 500}, CompressionType.GZIP)
    )
    data = frame.to_bytes()

    # 4 字节头 + 4 字节序号 = 8，随后 4 字节是 payload 长度
    on_wire_size = struct.unpack(">I", data[8:12])[0]
    assert on_wire_size == len(frame.payload)
    assert on_wire_size < len(struct.pack(">I", len(raw)) + raw)
    assert len(compressed) < len(raw)  # 确认测试用的数据确实是「压缩后更短」


def test_last_audio_packet_uses_negative_sequence() -> None:
    """末包：NEG_WITH_SEQUENCE + 负序号；非末包用正序号。"""
    builder = FrameBuilder(compression=CompressionType.GZIP)
    builder.full_request(encode_json_payload({}, CompressionType.GZIP))

    normal = builder.audio_packet(b"audio-1", is_last=False, sequence=builder.next_sequence())
    decoded_normal = Frame.from_bytes(normal.to_bytes())
    assert decoded_normal.message_type == MessageType.AUDIO_ONLY_CLIENT
    assert decoded_normal.flags == MessageFlag.POSITIVE_SEQUENCE
    assert decoded_normal.sequence == 2
    assert decoded_normal.is_last_package is False

    last = builder.audio_packet(b"", is_last=True, sequence=builder.next_sequence())
    decoded_last = Frame.from_bytes(last.to_bytes())
    assert decoded_last.flags == MessageFlag.NEGATIVE_SEQUENCE
    assert decoded_last.sequence == -3
    assert decoded_last.is_last_package is True


def test_tts_event_frame_round_trip() -> None:
    """TTS 事件帧：event 与 session_id 要能解回来，payload 是明文 JSON。"""
    builder = FrameBuilder(session_id="sess-1", compression=CompressionType.NONE)
    frame = builder.event_frame(EventType.START_SESSION, b'{"namespace":"BidirectionalTTS"}')

    decoded = Frame.from_bytes(frame.to_bytes())
    assert decoded.message_type == MessageType.FULL_CLIENT_REQUEST
    assert decoded.flags == MessageFlag.WITH_EVENT
    assert decoded.event == EventType.START_SESSION
    assert decoded.session_id == "sess-1"
    assert decoded.json_payload() == {"namespace": "BidirectionalTTS"}


def test_audio_packet_payload_is_compressed() -> None:
    """音频包：帧头声明 gzip，实际字节就必须是 gzip 过的（声明与内容不一致会直接报帧错误）。"""
    builder = FrameBuilder(compression=CompressionType.GZIP)
    chunk = b"\x00\x01" * 500  # 一段「PCM」
    frame = builder.audio_packet(chunk, is_last=False, sequence=2)

    assert frame.payload != chunk
    assert gzip.decompress(frame.payload) == chunk
    decoded = Frame.from_bytes(frame.to_bytes())
    # 解出来后 payload 仍是压缩态（压缩由调用方或本方法负责），json_payload 会自动解压
    assert decoded.compression == CompressionType.GZIP


def test_connection_scoped_event_has_no_session_id() -> None:
    """连接级事件（StartConnection）按协议不带 session_id 字段。"""
    builder = FrameBuilder(session_id="sess-1", compression=CompressionType.NONE)
    decoded = Frame.from_bytes(builder.event_frame(EventType.START_CONNECTION).to_bytes())
    assert decoded.event == EventType.START_CONNECTION
    assert decoded.session_id == ""
    assert decoded.json_payload() == {}


def test_server_error_frame_is_parsed() -> None:
    """服务端错误帧：能拿到 error_code 而不是抛异常。"""
    payload = b"bad request"
    frame = Frame(
        message_type=MessageType.ERROR,
        flags=MessageFlag.NO_SEQUENCE,
        serialization=SerializationType.JSON,
        compression=CompressionType.NONE,
        error_code=40000001,
        payload=payload,
    )
    decoded = Frame.from_bytes(frame.to_bytes())
    assert decoded.message_type == MessageType.ERROR
    assert decoded.error_code == 40000001
    assert decoded.payload == payload


def test_unknown_event_value_is_kept() -> None:
    """协议新增了事件值时不要丢信息：解不出枚举就原样保留数字。"""
    frame = Frame(
        message_type=MessageType.FULL_CLIENT_REQUEST,
        flags=MessageFlag.WITH_EVENT,
        compression=CompressionType.NONE,
        event=9999,
        session_id="s2",
    )
    decoded = Frame.from_bytes(frame.to_bytes())
    assert decoded.event == 9999
    assert decoded.session_id == "s2"


def test_truncated_frame_raises() -> None:
    """长度不足的帧要明确报错，而不是静默解析出错误结果。"""
    with pytest.raises(ValueError):
        Frame.from_bytes(b"\x11\x11")
