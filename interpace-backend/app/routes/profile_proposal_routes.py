"""画像待确认路由：列出、确认写入、忽略。

对应 T6.2（决策 D11）。路由只做接入与参数校验，业务逻辑在
`ProfileProposalService`（分层写法对齐笔记路由）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas.profile_proposal_schemas import (
    ProfileProposalConfirmRequest,
    ProfileProposalItem,
    ProfileProposalListResponse,
    ProfileProposalResponse,
)
from app.services.profile_proposal_service import ProfileProposalService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=ProfileProposalListResponse,
    responses=common_error_responses,
    summary="按会话列出画像待确认记录",
)
def list_profile_proposals(
    db: DBSession,
    current_user: CurrentUser,
    session_id: Annotated[int, Query(gt=0, description="会话ID")],
) -> ProfileProposalListResponse:
    """列出当前用户在某会话里的待确认记录。

    前端刷新页面后，用返回的 `message_id → id` 映射把确认卡片挂回历史消息。
    """
    proposals = ProfileProposalService.list_by_session(
        db=db, user_id=current_user.id, session_id=session_id
    )
    return ProfileProposalListResponse(
        items=[ProfileProposalItem.from_proposal(item) for item in proposals],
        total=len(proposals),
    )


@router.post(
    "/{proposal_id}/confirm",
    response_model=ProfileProposalResponse,
    responses=common_error_responses,
    summary="确认并写入用户画像",
)
def confirm_profile_proposal(
    proposal_id: Annotated[int, Path(gt=0, description="待确认记录ID")],
    payload: ProfileProposalConfirmRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> ProfileProposalResponse:
    """把（用户可改过的）画像字段写进 `user_profiles`，并标记这条记录已确认。"""
    proposal = ProfileProposalService.confirm(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
        target_job=payload.target_job,
        years_experience=payload.years_experience,
        target_level=payload.target_level,
        target_skills=payload.target_skills,
        weak_topics=payload.weak_topics,
    )
    return ProfileProposalResponse(
        message="画像已更新，之后的回答会参考这些信息",
        proposal=ProfileProposalItem.from_proposal(proposal),
    )


@router.post(
    "/{proposal_id}/dismiss",
    response_model=ProfileProposalResponse,
    responses=common_error_responses,
    summary="忽略这条画像信息",
)
def dismiss_profile_proposal(
    proposal_id: Annotated[int, Path(gt=0, description="待确认记录ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> ProfileProposalResponse:
    """忽略这条记录：不写画像，只把状态标记为已忽略。"""
    proposal = ProfileProposalService.dismiss(
        db=db, user_id=current_user.id, proposal_id=proposal_id
    )
    return ProfileProposalResponse(
        message="已忽略这条画像信息",
        proposal=ProfileProposalItem.from_proposal(proposal),
    )
