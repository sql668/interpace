"""简历导出相关的请求/响应模型（对应 T6.4，决策 D12）。"""

from pydantic import BaseModel, Field


class ResumeExportRequest(BaseModel):
    """导出请求：指明要导出哪条消息里的「优化后的简历」。"""

    message_id: int = Field(gt=0, description="包含优化后简历的助手消息ID")


class ResumeExportResponse(BaseModel):
    """导出结果：落成资源后返回资源 ID 与下载地址。

    下载地址是**接口路径**（不含域名），前端拿它去取字节——
    与附件下载走同一条路（`GET /resources/{id}/content`），鉴权方式一致。
    """

    resource_id: int
    file_name: str  # 建议的下载文件名
    content_type: str
    download_path: str  # 如 /resources/12/content
    reused: bool  # 相同内容之前已导出过时复用旧资源，不重复占存储
