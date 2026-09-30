"""长期记忆 L3 的检索接口（T9.14）。

返回**原文**，不做 LLM 摘要、不截断——Hermes 的明确做法：摘要会让检索结果不再可信。
检索范围**强制限定在当前用户**，不存在「只按相似度返回」的路径。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas.search_schemas import SearchHitItem, SearchResponse
from app.services.memory_search_service import MemorySearchService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "",
    response_model=SearchResponse,
    responses=common_error_responses,
    summary="检索我的历史内容",
)
def search_my_memory(
    q: Annotated[str, Query(min_length=1, max_length=100, description="关键词")],
    db: DBSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50, description="最多返回多少条")] = 10,
    source_types: Annotated[
        str | None,
        Query(description="限定来源，逗号分隔：0对话 1笔记 2复盘；不传为全部"),
    ] = None,
) -> SearchResponse:
    """按关键词检索当前用户的历史对话、笔记与复盘结论。"""
    types = None
    if source_types:
        types = [int(part) for part in source_types.split(",") if part.strip().isdigit()]
    hits = MemorySearchService.search(
        db, user_id=current_user.id, query=q, limit=limit, source_types=types
    )
    return SearchResponse(
        query=q,
        total=len(hits),
        items=[
            SearchHitItem(
                source_type=hit.document.source_type,
                source_label=hit.source_label,
                source_id=hit.document.source_id,
                session_id=hit.document.session_id,
                title=hit.document.title,
                content=hit.document.content,
                score=hit.score,
                created_at=hit.document.created_at,
            )
            for hit in hits
        ],
    )
