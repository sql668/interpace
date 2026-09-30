"""刷题评测服务：题库的结构化契约、解析与校验。

整条刷题链路都建立在一个假设上——**模型能稳定输出可解析的题库 JSON**。
所以这里把「契约」和「解析」放在一起，并且 `QUIZ_JSON_CONTRACT` 会被提示词
直接引用，保证提示词里写的结构和解析器认的结构永远是同一份。

对应 T5.4。解析容错点都是实测里常见的：外面套了 ```json 代码块、前后带解释文字。
"""

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import QuizPaper, QuizQuestion

# 难度取值，与 quiz_papers.difficulty 的注释保持一致。
DIFFICULTY_LEVELS = ("初级", "中级", "高级")

# quiz_papers.status 的取值，与模型注释保持一致。
QUIZ_STATUS_PENDING = 0  # 待作答
QUIZ_STATUS_SUBMITTED = 1  # 已提交（当前评分是同步的，这个状态只在评分进行中短暂存在）
QUIZ_STATUS_GRADED = 2  # 已评分

# 提示词里直接引用的结构约定。改这里就等于改提示词，避免两边写岔。
QUIZ_JSON_CONTRACT = (
    '{"target_job": "目标岗位", "difficulty": "初级|中级|高级", '
    '"question_count": 整数, '
    '"questions": [{"question": "题干", "reference_answer": "参考答案"}]}'
)

# 模型偶尔会用代码块包裹 JSON，解析前先剥掉。
_CODE_FENCE_MARKERS = ("```json", "```JSON", "```")

# 评分环节的输出契约，同样被提示词与解析器共用。
QUIZ_EVALUATION_JSON_CONTRACT = (
    '{"total_score": 整数0-100, "weak_topics": ["薄弱知识点"], '
    '"questions": [{"order_index": 整数, "score": 整数0-100, "analysis": "逐题点评"}]}'
)


@dataclass(frozen=True)
class QuizQuestionPayload:
    """一道题：题干 + 参考答案。"""

    question: str
    reference_answer: str | None = None


@dataclass(frozen=True)
class QuizPayload:
    """一份卷子：参数 + 题目列表。"""

    target_job: str | None
    difficulty: str | None
    questions: list[QuizQuestionPayload]

    @property
    def question_count(self) -> int:
        """题目数量以**实际列表长度**为准，不采信模型自报的数字。"""
        return len(self.questions)


@dataclass(frozen=True)
class QuizEvaluationQuestion:
    """一道题的评分结果。"""

    order_index: int
    score: int | None = None
    analysis: str | None = None


@dataclass(frozen=True)
class QuizEvaluation:
    """一份卷子的评分结果。"""

    total_score: int | None
    weak_topics: list[str]
    questions: list[QuizEvaluationQuestion]


def _strip_code_fence(text: str) -> str:
    """剥掉可能包裹 JSON 的 Markdown 代码块标记。"""
    stripped = text.strip()
    for marker in _CODE_FENCE_MARKERS:
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :]
            break
    if stripped.endswith("```"):
        stripped = stripped[: -len("```")]
    return stripped.strip()


def _extract_json_object(text: str) -> str | None:
    """从可能夹着解释文字的输出里取出那个 JSON 对象。

    取第一个 `{` 到最后一个 `}`：模型偶尔会在 JSON 前后写一句话，
    而这个契约下输出里只应该有一个对象，这个近似取法足够稳。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalize_text(value: Any) -> str | None:
    """把可选文本字段归一成「去空白的字符串」或 None。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_quiz_payload(text: str) -> QuizPayload | None:
    """从模型输出里解析题库；解析不出来返回 None，由调用方决定怎么兜底。

    **不抛异常**：这是流式回答的最后一步，解析失败只意味着「这轮不是出题」，
    不应该把整个对话打断。
    """
    if not text or not text.strip():
        return None

    candidate = _extract_json_object(_strip_code_fence(text))
    if candidate is None:
        return None

    try:
        data = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        return None

    questions: list[QuizQuestionPayload] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question_text = _normalize_text(item.get("question"))
        if not question_text:
            # 没有题干的条目直接丢——留着只会污染题库
            continue
        questions.append(
            QuizQuestionPayload(
                question=question_text,
                reference_answer=_normalize_text(item.get("reference_answer")),
            )
        )

    if not questions:
        return None

    difficulty = _normalize_text(data.get("difficulty"))
    if difficulty and difficulty not in DIFFICULTY_LEVELS:
        # 难度不在预期取值里不当作失败，原样保留，由上层决定怎么显示
        main_logger.warning(f"题库返回了预期外的难度取值: {difficulty}")

    return QuizPayload(
        target_job=_normalize_text(data.get("target_job")),
        difficulty=difficulty,
        questions=questions,
    )


def get_paper_by_message(db: Session, message_id: int) -> QuizPaper | None:
    """按入口消息查卷子；没有就返回 None。"""
    return db.scalar(select(QuizPaper).where(QuizPaper.message_id == message_id))


