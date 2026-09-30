"""简历路由：导出优化后的简历为 Word（T6.4）。

路由只做接入，生成与落资源都在 `ResumeExportService`。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import common_error_responses
from app.core.auth import get_current_user
from app.db import get_db
from app.db.models import User
from app.schemas.resume_schemas import ResumeExportRequest, ResumeExportResponse
from app.services.resume_export_service import DOCX_CONTENT_TYPE, ResumeExportService

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/export",
    response_model=ResumeExportResponse,
    responses=common_error_responses,
    summary="导出优化后的简历为 Word",
)
def export_resume(
    payload: ResumeExportRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> ResumeExportResponse:
    """把某条助手消息里的「优化后的简历」生成 `.docx` 并落成资源。

    返回 `resource_id` 与下载路径；前端再走 `GET /resources/{id}/content` 取文件。
    """
    resource, reused = ResumeExportService.export_from_message(
        db=db, user=current_user, message_id=payload.message_id
    )
    return ResumeExportResponse(
        resource_id=resource.id,
        file_name=resource.file_name,
        content_type=DOCX_CONTENT_TYPE,
        download_path=f"/resources/{resource.id}/content",
        reused=reused,
    )
