"""语音面试的一轮回合：把「候选人说的一句话」变成「面试官的一句话」。

对应 T7.6 的编排部分。这里是**同步**实现（DB + 大模型都是同步阻塞的），
由 WebSocket 层用 `asyncio.to_thread` 丢到线程里跑，避免阻塞事件循环。

数据落库的语义与文字链路（`StreamChatService`）保持一致：
一条 `chat_messages` 记录一轮问答 + 面试记录追加一问一答。
这样「用文字面试」和「用语音面试」在数据库里是同一种东西，复盘（阶段 8）不用区分来源。
"""

from dataclasses import dataclass
from uuid import uuid4

from langchain_core.messages import BaseMessage
from sqlalchemy.orm import Session

from app.agent.prompt_layer import build_personalized_prompt, build_stream_graph
from app.core.logging_config import main_logger
from app.db.models import ChatMessage
from app.services.interview_service import InterviewService

# 语音面试固定走「模拟面试」模式，与文字链路的取值一致。
INTERVIEW_SELECT_MODEL = 4
INTERVIEW_AGENT = "interview_host"
INTERVIEW_SCENE = "interview"


@dataclass
class InterviewTurnResult:
    """一轮语音面试的结果。"""

    transcript: str  # 候选人说的话
    reply_text: str  # 面试官的回答（会被 TTS 念出来）
    message_id: int  # 本轮落库的消息 ID
    interview_id: int | None  # 所属面试记录 ID


class SpeechTurnService:
    """一轮语音面试的落库 + 模型调用。"""

    @staticmethod
    def run_turn(
        db: Session,
        *,
        user_id: int,
        session_id: int,
        transcript: str,
        provider: str = "deepseek",
    ) -> InterviewTurnResult:
        """跑一轮：落用户消息 → 调模型出面试官的话 → 落库 → 追加面试记录。"""
        text = (transcript or "").strip()
        if not text:
            raise ValueError("识别结果为空，无法进行这一轮面试")

        # 1) 先落用户消息（与流式链路一样：先拿到 row.id，供历史截断使用）。
        row = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            select_model=INTERVIEW_SELECT_MODEL,
            request_id=uuid4().hex,
            request_text=text,
            response_text="",
            request_segments=[],
            response_segments=[],
            status=0,
            interview_id=None,
            file_extracted_text="",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        # 2) 组装提示词与编排图（复用文字链路那一套，保证两条路径行为一致）。
        system_prompt = build_personalized_prompt(
            db=db, user_id=user_id, agent_name=INTERVIEW_AGENT, scene=INTERVIEW_SCENE
        )
        graph, graph_inputs = build_stream_graph(
            db=db,
            user_id=user_id,
            session_id=session_id,
            current_message_id=row.id,
            provider=provider,
            request_text=text,
            system_prompt=system_prompt,
        )

        # 3) 非流式调用：语音链路要拿到完整文本才能送 TTS，逐字吐出来没有意义。
        state = graph.invoke(graph_inputs)
        reply_text = _extract_reply_text(state.get("history") or [])

        row.response_text = reply_text
        db.add(row)
        db.commit()

        # 4) 面试记录：复用文字链路的同一套规则（先回填上一题答案，再追加这一题）。
        interview_id = InterviewService.record_round(
            db=db,
            user_id=user_id,
            session_id=session_id,
            message_id=row.id,
            request_text=text,
            response_text=reply_text,
            response_ok=bool(reply_text),
        )
        db.commit()

        main_logger.info(
            f"[语音面试] message_id={row.id} interview_id={interview_id} "
            f"识别={len(text)}字 回复={len(reply_text)}字"
        )
        return InterviewTurnResult(
            transcript=text,
            reply_text=reply_text,
            message_id=row.id,
            interview_id=interview_id,
        )


def _extract_reply_text(history: list[BaseMessage]) -> str:
    """从编排图返回的历史里取最后一条助手消息的文本。"""
    for message in reversed(history):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""
