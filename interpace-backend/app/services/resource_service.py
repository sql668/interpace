"""资源读取服务：把 MinIO 里的对象取出来交给前端。

为什么需要它：`resources.storage_path` 是 `minio://bucket/object_key`，
浏览器没法直接加载；前端要显示图片、播放音频、下载文件，都得先经过后端。

鉴权说明：资源接口走 `Authorization: Bearer`，而 `<img src>` / `<audio src>`
带不了自定义请求头，所以前端是「用 axios 取成 Blob → 转 object URL」，
而不是把接口地址直接塞给 src。
"""

from minio.error import S3Error
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import Resource
from app.services.minio_storage_service import MinioStorageService


class ResourceService:
    """资源读取相关业务服务。"""

    @staticmethod
    def get_resource_or_404(db: Session, user_id: int, resource_id: int) -> Resource:
        """按 resource_id + user_id 取资源；不存在或不属于该用户一律 404。

        不区分「没有这条」与「不是你的」，避免用状态码探测他人资源是否存在。
        """
        resource = db.scalar(
            select(Resource).where(
                Resource.id == resource_id, Resource.user_id == user_id
            )
        )
        if not resource:
            raise_error(code=404, message="资源不存在")
        return resource

    @staticmethod
    def read_content(db: Session, user_id: int, resource_id: int) -> tuple[bytes, str]:
        """按资源 ID 读取内容，返回 (字节, mime_type)。"""
        resource = ResourceService.get_resource_or_404(
            db=db, user_id=user_id, resource_id=resource_id
        )
        return ResourceService._read_minio(resource)

    @staticmethod
    def read_content_by_path(
        db: Session, user_id: int, storage_path: str
    ) -> tuple[bytes, str]:
        """按存储路径读取内容，返回 (字节, mime_type)。

        为什么需要这一路：`users.avatar` 存的是 `minio://...` 路径而不是资源 ID，
        前端只有路径可用。查找同样带 `user_id` 条件，只能读自己的资源。
        """
        resource = db.scalar(
            select(Resource).where(
                Resource.user_id == user_id, Resource.storage_path == storage_path
            )
        )
        if not resource:
            raise_error(code=404, message="资源不存在")
        return ResourceService._read_minio(resource)

    @staticmethod
    def _read_minio(resource: Resource) -> tuple[bytes, str]:
        """从 MinIO 读出对象字节。"""
        if not MinioStorageService.is_minio_storage_path(resource.storage_path):
            # 历史数据里可能有非 MinIO 路径（比如"仅提取"场景的虚拟路径）
            raise_error(code=404, message="资源内容不可用")

        client = MinioStorageService.get_client()
        try:
            data, mime_type = MinioStorageService.get_object_bytes(
                client=client, storage_path=resource.storage_path
            )
        except S3Error:
            # 元数据还在、对象已经没了（过期清理或人工删除）
            main_logger.warning(f"资源对象不存在: {resource.storage_path}")
            raise_error(code=404, message="资源内容不存在")
        return data, mime_type
