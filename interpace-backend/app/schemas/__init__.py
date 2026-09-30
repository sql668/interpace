"""Schema 聚合导出：集中暴露接口请求/响应模型，便于路由层统一导入。"""

from .auth_schemas import LoginRequest, RefreshRequest, TokenResponse
from .chat_schemas import (
    ChatMessageItem,
    ChatMessagePageResponse,
    DeleteSessionResponse,
    MessageSegment,
    StopStreamChatRequest,
    StopStreamChatResponse,
    StreamChatRequest,
)
from .note_schemas import (
    NoteCreateRequest,
    NoteDetail,
    NoteImportRequest,
    NoteImportResponse,
    NoteItem,
    NoteListResponse,
    NoteUpdateRequest,
)
from .prompt_schemas import (
    PromptTemplateResponse,
    PromptVersionListResponse,
    RollbackPromptRequest,
)
from .runtime_config_schemas import (
    RuntimeConfigResponse,
    RuntimeFeatures,
    RuntimeNotice,
)
from .session_schemas import (
    InterviewDetailResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionItem,
    SessionListResponse,
    SessionUpdateTitleRequest,
    SessionUpdateTitleResponse,
)
from .upload_schemas import UploadParseInfo, UploadResponse
from .user_schemas import (
    UserCreateRequest,
    UserCreateResponse,
    UserDeleteResponse,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

# 对外统一导出，减少上层模块直接引用子文件路径。
__all__ = [
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    "MessageSegment",
    "ChatMessageItem",
    "ChatMessagePageResponse",
    "DeleteSessionResponse",
    "StreamChatRequest",
    "StopStreamChatRequest",
    "StopStreamChatResponse",
    "NoteItem",
    "NoteDetail",
    "NoteListResponse",
    "NoteCreateRequest",
    "NoteUpdateRequest",
    "NoteImportRequest",
    "NoteImportResponse",
    "RuntimeConfigResponse",
    "RuntimeFeatures",
    "RuntimeNotice",
    "PromptTemplateResponse",
    "PromptVersionListResponse",
    "RollbackPromptRequest",
    "SessionCreateRequest",
    "SessionCreateResponse",
    "SessionUpdateTitleRequest",
    "SessionUpdateTitleResponse",
    "SessionItem",
    "SessionListResponse",
    "InterviewDetailResponse",
    "UploadResponse",
    "UploadParseInfo",
    "UserCreateRequest",
    "UserCreateResponse",
    "UserDeleteResponse",
    "UserListResponse",
    "UserResponse",
    "UserUpdateRequest",
]