def list_papers_by_session(db: Session, user_id: int, session_id: int) -> list[QuizPaper]:
    """列出某个会话里的全部卷子（按创建时间升序）。

    查询条件带上 `user_id`：别人的卷子一律不返回，和笔记服务同一套隔离口径。
    前端刷新后用「message_id → paper_id」的映射给历史消息补答题卡片。
    """
    return list(
        db.scalars(
            select(QuizPaper)
            .where(QuizPaper.user_id == user_id, QuizPaper.session_id == session_id)
            .order_by(QuizPaper.id)
        )
    )


def get_paper_or_404(db: Session, user_id: int, paper_id: int) -> QuizPaper:
    """按 paper_id 取卷子；不存在或不属于当前用户时抛 404。"""
    paper = db.scalar(
        select(QuizPaper).where(
            QuizPaper.id == paper_id, QuizPaper.user_id == user_id
        )
    )
    if paper is None:
        raise_error(code=404, message="题库不存在")
    return paper


def list_questions(db: Session, paper_id: int) -> list[QuizQuestion]:
    """按序号列出某份卷子的题目。"""
    return list(
        db.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.paper_id == paper_id)
            .order_by(QuizQuestion.order_index)
        )
    )


def _normalize_score(value: Any) -> int | None:
    """把得分归一成 0-100 的整数；不是数字就返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def _normalize_index(value: Any) -> int | None:
    """把题号归一成正整数；不是正整数就返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    return index if index > 0 else None


def parse_quiz_evaluation(text: str) -> QuizEvaluation | None:
    """从模型的评分输出里解析结果；解析不出来返回 None。

    与 `parse_quiz_payload` 同一套容错口径：剥代码块、取首尾花括号、不抛异常。
    `questions` 允许为空列表——模型可能只给了总分和薄弱点，逐题解析可以后补。
    """
    if not text or not text.strip():
        return None

    candidate = _extract_json_object(_strip_code_fence(text))
    if candidate is None:
        return None

    try:
        data = json.loads(candidate)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    raw_topics = data.get("weak_topics")
    weak_topics: list[str] = []
    if isinstance(raw_topics, list):
        for item in raw_topics:
            topic = _normalize_text(item)
            # 去重但保持模型给的顺序
            if topic and topic not in weak_topics:
                weak_topics.append(topic)

    evaluations: list[QuizEvaluationQuestion] = []
    raw_questions = data.get("questions")
    if isinstance(raw_questions, list):
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            order_index = _normalize_index(item.get("order_index"))
            if order_index is None:
                continue
            evaluations.append(
                QuizEvaluationQuestion(
                    order_index=order_index,
                    score=_normalize_score(item.get("score")),
                    analysis=_normalize_text(item.get("analysis")),
                )
            )

    total_score = _normalize_score(data.get("total_score"))
    if total_score is None and not evaluations and not weak_topics:
        # 三样都没有，基本可以认定这不是一份评分结果
        return None

    return QuizEvaluation(
        total_score=total_score,
        weak_topics=weak_topics,
        questions=evaluations,
    )


def apply_evaluation(
    db: Session,
    *,
    paper: QuizPaper,
    questions: list[QuizQuestion],
    evaluation: QuizEvaluation,
) -> None:
    """把评分结果写回题目行，并把卷子状态推到「已评分」。

    逐题按 `order_index` 对齐；模型漏给某道题时那题保持未评分，不算整体失败
    （参考答案缺了都能容忍，解析缺了更不该整批回滚）。
    只 flush 不 commit，事务边界交给调用方。
    """
    by_index = {question.order_index: question for question in questions}
    for item in evaluation.questions:
        row = by_index.get(item.order_index)
        if row is None:
            continue
        if item.score is not None:
            row.score = item.score
        if item.analysis is not None:
            row.analysis = item.analysis
        db.add(row)

    paper.status = QUIZ_STATUS_GRADED
    db.add(paper)
    db.flush()


def save_quiz_paper(
    db: Session,
    *,
    user_id: int,
    session_id: int,
    message_id: int,
    payload: QuizPayload,
) -> QuizPaper:
    """把解析出的题库落库（卷子 + 题目），返回卷子。

    **幂等**：同一条入口消息已经有卷子时直接返回旧的，不新建、不覆盖——
    用户重放请求或接口重试不该产生第二份卷子（`message_id` 上也有唯一约束兜底）。

    只 flush 不 commit：事务边界交给调用方，落库失败时可以整体回滚，
    不会留下「有卷子没题目」的半截数据。
    """
    existing = get_paper_by_message(db, message_id)
    if existing is not None:
        return existing

    paper = QuizPaper(
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        target_job=payload.target_job,
        difficulty=payload.difficulty,
        question_count=payload.question_count,
        status=0,
    )
    db.add(paper)
    db.flush()  # 拿到 paper.id 才能挂题目

    for order_index, question in enumerate(payload.questions, start=1):
        db.add(
            QuizQuestion(
                paper_id=paper.id,
                order_index=order_index,
                question=question.question,
                reference_answer=question.reference_answer,
            )
        )
    db.flush()
    return paper
