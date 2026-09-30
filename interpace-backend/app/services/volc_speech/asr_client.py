"""火山引擎实时语音识别（双向流式 ASR）客户端。

对应 T7.6。协议细节见 `protocol.py` 的模块注释，这里负责会话生命周期：

1. 带鉴权头建连；
2. 发 full client request（序号 1），带上 `audio` / `request` 配置；
3. 持续推音频分片（每包约 200ms，序号从 2 自增）；
4. 收到 `is_last_package` 或主动结束时，**补发负序号末包**（这是最容易漏的一步）；
5. 把服务端返回的增量文本与最终分句文本交给上层。

服务端内置 VAD：连续静音达到 `end_window_size`（默认 800ms）就判定一句话说完并分句，
所以「候选人说完了没有」这件事不需要我们自己写静音检测。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import websockets

from app.core.logging_config import main_logger
from app.services.volc_speech.protocol import (
    CompressionType,
    Frame,
    FrameBuilder,
    MessageFlag,
    MessageType,
    encode_json_payload,
)

# 每包音频时长（毫秒）：官方 demo 默认 200ms，官方文档也建议按固定节拍发送。
DEFAULT_SEGMENT_MS = 200


@dataclass
class AsrTranscript:
    """一次识别回调的结果。

    `text` 是当前累计文本（增量结果会被后续音频更新，最终以 `is_final=True` 的那条为准）。
    """

    text: str
    is_final: bool
    is_last_package: bool = False
    raw: dict = field(default_factory=dict)


def build_asr_payload(
    *,
    sample_rate: int = 16000,
    bits: int = 16,
    channel: int = 1,
    audio_format: str = "pcm",
) -> dict:
    """构造 ASR 的 full client request 请求体。

    参数取值与官方文档一致；`show_utterances` 打开后才有分句信息（复盘要用到）。
    `audio_format` 要**与实际送去解码的字节一致**：上传的 wav 带 44 字节头就填 `wav`，
    直接推原始 PCM 帧就填 `pcm`，mp3 文件填 `mp3`（服务端自己解码，我们不用准备解码器）。
    """
    return {
        "user": {"uid": "interpace"},
        "audio": {
            "format": audio_format,
            "codec": "raw",
            "rate": sample_rate,
            "bits": bits,
            "channel": channel,
        },
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": True,
            "show_utterances": True,
            # 二遍识别：一句话结束后再识别一次，准确率更高（官方示例默认开启）
            "enable_nonstream": True,
            # 开头 1 秒即使静音也不判停，避免候选人刚开口就被截断
            "force_to_speech_time": 1000,
        },
    }


def build_auth_headers(api_key: str, resource_id: str) -> dict[str, str]:
    """构造握手鉴权头（新版控制台：X-Api-Key）。"""
    return {
        "X-Api-Key": api_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": str(uuid.uuid4()),
    }


class AsrSession:
    """一次 ASR 会话。作为异步上下文管理器使用。"""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        resource_id: str,
        sample_rate: int = 16000,
        segment_ms: int = DEFAULT_SEGMENT_MS,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.resource_id = resource_id
        self.sample_rate = sample_rate
        self.segment_ms = segment_ms
        self._connection = None
        self._builder = FrameBuilder(compression=CompressionType.GZIP)
        # 末包只能补发一次（官方要求补发幂等）
        self._last_packet_sent = False

    async def __aenter__(self) -> "AsrSession":
        await self.connect()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    async def connect(self) -> None:
        """建连并发送首个请求帧。"""
        if not self.api_key:
            raise RuntimeError("未配置 VOLC_API_KEY，无法使用语音服务")

        self._connection = await websockets.connect(
            self.url,
            additional_headers=build_auth_headers(self.api_key, self.resource_id),
            max_size=None,
        )
        payload = encode_json_payload(
            build_asr_payload(sample_rate=self.sample_rate), CompressionType.GZIP
        )
        await self._connection.send(self._builder.full_request(payload).to_bytes())
        main_logger.info(f"[ASR] 已建连并发送首帧 url={self.url}")

    async def send_audio(self, chunk: bytes, *, is_last: bool = False) -> None:
        """推一段音频。`is_last=True` 时发送负序号末包。"""
        if self._connection is None:
            raise RuntimeError("ASR 会话尚未建立")
        if self._last_packet_sent:
            # 末包已发过，后续音频直接丢弃，避免破坏负序号语义
            return
        if not chunk and not is_last:
            return

        sequence = self._builder.next_sequence()
        frame = self._builder.audio_packet(chunk, is_last=is_last, sequence=sequence)
        await self._connection.send(frame.to_bytes())
        if is_last:
            self._last_packet_sent = True

    async def finish(self) -> None:
        """best-effort 补发末包（幂等）。

        所有退出路径（正常结束、上游断连、异常、任务取消）都该调一次，
        否则服务端会一直等下一个包，8 秒后报 `session unexpectedly finished`。
        """
        if self._connection is None or self._last_packet_sent:
            return
        try:
            await self.send_audio(b"", is_last=True)
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"[ASR] 补发末包失败（忽略）: {exc!r}")

    async def close(self) -> None:
        """收尾：补末包 → 关闭连接。"""
        await self.finish()
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def responses(self) -> AsyncIterator[AsrTranscript]:
        """持续读服务端响应，产出识别结果。"""
        if self._connection is None:
            raise RuntimeError("ASR 会话尚未建立")

        async for raw in self._connection:
            if not isinstance(raw, bytes):
                continue
            frame = Frame.from_bytes(raw)
            if frame.message_type == MessageType.ERROR:
                raise RuntimeError(
                    f"ASR 服务端返回错误 code={frame.error_code} "
                    f"payload={frame.payload.decode('utf-8', 'ignore')}"
                )

            payload = frame.json_payload()
            text = _extract_text(payload)
            if text:
                yield AsrTranscript(
                    text=text,
                    # 只有 definite=True 才算「这句话说完了」；中间结果照样推给前端，
                    # 但不会触发一轮面试。判据的来由见 is_definite_end 的注释。
                    is_final=is_definite_end(payload),
                    is_last_package=frame.is_last_package,
                    raw=payload,
                )
            if frame.is_last_package:
                return

    async def stream_audio(
        self,
        audio_chunks: AsyncIterator[bytes] | list[bytes],
        on_transcript: Callable[[AsrTranscript], None] | None = None,
    ) -> AsyncIterator[AsrTranscript]:
        """边推音频边收结果：收发两个任务并发，发送方不阻塞等回包（官方硬性要求）。

        音频源可以是异步迭代器（边录边推）也可以是现成的分片列表（离线音频）。
        """
        results: list[AsrTranscript] = []
        done = asyncio.Event()

        async def sender() -> None:
            try:
                if isinstance(audio_chunks, list):
                    iterator = _iterate_chunks(audio_chunks)
                else:
                    iterator = audio_chunks
                async for chunk in iterator:
                    await self.send_audio(chunk)
            finally:
                # 任何退出路径都补末包，保证服务端会结束会话
                await self.finish()

        async def receiver() -> None:
            try:
                async for transcript in self.responses():
                    results.append(transcript)
                    if on_transcript is not None:
                        on_transcript(transcript)
            finally:
                done.set()

        sender_task = asyncio.create_task(sender())
        receiver_task = asyncio.create_task(receiver())
        try:
            await done.wait()
        finally:
            for task in (sender_task, receiver_task):
                if not task.done():
                    task.cancel()
        for transcript in results:
            yield transcript


async def _iterate_chunks(chunks: list[bytes]) -> AsyncIterator[bytes]:
    """把分片列表包成异步迭代器，让 sender 内部只有一条代码路径。"""
    for chunk in chunks:
        yield chunk


# 整段识别端点一次性推完音频；分片大小只影响网络往返次数，不影响结果
FILE_CHUNK_BYTES = 64 * 1024

# 支持的音频格式：与官方 `audio.format` 可选值对齐。
# 我们用**文件后缀**推断，不做内容嗅探——服务端会按声明的格式解码，声明错了它会直接报错。
SUPPORTED_AUDIO_FORMATS = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".m4a": "m4a",
    ".aac": "aac",
    ".ogg": "ogg",
    ".opus": "ogg",
    ".pcm": "pcm",
    ".amr": "amr",
    ".spx": "spx",
}


def resolve_audio_format(file_name: str) -> str | None:
    """按文件后缀推断 ASR 需要的 `audio.format`；不支持的后缀返回 None。"""
    suffix = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
    return SUPPORTED_AUDIO_FORMATS.get(suffix)


async def transcribe_file_bytes(
    data: bytes,
    *,
    file_name: str,
    url: str,
    api_key: str,
    resource_id: str,
) -> str:
    """整段识别一段音频文件，返回完整文本（空音频返回空串）。

    **为什么走单独的端点**：流式端点要求按实时节拍喂音频（官方明确要求，否则 VAD 分句会乱），
    一段 20 分钟的录音就要 20 分钟才能转写完。整段识别端点让服务端尽快跑完——
    实测 14.4 秒音频约 2.4 秒出结果，速度快一个量级。

    实测细节（2026-09-29）：该端点会回**大量空帧**（服务端在轮询），
    **只有 `is_last_package=True` 的那一帧带完整文本**，所以必须读到最后一帧才算完。
    """
    audio_format = resolve_audio_format(file_name)
    if audio_format is None:
        raise ValueError(f"不支持的音频格式: {file_name}")

    builder = FrameBuilder(compression=CompressionType.GZIP)
    headers = build_auth_headers(api_key, resource_id)
    chunks = [
        data[i : i + FILE_CHUNK_BYTES] for i in range(0, len(data), FILE_CHUNK_BYTES)
    ] or [b""]

    async with websockets.connect(url, additional_headers=headers, max_size=None) as ws:
        payload = encode_json_payload(
            build_asr_payload(audio_format=audio_format), CompressionType.GZIP
        )
        await ws.send(builder.full_request(payload).to_bytes())
        for index, chunk in enumerate(chunks, start=1):
            await ws.send(
                builder.audio_packet(chunk, is_last=False, sequence=index + 1).to_bytes()
            )
        await ws.send(
            builder.audio_packet(
                b"", is_last=True, sequence=len(chunks) + 2
            ).to_bytes()
        )

        while True:
            frame = Frame.from_bytes(await ws.recv())
            if frame.message_type == MessageType.ERROR:
                raise RuntimeError(
                    "ASR 整段识别失败: "
                    + frame.payload.decode("utf-8", "ignore")[:200]
                )
            if frame.is_last_package:
                result = frame.json_payload().get("result") or {}
                text = result.get("text")
                return str(text or "").strip()


def _extract_text(payload: dict) -> str:
    """从 ASR 响应里取识别文本。

    **优先取最后一个分句的文本**，而不是 `result.text`：
    `result.text` 是本次会话的累计文本（实测第二句结束时会把第一句也带上），
    直接拿去当「这一轮候选人说的话」会重复上一轮的内容。
    只在没有分句信息时才退回累计文本。

    结构：开启 `show_utterances` 后有 `result.utterances`
    （分句数组，每项含 `text` / `start_time` / `end_time` / `definite`）。
    """
    result = payload.get("result")
    if isinstance(result, dict):
        utterances = result.get("utterances")
        if isinstance(utterances, list) and utterances:
            last = utterances[-1]
            if isinstance(last, dict) and isinstance(last.get("text"), str):
                return last["text"]
        text = result.get("text")
        if isinstance(text, str):
            return text
    return ""


def is_definite_end(payload: dict) -> bool:
    """这一条响应是否表示「一句话真的说完了」。

    **判据是 `utterances[-1].definite`，而不是「有没有 utterances」**。
    真机实测（2026-09-29）：快速推流时服务端会连续给出中间结果，它们的
    `utterances` 同样非空、但 `definite=False`。只看「有没有 utterances」
    会把 3 句话判成 9 次「最终结果」，一轮面试被切得七零八落。
    """
    utterances = (payload.get("result") or {}).get("utterances")
    if not isinstance(utterances, list) or not utterances:
        return False
    last = utterances[-1]
    return isinstance(last, dict) and last.get("definite") is True
