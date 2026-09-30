"""刷题评分服务：组卷子的作答发给模型，把评分结果写回题目行。

和出题链路不同，这里是**一次性同步调用**，不走流式：评分没有「边算边给用户看」
的需求，用户点提交等一个结果就行。所以用 LangChain 的普通调用，不建 LangGraph 图。

对应 T5.7。薄弱点写回用户画像属于 T5.8，这里只负责**算出来并返回**。
"""

from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.prompt_layer import build_personalized_prompt
from app.core import raise_error
from app.core.logging_config import main_logger
from app.core.request_context import set_scene
from app.db.models import QuizPaper, QuizQuestion
from app.services.quiz_service import (
    QUIZ_STATUS_GRADED,
    QUIZ_STATUS_PENDING,
    QUIZ_STATUS_SUBMITTED,
    QuizEvaluation,
    apply_evaluation,
    get_paper_or_404,
    list_questions,
    parse_quiz_evaluation,
)
from app.services.user_memory_service import (
    CATEGORY_WEAK_TOPIC,
    SOURCE_BEHAVIOR,
    MemoryEntry,
    UserMemoryService,
)
from app.services.usage_quota_service import SCENE_QUIZ

# 评分用的内部 agent / 场景（对应 prompt_templates 里 seed 进去的模板）。
QUIZ_EVALUATOR_AGENT = "quiz_evaluator"
QUIZ_SCENE = "quiz"

# 参考答案缺失时的占位文案，让模型知道这题没留标准答案、按通用标准判。
NO_REFERENCE_ANSWER = "（本题未提供参考答案，请按该知识点的通用标准评判）"


def _build_grading_input(
    paper: QuizPaper, questions: list[QuizQuestion]
) -> str:
    """把「题干 + 参考答案 + 用户作答」拼成一段纯文本给模型。"""
    lines: list[str] = []
    meta_bits = [f"岗位：{paper.target_job or '未指定'}", f"难度：{paper.difficulty or '未指定'}"]
    lines.append("卷子信息：" + "；".join(meta_bits))
    lines.append(f"题量：{len(questions)}")
    lines.append("")
    lines.append("以下是逐题的题干、参考答案与用户作答：")

    for question in questions:
        lines.append("")
        lines.append(f"【第 {question.order_index} 题】")
        lines.append(f"题干：{question.question}")
        lines.append(f"参考答案：{question.reference_answer or NO_REFERENCE_ANSWER}")
        user_answer = (question.user_answer or "").strip()
        lines.append(f"用户作答：{user_answer or '（未作答）'}")

    return "\n".join(lines)


class QuizEvaluationService:
    """提交答案 → 评分 → 写回。"""

    @staticmethod
    def submit(
        db: Session,
        *,
        user_id: int,
        paper_id: int,
        answers: dict[int, str],
        provider: str = "deepseek",
    ) -> tuple[QuizPaper, list[QuizQuestion], QuizEvaluation]:
        """接收作答、调用模型评分、写回数据库，返回（卷子, 题目, 评分结果）。

        `answers` 的键是 `order_index`（题号），值是用户作答文本。

        校验：
        - 卷子必须属于当前用户（否则 404）；
        - 一份卷子**只允许评分一次**（T5.2 的约定），已评分的卷子再提交返回 409。

        分两次提交的好处：**用户作答先落库**（status=1 已提交），再调模型评分。
        评分失败（比如模型输出解析不出来）时抛 502，但用户的答案已经保住了，
        换个时间重试即可——重试时 `answers` 可以传空，直接用库里存着的作答重评。
        """
        paper = get_paper_or_404(db=db, user_id=user_id, paper_id=paper_id)
        if paper.status == QUIZ_STATUS_GRADED:
            raise_error(code=409, message="这份题库已经评分过了")

        questions = list_questions(db=db, paper_id=paper.id)
        if not questions:
            raise_error(code=409, message="这份题库没有题目，无法评分")

        # 1) 先把用户作答写进题目行并提交：评分是外部调用，失败概率不为零，
        #    用户的答案不能跟着评分一起丢。
        by_index = {question.order_index: question for question in questions}
        for order_index, answer in answers.items():
            question = by_index.get(order_index)
            if question is None:
                continue
            question.user_answer = answer
            db.add(question)
        paper.status = QUIZ_STATUS_SUBMITTED
        db.add(paper)
        db.commit()
        db.refresh(paper)
        for question in questions:
            db.refresh(question)

        # 2) 调模型评分。
        evaluation = QuizEvaluationService._grade(
            db=db,
            user_id=user_id,
            paper=paper,
            questions=questions,
            provider=provider,
        )

        # 3) 写回评分与解析，并把薄弱点合并进用户画像。
        #    两件事放在同一个事务里提交：要么都成功，要么都回滚——
        #    不会出现「卷子已评分但画像没更新、重试又被 409 挡住」的尴尬状态。
        apply_evaluation(db, paper=paper, questions=questions, evaluation=evaluation)
        # T9.6：写入记忆统一走 `UserMemoryService.ingest`——合并规则、来源权重、
        # 派生缓存重建都在那一处，三个业务场景共用，不再各写一套。
        # 这里**不调用 T9.5 的模型抽取**：评分结果里的 weak_topics 已经是知识点级别的
        # 结构化条目，再让模型抽一遍既费钱又只会丢信息。
        if evaluation.weak_topics:
            UserMemoryService.ingest(
                db,
                user_id=user_id,
                entries=[
                    MemoryEntry(
                        category=CATEGORY_WEAK_TOPIC, name=topic, mastery=30, confidence=70
                    )
                    for topic in evaluation.weak_topics
                ],
                source=SOURCE_BEHAVIOR,
                commit=False,
            )
        db.commit()
        db.refresh(paper)
        for question in questions:
            db.refresh(question)

        main_logger.info(
            f"[题库评分] paper_id={paper.id} 总分={evaluation.total_score} "
            f"薄弱点={len(evaluation.weak_topics)} 逐题解析={len(evaluation.questions)}"
        )
        return paper, questions, evaluation

    @staticmethod
    def _grade(
        db: Session,
        *,
        user_id: int,
        paper: QuizPaper,
        questions: list[QuizQuestion],
        provider: str,
    ) -> QuizEvaluation:
        """调一次模型完成整卷评分；输出解析不出来时抛 502，由调用方回滚。"""
        system_prompt = build_personalized_prompt(
            db=db,
            user_id=user_id,
            agent_name=QUIZ_EVALUATOR_AGENT,
            scene=QUIZ_SCENE,
        )
        if not system_prompt:
            # 模板没 seed 进去时兜底，保证链路可用（与流式链路的兜底口径一致）。
            system_prompt = "你是严谨的技术面试官，负责批改笔试题并给出薄弱点。"

        grading_input = _build_grading_input(paper, questions)
        # 标记场景：答卷评分（T12.4 按场景计配额）
        set_scene(SCENE_QUIZ)
        model = get_chat_model(provider=provider)
        message = model.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": grading_input},
            ]
        )
        content = message.content if isinstance(message.content, str) else str(message.content)

        evaluation = parse_quiz_evaluation(content)
        if evaluation is None:
            raise_error(
                code=502,
                message="评分结果解析失败，请稍后重试",
            )
        return evaluation
