"""面试复盘服务：把一场面试的问答记录变成结构化评测结果（对应 T8.1 / T8.2 / T8.4）。

设计取舍：

- **复用刷题评测那一套做法**：契约（`EVALUATION_JSON_CONTRACT`）由提示词与解析器共用，
  解析器不抛异常，拿不到就当这次生成失败。两处保持一致，避免「提示词改了、解析器没跟上」。
- **编排用同步单次调用**：复盘读的是一份已经落库的问答记录，不是流式对话，
  用户点一次等一个结果即可。多节点流转（取记录 → 评分 → 抽薄弱点 → 给建议）
  目前由一次结构化输出完成；真需要拆节点时再上 LangGraph，别为一张纯函数的图付复杂度。
- **薄弱点写回记忆**：T9.6 起走 `UserMemoryService.ingest` 这个统一入口（T8.4 与 T5.8 共用），
  不另写一套合并逻辑（这是 T8.4 的要求）。
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.prompt_layer import build_personalized_prompt
from app.core import raise_error
from app.core.logging_config import main_logger
from app.core.request_context import set_scene
from app.core.settings import settings
from app.db.models import Interview, InterviewEvaluation
from app.services.usage_quota_service import SCENE_EVALUATION
from app.services.resource_service import ResourceService
from app.services.memory_search_service import (
    SOURCE_EVALUATION,
    MemorySearchService,
)
from app.services.user_memory_service import (
    CATEGORY_WEAK_TOPIC,
    SOURCE_BEHAVIOR,
    MemoryEntry,
    UserMemoryService,
)
from app.services.volc_speech.asr_client import transcribe_file_bytes
from app.services.interview_service import InterviewService

# 复盘来源标记，与 interview_evaluations.source 对齐。
SOURCE_QA = 0  # 用面试记录里的问答文本
SOURCE_AUDIO = 1  # 用上传的录音转写

# 录音转写没有「提问 / 回答」的区分，要在提示词里说明清楚，
# 否则模型会按「问答记录」去理解，把一整段独白当成回答错位。
RECORDING_PREFIX = (
    "以下是一段真实面试录音的转写文本（**没有区分面试官提问与候选人回答**，"
    "可能含口头语与识别误差）。请按同样的复盘要求给出总结、薄弱点与改进建议：\n\n"
)

# 复盘用的内部 agent / 场景（对应 prompt_templates 里 seed 进去的模板）。
EVALUATOR_AGENT = "interview_evaluator"
EVALUATION_SCENE = "evaluation"

# 提示词里直接引用的结构约定。改这里就等于改提示词。
EVALUATION_JSON_CONTRACT = (
    '{"summary": "整体表现总结", "weak_topics": ["薄弱知识点"], "suggestions": ["改进建议"]}'
)

_CODE_FENCE_MARKERS = ("```json", "```JSON", "```")


@dataclass(frozen=True)
class EvaluationPayload:
    """一次复盘的解析结果。"""

    summary: str
    weak_topics: list[str]
    suggestions: list[str]


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    for marker in _CODE_FENCE_MARKERS:
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :]
            break
    if stripped.endswith("```"):
        stripped = stripped[: -len("```")]
    return stripped.strip()


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_list(value: Any) -> list[str]:
    """归一字符串列表：去空白、去重、保持顺序。"""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        text = _normalize_text(entry)
        if text and text not in items:
            items.append(text)
    return items


def parse_evaluation_payload(text: str) -> EvaluationPayload | None:
    """从模型输出里解析复盘结果；解析不出来返回 None（不抛异常）。

    至少要有一个字段有内容才算成功——否则说明这轮模型啥也没吐。
    """
    if not text or not text.strip():
        return None

    candidate = _strip_code_fence(text)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(candidate[start : end + 1])
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    payload = EvaluationPayload(
        summary=_normalize_text(data.get("summary")) or "",
        weak_topics=_normalize_list(data.get("weak_topics")),
        suggestions=_normalize_list(data.get("suggestions")),
    )
    if not payload.summary and not payload.weak_topics and not payload.suggestions:
        return None
    return payload


def build_qa_transcript(interview: Interview) -> str:
    """把 `qa_object` 拼成给模型看的问答记录。"""
    lines: list[str] = []
    for index, item in enumerate(interview.qa_object or [], start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question and not answer:
            continue
        lines.append(f"【第 {index} 题】面试官：{question}")
        lines.append(f"候选人：{answer or '（未作答）'}")
    return "\n".join(lines)


_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")


def _split_sentences(text: str) -> list[str]:
    """按中文标点粗分句，用于给录音复盘记一个「输入规模」的数字。

    不是精确的语言学分句，只是给回显提供一个参考量，别当严谨指标用。
    """
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


class InterviewEvaluationService:
    """生成 / 读取 / 写回一场面试的复盘结果。"""

    @staticmethod
    def _index_evaluation(db: Session, *, evaluation: InterviewEvaluation) -> None:
        """把复盘结果写进 L3 检索索引（T9.14）：复盘结论也属于「值得以后搜回来的东西」。"""
        content = "\n".join(
            [
                evaluation.summary,
                "薄弱点：" + "、".join(evaluation.weak_topics or []),
                "改进建议：" + "；".join(evaluation.suggestions or []),
            ]
        )
        try:
            MemorySearchService.index_document(
                db,
                user_id=evaluation.user_id,
                source_type=SOURCE_EVALUATION,
                source_id=evaluation.id,
                title=f"面试复盘（{evaluation.qa_count} 轮）",
                content=content,
                created_at=evaluation.created_at,
                commit=True,
            )
        except Exception as exc:  # noqa: BLE001
            # 索引失败不影响复盘结果本身（已经落库了）
            db.rollback()
            main_logger.warning(
                f"[检索索引] evaluation_id={evaluation.id} 写入失败: {exc!r}"
            )

    @staticmethod
    def _write_weak_topics(
        db: Session, *, user_id: int, weak_topics: list[str]
    ) -> None:
        """把复盘出的薄弱点写进长期记忆（统一入口，T8.4 / T9.6）。

        复盘产出的薄弱点已经是知识点级别的结构化条目，所以**不再跑一次 T9.5 的模型抽取**：
        那既费一次调用，又只会把已经归纳好的结论重新拆散。模型抽取留给
        「简历正文 / 用户自述」这类非结构化输入。
        """
        if not weak_topics:
            return
        UserMemoryService.ingest(
            db,
            user_id=user_id,
            entries=[
                MemoryEntry(
                    category=CATEGORY_WEAK_TOPIC, name=topic, mastery=30, confidence=70
                )
                for topic in weak_topics
            ],
            source=SOURCE_BEHAVIOR,
            commit=False,
        )

    @staticmethod
    def get_or_404(db: Session, *, user_id: int, interview_id: int) -> Interview:
        """按 interview_id 取面试记录（复用 `InterviewService` 的归属校验口径）。"""
        return InterviewService.get_or_404(
            db, user_id=user_id, interview_id=interview_id
        )

    @staticmethod
    def get_evaluation(
        db: Session, *, interview_id: int
    ) -> InterviewEvaluation | None:
        """读已生成的复盘结果；没生成过返回 None。"""
        return db.scalar(
            select(InterviewEvaluation).where(
                InterviewEvaluation.interview_id == interview_id
            )
        )

    @staticmethod
    def generate(
        db: Session,
        *,
        user_id: int,
        interview_id: int,
        provider: str = "deepseek",
    ) -> tuple[InterviewEvaluation, EvaluationPayload]:
        """生成（或重新生成）复盘结果，并把薄弱点合并进用户画像。

        重新生成是覆盖式的：面试记录可能还在变（用户又答了几轮），
        每次生成以最新的问答记录为准。
        """
        interview = InterviewEvaluationService.get_or_404(
            db, user_id=user_id, interview_id=interview_id
        )
        transcript = build_qa_transcript(interview)
        if not transcript.strip():
            raise_error(code=409, message="这场面试还没有问答记录，无法复盘")

        payload = InterviewEvaluationService._call_model(
            db=db, user_id=user_id, transcript=transcript, provider=provider
        )

        row = InterviewEvaluationService.get_evaluation(
            db, interview_id=interview_id
        )
        if row is None:
            row = InterviewEvaluation(
                user_id=user_id,
                interview_id=interview_id,
                summary="",
                weak_topics=[],
                suggestions=[],
            )
            db.add(row)

        row.summary = payload.summary
        row.weak_topics = list(payload.weak_topics)
        row.suggestions = list(payload.suggestions)
        row.source = SOURCE_QA
        row.resource_id = None
        # 记下评测时的问答条数：回显时能看出「复盘之后面试记录又变了」
        row.qa_count = len(interview.qa_object or [])

        # T8.4 / T9.6：薄弱点写回记忆，走统一入口（合并规则与来源权重都在那一处）
        InterviewEvaluationService._write_weak_topics(
            db, user_id=user_id, weak_topics=payload.weak_topics
        )

        db.commit()
        db.refresh(row)
        InterviewEvaluationService._index_evaluation(db, evaluation=row)
        main_logger.info(
            f"[面试复盘] interview_id={interview_id} 问答={row.qa_count} "
            f"薄弱点={len(payload.weak_topics)} 建议={len(payload.suggestions)}"
        )
        return row, payload

    @staticmethod
    def generate_from_audio(
        db: Session,
        *,
        user_id: int,
        interview_id: int,
        resource_id: int,
        provider: str = "deepseek",
    ) -> tuple[InterviewEvaluation, EvaluationPayload, str]:
        """用**上传的面试录音**生成复盘（T8.3，方案 A：挂在已有面试记录上）。

        流程：取录音 → 整段识别转写 → 走与问答复盘同一套评测 → 落库（覆盖同一行）。
        返回 (复盘记录, 解析结果, 转写文本)，转写文本给前端展示「AI 听到的是什么」。

        资源归属校验复用 `ResourceService`：别人的录音一律 404，不会越权读取。
        """
        interview = InterviewEvaluationService.get_or_404(
            db, user_id=user_id, interview_id=interview_id
        )
        resource = ResourceService.get_resource_or_404(
            db, user_id=user_id, resource_id=resource_id
        )
        data, _mime = ResourceService.read_content(
            db, user_id=user_id, resource_id=resource_id
        )
        if not data:
            raise_error(code=409, message="录音文件是空的，无法复盘")

        try:
            transcript = asyncio.run(
                transcribe_file_bytes(
                    data,
                    file_name=resource.file_name,
                    url=settings.volc_asr_file_url,
                    api_key=settings.volc_api_key,
                    resource_id=settings.volc_asr_resource_id,
                )
            )
        except ValueError as exc:
            # 不支持的音频格式：这是用户可修的输入问题，用 400 而不是 500
            raise_error(code=400, message=str(exc))
        except Exception as exc:  # noqa: BLE001
            main_logger.exception("面试复盘：录音转写失败", exc_info=exc)
            raise_error(code=502, message="录音转写失败，请稍后重试")

        if not transcript.strip():
            raise_error(code=409, message="录音里没有识别到内容，请换一段更清晰的录音")

        payload = InterviewEvaluationService._call_model(
            db=db,
            user_id=user_id,
            transcript=RECORDING_PREFIX + transcript,
            provider=provider,
        )

        row = InterviewEvaluationService.get_evaluation(db, interview_id=interview_id)
        if row is None:
            row = InterviewEvaluation(
                user_id=user_id,
                interview_id=interview_id,
                summary="",
                weak_topics=[],
                suggestions=[],
            )
            db.add(row)

        row.summary = payload.summary
        row.weak_topics = list(payload.weak_topics)
        row.suggestions = list(payload.suggestions)
        row.source = SOURCE_AUDIO
        row.resource_id = resource_id
        # 录音没有「问答条数」，这里记转写出多少个句子，含义在模型注释里写明了
        row.qa_count = len(_split_sentences(transcript))

        if payload.weak_topics:
            InterviewEvaluationService._write_weak_topics(
                db, user_id=user_id, weak_topics=payload.weak_topics
            )

        db.commit()
        db.refresh(row)
        InterviewEvaluationService._index_evaluation(db, evaluation=row)
        main_logger.info(
            f"[面试复盘] interview_id={interview_id} 来源=录音 "
            f"resource_id={resource_id} 转写={len(transcript)}字 分句={row.qa_count}"
        )
        return row, payload, transcript

    @staticmethod
    def _call_model(
        db: Session, *, user_id: int, transcript: str, provider: str
    ) -> EvaluationPayload:
        """调一次模型做复盘；解析失败抛 502，让调用方回滚。"""
        system_prompt = build_personalized_prompt(
            db=db, user_id=user_id, agent_name=EVALUATOR_AGENT, scene=EVALUATION_SCENE
        )
        if not system_prompt:
            # 模板没 seed 时兜底，保证链路可用（与其它链路口径一致）
            system_prompt = (
                "你是资深技术面试官，负责复盘一场模拟面试，"
                "输出整体表现总结、薄弱知识点与可执行的改进建议。"
            )

        # 标记场景：面试复盘（T12.4 按场景计配额）
        set_scene(SCENE_EVALUATION)
        model = get_chat_model(provider=provider)
        message = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ]
        )
        content = message.content if isinstance(message.content, str) else str(message.content)
        payload = parse_evaluation_payload(content)
        if payload is None:
            raise_error(code=502, message="复盘结果解析失败，请稍后重试")
        return payload
