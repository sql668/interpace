"""T9.2 / T9.3 回归测试：能力类记忆的明细结构与画像读写接口。

重点覆盖三件事：
1. **合并规则**（阶段 9 的来源策略）：行为证据能覆盖简历声明，弱来源不能反向覆盖；
2. **接口隔离**：A 用户改不到 / 删不掉 B 用户的条目，一律 404；
3. **既有链路不受影响**：老写入路径（merge_weak_topics）会同时写明细表，
   且 JSON 派生缓存仍可被提示词注入读取。
"""

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_helpers import purge_user

from app.db.database import SessionLocal
from app.db.models import UserMemory
from app.services.user_memory_service import (
    CATEGORY_METHOD,
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    SOURCE_BEHAVIOR,
    SOURCE_RESUME,
    SOURCE_SELF_REPORT,
    UserMemoryService,
    mastery_label,
)
from app.services.user_profile_service import UserProfileService

RegisterAndLogin = Callable[[str], Awaitable[dict[str, str]]]


def test_mastery_label_buckets() -> None:
    """掌握程度对外只给四档：分数是内部结构，对用户没有意义。"""
    assert [mastery_label(v) for v in (95, 80, 79, 60, 59, 35, 34, 0)] == [
        "熟练",
        "熟练",
        "熟悉",
        "熟悉",
        "了解",
        "了解",
        "待加强",
        "待加强",
    ]


def test_behavior_evidence_overrides_resume_claim() -> None:
    """行为证据覆盖简历声明；反过来不行（这是能力类字段的核心合并规则）。"""
    db = SessionLocal()
    user_id = None
    try:
        from app.db.models import User
        import time
        import uuid

        user = User(
            username=f"mem_{uuid.uuid4().hex[:8]}",
            password="x" * 12,
            avatar=None,
            create_time=int(time.time()),
        )
        db.add(user)
        db.commit()
        user_id = user.id

        # 简历自报「精通 Python」→ 90 分，来源=简历
        UserMemoryService.upsert_memory(
            db,
            user_id=user_id,
            category=CATEGORY_SKILL,
            name="Python",
            mastery=90,
            source=SOURCE_RESUME,
            confidence=70,
        )
        db.commit()

        # 刷题表现不好 → 行为证据 40 分，应当覆盖
        memory = UserMemoryService.upsert_memory(
            db,
            user_id=user_id,
            category=CATEGORY_SKILL,
            name="Python",
            mastery=40,
            source=SOURCE_BEHAVIOR,
            confidence=80,
        )
        db.commit()
        assert memory.mastery == 40
        assert memory.source == SOURCE_BEHAVIOR
        assert memory.evidence_count == 2

        # 再拿简历去覆盖行为证据：不成立，只增加证据计数
        again = UserMemoryService.upsert_memory(
            db,
            user_id=user_id,
            category=CATEGORY_SKILL,
            name="Python",
            mastery=95,
            source=SOURCE_RESUME,
            confidence=70,
        )
        db.commit()
        assert again.mastery == 40  # 弱来源不覆盖
        assert again.evidence_count == 3
    finally:
        if user_id is not None:
            db.rollback()
        db.close()
        if user_id is not None:
            # 统一走共享清理：顺序与外键依赖一致（记忆日志/记忆/画像/用户）
            purge_user(user_id)


def test_same_source_uses_evidence_weighted_average() -> None:
    """同来源重复观测取加权平均，避免一次偶发观测把结论带偏。"""
    db = SessionLocal()
    user_id = None
    try:
        from app.db.models import User
        import time
        import uuid

        user = User(
            username=f"mem2_{uuid.uuid4().hex[:8]}",
            password="x" * 12,
            avatar=None,
            create_time=int(time.time()),
        )
        db.add(user)
        db.commit()
        user_id = user.id

        UserMemoryService.upsert_memory(
            db,
            user_id=user_id,
            category=CATEGORY_WEAK_TOPIC,
            name="索引失效",
            mastery=40,
            source=SOURCE_BEHAVIOR,
        )
        memory = UserMemoryService.upsert_memory(
            db,
            user_id=user_id,
            category=CATEGORY_WEAK_TOPIC,
            name="索引失效",
            mastery=70,
            source=SOURCE_BEHAVIOR,
        )
        db.commit()
        assert memory.mastery == round((40 * 1 + 70) / 2)  # 55
        assert memory.evidence_count == 2
    finally:
        if user_id is not None:
            db.rollback()
        db.close()
        if user_id is not None:
            # 统一走共享清理：顺序与外键依赖一致（记忆日志/记忆/画像/用户）
            purge_user(user_id)


