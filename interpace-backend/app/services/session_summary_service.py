"""长会话上下文压缩（T9.16）。

**它不属于三层记忆**：这是「一个会话聊到几十轮，早期内容被截断」的问题，
对应 Hermes 的上下文压缩（`/compress`），和 L1/L2/L3 是两件事。

## 为什么要压缩

`prompt_layer` 只注入最近 N 条原始消息，更早的内容原本**彻底丢失**——
用户在第 3 轮说过的关键信息，到第 30 轮模型就完全不知道了。

## 做法：渐进式摘要，不是每次全量重压

- 保留最近 `KEEP_RECENT` 条原文（细节不能丢）；
- 更早的消息攒够 `SUMMARY_TRIGGER` 条就压一次，把「上一版摘要 + 这一批新消息」
  一起压成新版摘要；
- `covered_message_id` 记录压到哪条，据此算增量——所以长会话里大约每 10 条消息
  才花一次模型调用，而不是每轮都压一遍整段历史。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.core.logging_config import main_logger
from app.core.request_context import set_scene
from app.db.models import ChatMessage, SessionSummary
from app.services.usage_quota_service import SCENE_SUMMARY

# 保留多少条最近消息的**原文**（细节不压缩）
KEEP_RECENT = 10

# 未总结的消息攒到多少条才压一次（控制模型调用频率）
SUMMARY_TRIGGER = 10

# 摘要注入提示词时的长度上限，防止摘要本身把提示词撑大
SUMMARY_MAX_CHARS = 2000

SUMMARIZER_AGENT = "session_summarizer"
SUMMARY_SCENE = "summary"

# 摘要提示词：内置兜底（没有 seed 模板时也能用）
DEFAULT_SUMMARY_PROMPT = """你在为一段较长的对话做上下文压缩。

要求：
- 保留**事实性信息**：用户的背景、偏好、明确说过的结论、已确定的方案、待办事项。
- 保留**尚未解决的问题**与用户明确表达过的目标。
- 丢掉寒暄、重复内容、以及已经被后续对话推翻的中间结论。
- 用第三人称陈述，条理化；不要复述原文，不要加评论。
- 控制在 400 字以内。
"""


class SessionSummaryService:
    """会话摘要的读取与渐进式更新。"""

    @staticmethod
    def get_summary(db: Session, *, session_id: int) -> SessionSummary | None:
        return db.scalar(
            select(SessionSummary).where(SessionSummary.session_id == session_id)
        )

    @staticmethod
    def ensure_summary(
        db: Session,
        *,
        user_id: int,
        session_id: int,
        provider: str = "deepseek",
        keep_recent: int = KEEP_RECENT,
        trigger: int = SUMMARY_TRIGGER,
    ) -> str:
        """确保会话摘要是最新的，返回可直接注入提示词的摘要文本（没有则空串）。

        这个函数在**每轮组装提示词时**调用，所以必须够便宜：
        大多数情况下它只做一次「未总结条数够不够」的判断就返回。
        """
        rows = list(
            db.scalars(
                select(ChatMessage)
                .where(
                    ChatMessage.user_id == user_id,
                    ChatMessage.session_id == session_id,
                )
                .order_by(ChatMessage.id.asc())
            )
        )
        if len(rows) <= keep_recent:
            return ""

        # 需要压缩的候选：除了最近 keep_recent 条之外的、且还没被总结过的
        older_rows = rows[:-keep_recent]
        summary_row = SessionSummaryService.get_summary(db, session_id=session_id)
        covered = summary_row.covered_message_id if summary_row else 0
        pending = [row for row in older_rows if row.id > covered]
        if len(pending) < trigger and summary_row is not None:
            # 攒得还不够，先用现有摘要
            return SessionSummaryService._trim(summary_row.summary)
        if not pending:
            return SessionSummaryService._trim(summary_row.summary) if summary_row else ""

        # 第一次触发：条数不够 trigger 也要先压一次，否则早期内容一直是丢的
        previous = summary_row.summary if summary_row else ""
        new_summary = SessionSummaryService._summarize(
            db, previous=previous, rows=pending, provider=provider
        )
        if not new_summary:
            # 压缩失败：退回现有摘要（可能是空），不打断正常回答
            return SessionSummaryService._trim(previous) if previous else ""

        if summary_row is None:
            summary_row = SessionSummary(
                user_id=user_id, session_id=session_id, summary=new_summary
            )
            db.add(summary_row)
        else:
            summary_row.summary = new_summary
        summary_row.covered_message_id = pending[-1].id
        summary_row.covered_count = (summary_row.covered_count or 0) + len(pending)
        db.add(summary_row)
        db.commit()
        main_logger.info(
            f"[上下文压缩] session_id={session_id} 新压 {len(pending)} 条，"
            f"已覆盖到 message_id={summary_row.covered_message_id}"
        )
        return SessionSummaryService._trim(new_summary)

    @staticmethod
    def _trim(summary: str) -> str:
        """摘要注入前统一限长。"""
        text = (summary or "").strip()
        if len(text) <= SUMMARY_MAX_CHARS:
            return text
        return text[:SUMMARY_MAX_CHARS] + "……（摘要已截断）"

    @staticmethod
    def _summarize(
        db: Session, *, previous: str, rows: list[ChatMessage], provider: str
    ) -> str:
        """把「上一版摘要 + 这一批消息」压成新版摘要；失败返回空串。"""
        parts: list[str] = []
        if previous.strip():
            parts.append(f"【已有摘要】\n{previous.strip()}")
        transcript = []
        for row in rows:
            question = (row.request_text or "").strip()
            answer = (row.response_text or "").strip()
            if question:
                transcript.append(f"用户：{question}")
            if answer:
                transcript.append(f"助手：{answer}")
        parts.append("【新增对话】\n" + "\n".join(transcript))

        try:
            system_prompt = DEFAULT_SUMMARY_PROMPT
            from app.services.prompt_template_service import prompt_template_manager

            template = prompt_template_manager.get_full_prompt(
                SUMMARIZER_AGENT, SUMMARY_SCENE, db
            )
            if template:
                system_prompt = template

            # 标记场景：会话摘要压缩（用户看不见的额外调用，演示环境会整体跳过）
            set_scene(SCENE_SUMMARY)
            model = get_chat_model(provider=provider)
            message = model.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "\n\n".join(parts)},
                ]
            )
            content = (
                message.content if isinstance(message.content, str) else str(message.content)
            )
            return content.strip()
        except Exception as exc:  # noqa: BLE001
            main_logger.warning(f"[上下文压缩] 摘要生成失败，本轮跳过: {exc!r}")
            return ""
