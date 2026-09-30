"""火山引擎语音服务的二进制帧协议（ASR 与 TTS 共用）。

**协议来源**：火山引擎官方文档 + 官方 Python 参考实现（ASR 与 TTS 各一份依赖包）。
两边的帧格式属于同一个协议家族，所以这里合并成一份实现，避免两套编解码各自漂移。

帧结构（每帧固定以 4 字节头开始）::

    byte0: (protocol_version << 4) | header_size   # header_size 以 4 字节为单位，填 1 表示 4 字节头
    byte1: (message_type  << 4) | flags
    byte2: (serialization << 4) | compression
    byte3: 保留
    [扩展字段]  按 flags / message_type 决定顺序（见下方 _write_extensions / _read_extensions）
    payload_size (4 字节大端无符号) + payload

**两个必须记住的坑**（官方排查清单里的第 3、4 条）：

1. `payload_size` 填的是**压缩后**的字节数；填原始长度会让服务端读帧错位。
2. ASR 的**末包**：flags 必须是 `NEG_WITH_SEQUENCE`，且 `seq` 取负值；
   否则服务端会一直等下一个包，8 秒后报 `session unexpectedly finished`。
"""

from __future__ import annotations

import gzip
import json
import struct
from dataclasses import dataclass, field
from enum import IntEnum


class ProtocolVersion(IntEnum):
    """协议版本。"""

    V1 = 0b0001


class MessageType(IntEnum):
    """消息类型。ASR 与 TTS 共用同一套取值。"""

    FULL_CLIENT_REQUEST = 0b0001
    AUDIO_ONLY_CLIENT = 0b0010
    FULL_SERVER_RESPONSE = 0b1001
    AUDIO_ONLY_SERVER = 0b1011
    FRONT_END_RESULT_SERVER = 0b1100
    ERROR = 0b1111


class MessageFlag(IntEnum):
    """flags 位。bit0=带序号，bit1=末包，bit2=带 event。"""

    NO_SEQUENCE = 0b0000
    POSITIVE_SEQUENCE = 0b0001
    LAST_NO_SEQUENCE = 0b0010
    NEGATIVE_SEQUENCE = 0b0011
    WITH_EVENT = 0b0100


class SerializationType(IntEnum):
    """payload 序列化方式。"""

    RAW = 0b0000
    JSON = 0b0001


class CompressionType(IntEnum):
    """payload 压缩方式。"""

    NONE = 0b0000
    GZIP = 0b0001


class EventType(IntEnum):
    """事件类型（TTS 双向流式用；ASR 的响应里也会带 event 位）。"""

    NONE = 0
    # 连接级
    START_CONNECTION = 1
    FINISH_CONNECTION = 2
    CONNECTION_STARTED = 50
    CONNECTION_FAILED = 51
    CONNECTION_FINISHED = 52
    # 会话级
    START_SESSION = 100
    CANCEL_SESSION = 101
    FINISH_SESSION = 102
    SESSION_STARTED = 150
    SESSION_CANCELED = 151
    SESSION_FINISHED = 152
    SESSION_FAILED = 153
    USAGE_RESPONSE = 154
    # 任务请求
    TASK_REQUEST = 200
    # TTS 下行
    TTS_SENTENCE_START = 350
    TTS_SENTENCE_END = 351
    TTS_RESPONSE = 352
    TTS_ENDED = 359
    TTS_SUBTITLE = 364


# 连接级事件不带 session_id（协议规定，官方参考实现同样如此处理）。
_CONNECTION_SCOPED_EVENTS = {
    EventType.START_CONNECTION,
    EventType.FINISH_CONNECTION,
    EventType.CONNECTION_STARTED,
    EventType.CONNECTION_FAILED,
    EventType.CONNECTION_FINISHED,
}

# 这些消息类型在「带序号」标志下会多一个 4 字节序号字段。
_SEQUENCED_TYPES = {
    MessageType.FULL_CLIENT_REQUEST,
    MessageType.AUDIO_ONLY_CLIENT,
    MessageType.FULL_SERVER_RESPONSE,
    MessageType.AUDIO_ONLY_SERVER,
    MessageType.FRONT_END_RESULT_SERVER,
}


