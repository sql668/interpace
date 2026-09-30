"""资源读取路由：把 MinIO 对象透出去给前端显示 / 播放 / 下载。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.services.resource_service import ResourceService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# 两种寻址方式：按资源 ID（附件等场景）与按存储路径（users.avatar 这类只存路径的场景）。
# 路径段数不同，不会互相遮蔽。
@router.get(
    "/content",
    responses=common_error_responses,
    summary="按存储路径读取资源内容",
)
def get_resource_content_by_path(
    db: DBSession,
    current_user: CurrentUser,
    storage_path: Annotated[
        str, Query(min_length=1, description="资源存储路径，如 minio://bucket/key")
    ],
) -> Response:
    """按 `minio://` 存储路径读取资源内容。

    主要服务于 `users.avatar` 这类只存了路径、没有资源 ID 的场景。
    查找同样按当前用户过滤，读不到别人的资源。
    """
    data, mime_type = ResourceService.read_content_by_path(
        db=db, user_id=current_user.id, storage_path=storage_path
    )
    return Response(content=data, media_type=mime_type)


@router.get(
    "/{resource_id}/content",
    responses=common_error_responses,
    summary="读取资源内容",
)
def get_resource_content(
    resource_id: Annotated[int, Path(gt=0, description="资源ID")],
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    """返回资源的原始字节；只能读自己的资源，越权一律 404。

    注意：没有做 HTTP Range 支持，音频无法拖动进度条——对当前场景够用，
    真要支持得改成 StreamingResponse 并处理 Range 头。
    """
    data, mime_type = ResourceService.read_content(
        db=db, user_id=current_user.id, resource_id=resource_id
    )
    return Response(content=data, media_type=mime_type)
