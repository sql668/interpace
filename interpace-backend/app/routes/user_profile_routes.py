"""用户画像路由（T9.3）：读取画像、改意图字段、增删改能力记忆。

全部走 `get_current_user`，天然按当前用户隔离；条目级操作还要再校验归属，
越权一律 404（与笔记、题库、记忆的口径一致）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User, UserProfile
from app.schemas.user_profile_schemas import (
    ProfileIntent,
    ProfileIntentUpdateRequest,
    ProfileMemoryLogItem,
    ProfileMemoryCreateRequest,
    ProfileMemoryItem,
    ProfileMemoryUpdateRequest,
    UserProfileResponse,
)
from app.services.user_memory_service import (
    CATEGORY_LABELS,
    SOURCE_LABELS,
    SOURCE_SELF_REPORT,
    UserMemoryService,
    MEMORY_LOG_ACTION_LABELS,
    mastery_label,
)
from app.services.user_profile_service import UserProfileService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _to_item(memory) -> ProfileMemoryItem:
    """把 ORM 行补上展示用的中文标签。

    掌握程度对外只给四档——用户看到「73 分」只会纠结为什么不是 80，
    看到「熟悉」才知道下一步该干嘛。
    """
    item = ProfileMemoryItem.model_validate(memory)
    item.category_label = CATEGORY_LABELS.get(memory.category, "其它")
    item.mastery_label = mastery_label(memory.mastery)
    item.source_label = SOURCE_LABELS.get(memory.source, "未知来源")
    return item


def _to_log_item(log) -> ProfileMemoryLogItem:
    """日志条目也补中文标签，界面上要能直接读。"""
    item = ProfileMemoryLogItem.model_validate(log)
    item.category_label = CATEGORY_LABELS.get(log.category, "其它")
    item.action_label = MEMORY_LOG_ACTION_LABELS.get(log.action, log.action)
    return item


def _build_response(db: Session, user_id: int) -> UserProfileResponse:
    profile = UserProfileService.get_user_profile(db, user_id)
    memories = UserMemoryService.list_memories(
        db, user_id=user_id, include_pending=True
    )
    return UserProfileResponse(
        intent=ProfileIntent.model_validate(profile) if profile else ProfileIntent(),
        memories=[_to_item(memory) for memory in memories],
        target_skills=list(profile.target_skills) if profile and profile.target_skills else [],
        weak_topics=list(profile.weak_topics) if profile and profile.weak_topics else [],
    )


@router.get(
    "",
    response_model=UserProfileResponse,
    responses=common_error_responses,
    summary="读取当前用户画像",
)
def get_profile(db: DBSession, current_user: CurrentUser) -> UserProfileResponse:
    """返回意图字段 + 能力记忆明细。没有画像记录时返回空结构而不是 404。"""
    return _build_response(db, current_user.id)


@router.put(
    "",
    response_model=UserProfileResponse,
    responses=common_error_responses,
    summary="更新意图类字段",
)
def update_profile(
    payload: ProfileIntentUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> UserProfileResponse:
    """更新目标岗位 / 经验年限 / 目标级别；只更新显式传入的字段。"""
    profile = UserProfileService.get_user_profile(db, current_user.id)
    if profile is None:
        profile = UserProfile(
            user_id=current_user.id, target_skills=[], weak_topics=[]
        )
        db.add(profile)
        db.flush()

    if payload.target_job is not None:
        profile.target_job = payload.target_job.strip() or None
    if payload.years_experience is not None:
        profile.years_experience = payload.years_experience.strip() or None
    if payload.target_level is not None:
        profile.target_level = payload.target_level.strip() or None
    db.add(profile)
    db.commit()
    return _build_response(db, current_user.id)


@router.post(
    "/memories",
    response_model=ProfileMemoryItem,
    status_code=status.HTTP_201_CREATED,
    responses=common_error_responses,
    summary="新增一条能力记忆",
)
def create_memory(
    payload: ProfileMemoryCreateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> ProfileMemoryItem:
    """用户手动新增（自建即生效，标记来源为「你的自述」）。"""
    memory = UserMemoryService.upsert_memory(
        db,
        user_id=current_user.id,
        category=payload.category,
        name=payload.name,
        mastery=payload.mastery,
        source=SOURCE_SELF_REPORT,
        confidence=80,
    )
    db.commit()
    db.refresh(memory)
    return _to_item(memory)


@router.put(
    "/memories/{memory_id}",
    response_model=ProfileMemoryItem,
    responses=common_error_responses,
    summary="修改一条能力记忆",
)
def update_memory(
    memory_id: Annotated[int, Path(gt=0, description="记忆条目ID")],
    payload: ProfileMemoryUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> ProfileMemoryItem:
    """改条目名或掌握程度；用户手动改过即生效，不再等确认。"""
    memory = UserMemoryService.update_memory(
        db,
        user_id=current_user.id,
        memory_id=memory_id,
        name=payload.name,
        mastery=payload.mastery,
    )
    return _to_item(memory)


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=common_error_responses,
    summary="删除一条能力记忆",
)
def delete_memory(
    memory_id: Annotated[int, Path(gt=0, description="记忆条目ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    """用户有权删掉系统记错的东西（D19）。"""
    UserMemoryService.delete_memory(
        db, user_id=current_user.id, memory_id=memory_id
    )


@router.get(
    "/memories",
    response_model=list[ProfileMemoryItem],
    responses=common_error_responses,
    summary="按类别列出能力记忆",
)
def list_memories(
    db: DBSession,
    current_user: CurrentUser,
    category: Annotated[
        int | None, Query(ge=0, le=2, description="0技能 1薄弱点 2答题方法；不传为全部")
    ] = None,
) -> list[ProfileMemoryItem]:
    """列出当前用户的能力记忆，可按类别过滤。"""
    memories = UserMemoryService.list_memories(
        db, user_id=current_user.id, category=category, include_pending=True
    )
    return [_to_item(memory) for memory in memories]


@router.get(
    "/memories/pending",
    response_model=list[ProfileMemoryItem],
    responses=common_error_responses,
    summary="列出待确认的记忆",
)
def list_pending_memories(
    db: DBSession, current_user: CurrentUser
) -> list[ProfileMemoryItem]:
    """自动抽取的记忆在用户批准前不影响对话（D20），这里是治理入口。"""
    memories = UserMemoryService.list_memories(
        db, user_id=current_user.id, include_pending=True
    )
    return [_to_item(memory) for memory in memories if memory.pending_approval == 1]


@router.post(
    "/memories/{memory_id}/approve",
    response_model=ProfileMemoryItem,
    responses=common_error_responses,
    summary="批准一条待确认记忆",
)
def approve_memory(
    memory_id: Annotated[int, Path(gt=0, description="记忆条目ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> ProfileMemoryItem:
    """批准后这条记忆开始影响对话，并进入提示词注入。"""
    memory = UserMemoryService.approve(
        db, user_id=current_user.id, memory_id=memory_id
    )
    return _to_item(memory)


@router.post(
    "/memories/{memory_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=common_error_responses,
    summary="拒绝一条待确认记忆",
)
def reject_memory(
    memory_id: Annotated[int, Path(gt=0, description="记忆条目ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    """拒绝即删除，并留下原文便于回溯（不保留「已拒绝」状态，免得列表反复出现）。"""
    UserMemoryService.reject(db, user_id=current_user.id, memory_id=memory_id)


@router.get(
    "/memory-logs",
    response_model=list[ProfileMemoryLogItem],
    responses=common_error_responses,
    summary="记忆变更日志",
)
def list_memory_logs(
    db: DBSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200, description="最多返回多少条")] = 50,
) -> list[ProfileMemoryLogItem]:
    """最近的能力记忆变更，用于回溯「系统原来记的是什么」。"""
    logs = UserMemoryService.list_logs(db, user_id=current_user.id, limit=limit)
    return [_to_log_item(log) for log in logs]
