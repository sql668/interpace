"""聊天相关 Schema：消息、分页、删除会话、流式请求。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageSegment(BaseModel):
    """附件片段（当前仅约定 file/image/audio）。"""

    # 兼容历史数据中的冗余字段，避免序列化时报错。
    model_config = ConfigDict(extra="ignore")

    # 用 Literal 而不是裸 str：写入时就把非法类型挡掉，
    # 读取侧 ChatService 也会按同一组白名单过滤。
    type: Literal["file", "image", "audio"] = Field(description="附件类型：file/image/audio")
    name: str | None = Field(default=None, description="附件显示名称")
    url: str | None = Field(default=None, description="附件访问地址")
    resource_id: int | None = Field(default=None, description="资源ID")


class ChatMessageItem(BaseModel):
    """会话消息行（含用户问句与助手回复）。"""

    id: int  # chat_messages 主键
    status: int  # 消息状态（与数据库状态码保持一致）
    select_model: int  # 消息所属模式，用于前端回显模式标签
    interview_id: int | None = None  # 关联面试记录ID（无则为空）
    request_text: str  # 用户输入文本
    response_text: str  # 助手输出文本（流式完成后为最终全文）
    request_segments: list[MessageSegment] = Field(default_factory=list)  # 用户侧附件片段
    response_segments: list[MessageSegment] = Field(default_factory=list)  # 助手侧附件片段
    created_at: int  # 创建时间戳（秒）


class ChatMessagePageResponse(BaseModel):
    """会话消息分页返回。"""

    session_id: int  # 所属会话ID
    page: int  # 当前页（从1开始）
    page_size: int  # 每页条数
    has_more: bool  # 是否存在下一页
    messages: list[ChatMessageItem]  # 当前页消息列表


class DeleteSessionResponse(BaseModel):
    """删除会话返回摘要。"""

    message: str  # 人类可读提示
    session_id: int  # 被删除的会话ID
    deleted_messages: int  # 删除的消息条数
    deleted_interviews: int  # 删除的面试记录条数
    deleted_resources: int  # 删除的资源条数
    deleted_quizzes: int = 0  # 删除的题库卷数


class StreamChatRequest(BaseModel):
    """流式聊天接口请求体。"""

    request_text: str = Field(min_length=1, max_length=8000, description="用户输入")
    # 与数据库 chat_messages.select_model 字段保持一致。
    select_model: int = Field(default=0, ge=0, le=5, description="模型选择标记")
    # 轻量扩展口：当前默认 deepseek，后续可扩 provider。
    provider: str = Field(default="deepseek", description="模型提供方")
    # 本轮消息携带的附件段（文件 / 图片 / 音频），会原样落到 chat_messages.request_segments。
    segments: list[MessageSegment] = Field(default_factory=list, description="附件段列表")


class StopStreamChatRequest(BaseModel):
    """停止流式对话请求体。"""

    # 取自 SSE start 事件里的 message_id。
    message_id: int = Field(gt=0, description="要停止的消息ID")


class StopStreamChatResponse(BaseModel):
    """停止流式对话响应体。"""

    message: str  # 人类可读提示
    message_id: int  # 被停止的消息ID
    first_request: bool  # 本次调用是否为首次登记停止（false 表示幂等重复调用）