def test_legacy_weak_topics_write_also_fills_memory_table() -> None:
    """老路径（T5.8 / T8.4 用的 merge_weak_topics）要同时写明细表。

    这样新表从第一天就有真实数据，而不是空跑到 T9.6 才统一入口。
    """
    db = SessionLocal()
    user_id = None
    try:
        from app.db.models import User
        import time
        import uuid

        user = User(
            username=f"mem3_{uuid.uuid4().hex[:8]}",
            password="x" * 12,
            avatar=None,
            create_time=int(time.time()),
        )
        db.add(user)
        db.commit()
        user_id = user.id

        UserProfileService.merge_weak_topics(
            db, user_id=user_id, new_topics=["MySQL 索引优化", "GIL 并发模型"]
        )
        profile = UserProfileService.get_user_profile(db, user_id)
        assert profile is not None
        # JSON 派生缓存仍在（既有提示词注入读它）
        assert profile.weak_topics == ["MySQL 索引优化", "GIL 并发模型"]

        memories = UserMemoryService.list_memories(
            db, user_id=user_id, category=CATEGORY_WEAK_TOPIC
        )
        assert {m.name for m in memories} == {"MySQL 索引优化", "GIL 并发模型"}
        assert all(m.source == SOURCE_BEHAVIOR for m in memories)
    finally:
        if user_id is not None:
            db.rollback()
        db.close()
        if user_id is not None:
            # 统一走共享清理：顺序与外键依赖一致（记忆日志/记忆/画像/用户）
            purge_user(user_id)


