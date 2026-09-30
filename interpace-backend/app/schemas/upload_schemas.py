"""上传接口响应模型定义。"""

from datetime import datetime

from pydantic import BaseModel


class UploadParseInfo(BaseModel):
    """上传文档时的解析结果摘要。

    只有 PDF / Word / 纯文本会带这一段——上传完就能告诉用户「读到了没有」，
    而不是等他发完消息才发现模型根本没看到简历。
    """

    ok: bool  # 是否读到了可用文本
    char_count: int  # 读到的正文字数
    suspected_scanned: bool  # 疑似扫描件（会改用逐页图片识别）
    message: str  # 给用户看的说明


class UploadResponse(BaseModel):
    """统一上传响应体。"""

    # 接口响应文案。
    message: str
    # resources 表主键。
    resource_id: int
    # 资源存储路径（本地或对象存储路径）。
    file_path: str
    # 文件 MD5 哈希值。
    file_hash: str
    # 资源类型：0文件，1图片，2音频。
    resource_type: int
    # 存储场景：0长过期，1短过期，2仅提取，3永久。
    storage_scene: int
    # 上传用途：0普通资源，1用户头像。
    upload_purpose: int
    # 资源过期时间；永久场景为 null。
    expire_time: datetime | None = None
    # 是否命中去重（true 表示复用已有资源）。
    is_deduplicated: bool
    # 文档解析结果；图片 / 音频等非文档类型为 null。
    parse: UploadParseInfo | None = None
