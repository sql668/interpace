"""把消息附件段解析成模型能吃的输入：文档文本 + 图片。

为什么要单独一层：附件段里只有一个 `resource_id`，模型需要的是「文本内容」或
「图片字节」。中间要完成：归属校验 → 从 MinIO 取字节 → 按类型分流（文档解析 /
扫描件渲染 / 图片直传）。

对应 T3.6。修的是两个洞：
1. `image` 类型的附件从来没进过模型调用；
2. `chat_messages.file_extracted_text` 写了没人读。
"""

from dataclasses import dataclass, field
from pathlib import Path

from minio.error import S3Error
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import main_logger
from app.db.models import Resource
from app.schemas.chat_schemas import MessageSegment
from app.services.document_parse_service import DocumentParseService
from app.services.minio_storage_service import MinioStorageService

# resources.resource_type 的取值
RESOURCE_TYPE_FILE = 0
RESOURCE_TYPE_IMAGE = 1
RESOURCE_TYPE_AUDIO = 2

# 图片后缀 → MIME，用于给多模态模型拼 data URL
IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}
DEFAULT_IMAGE_MIME = "image/png"


@dataclass(frozen=True)
class AttachmentImage:
    """一张要交给多模态模型的图片。"""

    data: bytes
    mime_type: str


@dataclass
class ResolvedAttachments:
    """一轮消息里所有附件的解析结果。"""

    text: str = ""  # 文档提取出的正文，拼进人类消息
    images: list[AttachmentImage] = field(default_factory=list)  # 交给多模态模型
    notes: list[str] = field(default_factory=list)  # 给模型看的简短说明（扫描件 / 失败等）


class AttachmentContentService:
    """附件内容解析：把附件段变成文本与图片。"""

    @staticmethod
    def resolve(
        db: Session, user_id: int, segments: list[MessageSegment] | None
    ) -> ResolvedAttachments:
        """解析本轮消息的附件段。任何单个附件出问题都不影响其它附件与整轮对话。"""
        resolved = ResolvedAttachments()
        if not segments:
            return resolved

        client = MinioStorageService.get_client()
        text_blocks: list[str] = []

        for segment in segments:
            if segment.resource_id is None:
                continue
            resource = AttachmentContentService._get_owned_resource(
                db=db, user_id=user_id, resource_id=segment.resource_id
            )
            if resource is None:
                # 不是自己的资源或已不存在：跳过并留痕，不打断整轮对话
                resolved.notes.append(f"附件「{segment.name or segment.resource_id}」不可用，已忽略。")
                continue

            try:
                data, _mime = MinioStorageService.get_object_bytes(
                    client=client, storage_path=resource.storage_path
                )
            except S3Error:
                main_logger.warning(f"附件对象读取失败: {resource.storage_path}")
                resolved.notes.append(f"附件「{resource.file_name}」读取失败，已忽略。")
                continue

            AttachmentContentService._handle_resource(
                resource=resource, data=data, resolved=resolved, text_blocks=text_blocks
            )

        resolved.text = "\n\n".join(text_blocks)
        return resolved

    @staticmethod
    def _handle_resource(
        resource: Resource,
        data: bytes,
        resolved: ResolvedAttachments,
        text_blocks: list[str],
    ) -> None:
        """按资源类型分流：图片直传、文档解析、扫描件渲染。"""
        if resource.resource_type == RESOURCE_TYPE_IMAGE:
            resolved.images.append(
                AttachmentImage(
                    data=data,
                    mime_type=IMAGE_MIME_BY_SUFFIX.get(
                        Path(resource.file_name).suffix.lower(), DEFAULT_IMAGE_MIME
                    ),
                )
            )
            return

        if resource.resource_type == RESOURCE_TYPE_AUDIO:
            # 语音识别属于阶段 7，这里先明确告知，避免用户以为没人理
            resolved.notes.append(f"附件「{resource.file_name}」是音频，暂不支持在对话中使用。")
            return

        parsed = DocumentParseService.parse(data, resource.file_name)
        if parsed.ok:
            text_blocks.append(f"【附件：{resource.file_name}】\n{parsed.text}")
            return

        if parsed.suspected_scanned:
            # 扫描件：渲染成图片交给多模态模型，用户全程无感
            try:
                pages = DocumentParseService.render_pdf_pages(data)
            except Exception as exc:
                main_logger.warning(f"扫描件渲染失败: {resource.file_name}, {exc}")
                pages = []
            for page in pages:
                resolved.images.append(AttachmentImage(data=page, mime_type="image/png"))
            resolved.notes.append(
                f"附件「{resource.file_name}」是扫描件，已把前 {len(pages)} 页转成图片提供。"
            )
            return

        resolved.notes.append(f"附件「{resource.file_name}」无法解析：{parsed.message}")

    @staticmethod
    def _get_owned_resource(db: Session, user_id: int, resource_id: int) -> Resource | None:
        """按 resource_id + user_id 取资源，避免引用到别人的文件。"""
        return db.scalar(
            select(Resource).where(Resource.id == resource_id, Resource.user_id == user_id)
        )
