"""火山引擎双向流式语音合成（TTS）客户端。

对应 T7.6。会话流程（官方文档的事件序列）：

    StartConnection → 等 ConnectionStarted
    StartSession    → 等 SessionStarted
    TaskRequest（带要合成的文本）→ 收 TTSSentenceStart / TTSResponse(音频) /
                                   TTSSubtitle(字幕) / TTSSentenceEnd
    FinishSession   → 等 SessionFinished
    FinishConnection

`enable_subtitle=True` 时服务端会额外回 `TTSSubtitle`，里面的 `words`（字级别）与
`phonemes`（音素级）时间戳就是 T7.9 做口型同步的数据来源——**不要把这两个字段丢掉**，
否则以后要重新合成一次才能拿到。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import websockets

from app.core.logging_config import main_logger
from app.services.volc_speech.protocol import (
    CompressionType,
    EventType,
    Frame,
    FrameBuilder,
    MessageType,
    encode_json_payload,
)

# 事件等待超时（秒）：卡住时宁可报错也不要无限等
EVENT_TIMEOUT_SECONDS = 10.0


@dataclass
class TtsAudioChunk:
    """一段合成音频。"""

    data: bytes
    sequence: int = 0
    is_sentence_end: bool = False


@dataclass
class TtsSubtitleWord:
    """字 / 音素级时间戳，口型同步的输入。

    `words` 是官方返回的字级别时间戳**原始数组**（每项形如
    `{"word": "你", "startTime": 0.0, "endTime": 0.12, "confidence": 0.9}`，
    时间单位是**秒**）。这里原样保留，避免我们自己的字段设计把厂商信息吃掉。

    ⚠️ 真机实测（2026-09-29，音色 `zh_male_liufei_uranus_bigtts` / `seed-tts-2.0`）：
    即使 `enable_subtitle=True`，返回的 `words` 与 `phonemes` **都是空数组**。
    也就是说**当前拿不到时间戳**，T7.9 的口型同步要按「音量分析兜底」那条路走。
    字段先保留好，等换成支持字幕的音色时可以直接用。
    """

    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    words: list[dict] = field(default_factory=list)
    phonemes: list[dict] = field(default_factory=list)


def build_session_payload(
    *,
    speaker: str,
    sample_rate: int = 24000,
    audio_format: str = "pcm",
    enable_subtitle: bool = True,
) -> dict:
    """构造 **StartSession** 的请求体（会话级参数）。

    ⚠️ **音色必须放在这里。** 这是 2026-09-29 连真服务试出来的坑：

    - `speaker` 放在 `TaskRequest` 里 → 服务端报
      `resource ID is mismatched with speaker related resource`
      （看着像资源包买错了，其实是参数放错了层级）；
    - `speaker` 放在 `StartSession` 的 `req_params` 里 → 正常出音频；
    - `TaskRequest` 只需要带 `req_params.text`。

    文档的示例代码没有把这个层级讲清楚，改这里之前请先看这条注释。

    音频格式用 `pcm`：官方明确「流式场景推荐 pcm，不建议 wav」，
    而且前端用 Web Audio 播放时 pcm 可以直接喂给 AudioBuffer。
    """
    return {
        "event": int(EventType.START_SESSION),
        "namespace": "BidirectionalTTS",
        "req_params": {
            "speaker": speaker,
            "audio_params": {"format": audio_format, "sample_rate": sample_rate},
            # 打开字幕服务才会回字级别时间戳；音素时间戳随后一并给到
            "enable_subtitle": enable_subtitle,
        },
    }


def build_task_payload(text: str) -> dict:
    """构造 **TaskRequest** 的请求体：只带要合成的文本。"""
    return {"req_params": {"text": text}}


class TtsSession:
    """一次 TTS 会话。作为异步上下文管理器使用。"""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        resource_id: str,
        speaker: str,
        sample_rate: int = 24000,
        audio_format: str = "pcm",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.resource_id = resource_id
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.session_id = uuid.uuid4().hex
        self._connection = None
        # TTS 侧官方参考实现默认不压缩 payload
        self._builder = FrameBuilder(
            session_id=self.session_id, compression=CompressionType.NONE
        )
        self._connected = False

    async def __aenter__(self) -> "TtsSession":
        await self.connect()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def connect(self) -> None:
        """建连并握手到 SessionStarted。"""
        if not self.api_key:
            raise RuntimeError("未配置 VOLC_API_KEY，无法使用语音服务")

        self._connection = await websockets.connect(
            self.url,
            additional_headers={
                "X-Api-Key": self.api_key,
                "X-Api-Resource-Id": self.resource_id,
            },
            max_size=None,
        )
        await self._send_event(EventType.START_CONNECTION)
        await self._wait_event(EventType.CONNECTION_STARTED)

        # 会话级参数（音色、音频格式、字幕开关）必须在 StartSession 里带上，
        # 不能留到 TaskRequest——原因见 build_session_payload 的注释。
        payload = encode_json_payload(
            build_session_payload(
                speaker=self.speaker,
                sample_rate=self.sample_rate,
                audio_format=self.audio_format,
            ),
            CompressionType.NONE,
        )
        await self._send_event(EventType.START_SESSION, payload)
        await self._wait_event(EventType.SESSION_STARTED)
        self._connected = True
        self._finish_sent = False
        main_logger.info(f"[TTS] 会话已建立 session_id={self.session_id}")

    async def synthesize(self, text: str) -> AsyncIterator[bytes | TtsSubtitleWord]:
        """合成一段文本：产出音频分片（bytes）与字幕时间戳（TtsSubtitleWord）。"""
        if not self._connected:
            raise RuntimeError("TTS 会话尚未建立")

        payload = encode_json_payload(
            build_task_payload(text),
            CompressionType.NONE,
        )
        await self._send_event(EventType.TASK_REQUEST, payload)
        # **必须主动告诉服务端「文本给完了」**：这是「文本流式输入」的接口，
        # 不发明文结束标记，服务端会一直等后续文本——音频会照流，但**永远不补
        # `TTSSentenceEnd` 与 `SessionFinished`**，客户端就只能干等到超时。
        # 实测：不发这一帧时音频已收满 134KB 但句子结束事件始终不来。
        await self._send_event(EventType.FINISH_SESSION)
        self._finish_sent = True

        while True:
            frame = await self._receive()
            if frame.message_type == MessageType.ERROR:
                raise RuntimeError(
                    f"TTS 服务端返回错误 code={frame.error_code} "
                    f"payload={frame.payload.decode('utf-8', 'ignore')}"
                )
            event = frame.event
            # 音频按「事件是 TTSResponse」判定，而不是按消息类型：
            # 官方示例里音频是 `MsgType=AudioOnlyServer` + `EventType=TTSResponse`，
            # 但也见过 FullServerResponse 承载音频的情况，两者都算音频。
            if event == EventType.TTS_RESPONSE:
                if frame.payload:
                    yield frame.payload
                continue
            if event == EventType.TTS_SUBTITLE:
                # 字幕（含音素时间戳）：给 T7.9 存着，别丢
                yield _parse_subtitle(frame.json_payload())
                continue
            if event == EventType.TTS_SENTENCE_END:
                # 一句话结束。**字/音素时间戳就挂在这个事件的 payload 里**
                # （`{"text": ..., "words": [...], "phonemes": [...]}`），
                # 不是单独一个 TtsSubtitle 事件——真机实测确认，别只等 TTS_SUBTITLE。
                # 当前音色下这两个数组是空的（拿不到时间戳），但只要有就往下传，
                # 不能丢——T7.9 的口型同步要的就是它。
                subtitle = _parse_subtitle(frame.json_payload())
                if subtitle.words or subtitle.phonemes:
                    yield subtitle
                continue
            if event in (EventType.SESSION_FINISHED, EventType.SESSION_FAILED):
                return

    async def close(self) -> None:
        """正常收尾：FinishSession → FinishConnection → 关闭。"""
        if self._connection is None:
            return
        try:
            # 已经发过 FinishSession 就不再重复发（重复发可能被当成新的一轮）
            if self._connected and not self._finish_sent:
                await self._send_event(EventType.FINISH_SESSION)
                self._finish_sent = True
                self._connected = False
            await self._send_event(EventType.FINISH_CONNECTION)
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"[TTS] 收尾时出错（忽略）: {exc!r}")
        finally:
            await self._connection.close()
            self._connection = None

    # ---------- 内部工具 ----------

    async def _send_event(self, event: EventType, payload: bytes = b"{}") -> None:
        if self._connection is None:
            raise RuntimeError("TTS 会话尚未建立")
        await self._connection.send(self._builder.event_frame(event, payload).to_bytes())

    async def _receive(self) -> Frame:
        if self._connection is None:
            raise RuntimeError("TTS 会话尚未建立")
        # 必须带超时：服务端在建会话失败后不会再回任何事件，
        # 而收尾流程（close → FinishSession → 等 SessionFinished）如果裸等就会永久挂住。
        # 实测踩过：一次失败的合成让连接卡到调用方超时 180 秒才被强杀。
        raw = await asyncio.wait_for(
            self._connection.recv(), timeout=EVENT_TIMEOUT_SECONDS
        )
        if not isinstance(raw, bytes):
            raise RuntimeError(f"TTS 收到非二进制帧: {raw!r}")
        return Frame.from_bytes(raw)

    async def _wait_event(self, event: EventType) -> Frame:
        """等一个指定事件；期间其它事件直接跳过。"""
        while True:
            frame = await self._receive()
            if frame.message_type == MessageType.ERROR:
                raise RuntimeError(
                    f"TTS 服务端返回错误 code={frame.error_code} "
                    f"payload={frame.payload.decode('utf-8', 'ignore')}"
                )
            if frame.event == event:
                return frame


def _parse_subtitle(payload: dict) -> TtsSubtitleWord:
    """把 TTSSubtitle 的 payload 解析成时间戳对象。

    官方示例的 payload 形如：`{"text": "...", "words": [...], "phonemes": [...]}`。
    """
    words = payload.get("words") or []
    first = words[0] if isinstance(words, list) and words else {}
    if not isinstance(first, dict):
        first = {}
    # 注意不能写成 `a or b`：起始时间就是 0.0，是 falsy，会被「或」吞掉。
    start_raw = first.get("startTime")
    if start_raw is None:
        start_raw = first.get("start_time")
    end_raw = first.get("endTime")
    if end_raw is None:
        end_raw = first.get("end_time")
    return TtsSubtitleWord(
        text=str(payload.get("text") or ""),
        # 官方字段名是 startTime/endTime（秒），也兼容下划线写法
        start_ms=_as_int(start_raw),
        end_ms=_as_int(end_raw),
        words=[item for item in (payload.get("words") or []) if isinstance(item, dict)],
        phonemes=[item for item in (payload.get("phonemes") or []) if isinstance(item, dict)],
    )


def _as_int(value) -> int | None:
    """把可能是秒 / 毫秒浮点的字段转成整数毫秒。"""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    # 官方 words 的 start_time/end_time 单位是秒（float）；小于 1000 时按秒处理更安全
    return int(number * 1000) if number < 1000 else int(number)
