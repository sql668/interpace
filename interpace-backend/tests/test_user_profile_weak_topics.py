"""T5.8 回归测试：薄弱点合并进用户画像的规则。

纯数据层测试（不需要 HTTP）：去重、保持顺序、超上限截断、缺记录时自动建。
"""

import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_helpers import purge_user

from app.db.database import SessionLocal
from app.db.models import User, UserMemory, UserProfile
from app.services.user_profile_service import UserProfileService


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _make_user(db: Session) -> User:
    user = User(
        username=f"t58_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=int(time.time()),
    )
    db.add(user)
    db.commit()
    return user


def test_creates_profile_when_missing(db_session: Session) -> None:
    """没有画像记录时顺手建一条，不报错。"""
    user = _make_user(db_session)
    try:
        merged = UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["GIL"]
        )
        assert merged == ["GIL"]
        profile = (
            db_session.query(UserProfile)
            .filter(UserProfile.user_id == user.id)
            .first()
        )
        assert profile is not None
        assert profile.weak_topics == ["GIL"]
    finally:
        _cleanup(db_session, user.id)


def test_merge_dedupes_and_keeps_order(db_session: Session) -> None:
    """重复提交不会堆积：已有的不再追加，新的排在后面。"""
    user = _make_user(db_session)
    try:
        UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["GIL", "索引"]
        )
        merged = UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["GIL", "事务隔离", "索引"]
        )
        assert merged == ["GIL", "索引", "事务隔离"]

        # 重复的再来一轮也不变
        again = UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["索引", "GIL"]
        )
        assert again == ["GIL", "索引", "事务隔离"]
    finally:
        _cleanup(db_session, user.id)


def test_merge_truncates_to_max_items(db_session: Session) -> None:
    """超过上限时保留最近的若干条，不会无限增长。"""
    user = _make_user(db_session)
    try:
        UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["t1", "t2", "t3"], max_items=2
        )
        merged = UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["t4"], max_items=2
        )
        assert merged == ["t3", "t4"]
    finally:
        _cleanup(db_session, user.id)


def test_merge_ignores_blank_topics(db_session: Session) -> None:
    """空白与纯空格的知识点被忽略。"""
    user = _make_user(db_session)
    try:
        merged = UserProfileService.merge_weak_topics(
            db_session, user_id=user.id, new_topics=["  ", "GIL", ""]
        )
        assert merged == ["GIL"]
    finally:
        _cleanup(db_session, user.id)


def _cleanup(db: Session, user_id: int) -> None:
    """删掉本用例产生的数据，不给开发库留残留。

    顺序交给共享 helper（记忆日志 / 记忆 / 画像 / 用户）——`users` 被多张表
    NO ACTION 外键引用，手写顺序很容易漏一张（这次就漏了记忆日志）。
    """
    db.rollback()
    db.close()
    purge_user(user_id)
