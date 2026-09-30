"""笔记相关的请求/响应模型。

时间字段沿用项目现有约定：Unix 秒（与 `sessions` / `chat_messages` 一致），
没有采用 `AGENTS.md` 里写的 ISO 8601 字符串——现有接口全部是 Unix 秒，
这里保持一致，避免前端要处理两套时间格式。
"""

from pydantic import BaseModel, ConfigDict, Field


class NoteItem(BaseModel):
    """笔记列表项：**不含正文**，避免列表接口返回大字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_type: int  # 来源：0=手写，1=来自对话，2=来自复盘
    source_message_id: int | None = None  # 来源消息 ID（软引用，可能失效）
    created_at: int  # 创建时间 Unix 秒
    updated_at: int  # 最后更新 Unix 秒


class NoteDetail(NoteItem):
    """笔记详情：在列表项基础上带上正文。"""

    content: str


class NoteListResponse(BaseModel):
    """笔记分页列表响应。"""

    items: list[NoteItem]
    total: int


class NoteCreateRequest(BaseModel):
    """创建笔记请求体。"""

    title: str = Field(default="未命名笔记", min_length=1, max_length=255)
    content: str = Field(default="")
    source_type: int = Field(default=0, ge=0, le=2, description="来源：0手写 1来自对话 2来自复盘")
    source_message_id: int | None = Field(default=None, gt=0)


class NoteUpdateRequest(BaseModel):
    """更新笔记请求体：只更新显式传入的字段。"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = None


class NoteImportRequest(BaseModel):
    """把某条对话消息存成笔记的请求体。"""

    message_id: int = Field(gt=0, description="要存入笔记的消息ID")
    title: str | None = Field(
        default=None, min_length=1, max_length=255, description="自定义标题；不传则由问题文本生成"
    )


class NoteImportResponse(BaseModel):
    """一键存入笔记的响应体。"""

    message: str  # 人类可读提示
    created: bool  # false 表示这条消息之前已存过，返回的是已有笔记
    note: NoteDetail
