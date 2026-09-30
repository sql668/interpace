"""测试用的 API 助手：上传、建会话、替换模型。

放在单独模块里供多个测试文件共用（pytest 会把 tests/ 加到 sys.path）。
"""

from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.agent import prompt_layer
from app.services import (
    interview_evaluation_service,
    memory_extract_service,
    profile_extraction_service,
    quiz_evaluation_service,
    stream_chat_service,
)


def make_recording_model(
    captured: list[list[Any]], content: str = "收到"
) -> GenericFakeChatModel:
    """假模型：记录收到的消息，再返回固定回答。"""

    class RecordingChatModel(GenericFakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            captured.append(list(messages))
            return super()._generate(messages, stop, run_manager, **kwargs)

        def _stream(self, messages, stop=None, run_manager=None, **kwargs):
            captured.append(list(messages))
            yield from super()._stream(messages, stop, run_manager, **kwargs)

    return RecordingChatModel(messages=iter([AIMessage(content=content)]))


def stub_chat_model(
    monkeypatch: pytest.MonkeyPatch,
    captured: list[list[Any]] | None = None,
    content: str = "收到",
) -> None:
    """替换掉真模型与提示词构建，避免外部调用。

    传了 `captured` 就能断言「模型实际收到了什么」，不传只关心接口是否跑通。
    `content` 用于让假模型吐出指定的回复正文（例如题库 JSON）。
    """

    def factory(provider: str = "deepseek") -> GenericFakeChatModel:
        if captured is None:
            return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))
        return make_recording_model(captured, content=content)

    monkeypatch.setattr(prompt_layer, "get_chat_model", factory)
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")
    monkeypatch.setattr(
        stream_chat_service, "build_personalized_prompt", lambda **kwargs: None
    )
    # 评分链路走的是同步调用，用的是自己模块里的引用，得单独替换。
    monkeypatch.setattr(quiz_evaluation_service, "get_chat_model", factory)
    monkeypatch.setattr(
        quiz_evaluation_service, "build_personalized_prompt", lambda **kwargs: None
    )
    # 画像抽取同理：它也是同步调用，且只关心解析结果。
    monkeypatch.setattr(profile_extraction_service, "get_chat_model", factory)
    monkeypatch.setattr(
        profile_extraction_service, "build_personalized_prompt", lambda **kwargs: None
    )
    # 面试复盘同理（T8.2）
    monkeypatch.setattr(interview_evaluation_service, "get_chat_model", factory)
    monkeypatch.setattr(
        interview_evaluation_service, "build_personalized_prompt", lambda **kwargs: None
    )
    # 记忆抽取同理（T9.5）
    monkeypatch.setattr(memory_extract_service, "get_chat_model", factory)
    monkeypatch.setattr(
        memory_extract_service, "build_personalized_prompt", lambda **kwargs: None
    )


async def upload_file(
    async_client: AsyncClient,
    headers: dict[str, str],
    filename: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    """上传一个文件，返回后端的完整响应体。"""
    response = await async_client.post(
        "/upload/file",
        files={"file": (filename, BytesIO(content), mime_type)},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_session(
    async_client: AsyncClient,
    headers: dict[str, str],
    title: str = "测试会话",
    session_model: int = 0,
) -> int:
    """建一个会话，返回会话 ID。注意 POST /sessions 返回的是 200 不是 201。

    `session_model` 要跟后续请求里的查询参数一致（学习室 0 / 面试间 1），
    否则会话归属校验会 404。
    """
    response = await async_client.post(
        "/sessions", json={"title": title, "session_model": session_model}, headers=headers
    )
    assert response.status_code == 200, response.text
    return int(response.json()["session"]["id"])


def purge_user(user_id: int) -> None:
    """测试清理：按外键依赖顺序删掉一个用户及其记忆相关数据。

    顺序不能乱——`users` 被十几张表以 NO ACTION 外键引用，删错顺序就撞外键。
    这里只覆盖测试常造的那几张表；完整的级联由生产侧的 `UserService.delete_user` 负责
    （那条路径有专门的用例盯着）。
    """
    from app.db.database import SessionLocal
    from app.db.models import (
        ChatMessage,
        SearchDocument,
        SessionSummary,
        Session as SessionModel,
        User,
        UserMemory,
        UserMemoryLog,
        UserProfile,
    )

    db = SessionLocal()
    try:
        db.query(SessionSummary).filter(SessionSummary.user_id == user_id).delete()
        db.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()
        db.query(SessionModel).filter(SessionModel.user_id == user_id).delete()
        db.query(SearchDocument).filter(SearchDocument.user_id == user_id).delete()
        db.query(UserMemoryLog).filter(UserMemoryLog.user_id == user_id).delete()
        db.query(UserMemory).filter(UserMemory.user_id == user_id).delete()
        db.query(UserProfile).filter(UserProfile.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
    finally:
        db.close()
