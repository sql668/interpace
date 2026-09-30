
"""上传路由：对外暴露统一资源上传接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core import raise_error
from app.db import User, get_db
from app.schemas import UploadParseInfo, UploadResponse
from app.services.upload_service_minio import UploadService
from app.services.usage_quota_service import UsageQuotaService

# 上传路由组，不单独设置前缀，由 main.py 统一挂载。
router = APIRouter()


@router.post(
    "/upload/file",
    summary="通用文件上传接口",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
def upload_file(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    # 存储场景：0长过期，1短过期，2仅提取，3永久。
    storage_scene: Annotated[int, Form()] = 0,
    # 上传用途：0普通资源，1用户头像。仅头像用途会更新 users.avatar。
    upload_purpose: Annotated[int, Form()] = 0,
    file: UploadFile = File(...),
) -> UploadResponse:
    """
    支持文件/图片/音频上传，自动完成类型识别、去重与资源记录管理。
    """
    # 演示环境可以在配置里整体关掉附件上传（T12.5）。前端不显示入口只是界面，
    # 这里判一次才算数：附件（尤其 PDF）解析出的全文会整段进上下文，
    # 一次上传能顶几十轮对话的 token。
    if UsageQuotaService.file_upload_disabled():
        raise_error(
            code=status.HTTP_403_FORBIDDEN,
            message="当前环境未开放附件上传",
        )

    # 业务逻辑全部在 service 层，路由仅做参数接入与响应组装。
    resource, is_deduplicated, parse_result = UploadService.save_file(
        db=db,
        user=current_user,
        file=file,
        storage_scene=storage_scene,
        upload_purpose=upload_purpose,
    )
    return UploadResponse(
        message="文件上传成功",
        resource_id=resource.id,
        file_path=resource.storage_path,
        file_hash=resource.file_hash,
        resource_type=resource.resource_type,
        storage_scene=resource.storage_scene,
        upload_purpose=resource.upload_purpose,
        expire_time=resource.expire_time,
        is_deduplicated=is_deduplicated,
        parse=(
            UploadParseInfo(
                ok=parse_result.ok,
                char_count=parse_result.char_count,
                suspected_scanned=parse_result.suspected_scanned,
                message=parse_result.message,
            )
            if parse_result
            else None
        ),
    )
