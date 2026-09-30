"""语音面试的 WebSocket 编排（对应 T7.6）。

把三件事串起来：**火山 ASR → 面试 Agent → 火山 TTS**，全部以流式方式在一条
WebSocket 里完成。前端只连我们的后端，**API Key 不下发到浏览器**。

## 与前端约定的消息协议

前端 → 后端：

- 文本帧 JSON：`{"type": "start_utterance"}` 开始这一次说话（会新建一趟 ASR 会话）
- 二进制帧：16kHz / 16bit / 单声道的原始 PCM 分片
- 文本帧 JSON：`{"type": "end_utterance"}` 说完了（也可不传，服务端 VAD 会自动分句）
- 文本帧 JSON：`{"type": "text", "text": "..."}` 直接给文字（跳过 ASR，便于调试与降级）

后端 → 前端：

- `{"type": "ready", ...}` 连接就绪
- `{"type": "asr_partial" | "asr_final", "text": "..."}` 识别中间结果 / 最终结果
- `{"type": "reply", "text": "...", "interview_id": 1, "message_id": 2}` 面试官的话
- `{"type": "tts_start", "format": "pcm", "sample_rate": 24000}` 后面开始推音频二进制帧
- `{"type": "tts_end"}` 这一轮音频推完了，前端可以开始说下一句
- `{"type": "error", "message": "..."}`

## 为什么按「一句话一趟 ASR 会话」

火山要求音频流持续有包，8 秒收不到就断会话。面试天然是一问一答，按句开会话
既能避开这个超时，又不用自己写静音检测（服务端 VAD 会给出分句）。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.logging_config import main_logger
from app.core.settings import settings
from app.db.database import SessionLocal
from app.services.interview_service import InterviewService
from app.services.speech_turn_service import SpeechTurnService
from app.services.usage_quota_service import UsageQuotaService
from app.services.volc_speech.asr_client import AsrSession
from app.services.volc_speech.tts_client import TtsSession, TtsSubtitleWord

# 与前端约定的音频参数（ASR 侧）。前端录音必须按这个规格重采样。
ASR_SAMPLE_RATE = 16000
# TTS 输出参数：流式场景用 pcm，前端用 Web Audio 直接播放。
TTS_SAMPLE_RATE = 24000
TTS_FORMAT = "pcm"


class SpeechStreamSession:
    """一条 WebSocket 连接的生命周期。"""

    def __init__(self, *, websocket: WebSocket, user_id: int, session_id: int, session_model: int) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self.session_id = session_id
        self.session_model = session_model
        self._asr: AsrSession | None = None
        self._asr_pump: asyncio.Task | None = None
        self._utterance_final: str = ""
        self._turn_active = False
        self._closing = False

    # ---------- 主循环 ----------

    async def run(self) -> None:
        """主循环：收消息 → 分发。"""
        # 演示环境的单场面试时长上限（T12.4）。截止时间按「面试记录创建时间 + N 分钟」
        # 算，而不是从连接建立起算——这样语音和文字共用同一个时钟，中途切换也不会各算一份。
        deadline_seconds = self._resolve_deadline_seconds()
        if deadline_seconds is not None and deadline_seconds <= 0:
            # 进连接时就已经超时：直接告知并结束，不再开门让用户白说一轮。
            await self._finish_by_timeout(deadline_seconds)
            return

        await self.websocket.send_json(
            {
                "type": "ready",
                "asr_sample_rate": ASR_SAMPLE_RATE,
                "tts_sample_rate": TTS_SAMPLE_RATE,
                "tts_format": TTS_FORMAT,
            }
        )

        try:
            while True:
                # 用 wait_for 给 receive 加超时：到点就从这里跳出去收尾，
                # 而不是等用户挂断——演示环境的时长上限必须由服务端说了算。
                try:
                    message = await asyncio.wait_for(
                        self.websocket.receive(), timeout=deadline_seconds
                    )
                except asyncio.TimeoutError:
                    await self._finish_by_timeout(0)
                    break
                if message.get("type") == "websocket.disconnect":
                    break

                if (payload := message.get("bytes")) is not None:
                    await self._on_audio(payload)
                elif (text := message.get("text")) is not None:
                    await self._on_text(text)
                    # 每轮过后重算剩余时间（第一轮会创建面试记录，时钟从那一刻起算）。
                    deadline_seconds = self._resolve_deadline_seconds()
        except WebSocketDisconnect:
            pass
        finally:
            self._closing = True
            await self._abort_utterance()

    # ---------- 时长限制（T12.4） ----------

    def _resolve_deadline_seconds(self) -> float | None:
        """本场面试还剩多少秒；None 表示不限制。"""
        max_minutes = UsageQuotaService.interview_max_minutes()
        if max_minutes <= 0:
            return None
        started_at: int | None = None
        db = SessionLocal()
        try:
            interview = InterviewService.get_running_interview(
                db, user_id=self.user_id, session_id=self.session_id
            )
            if interview is not None:
                started_at = int(interview.created_at or 0)
        finally:
            db.close()
        remaining = UsageQuotaService.interview_remaining_seconds(started_at)
        return None if remaining is None else float(remaining)

    async def _finish_by_timeout(self, remaining_seconds: float) -> None:
        """到点收尾：结束面试记录 + 告知前端 + 关闭连接。"""
        max_minutes = UsageQuotaService.interview_max_minutes()
        message = UsageQuotaService.interview_timeout_message(max_minutes)
        interview_id: int | None = None

        db = SessionLocal()
        try:
            interview = InterviewService.get_running_interview(
                db, user_id=self.user_id, session_id=self.session_id
            )
            if interview is not None:
                interview_id = interview.id
                # 用与手动「结束面试」同一条路径收尾，时长口径保持一致。
                InterviewService.finish(db, user_id=self.user_id, interview_id=interview.id)
        except Exception as exc:  # noqa: BLE001 —— 收尾失败也要把连接关干净
            db.rollback()
            main_logger.warning(f"[语音面试] 超时收尾失败: {exc!r}")
        finally:
            db.close()

        main_logger.info(
            f"[语音面试] 达到演示环境时长上限（{max_minutes} 分钟）自动结束 "
            f"user_id={self.user_id} session_id={self.session_id} interview_id={interview_id}"
        )
        try:
            await self.websocket.send_json(
                {
                    "type": "interview_timeout",
                    "message": message,
                    "max_minutes": max_minutes,
                    "interview_id": interview_id,
                }
            )
        except Exception:  # noqa: BLE001 —— 对端可能已经断开
            pass

    async def _on_text(self, raw: str) -> None:
        """处理文本帧（都是 JSON 控制消息）。"""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error("控制消息不是合法 JSON")
            return

        kind = payload.get("type")
        if kind == "start_utterance":
            # 上一轮还没结束就先中止，避免两趟 ASR 会话交叉写回
            await self._abort_utterance()
            await self._start_utterance()
        elif kind == "end_utterance":
            await self._finish_utterance()
        elif kind == "text":
            # 直接给文字：跳过 ASR，用来做降级与联调
            await self._run_turn(str(payload.get("text") or ""))
        else:
            await self._send_error(f"未知的控制消息类型: {kind}")

    async def _on_audio(self, chunk: bytes) -> None:
        """收到音频分片：转给 ASR。"""
        if self._turn_active:
            # 面试官正在说话/合成中，这段时间候选人一般不会说话，收到就丢弃，
            # 免得把上一轮的尾音混进下一轮（前端也会在这段时间停录）。
            return
        if self._asr is None:
            # 允许前端不显式发 start_utterance：第一块音频自动开一趟会话
            await self._start_utterance()
        if self._asr is not None:
            await self._asr.send_audio(chunk)

    # ---------- 一趟说话（ASR） ----------

    async def _start_utterance(self) -> None:
        self._utterance_final = ""
        try:
            self._asr = AsrSession(
                url=settings.volc_asr_url,
                api_key=settings.volc_api_key,
                resource_id=settings.volc_asr_resource_id,
                sample_rate=ASR_SAMPLE_RATE,
            )
            await self._asr.connect()
        except Exception as exc:  # noqa: BLE001
            self._asr = None
            main_logger.exception("语音面试：ASR 建连失败", exc_info=exc)
            await self._send_error("语音识别服务连接失败，请稍后重试")
            return
        self._asr_pump = asyncio.create_task(self._pump_asr(self._asr))

    async def _pump_asr(self, asr: AsrSession) -> None:
        """把 ASR 结果持续推给前端；拿到最终分句后自动结束这一趟。"""
        try:
            async for transcript in asr.responses():
                text = transcript.text.strip()
                if not text:
                    continue
                if transcript.is_final:
                    self._utterance_final = text
                    await self.websocket.send_json({"type": "asr_final", "text": text})
                    # 服务端 VAD 判到句子结束：跳出循环，下面统一收尾
                    break
                await self.websocket.send_json({"type": "asr_partial", "text": text})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"语音面试：ASR 读流异常 {exc!r}")
            return

        # 自动分句（或服务端正常结束）后进入回合。
        # 注意：这里是「泵自己」调用收尾，所以 _finish_utterance 里不能再等这个任务，否则自己等自己。
        if self._asr is asr and not self._closing:
            await self._finish_utterance()

    async def _finish_utterance(self) -> None:
        """结束这一趟说话并进入回合（幂等：重复调用只跑一次）。"""
        if self._turn_active:
            return
        asr, self._asr = self._asr, None
        if asr is None:
            return

        pump = self._asr_pump
        # 先让 ASR 收尾（补末包），服务端才会把最后的分句吐出来
        try:
            await asr.finish()
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"语音面试：ASR 收尾异常 {exc!r}")

        # 等泵把最后的分句送上来；但如果「泵就是当前调用者」，跳过等待（否则自己等自己会死锁）。
        if pump is not None and pump is not asyncio.current_task():
            try:
                await asyncio.wait_for(asyncio.shield(pump), timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pump.cancel()
            except Exception:  # noqa: BLE001
                pass
        self._asr_pump = None
        try:
            await asr.close()
        except Exception:  # noqa: BLE001
            pass

        transcript = self._utterance_final.strip()
        if not transcript:
            await self.websocket.send_json(
                {"type": "error", "message": "没有识别到内容，请再说一次"}
            )
            return
        await self._run_turn(transcript)

    async def _abort_utterance(self) -> None:
        """中止当前这趟说话（切换/断开时用）。"""
        asr, self._asr = self._asr, None
        pump, self._asr_pump = self._asr_pump, None
        if pump is not None and not pump.done():
            pump.cancel()
        if asr is not None:
            try:
                await asr.close()
            except Exception:  # noqa: BLE001
                pass

    # ---------- 一轮回合（Agent + TTS） ----------

    async def _run_turn(self, transcript: str) -> None:
        """跑一轮面试问答，并把面试官的话合成音频推给前端。"""
        if not transcript.strip():
            return
        self._turn_active = True
        try:
            result = await asyncio.to_thread(
                self._run_turn_sync, self.user_id, self.session_id, transcript
            )
            await self.websocket.send_json(
                {
                    "type": "reply",
                    "text": result["reply_text"],
                    "interview_id": result["interview_id"],
                    "message_id": result["message_id"],
                }
            )
            await self._speak(result["reply_text"])
        except Exception as exc:  # noqa: BLE001
            main_logger.exception("语音面试：回合执行失败", exc_info=exc)
            await self._send_error("这一轮处理失败，请再说一次")
        finally:
            self._turn_active = False
            await self.websocket.send_json({"type": "tts_end"})

    @staticmethod
    def _run_turn_sync(user_id: int, session_id: int, transcript: str) -> dict[str, Any]:
        """在独立线程里跑同步的 DB + 大模型逻辑（不能阻塞事件循环）。"""
        # 自己开一个会话：跨线程复用同一个 Session 不安全，而且 WS 生命周期比一次请求长。
        db: Session = SessionLocal()
        try:
            result = SpeechTurnService.run_turn(
                db=db,
                user_id=user_id,
                session_id=session_id,
                transcript=transcript,
            )
            return {
                "reply_text": result.reply_text,
                "interview_id": result.interview_id,
                "message_id": result.message_id,
            }
        finally:
            db.close()

    async def _speak(self, text: str) -> None:
        """把面试官的话合成音频，边收边推给前端。"""
        if not text.strip():
            return
        await self.websocket.send_json(
            {"type": "tts_start", "format": TTS_FORMAT, "sample_rate": TTS_SAMPLE_RATE}
        )
        try:
            async with TtsSession(
                url=settings.volc_tts_url,
                api_key=settings.volc_api_key,
                resource_id=settings.volc_tts_resource_id,
                speaker=settings.volc_tts_speaker,
                sample_rate=TTS_SAMPLE_RATE,
                audio_format=TTS_FORMAT,
            ) as tts:
                async for item in tts.synthesize(text):
                    if isinstance(item, bytes):
                        if item:
                            await self.websocket.send_bytes(item)
                    elif isinstance(item, TtsSubtitleWord):
                        # 时间戳先原样透传给前端；T7.9 口型同步要用，
                        # 这一版前端可以忽略，但服务端不能把它丢掉。
                        await self.websocket.send_json(
                            {
                                "type": "tts_subtitle",
                                "text": item.text,
                                "start_ms": item.start_ms,
                                "end_ms": item.end_ms,
                                "phonemes": item.phonemes,
                            }
                        )
        except Exception as exc:  # noqa: BLE001
            main_logger.exception("语音面试：TTS 合成失败", exc_info=exc)
            await self._send_error("语音合成失败，这一轮的回复请以文字为准")

    async def _send_error(self, message: str) -> None:
        if self._closing:
            return
        try:
            await self.websocket.send_json({"type": "error", "message": message})
        except Exception:  # noqa: BLE001
            pass
