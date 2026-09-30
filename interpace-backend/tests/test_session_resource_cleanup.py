"""T3.5 回归测试：删除会话时的资源回收。

验证「有附件」与「无附件」两条路径：
- 带附件的会话删除后，`resources` 记录与 MinIO 对象都被清理；
- 没有附件的会话删除照常成功，且报告 0 个资源。

MinIO 对象是否存在用 `stat_object` 直接查，不看接口——接口在记录删掉之后
本来就会 404，光看接口区分不出「记录没了但对象还在」这种情况。
"""

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient
from minio.error import S3Error

from api_helpers import create_session, stub_chat_model, upload_file

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.minio_storage_service import MinioStorageService
from app.db.database import SessionLocal
from app.db.models import ChatMessage, QuizPaper, QuizQuestion

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def _minio_object_exists(storage_path: str) -> bool:
    """直接查 MinIO 里对象还在不在。"""
    client = MinioStorageService.get_client()
    bucket, object_name = MinioStorageService.parse_storage_path(storage_path)
    try:
        client.stat_object(bucket, object_name)
        return True
    except S3Error:
        return False


async def _send_with_attachment(
    async_client: AsyncClient,
    headers: dict[str, str],
    session_id: int,
    resource_id: int | None,
) -> None:
    """发一条消息；resource_id 为 None 时不带附件。"""
    segments = (
        [{"type": "file", "name": "note.txt", "resource_id": resource_id}]
        if resource_id is not None
        else []
    )
    response = await async_client.post(
        f"/sessions/{session_id}/stream-chat?session_model=0",
        json={"request_text": "带附件的消息", "segments": segments},
        headers=headers,
    )
    assert response.status_code == 200, response.text


@pytest.mark.anyio
async def test_deleting_session_cleans_attachment_resources(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """带附件的会话删除后，resources 记录与 MinIO 对象都要被回收。"""
    headers = await register_and_login("clean")
    uploaded = await upload_file(
        async_client, headers, "note.txt", b"cleanup-me", "text/plain"
    )
    resource_id = uploaded["resource_id"]
    storage_path = uploaded["file_path"]

    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch)
    await _send_with_attachment(async_client, headers, session_id, resource_id)

    # 删除前：记录可读、对象存在
    before = await async_client.get(
        f"/resources/{resource_id}/content", headers=headers
    )
    assert before.status_code == 200
    assert _minio_object_exists(storage_path)

    deleted = await async_client.delete(
        f"/sessions/{session_id}?session_model=0", headers=headers
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted_messages"] == 1
    assert body["deleted_resources"] == 1

    # 删除后：记录没了（接口 404），MinIO 对象也没了
    after = await async_client.get(
        f"/resources/{resource_id}/content", headers=headers
    )
    assert after.status_code == 404
    assert not _minio_object_exists(storage_path)


@pytest.mark.anyio
async def test_deleting_session_without_attachments(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有附件的会话删除照常成功，且报告 0 个资源。"""
    headers = await register_and_login("clean2")
    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch)
    await _send_with_attachment(async_client, headers, session_id, None)

    deleted = await async_client.delete(
        f"/sessions/{session_id}?session_model=0", headers=headers
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted_messages"] == 1
    assert body["deleted_resources"] == 0


@pytest.mark.anyio
async def test_deleting_session_cleans_quiz_papers(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T5.3：带题库的会话删除后，题目与卷子都要被清掉。

    这条专门验证**外键删除顺序**：卷子指向 chat_messages 和 sessions，
    如果先删消息就会撞外键、整个删除请求失败。
    """
    headers = await register_and_login("quizclean")
    session_id = await create_session(async_client, headers)
    stub_chat_model(monkeypatch)
    await _send_with_attachment(async_client, headers, session_id, None)

    # T5.5 才会真正生成题库，这里直接写库造一份，只为验删除路径
    db = SessionLocal()
    try:
        message = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .first()
        )
        assert message is not None
        paper = QuizPaper(
            user_id=message.user_id,
            session_id=session_id,
            message_id=message.id,
            target_job="Python 后端",
            difficulty="中级",
            question_count=1,
            status=0,
        )
        db.add(paper)
        db.flush()
        paper_id = paper.id
        db.add(
            QuizQuestion(
                paper_id=paper_id,
                order_index=1,
                question="什么是覆盖索引？",
                reference_answer="查询所需列全部由索引提供。",
            )
        )
        db.commit()
    finally:
        db.close()

    deleted = await async_client.delete(
        f"/sessions/{session_id}?session_model=0", headers=headers
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_quizzes"] == 1

    check = SessionLocal()
    try:
        assert check.get(QuizPaper, paper_id) is None
        assert (
            check.query(QuizQuestion).filter(QuizQuestion.paper_id == paper_id).count() == 0
        )
    finally:
        check.close()