@dataclass
class Frame:
    """一帧消息。编码用 `to_bytes()`，解码用 `Frame.from_bytes()`。"""

    message_type: MessageType
    flags: MessageFlag = MessageFlag.NO_SEQUENCE
    serialization: SerializationType = SerializationType.JSON
    compression: CompressionType = CompressionType.NONE
    event: EventType | int = EventType.NONE
    session_id: str = ""
    connect_id: str = ""
    sequence: int = 0
    error_code: int = 0
    payload: bytes = b""

    # ---------- 编码 ----------

    def to_bytes(self) -> bytes:
        """编码成可发送的字节串。"""
        header = bytearray(
            [
                (ProtocolVersion.V1 << 4) | 1,  # header_size=1 → 4 字节头
                (self.message_type << 4) | self.flags,
                (self.serialization << 4) | self.compression,
                0x00,
            ]
        )
        body = bytearray()
        self._write_extensions(body)
        # payload 长度必须写「实际要发的字节数」（已压缩的按压缩后算）
        body.extend(struct.pack(">I", len(self.payload)))
        body.extend(self.payload)
        return bytes(header + body)

    def _write_extensions(self, buffer: bytearray) -> None:
        """按协议的字段顺序写扩展字段：序号 → error_code → event → session_id。"""
        if (
            self.message_type in _SEQUENCED_TYPES
            and self.flags in (MessageFlag.POSITIVE_SEQUENCE, MessageFlag.NEGATIVE_SEQUENCE)
        ):
            buffer.extend(struct.pack(">i", self.sequence))

        # 错误帧在 payload 之前多一个 error_code 字段（与解码顺序严格对应）
        if self.message_type == MessageType.ERROR:
            buffer.extend(struct.pack(">I", self.error_code))

        if self.flags == MessageFlag.WITH_EVENT:
            buffer.extend(struct.pack(">i", int(self.event)))
            if self.event not in _CONNECTION_SCOPED_EVENTS:
                encoded = self.session_id.encode("utf-8")
                buffer.extend(struct.pack(">I", len(encoded)))
                buffer.extend(encoded)

    # ---------- 解码 ----------

    @classmethod
    def from_bytes(cls, data: bytes) -> "Frame":
        """从字节串解出一帧；格式不认识时抛 `ValueError`。"""
        if len(data) < 4:
            raise ValueError(f"帧长度不足，至少需要 4 字节，实际 {len(data)}")

        header_size = (data[0] & 0x0F) * 4
        raw_type = data[1] >> 4
        raw_flags = data[1] & 0x0F
        serialization = data[2] >> 4
        compression = data[2] & 0x0F

        try:
            message_type = MessageType(raw_type)
        except ValueError as exc:
            raise ValueError(f"未知消息类型: {raw_type}") from exc
        flags = MessageFlag(raw_flags) if raw_flags in set(MessageFlag) else raw_flags

        frame = cls(
            message_type=message_type,
            flags=flags,
            serialization=SerializationType(serialization),
            compression=CompressionType(compression),
        )
        frame._read_extensions(data[header_size:])
        return frame

    def _read_extensions(self, body: bytes) -> None:
        """按协议的字段顺序读扩展字段，剩余部分即 payload。"""
        offset = 0

        def take(size: int) -> bytes:
            nonlocal offset
            chunk = body[offset : offset + size]
            offset += size
            return chunk

        if (
            self.message_type in _SEQUENCED_TYPES
            and self.flags in (MessageFlag.POSITIVE_SEQUENCE, MessageFlag.NEGATIVE_SEQUENCE)
        ):
            frame_seq = take(4)
            if frame_seq:
                self.sequence = struct.unpack(">i", frame_seq)[0]

        if self.message_type == MessageType.ERROR:
            error_code = take(4)
            if error_code:
                self.error_code = struct.unpack(">I", error_code)[0]

        if self.flags == MessageFlag.WITH_EVENT:
            raw_event = take(4)
            if raw_event:
                event_value = struct.unpack(">i", raw_event)[0]
                try:
                    self.event = EventType(event_value)
                except ValueError:
                    # 未定义事件值原样保留，交给调用方判断，别在这里丢弃信息
                    self.event = event_value
            if self.event not in _CONNECTION_SCOPED_EVENTS:
                size_bytes = take(4)
                if size_bytes:
                    size = struct.unpack(">I", size_bytes)[0]
                    if size:
                        self.session_id = take(size).decode("utf-8", "ignore")
            if self.event in {
                EventType.CONNECTION_STARTED,
                EventType.CONNECTION_FAILED,
                EventType.CONNECTION_FINISHED,
            }:
                size_bytes = take(4)
                if size_bytes:
                    size = struct.unpack(">I", size_bytes)[0]
                    if size:
                        self.connect_id = take(size).decode("utf-8", "ignore")

        size_bytes = take(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size:
                self.payload = take(size)

    # ---------- 便捷属性 ----------

    @property
    def is_last_package(self) -> bool:
        """是否是末包（flags 的 bit1）。"""
        return bool(int(self.flags) & 0b0010)

    def json_payload(self) -> dict:
        """把 payload 当 JSON 解出来（需要时先解压）。"""
        data = gzip.decompress(self.payload) if self.compression == CompressionType.GZIP else self.payload
        if not data:
            return {}
        return json.loads(data.decode("utf-8"))


def encode_payload(data: bytes, compression: CompressionType) -> bytes:
    """按指定压缩方式处理 payload。"""
    if compression == CompressionType.GZIP:
        return gzip.compress(data)
    return data


def encode_json_payload(data: dict, compression: CompressionType) -> bytes:
    """把字典编码成（可选压缩的）payload。"""
    return encode_payload(json.dumps(data, ensure_ascii=False).encode("utf-8"), compression)


@dataclass
class FrameBuilder:
    """按「先建请求帧、再发音频」的流程构建帧，集中管理序号自增。

    ASR 的序号规则（官方要求）：full request 占 seq=1，音频包从 2 起逐包 +1；
    末包序号取**负值**。
    """

    session_id: str = ""
    compression: CompressionType = CompressionType.GZIP
    _next_sequence: int = field(default=1, init=False)

    def next_sequence(self) -> int:
        """取下一个序号并自增。"""
        current = self._next_sequence
        self._next_sequence += 1
        return current

    def full_request(self, payload: bytes, sequence: int | None = None) -> Frame:
        """ASR 首个请求帧（带序号）。`payload` 需要调用方**已经编码好**（见 `encode_json_payload`）。"""
        return Frame(
            message_type=MessageType.FULL_CLIENT_REQUEST,
            flags=MessageFlag.POSITIVE_SEQUENCE,
            serialization=SerializationType.JSON,
            compression=self.compression,
            sequence=self.next_sequence() if sequence is None else sequence,
            payload=payload,
        )

    def audio_packet(self, chunk: bytes, *, is_last: bool, sequence: int) -> Frame:
        """ASR 音频帧；末包用负序号 + `NEG_WITH_SEQUENCE`。

        `chunk` 传**原始音频字节**即可，压缩在这里做——帧头的 compression 位与实际
        发送的字节必须一致，否则服务端会拿压缩标志去解压原始 PCM，直接报帧解析错误。
        """
        payload = encode_payload(chunk, self.compression)
        if is_last:
            return Frame(
                message_type=MessageType.AUDIO_ONLY_CLIENT,
                flags=MessageFlag.NEGATIVE_SEQUENCE,
                serialization=SerializationType.RAW,
                compression=self.compression,
                sequence=-abs(sequence),
                payload=payload,
            )
        return Frame(
            message_type=MessageType.AUDIO_ONLY_CLIENT,
            flags=MessageFlag.POSITIVE_SEQUENCE,
            serialization=SerializationType.RAW,
            compression=self.compression,
            sequence=abs(sequence),
            payload=payload,
        )

    def event_frame(self, event: EventType, payload: bytes = b"{}") -> Frame:
        """TTS 侧的连接 / 会话事件帧。"""
        return Frame(
            message_type=MessageType.FULL_CLIENT_REQUEST,
            flags=MessageFlag.WITH_EVENT,
            serialization=SerializationType.JSON,
            compression=self.compression,
            event=event,
            session_id=self.session_id,
            payload=payload,
        )