@pytest.mark.anyio
async def test_profile_api_crud(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """画像接口：读空画像 → 改意图字段 → 增删改记忆条目。"""
    headers = await register_and_login("prof")
    # 用例内建的数据在最后清理干净（注册出来的用户行沿用其它用例的做法保留）
    created_ids: list[int] = []
    try:
        empty = await async_client.get("/profile", headers=headers)
        assert empty.status_code == 200, empty.text
        body = empty.json()
        assert body["intent"]["target_job"] is None
        assert body["memories"] == []

        updated = await async_client.put(
            "/profile",
            json={"target_job": "Python 后端", "target_level": "中级"},
            headers=headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["intent"]["target_job"] == "Python 后端"

        created = await async_client.post(
            "/profile/memories",
            json={"category": CATEGORY_SKILL, "name": "FastAPI", "mastery": 85},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        item = created.json()
        created_ids.append(item["id"])
        assert item["mastery_label"] == "熟练"
        assert item["source"] == SOURCE_SELF_REPORT
        assert item["category_label"] == "技能"
        memory_id = item["id"]

        patched = await async_client.put(
            f"/profile/memories/{memory_id}",
            json={"mastery": 40},
            headers=headers,
        )
        assert patched.status_code == 200
        assert patched.json()["mastery_label"] == "了解"

        listed = await async_client.get("/profile/memories", headers=headers)
        assert [m["name"] for m in listed.json()] == ["FastAPI"]

        filtered = await async_client.get(
            "/profile/memories", params={"category": CATEGORY_METHOD}, headers=headers
        )
        assert filtered.json() == []

        removed = await async_client.delete(
            f"/profile/memories/{memory_id}", headers=headers
        )
        assert removed.status_code == 204
        assert (await async_client.get("/profile/memories", headers=headers)).json() == []
    finally:
        for memory_id in created_ids:
            # 已经删掉的再删会 404，这里只做兜底，失败也无所谓
            await async_client.delete(f"/profile/memories/{memory_id}", headers=headers)


@pytest.mark.anyio
async def test_other_users_memory_is_404(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """别人的记忆条目：改与删都是 404。"""
    owner_headers = await register_and_login("memowner")
    intruder_headers = await register_and_login("memintruder")

    created = await async_client.post(
        "/profile/memories",
        json={"category": CATEGORY_SKILL, "name": "Docker", "mastery": 60},
        headers=owner_headers,
    )
    memory_id = created.json()["id"]

    patched = await async_client.put(
        f"/profile/memories/{memory_id}", json={"mastery": 10}, headers=intruder_headers
    )
    assert patched.status_code == 404
    removed = await async_client.delete(
        f"/profile/memories/{memory_id}", headers=intruder_headers
    )
    assert removed.status_code == 404
    # 侵入者自己的画像里不该看到别人的条目
    listed = await async_client.get("/profile/memories", headers=intruder_headers)
    assert listed.json() == []


# ---------------- T9.9 写入审批与治理 ----------------


@pytest.mark.anyio
async def test_pending_memory_needs_approval_before_affecting_conversation(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """自动抽取的记忆在批准前不影响对话，批准后才进入画像缓存。"""
    from app.db.database import SessionLocal
    from app.db.models import User
    from app.services.user_memory_service import (
        CATEGORY_SKILL,
        SOURCE_INFERENCE,
        MemoryEntry,
        UserMemoryService,
    )

    headers = await register_and_login("appr")
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        UserMemoryService.ingest(
            db,
            user_id=user.id,
            entries=[MemoryEntry(category=CATEGORY_SKILL, name="Docker", mastery=60)],
            source=SOURCE_INFERENCE,  # 模型推断 → 待确认
            commit=True,
        )

        # 批准前：不在生效列表里，也不进派生缓存（也就是不影响对话）
        effective = await async_client.get("/profile/memories", headers=headers)
        assert [m["name"] for m in effective.json() if m["pending_approval"] == 0] == []
        profile = await async_client.get("/profile", headers=headers)
        assert profile.json()["target_skills"] == []

        # 待确认列表能看到
        pending = await async_client.get("/profile/memories/pending", headers=headers)
        assert [m["name"] for m in pending.json()] == ["Docker"]

        memory_id = pending.json()[0]["id"]
        approved = await async_client.post(
            f"/profile/memories/{memory_id}/approve", headers=headers
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["pending_approval"] == 0

        # 批准后进入画像缓存
        profile = await async_client.get("/profile", headers=headers)
        assert profile.json()["target_skills"] == ["Docker"]

        # 日志里有「已批准」这一条，且记录了原文
        logs = await async_client.get("/profile/memory-logs", headers=headers)
        actions = [item["action"] for item in logs.json()]
        assert "approved" in actions
        approved_log = next(item for item in logs.json() if item["action"] == "approved")
        assert approved_log["before_json"] is not None
        assert approved_log["action_label"] == "已批准"
    finally:
        db.close()


@pytest.mark.anyio
async def test_reject_removes_memory_and_keeps_log(
    async_client: AsyncClient,
    register_and_login: RegisterAndLogin,
) -> None:
    """拒绝：条目消失、缓存里也没有，但日志留了原文便于回溯。"""
    from app.db.database import SessionLocal
    from app.db.models import User
    from app.services.user_memory_service import (
        CATEGORY_WEAK_TOPIC,
        SOURCE_INFERENCE,
        MemoryEntry,
        UserMemoryService,
    )

    headers = await register_and_login("rej")
    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        UserMemoryService.ingest(
            db,
            user_id=user.id,
            entries=[MemoryEntry(category=CATEGORY_WEAK_TOPIC, name="乱猜的薄弱点")],
            source=SOURCE_INFERENCE,
            commit=True,
        )

        pending = await async_client.get("/profile/memories/pending", headers=headers)
        memory_id = pending.json()[0]["id"]

        rejected = await async_client.post(
            f"/profile/memories/{memory_id}/reject", headers=headers
        )
        assert rejected.status_code == 204

        # 拒绝后不再出现在任何列表里
        assert (await async_client.get("/profile/memories/pending", headers=headers)).json() == []
        assert (await async_client.get("/profile/memories", headers=headers)).json() == []

        # 但日志里有原文
        logs = await async_client.get("/profile/memory-logs", headers=headers)
        rejected_log = next(item for item in logs.json() if item["action"] == "rejected")
        assert rejected_log["name"] == "乱猜的薄弱点"
        assert "乱猜的薄弱点" in rejected_log["before_json"]
    finally:
        db.close()
