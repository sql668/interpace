"""面试路由：按 interview_id 查询面试记录、生成 / 读取面试复盘。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas.interview_evaluation_schemas import (
    InterviewEvaluationFromAudioRequest,
    InterviewEvaluationFromAudioResponse,
    InterviewEvaluationQueryResponse,
    InterviewEvaluationResponse,
    InterviewEvaluationResult,
    InterviewFinishResponse,
)
from app.schemas import InterviewDetailResponse
from app.services.interview_evaluation_service import InterviewEvaluationService
from app.services.interview_service import InterviewService
from app.services.session_service import SessionService

router = APIRouter()
# 统一数据库会话依赖类型，避免每个接口重复声明。
DBSession = Annotated[Session, Depends(get_db)]
# 统一当前登录用户依赖类型，确保数据按用户隔离。
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/{interview_id}",
    response_model=InterviewDetailResponse,
    responses=common_error_responses,
    summary="获取面试详情",
)
def get_interview_detail(
    interview_id: Annotated[int, Path(gt=0, description="面试记录ID，必须大于0")],
    db: DBSession,
    current_user: CurrentUser,
) -> InterviewDetailResponse:
    """按 interview_id 获取面试详情文本信息。"""
    interview = SessionService.get_interview_detail(
        db=db, user_id=current_user.id, interview_id=interview_id
    )
    return InterviewDetailResponse(
        id=interview.id,
        session_id=interview.session_id,
        message_id=interview.message_id,
        qa_object=interview.qa_object,
        interview_duration=interview.interview_duration,
        status=interview.status,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
    )


@router.post(
    "/{interview_id}/finish",
    response_model=InterviewFinishResponse,
    responses=common_error_responses,
    summary="结束面试",
)
def finish_interview(
    interview_id: Annotated[int, Path(gt=0, description="面试记录ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> InterviewFinishResponse:
    """结束一场模拟面试并把时长冻结（T7.8）。

    **幂等**：重复调用不报错、不改数据，只是 `already_finished=True`。
    复盘不在这里触发——前端结束后再调复盘接口，好处是「结束」瞬时完成，
    生成复盘可以有独立的等待状态，失败了也能单独重试。
    """
    interview, already_finished = InterviewService.finish(
        db, user_id=current_user.id, interview_id=interview_id
    )
    return InterviewFinishResponse(
        message="这场面试之前已经结束了" if already_finished else "面试已结束",
        interview_id=interview.id,
        status=interview.status,
        interview_duration=interview.interview_duration,
        qa_count=len(interview.qa_object or []),
        already_finished=already_finished,
    )


@router.post(
    "/{interview_id}/evaluations",
    response_model=InterviewEvaluationResponse,
    responses=common_error_responses,
    summary="生成面试复盘",
)
def generate_interview_evaluation(
    interview_id: Annotated[int, Path(gt=0, description="面试记录ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> InterviewEvaluationResponse:
    """按面试记录生成复盘（表现总结 + 薄弱点 + 改进建议）。

    会后生成一次；重复调用会**按最新问答记录重新生成并覆盖**。
    薄弱点会同时合并进用户画像（T8.4）。
    """
    evaluation, _payload = InterviewEvaluationService.generate(
        db=db, user_id=current_user.id, interview_id=interview_id
    )
    return InterviewEvaluationResponse(
        message="复盘已生成",
        evaluation=InterviewEvaluationResult.model_validate(evaluation),
    )


@router.post(
    "/{interview_id}/evaluations/from-audio",
    response_model=InterviewEvaluationFromAudioResponse,
    responses=common_error_responses,
    summary="用上传的面试录音生成复盘",
)
def generate_evaluation_from_audio(
    interview_id: Annotated[int, Path(gt=0, description="面试记录ID")],
    payload: InterviewEvaluationFromAudioRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> InterviewEvaluationFromAudioResponse:
    """把上传的面试录音转写成文本后做复盘（T8.3）。

    录音要挂在一场已有的面试记录上（方案 A）：录音本身没有「面试记录」这个实体，
    挂上去才能复用同一张复盘表与回显逻辑。结果会**覆盖**这场面试原有的复盘。

    只支持火山 ASR 能直接解码的格式（wav / mp3 / m4a / aac / ogg / pcm 等），
    我们不做本地解码，声明格式后交给服务端解。
    """
    evaluation, _payload, transcript = InterviewEvaluationService.generate_from_audio(
        db=db,
        user_id=current_user.id,
        interview_id=interview_id,
        resource_id=payload.resource_id,
    )
    return InterviewEvaluationFromAudioResponse(
        message="已根据录音生成复盘",
        evaluation=InterviewEvaluationResult.model_validate(evaluation),
        transcript=transcript,
    )


@router.get(
    "/{interview_id}/evaluations",
    response_model=InterviewEvaluationQueryResponse,
    responses=common_error_responses,
    summary="读取面试复盘",
)
def get_interview_evaluation(
    interview_id: Annotated[int, Path(gt=0, description="面试记录ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> InterviewEvaluationQueryResponse:
    """读已生成的复盘结果；**没生成过返回 200 + `evaluation=null`**，不返回 404。

    404 只留给「面试记录不存在 / 不是你的」——把「还没生成」当错误会让前端
    每次打开面板都触发一次错误响应（全局拦截器还会顺手弹一个红色提示）。
    """
    # 先校验面试记录归属，避免用「有没有复盘」探测他人面试记录是否存在
    InterviewEvaluationService.get_or_404(
        db, user_id=current_user.id, interview_id=interview_id
    )
    evaluation = InterviewEvaluationService.get_evaluation(
        db, interview_id=interview_id
    )
    if evaluation is None:
        return InterviewEvaluationQueryResponse(
            message="这场面试还没有生成复盘", evaluation=None
        )
    return InterviewEvaluationQueryResponse(
        message="已获取复盘结果",
        evaluation=InterviewEvaluationResult.model_validate(evaluation),
    )
