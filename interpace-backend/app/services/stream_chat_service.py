"""轻量单Agent流式对话服务。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from typing import Any

from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.prompt_layer import build_stream_graph, build_personalized_prompt
from app.agent.scene_registry import resolve_scene
from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import ChatMessage
from app.schemas.chat_schemas import MessageSegment
from app.services.attachment_content_service import AttachmentContentService
from app.services.interview_service import InterviewService
from app.services.memory_search_service import (
    SOURCE_MESSAGE,
    MemorySearchService,
)
from app.services.profile_extraction_service import extract_profile
from app.services.profile_proposal_service import ProfileProposalService
from app.services.quiz_service import get_paper_by_message, parse_quiz_payload, save_quiz_paper
from app.services.session_service import SessionService
from app.services.stream_cancel_service import stream_cancel_registry
from app.services.usage_quota_service import UsageQuotaService
from app.utils.prompt_logger import log_chain_ready

# chat_messages.status 的取值：0=常规聊天，1=面试转写入口，2=用户主动停止，
# 3=题库入口（这条消息的回复里出了一份卷子），4=画像待确认。
# 1 目前没有任何写入点（面试转写入口属于阶段 7）。
MESSAGE_STATUS_STOPPED = 2
MESSAGE_STATUS_QUIZ_ENTRY = 3
# 4=画像待确认（简历优化这条消息抽出了画像，等用户确认后才写进 user_profiles）。
MESSAGE_STATUS_PROFILE_PENDING = 4

# 只有这个场景的回复才尝试解析题库；其它场景的正文都当普通文本。
QUIZ_SCENE = "quiz"

# 简历优化场景：回复之外还要顺手抽一次画像（决策 D11，结果先落「待确认」）。
RESUME_SCENE = "resume"

# 模拟面试场景：一轮请求要顺手写面试记录（T7.4 / T7.5）。
INTERVIEW_SCENE = "interview"

# 走画像抽取的最短输入长度：太短的输入（例如只问了「简历怎么写」）不可能含简历内容，
# 白白多一次模型调用和几秒等待。120 字是个经验值，够挡住纯提问、放得住精简简历。
PROFILE_EXTRACT_MIN_CHARS = 120

def _sse_data(payload: dict[str, Any]) -> str:
    """将事件对象编码为一帧 SSE 文本。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class StreamChatService:
    """负责流式推送、历史重建与最终落库。"""

    @staticmethod
    def stream_chat(
        db: Session,
        user_id: int,
        session_id: int,
        session_model: int,
        request_text: str,
        select_model: int = 0,
        provider: str = "deepseek",
        agent_name: str | None = None,
        scene: str | None = None,
        segments: list[MessageSegment] | None = None,
    ) -> StreamingResponse:
        # 1) 会话归属校验，不存在则抛 404。
        SessionService.get_session_or_404(
            db=db,
            user_id=user_id,
            session_id=session_id,
            session_model=session_model,
        )

        # 2) 解析执行模式：显式传入的 agent / scene 优先（保持向后兼容），
        #    否则按 select_model 查模式注册表，未知取值回退到默认模式。
        spec = resolve_scene(select_model)
        resolved_agent = agent_name or spec.agent_name
        resolved_scene = scene or spec.scene
        override_note = "（调用方显式指定）" if (agent_name or scene) else ""
        main_logger.info(
            f"[模式路由] select_model={select_model}（{spec.label}）"
            f" -> agent_name={resolved_agent} scene={resolved_scene}{override_note}"
        )

        # 3) 解析附件内容：文档取正文、图片与扫描件取图片字节。
        #    放在建行之前，解析结果可以直接写进 file_extracted_text。
        attachments = AttachmentContentService.resolve(
            db=db, user_id=user_id, segments=segments
        )
        attachment_text = "\n\n".join(
            part for part in [attachments.text, *attachments.notes] if part
        )

        # 4) 预写入消息占位行：先落库拿到 row.id，供历史记忆截断用。
        row = ChatMessage(
            user_id=user_id,
            session_id=session_id,
            select_model=select_model,
            request_id=uuid.uuid4().hex,
            request_text=request_text,
            response_text="",
            # 附件段原样落库；历史回显与会话删除时的资源回收都依赖它。
            request_segments=[segment.model_dump() for segment in (segments or [])],
            response_segments=[],
            status=0,
            interview_id=None,
            file_extracted_text=attachment_text,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        # 4.5) 演示环境的模拟面试时长上限（T12.4）：一场面试从创建算起最多 N 分钟。
        #      到点后**不再回答问题**，而且这里位于「建提示词 / 建模型」之前，
        #      所以超时之后完全不消耗 token——这既是产品限制，也是最省钱的一道闸。
        if resolved_scene == INTERVIEW_SCENE:
            timeout_notice = StreamChatService._interview_timeout_notice(
                db=db, user_id=user_id, session_id=session_id
            )
            if timeout_notice is not None:
                return StreamChatService._build_notice_response(
                    db=db, row=row, text=timeout_notice
                )

        # 5) 构建个性化提示词（注入用户画像信息）；无模板时返回 None，由链路层使用默认提示词兜底。
        system_prompt = build_personalized_prompt(
            db=db,
            user_id=user_id,
            agent_name=resolved_agent,
            scene=resolved_scene,
        )

        log_chain_ready(user_id, session_id, resolved_agent, resolved_scene, provider, len(system_prompt) if system_prompt else 0)

        # 6) 组装编排图：历史记忆截断 + LLM 绑定 + 输入变量准备。
        graph, graph_inputs = build_stream_graph(
            db=db,
            user_id=user_id,
            session_id=session_id,
            current_message_id=row.id,
            provider=provider,
            request_text=request_text,
            system_prompt=system_prompt,
            attachment_text=attachment_text,
            attachment_images=attachments.images,
        )

        def event_generator() -> Generator[str, None, None]:
            response_text = ""
            error_message = ""
            stopped = False
            quiz_paper_id: int | None = None
            proposal_id: int | None = None
            interview_id: int | None = None
            model_stream = None
            yield _sse_data({"type": "start", "message_id": row.id})
            try:
                # stream_mode="messages" 返回 (消息块, 元数据)；当前只消费消息块，
                # 元数据里的节点名留给后续多节点场景做区分。
                model_stream = graph.stream(graph_inputs, stream_mode="messages")
                for chunk, _meta in model_stream:
                    # 用户点了停止：跳出循环，不再消费模型输出。
                    if stream_cancel_registry.is_cancelled(row.id):
                        stopped = True
                        break
                    delta = StreamChatService._extract_text_delta(chunk)
                    if not delta:
                        continue
                    response_text += delta
                    yield _sse_data({"type": "delta", "text": delta})
            except Exception as exc:
                error_message = str(exc)
                main_logger.exception("stream_chat failed", exc_info=exc)
            finally:
                # close() 会中断底下那次模型调用，立刻释放 HTTP 连接。
                if model_stream is not None:
                    model_stream.close()
                # 无论正常结束、异常还是被停止，都把已积累的文本回写到占位行。
                row.response_text = response_text
                # 只在「用户停止」这条路径上改状态，避免覆盖将来可能的其他状态值。
                if stopped:
                    row.status = MESSAGE_STATUS_STOPPED
                db.add(row)
                db.commit()
                if stopped:
                    main_logger.info(f"[流式停止] message_id={row.id} 已按用户请求停止")
                # 无论正常结束、出错还是被停止，都把这条消息写进 L3 检索索引（T9.14）：
                # 被停止的半截回答也是用户真实经历的一部分，搜得到比搜不到更有用。
                try:
                    MemorySearchService.index_document(
                        db,
                        user_id=row.user_id,
                        source_type=SOURCE_MESSAGE,
                        source_id=row.id,
                        session_id=row.session_id,
                        title=request_text,
                        content=f"{request_text}\n\n{response_text}".strip(),
                        created_at=row.created_at,
                        commit=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    # 索引失败不该影响对话本身：主流程已经落库了
                    db.rollback()
                    main_logger.warning(f"[检索索引] message_id={row.id} 写入失败: {exc!r}")
                # 刷题场景：回复整段拿到后再尝试解析题库。
                # 用「解析成功」当出题判据（T5.1 的结论），拿不到就什么都不做。
                # 用户中途停止或这轮报错时一律跳过——半截输出不该落成卷子。
                if not stopped and not error_message:
                    quiz_paper_id = StreamChatService._persist_quiz_if_any(
                        db=db, row=row, scene=resolved_scene, response_text=response_text
                    )
                    proposal_id = StreamChatService._persist_profile_proposal_if_any(
                        db=db,
                        row=row,
                        scene=resolved_scene,
                        request_text=request_text,
                        attachment_text=attachment_text,
                        provider=provider,
                    )

                # 模拟面试：即使在「停止 / 报错」路径上也要走一趟——
                # 用户确实回答了上一题，答案该留下；只是不再追加新问题。
                interview_id = StreamChatService._persist_interview_round_if_any(
                    db=db,
                    row=row,
                    scene=resolved_scene,
                    request_text=request_text,
                    response_text=response_text,
                    stopped=stopped,
                    error_message=error_message,
                )

            if error_message:
                yield _sse_data({"type": "error", "message": error_message})
            yield _sse_data(
                {
                    "type": "done",
                    "response_text": response_text,
                    "stopped": stopped,
                    "quiz_paper_id": quiz_paper_id,
                    "profile_proposal_id": proposal_id,
                    "interview_id": interview_id,
                }
            )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @staticmethod
    def _extract_text_delta(chunk: Any) -> str:
        """从 LangChain 链式调用返回的增量块中提取文本。"""
        if isinstance(chunk, AIMessageChunk):
            return chunk.content or ""
        return ""

    @staticmethod
    def _interview_timeout_notice(
        db: Session, *, user_id: int, session_id: int
    ) -> str | None:
        """这场模拟面试是否已超时；超时返回给用户看的提示文案，否则 None。

        时长从**面试记录创建**算起，所以语音与文字共用同一个时钟：用户语音聊了 2 分钟
        再切到文字，也只剩 1 分钟。

        返回 None 的三种情况：非演示环境（不限制）、本会话还没开始面试（这一轮就是开始）、
        以及还没到点。
        """
        max_minutes = UsageQuotaService.interview_max_minutes()
        if max_minutes <= 0:
            return None

        interview = InterviewService.get_running_interview(
            db, user_id=user_id, session_id=session_id
        )
        if interview is None:
            return None

        remaining = UsageQuotaService.interview_remaining_seconds(interview.created_at)
        if remaining is None or remaining > 0:
            return None

        # 到点：顺手把面试记录结束掉（冻结时长），避免它一直停在「进行中」。
        # 前端刷新后看到的就是「已结束」，可以直接进复盘。
        try:
            InterviewService.finish(db, user_id=user_id, interview_id=interview.id)
            main_logger.info(
                f"[模拟面试] 已达演示环境时长上限，自动结束 "
                f"interview_id={interview.id} 超时={-remaining}s"
            )
        except Exception as exc:  # noqa: BLE001 —— 结束失败也不要挡住提示
            db.rollback()
            main_logger.warning(f"[模拟面试] 自动结束失败 interview_id={interview.id}: {exc!r}")

        return UsageQuotaService.interview_timeout_message(max_minutes)

    @staticmethod
    def _build_notice_response(db: Session, *, row: ChatMessage, text: str) -> StreamingResponse:
        """把一段固定提示当作正常回答返回（**不调用模型**）。

        为什么不直接返回 4xx：接口成功了、用户也确实该看到这段话，只是内容不是模型生成的。
        复用正常的 SSE 事件序列，前端不需要为这种情况写第二套渲染逻辑。
        """
        row.response_text = text
        db.add(row)
        db.commit()

        def notice_generator() -> Generator[str, None, None]:
            yield _sse_data({"type": "start", "message_id": row.id})
            yield _sse_data({"type": "delta", "text": text})
            yield _sse_data(
                {
                    "type": "done",
                    "response_text": text,
                    "stopped": True,
                    "quiz_paper_id": None,
                    "profile_proposal_id": None,
                    "interview_id": row.interview_id,
                }
            )

        return StreamingResponse(
            notice_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @staticmethod
    def _persist_quiz_if_any(
        db: Session, row: ChatMessage, scene: str, response_text: str
    ) -> int | None:
        """刷题场景下，若这轮回复能解析成题库就落库，并返回卷子 id。

        返回 None 表示「这轮不是出题」——绝大多数轮次（还在确认参数）都是这个结果，
        属于正常路径，不打错误日志。落库失败只回滚本次写入，不影响已经存好的消息。
        """
        if scene != QUIZ_SCENE:
            return None

        payload = parse_quiz_payload(response_text)
        if payload is None:
            return None

        message_id = row.id
        try:
            paper = save_quiz_paper(
                db,
                user_id=row.user_id,
                session_id=row.session_id,
                message_id=message_id,
                payload=payload,
            )
            # 标记入口消息：前端靠 status=3 认出「这条消息该渲染答题卡片」。
            row.status = MESSAGE_STATUS_QUIZ_ENTRY
            db.add(row)
            db.commit()
            main_logger.info(
                f"[题库落库] message_id={message_id} paper_id={paper.id} "
                f"题量={payload.question_count} 岗位={payload.target_job} "
                f"难度={payload.difficulty}"
            )
            return paper.id
        except Exception as exc:  # noqa: BLE001
            # 落库失败不该影响这次对话已经返回的内容：回滚本次写入，
            # 但消息本身（response_text）已经在上一步提交过了，不会丢。
            db.rollback()
            existing = get_paper_by_message(db, message_id)
            main_logger.exception(
                f"[题库落库] message_id={message_id} 写入失败，已回滚", exc_info=exc
            )
            return existing.id if existing is not None else None

    @staticmethod
    def _persist_profile_proposal_if_any(
        db: Session,
        row: ChatMessage,
        scene: str,
        request_text: str,
        attachment_text: str,
        provider: str,
    ) -> int | None:
        """简历优化场景下，从本轮内容里抽一次画像，落成「待确认」记录并返回其 id。

        对应 T6.2（决策 D11）：**不直接写 user_profiles**，先给用户确认。

        几个刻意的取舍：
        - 抽取是一次额外的同步模型调用，会推迟 `done` 事件几秒。用户此时已经看到完整
          回复（delta 早就流完了），只是输入框多转几秒；比起让前端再发一次请求、或者
          把抽取塞进主链路，这样最简单也最不易漏。
        - 输入太短时直接跳过：纯提问（「简历怎么写」）不含简历内容，白花一次调用。
        - 任何失败都只记日志、返回 None，绝不影响已经返回给用户的回答。
        """
        if scene != RESUME_SCENE:
            return None

        resume_text = "\n\n".join(
            part for part in [request_text, attachment_text] if part and part.strip()
        )
        if len(resume_text) < PROFILE_EXTRACT_MIN_CHARS:
            return None

        payload = extract_profile(
            db=db, user_id=row.user_id, resume_text=resume_text, provider=provider
        )
        if payload is None or payload.is_empty:
            return None

        message_id = row.id
        try:
            proposal = ProfileProposalService.create_proposal(
                db=db,
                user_id=row.user_id,
                session_id=row.session_id,
                message_id=message_id,
                payload=payload,
            )
            row.status = MESSAGE_STATUS_PROFILE_PENDING
            db.add(row)
            db.commit()
            main_logger.info(
                f"[画像待确认] message_id={message_id} proposal_id={proposal.id} "
                f"岗位={payload.target_job} 级别={payload.target_level}"
            )
            return proposal.id
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            main_logger.exception(
                f"[画像待确认] message_id={message_id} 写入失败，已回滚", exc_info=exc
            )
            return None

    @staticmethod
    def _persist_interview_round_if_any(
        db: Session,
        row: ChatMessage,
        scene: str,
        request_text: str,
        response_text: str,
        stopped: bool,
        error_message: str,
    ) -> int | None:
        """模拟面试场景下，把这一轮写进面试记录，返回面试记录 id。

        对应 T7.4 / T7.5，规则见 `docs/TODO.md` T7.2：先回填上一题的答案，
        再追加这一轮的问题；用户中途停止或报错时不追加问题，但**答案照留**。

        任何失败只记日志、返回 None——面试记录写失败不该影响用户已经拿到的回答。
        """
        if scene != INTERVIEW_SCENE:
            return None

        try:
            interview_id = InterviewService.record_round(
                db=db,
                user_id=row.user_id,
                session_id=row.session_id,
                message_id=row.id,
                request_text=request_text,
                response_text=response_text,
                response_ok=not stopped and not error_message,
            )
            if interview_id is None:
                return None
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            main_logger.exception(
                f"[模拟面试] message_id={row.id} 面试记录写入失败，已回滚", exc_info=exc
            )
            return None

        # 停止路径上消息状态保持「用户主动停止」：建面试记录时会把入口消息标成 1，
        # 这里再盖回去，免得前端把一条被停止的消息当成正常的面试入口。
        if stopped or error_message:
            try:
                row.status = MESSAGE_STATUS_STOPPED
                db.add(row)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                main_logger.warning(f"[模拟面试] message_id={row.id} 状态回写失败: {exc!r}")
        return interview_id

    @staticmethod
    def stop_stream(db: Session, user_id: int, session_id: int, message_id: int) -> bool:
        """登记停止标志，返回本次调用是否首次登记（用于幂等反馈）。

        消息必须属于当前用户且属于该会话；校验不通过抛 404，
        避免越权停止他人会话。
        """
        belongs = db.scalar(
            select(ChatMessage.id).where(
                ChatMessage.id == message_id,
                ChatMessage.user_id == user_id,
                ChatMessage.session_id == session_id,
            )
        )
        if not belongs:
            raise_error(code=404, message="消息不存在")

        first_time = stream_cancel_registry.request_cancel(message_id)
        main_logger.info(
            f"[流式停止] 收到停止请求 message_id={message_id} first_time={first_time}"
        )
        return first_time
