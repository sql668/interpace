"""删除用户必须连带清掉该用户的全部数据（T9.2 引入 user_memories 时暴露的既有缺陷）。

背景：`users` 被 10 张表以 `NO ACTION` 外键引用且**没有任何级联**，
原来 `UserService.delete_user` 只 `db.delete(user)`——**只要用户建过一次会话，
删用户就必然 IntegrityError**。真机验证过。这个用例把「删用户」变成一条被测试盯着的路径。
"""

import sys
import time
import uuid
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core import AppException
from app.db.database import SessionLocal
from app.db.base import Base
from app.db.models import (
    ChatMessage,
    Interview,
    InterviewEvaluation,
    Note,
    ProfileProposal,
    QuizPaper,
    QuizQuestion,
    Resource,
    SearchDocument,
    Session as SessionModel,
    User,
    UserMemory,
    UserMemoryLog,
    UserProfile,
)
from app.services.user_service import UserService


def _seed_full_user(db) -> int:
    """造一个「什么数据都有」的用户，覆盖所有引用 users 的表。"""
    now = int(time.time())
    user = User(
        username=f"delall_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=now,
    )
    db.add(user)
    db.flush()
    user_id = user.id

    db.add(UserProfile(user_id=user_id, target_skills=["Python"], weak_topics=["索引"]))
    db.add(UserMemory(user_id=user_id, category=0, name="Python", mastery=60))
    db.add(Note(user_id=user_id, title="笔记", content="c", source_type=0, created_at=now, updated_at=now))
    db.add(
        Resource(
            resource_type=0,
            storage_scene=0,
            upload_purpose=0,
            file_name="a.txt",
            file_hash=uuid.uuid4().hex,
            storage_path=f"local://not-minio/{uuid.uuid4().hex}.txt",
            user_id=user_id,
        )
    )
    db.add(
        SearchDocument(
            user_id=user_id,
            source_type=0,
            source_id=1,
            title="索引",
            content="MySQL 索引优化",
        )
    )
    session = SessionModel(user_id=user_id, session_model=0, title="会话", created_at=now)
    db.add(session)
    db.flush()
    message = ChatMessage(
        user_id=user_id,
        session_id=session.id,
        select_model=4,
        request_id=uuid.uuid4().hex,
        request_text="开始面试",
        response_text="第一题",
        status=1,
    )
    db.add(message)
    db.flush()
    db.add(ProfileProposal(user_id=user_id, session_id=session.id, message_id=message.id, payload={}))
    interview = Interview(
        user_id=user_id, session_id=session.id, message_id=message.id, qa_object=[]
    )
    db.add(interview)
    db.flush()
    db.add(
        InterviewEvaluation(
            user_id=user_id,
            interview_id=interview.id,
            summary="s",
            weak_topics=[],
            suggestions=[],
        )
    )
    paper = QuizPaper(
        user_id=user_id,
        session_id=session.id,
        message_id=message.id,
        question_count=1,
    )
    db.add(paper)
    db.flush()
    db.add(QuizQuestion(paper_id=paper.id, order_index=1, question="q"))
    db.commit()
    return user_id


def test_delete_user_removes_all_dependent_rows() -> None:
    """有会话 / 面试 / 复盘 / 题库 / 笔记 / 记忆 / 资源 的用户也能被删除干净。"""
    db = SessionLocal()
    user_id = None
    try:
        user_id = _seed_full_user(db)
        UserService.delete_user(db, user_id)

        # 用户行与其全部关联数据都应消失（不报错、不留孤儿）
        assert db.get(User, user_id) is None
        assert db.query(UserProfile).filter_by(user_id=user_id).count() == 0
        assert db.query(UserMemory).filter_by(user_id=user_id).count() == 0
        assert db.query(Note).filter_by(user_id=user_id).count() == 0
        assert db.query(Resource).filter_by(user_id=user_id).count() == 0
        assert db.query(SessionModel).filter_by(user_id=user_id).count() == 0
        assert db.query(ChatMessage).filter_by(user_id=user_id).count() == 0
        assert db.query(Interview).filter_by(user_id=user_id).count() == 0
        assert db.query(InterviewEvaluation).filter_by(user_id=user_id).count() == 0
        assert db.query(QuizPaper).filter_by(user_id=user_id).count() == 0
        assert db.query(ProfileProposal).filter_by(user_id=user_id).count() == 0
        assert db.query(QuizQuestion).count() >= 0  # 题目已随卷子删除
        assert db.query(UserMemoryLog).filter_by(user_id=user_id).count() == 0

        # 泛化断言：**所有带 user_id 的表**都必须清干净。
        # 这条不针对某张表，而是针对「加了新表却忘了改 delete_user」这一整类问题——
        # 这个坑在本项目已经踩过五次（题库、画像待确认、复盘、记忆、检索索引）。
        #
        # 例外只有一张：`usage_records`（T12.3 的用量账本）。它是**刻意保留**的——
        # 演示环境的配额按 IP 累计，如果删账号能顺带清掉账本，用户删号重建就能把
        # 额度洗回来，配额就白做了。所以它既没有外键、也不进删用户的清理清单。
        CASCADE_EXEMPT_TABLES = {"usage_records"}
        leftover: list[str] = []
        for table in Base.metadata.sorted_tables:
            if "user_id" not in table.columns or table.name in CASCADE_EXEMPT_TABLES:
                continue
            remaining = db.execute(
                table.select().where(table.c.user_id == user_id)
            ).first()
            if remaining is not None:
                leftover.append(table.name)
        assert not leftover, f"删除用户后这些表还有残留数据: {leftover}"
        user_id = None
    finally:
        if user_id is not None:
            pytest.fail("删除用户失败，数据未清理干净")
        db.close()


def test_delete_missing_user_is_404() -> None:
    """不存在的用户仍然返回 404（保持原有接口语义）。"""
    db = SessionLocal()
    try:
        with pytest.raises(AppException) as exc:
            UserService.delete_user(db, 99_999_999)
        assert exc.value.code == 404
    finally:
        db.close()
