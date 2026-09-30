"""笔记路由：增删改查，全部按当前登录用户隔离。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas import (
    NoteCreateRequest,
    NoteDetail,
    NoteImportRequest,
    NoteImportResponse,
    NoteItem,
    NoteListResponse,
    NoteUpdateRequest,
)
from app.services.note_service import NoteService

router = APIRouter()
# 统一依赖别名，减少每个路由函数重复书写 Depends。
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=NoteListResponse,
    responses=common_error_responses,
    summary="分页获取笔记列表",
)
def list_notes(
    db: DBSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量，1-100")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
) -> NoteListResponse:
    """按最近更新时间倒序分页返回当前用户的笔记（不含正文）。"""
    notes, total = NoteService.list_notes(
        db=db, user_id=current_user.id, limit=limit, offset=offset
    )
    return NoteListResponse(
        items=[NoteItem.model_validate(note) for note in notes],
        total=total,
    )


@router.post(
    "",
    response_model=NoteDetail,
    status_code=status.HTTP_201_CREATED,
    responses=common_error_responses,
    summary="创建笔记",
)
def create_note(
    payload: NoteCreateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> NoteDetail:
    """创建一条新笔记。"""
    note = NoteService.create_note(
        db=db,
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        source_type=payload.source_type,
        source_message_id=payload.source_message_id,
    )
    return NoteDetail.model_validate(note)


# 注意：本路由必须声明在 `/{note_id}` 之前，否则 "import" 会被当成 note_id 解析。
@router.post(
    "/import",
    response_model=NoteImportResponse,
    responses=common_error_responses,
    summary="把一条对话消息存入笔记",
)
def import_note_from_message(
    payload: NoteImportRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> NoteImportResponse:
    """把某条消息的问答内容存成笔记；同一条消息重复调用是幂等的。"""
    note, created = NoteService.import_from_message(
        db=db,
        user_id=current_user.id,
        message_id=payload.message_id,
        title=payload.title,
    )
    return NoteImportResponse(
        message="已存入笔记" if created else "这条消息之前已存入笔记",
        created=created,
        note=NoteDetail.model_validate(note),
    )


@router.get(
    "/{note_id}",
    response_model=NoteDetail,
    responses=common_error_responses,
    summary="获取笔记详情",
)
def get_note(
    note_id: Annotated[int, Path(gt=0, description="笔记ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> NoteDetail:
    """按 note_id 获取笔记详情（含正文）。"""
    note = NoteService.get_note_or_404(
        db=db, user_id=current_user.id, note_id=note_id
    )
    return NoteDetail.model_validate(note)


@router.put(
    "/{note_id}",
    response_model=NoteDetail,
    responses=common_error_responses,
    summary="更新笔记",
)
def update_note(
    note_id: Annotated[int, Path(gt=0, description="笔记ID")],
    payload: NoteUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> NoteDetail:
    """更新笔记标题与正文；只更新显式传入的字段。"""
    note = NoteService.update_note(
        db=db,
        user_id=current_user.id,
        note_id=note_id,
        title=payload.title,
        content=payload.content,
    )
    return NoteDetail.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=common_error_responses,
    summary="删除笔记",
)
def delete_note(
    note_id: Annotated[int, Path(gt=0, description="笔记ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    """删除笔记；不存在或不属于当前用户时 404。"""
    NoteService.delete_note(db=db, user_id=current_user.id, note_id=note_id)
