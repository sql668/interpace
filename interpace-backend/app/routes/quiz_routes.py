"""刷题评测路由：按会话列出卷子、按 paper_id 拉取卷子详情。

路由只做接入与参数校验，查询与归属校验放在 `QuizService`（分层写法对齐笔记路由）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas.quiz_schemas import (
    QuizPaperDetail,
    QuizPaperItem,
    QuizPaperListResponse,
    QuizQuestionItem,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.quiz_evaluation_service import QuizEvaluationService
from app.services.quiz_service import (
    get_paper_or_404,
    list_papers_by_session,
    list_questions,
)

router = APIRouter()
# 统一依赖别名，减少每个路由函数重复书写 Depends。
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=QuizPaperListResponse,
    responses=common_error_responses,
    summary="按会话列出题库",
)
def list_quiz_papers(
    db: DBSession,
    current_user: CurrentUser,
    session_id: Annotated[int, Query(gt=0, description="会话ID")],
) -> QuizPaperListResponse:
    """列出当前用户在某会话里的全部卷子（不含题目）。

    前端刷新页面后，用返回的 `message_id → id` 映射给历史消息补上答题卡片。
    """
    papers = list_papers_by_session(
        db=db, user_id=current_user.id, session_id=session_id
    )
    return QuizPaperListResponse(
        items=[QuizPaperItem.model_validate(paper) for paper in papers],
        total=len(papers),
    )


@router.get(
    "/{paper_id}",
    response_model=QuizPaperDetail,
    responses=common_error_responses,
    summary="获取题库详情",
)
def get_quiz_paper(
    paper_id: Annotated[int, Path(gt=0, description="题库ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> QuizPaperDetail:
    """按 paper_id 拉取卷子与题目；**返回的题目不含参考答案**。"""
    paper = get_paper_or_404(db=db, user_id=current_user.id, paper_id=paper_id)
    questions = list_questions(db=db, paper_id=paper.id)
    # 卷子本体没有 questions 关系属性，所以先从列表项复用字段，再挂上题目列表。
    return QuizPaperDetail(
        **QuizPaperItem.model_validate(paper).model_dump(),
        questions=[QuizQuestionItem.model_validate(q) for q in questions],
    )


@router.post(
    "/{paper_id}/submissions",
    response_model=QuizSubmitResponse,
    responses=common_error_responses,
    summary="提交答案并评分",
)
def submit_quiz_paper(
    paper_id: Annotated[int, Path(gt=0, description="题库ID")],
    payload: QuizSubmitRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> QuizSubmitResponse:
    """提交整卷作答，同步评分并返回总分、薄弱点与逐题解析。

    一份卷子只评分一次；已评分的卷子再提交返回 409。
    """
    answers = {item.order_index: item.answer for item in payload.answers}
    paper, questions, evaluation = QuizEvaluationService.submit(
        db=db,
        user_id=current_user.id,
        paper_id=paper_id,
        answers=answers,
    )
    return QuizSubmitResponse(
        paper_id=paper.id,
        status=paper.status,
        total_score=evaluation.total_score,
        weak_topics=evaluation.weak_topics,
        questions=[QuizQuestionItem.model_validate(q) for q in questions],
    )
