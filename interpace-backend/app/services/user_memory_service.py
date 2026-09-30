"""能力类长期记忆的服务层（T9.2 / T9.3 的底座）。

三层记忆里 L1 与 L2 都落在这张 `user_memories` 表上，区别只在 `category`：
**陈述性事实（技能、薄弱点）是 L1，可复用的做法（答题方法）是 L2**——
这是 Hermes 的判据，也是 T9.10 的结论。

合并规则（按本阶段「画像来源策略」，对应 D21 的参数先取一组可配置默认值）：

1. **来源权重**：行为证据 > 用户自述 ≈ 简历声明 > 模型推断。
   弱来源**不会覆盖**强来源的掌握程度，只增加证据计数（「又观察到一次」）。
2. **同权重合并**用证据数加权平均，避免一次偶发观测把结论带偏。
3. **证据计数与时间**每次写入都刷新，供 T9.8 的容量整合与时间衰减使用。
"""

import json
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import UserMemory, UserMemoryLog

# category 取值
CATEGORY_SKILL = 0  # 技能（L1）
CATEGORY_WEAK_TOPIC = 1  # 薄弱点（L1）
CATEGORY_METHOD = 2  # 答题方法 / 反复出现的表达问题（L2）

CATEGORY_LABELS = {
    CATEGORY_SKILL: "技能",
    CATEGORY_WEAK_TOPIC: "薄弱点",
    CATEGORY_METHOD: "答题方法",
}

# source 取值
SOURCE_INFERENCE = 0  # 模型推断
SOURCE_SELF_REPORT = 1  # 用户自述
SOURCE_RESUME = 2  # 简历声明
SOURCE_BEHAVIOR = 3  # 行为证据（刷题得分、面试表现）

# 来源权重：数值越大越可信。行为证据能覆盖简历里的「精通」声明，
# 反之则不成立——这正是「画像来源策略」里定的能力类字段合并规则。
SOURCE_WEIGHTS = {
    SOURCE_INFERENCE: 1,
    SOURCE_SELF_REPORT: 2,
    SOURCE_RESUME: 2,
    SOURCE_BEHAVIOR: 3,
}

SOURCE_LABELS = {
    SOURCE_INFERENCE: "模型推断",
    SOURCE_SELF_REPORT: "你的自述",
    SOURCE_RESUME: "简历",
    SOURCE_BEHAVIOR: "答题与面试表现",
}

# 变更日志的动作名 → 中文（T9.9 的回溯展示）
MEMORY_LOG_ACTION_LABELS = {
    "created": "新增",
    "merged": "合并更新",
    "approved": "已批准",
    "rejected": "已拒绝",
    "updated": "你修改了",
    "deleted": "已删除",
}

# 掌握程度对外只给四档：用户看到「73 分」只会纠结为什么不是 80，
# 看到「熟悉」才知道下一步该干嘛。
MASTERY_LEVELS = (
    (80, "熟练"),
    (60, "熟悉"),
    (35, "了解"),
    (0, "待加强"),
)

# 掌握程度上限/下限，防止越界数据写进去
MASTERY_MIN = 0
MASTERY_MAX = 100

# 能力类字段的条目上限（T9.8，对齐 Hermes 的「容量必须封顶」）。
#
# 达到上限时**新增写入直接报错**，而不是静默淘汰旧条目——Hermes 的原话是
# 「超限写入直接报错而不是静默丢弃，逼 agent 在同一轮内做整合」。
# 静默淘汰最坏的结果是：用户不知道系统把自己说过的东西丢了。
#
# 计数包含待确认的条目（它们也占存储），但**只对「新增」生效**：
# 命中已有条目属于合并，不增加条数，永远不该被容量挡住。
CATEGORY_LIMITS = {
    CATEGORY_SKILL: 30,
    CATEGORY_WEAK_TOPIC: 20,
    CATEGORY_METHOD: 20,
}

# 派生缓存的容量：与表上限保持一致，避免「表里有 30 条、注入只有 20 条」这种
# 说不清的差异（注入还会按场景再裁一次，那是另一回事）。
MAX_SKILLS = CATEGORY_LIMITS[CATEGORY_SKILL]
MAX_WEAK_TOPICS = CATEGORY_LIMITS[CATEGORY_WEAK_TOPIC]


class MemoryCapacityExceeded(RuntimeError):
    """某个类别的能力条目已达上限，且这次要新增一条。

    这是**领域异常**不是 HTTP 错误：抽取服务会捕获它、先做一次整合再重试；
    重试后仍然超限才会往上抛（那时才是真的该报错）。
    """

    def __init__(self, category: int, limit: int, current: int) -> None:
        self.category = category
        self.limit = limit
        self.current = current
        label = CATEGORY_LABELS.get(category, str(category))
        super().__init__(f"{label}条目已达上限 {limit}（当前 {current}），需要先整合")


@dataclass(frozen=True)
class MemoryEntry:
    """一条待写入的能力条目。

    结构化来源（刷题评分、面试复盘、简历确认）已经有条目名，直接用它落库；
    非结构化来源（简历正文、用户自述）才需要 T9.5 的模型抽取先产出条目。
    """

    category: int
    name: str
    mastery: int = 50
    confidence: int = 60


def mastery_label(mastery: int) -> str:
    """把 0-100 的掌握程度映射成对外展示的四档。"""
    for threshold, label in MASTERY_LEVELS:
        if mastery >= threshold:
            return label
    return MASTERY_LEVELS[-1][1]


def _clamp(value: int, low: int = MASTERY_MIN, high: int = MASTERY_MAX) -> int:
    return max(low, min(high, int(value)))


class UserMemoryService:
    """能力类记忆的增删改查与合并。"""

    @staticmethod
    def _snapshot(memory: UserMemory) -> str:
        """把一条记忆存成快照文本，供日志记录「改之前是什么样」。"""
        return json.dumps(
            {
                "category": memory.category,
                "name": memory.name,
                "mastery": memory.mastery,
                "source": memory.source,
                "confidence": memory.confidence,
                "evidence_count": memory.evidence_count,
                "pending_approval": memory.pending_approval,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _log(
        db: Session,
        *,
        user_id: int,
        memory: UserMemory | None,
        category: int,
        name: str,
        action: str,
        before: str | None = None,
        after: str | None = None,
    ) -> None:
        """写一条变更日志（T9.9）。

        为什么值得单独建表：用户能改能删，就必须能回答「系统原来记的是什么」。
        尤其是**自动写入覆盖了用户手改过的条目**时，没有原文就无从回溯。
        """
        db.add(
            UserMemoryLog(
                user_id=user_id,
                memory_id=memory.id if memory is not None else None,
                category=category,
                name=name,
                action=action,
                before_json=before,
                after_json=after,
            )
        )

    @staticmethod
    def list_logs(
        db: Session, *, user_id: int, limit: int = 50
    ) -> list[UserMemoryLog]:
        """最近的变更日志（新的在前），用于「我的画像」页的回溯展示。"""
        return list(
            db.scalars(
                select(UserMemoryLog)
                .where(UserMemoryLog.user_id == user_id)
                .order_by(UserMemoryLog.id.desc())
                .limit(limit)
            )
        )

    @staticmethod
    def approve(
        db: Session, *, user_id: int, memory_id: int, commit: bool = True
    ) -> UserMemory:
        """批准一条待确认记忆：批准后它才开始影响对话（D20）。"""
        memory = UserMemoryService.get_or_404(
            db, user_id=user_id, memory_id=memory_id
        )
        before = UserMemoryService._snapshot(memory)
        memory.pending_approval = 0
        db.add(memory)
        db.flush()
        UserMemoryService._log(
            db,
            user_id=user_id,
            memory=memory,
            category=memory.category,
            name=memory.name,
            action="approved",
            before=before,
            after=UserMemoryService._snapshot(memory),
        )
        UserMemoryService.rebuild_profile_cache(db, user_id=user_id)
        if commit:
            db.commit()
            db.refresh(memory)
        return memory

    @staticmethod
    def reject(
        db: Session, *, user_id: int, memory_id: int, commit: bool = True
    ) -> None:
        """拒绝一条待确认记忆：直接删掉，并留下原文便于回溯。

        拒绝用「删除」而不是「标记为已拒绝」：用户明确说不要的东西，
        留着只会在列表里反复出现，也占着容量。
        """
        memory = UserMemoryService.get_or_404(
            db, user_id=user_id, memory_id=memory_id
        )
        before = UserMemoryService._snapshot(memory)
        category, name = memory.category, memory.name
        db.delete(memory)
        db.flush()
        UserMemoryService._log(
            db,
            user_id=user_id,
            memory=None,  # 条目已删，日志里只留快照
            category=category,
            name=name,
            action="rejected",
            before=before,
        )
        UserMemoryService.rebuild_profile_cache(db, user_id=user_id)
        if commit:
            db.commit()

    @staticmethod
    def count_entries(db: Session, *, user_id: int, category: int) -> int:
        """某个类别的条目数（**含待确认条目**：它们一样占存储）。"""
        from sqlalchemy import func

        return int(
            db.scalar(
                select(func.count(UserMemory.id)).where(
                    UserMemory.user_id == user_id,
                    UserMemory.category == category,
                )
            )
            or 0
        )

    @staticmethod
    def delete_by_name(
        db: Session, *, user_id: int, category: int, name: str, commit: bool = False
    ) -> bool:
        """按 (类别, 名字) 删除条目；用于整合时淘汰旧条目。"""
        memory = db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.category == category,
                UserMemory.name == name,
            )
        )
        if memory is None:
            return False
        db.delete(memory)
        if commit:
            db.commit()
        else:
            db.flush()
        return True

    @staticmethod
    def get_or_404(db: Session, *, user_id: int, memory_id: int) -> UserMemory:
        """按 ID 取条目；不存在或不属于当前用户一律 404（不泄露他人数据是否存在）。"""
        memory = db.scalar(
            select(UserMemory).where(
                UserMemory.id == memory_id, UserMemory.user_id == user_id
            )
        )
        if memory is None:
            raise_error(code=404, message="记忆条目不存在")
        return memory

    @staticmethod
    def list_memories(
        db: Session,
        *,
        user_id: int,
        category: int | None = None,
        include_pending: bool = False,
    ) -> list[UserMemory]:
        """列出条目：掌握度高的在前，同分按最近证据时间倒序。"""
        stmt = select(UserMemory).where(UserMemory.user_id == user_id)
        if category is not None:
            stmt = stmt.where(UserMemory.category == category)
        if not include_pending:
            # 待确认的条目（T9.9）默认不影响对话，只在治理页面里可见
            stmt = stmt.where(UserMemory.pending_approval == 0)
        stmt = stmt.order_by(
            UserMemory.mastery.desc(), UserMemory.last_evidence_at.desc()
        )
        return list(db.scalars(stmt))

    @staticmethod
    def upsert_memory(
        db: Session,
        *,
        user_id: int,
        category: int,
        name: str,
        mastery: int,
        source: int,
        confidence: int = 60,
        pending_approval: bool = False,
        commit: bool = False,
    ) -> UserMemory:
        """写入或合并一条能力记忆，返回最终条目。

        合并逻辑见模块注释；**只 flush 不 commit**（默认），事务边界交给调用方。
        """
        text = (name or "").strip()
        if not text:
            raise_error(code=400, message="记忆条目名不能为空")
        if category not in CATEGORY_LABELS:
            raise_error(code=400, message=f"不支持的记忆类别: {category}")

        now = int(time.time())
        mastery_value = _clamp(mastery)
        confidence_value = _clamp(confidence)

        existing = db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.category == category,
                UserMemory.name == text,
            )
        )
        if existing is None:
            # 新增前先查容量：**超限直接报错**，交给上层整合后重试（T9.8）
            limit = CATEGORY_LIMITS.get(category)
            if limit is not None:
                current = UserMemoryService.count_entries(
                    db, user_id=user_id, category=category
                )
                if current >= limit:
                    raise MemoryCapacityExceeded(category, limit, current)
            memory = UserMemory(
                user_id=user_id,
                category=category,
                name=text,
                mastery=mastery_value,
                source=source,
                confidence=confidence_value,
                evidence_count=1,
                last_evidence_at=now,
                pending_approval=1 if pending_approval else 0,
            )
            db.add(memory)
            db.flush()
            return memory

        # 已有条目：先按来源权重决定能不能改写掌握程度
        before = UserMemoryService._snapshot(existing)
        old_weight = SOURCE_WEIGHTS.get(existing.source, 1)
        new_weight = SOURCE_WEIGHTS.get(source, 1)
        if new_weight >= old_weight:
            # 同权重做证据数加权平均，避免一次偶发观测把结论带偏；
            # 更强的来源则直接采纳（行为证据推翻简历声明就发生在这里）。
            if new_weight == old_weight and existing.evidence_count > 0:
                total = existing.mastery * existing.evidence_count + mastery_value
                existing.mastery = _clamp(round(total / (existing.evidence_count + 1)))
            else:
                existing.mastery = mastery_value
            existing.source = source

        existing.confidence = max(existing.confidence, confidence_value)
        existing.evidence_count += 1
        existing.last_evidence_at = now
        if not pending_approval:
            # 用户主动编辑或已确认过的条目，不该再被打回待确认
            existing.pending_approval = 0
        after = UserMemoryService._snapshot(existing)
        db.add(existing)
        db.flush()
        if before != after:
            # 只有真的改了才记日志，避免每次重复观测都留一条噪声
            UserMemoryService._log(
                db,
                user_id=user_id,
                memory=existing,
                category=existing.category,
                name=existing.name,
                action="merged",
                before=before,
                after=after,
            )
        return existing

    @staticmethod
    def update_memory(
        db: Session,
        *,
        user_id: int,
        memory_id: int,
        name: str | None = None,
        mastery: int | None = None,
        commit: bool = True,
    ) -> UserMemory:
        """用户手动修改条目（「我的画像」页），改完即生效、不再待确认。"""
        memory = UserMemoryService.get_or_404(
            db, user_id=user_id, memory_id=memory_id
        )
        if name is not None:
            text = name.strip()
            if not text:
                raise_error(code=400, message="记忆条目名不能为空")
            memory.name = text
        if mastery is not None:
            memory.mastery = _clamp(mastery)
        # 用户手动改过就按「用户自述」记账，并标为已生效
        memory.source = SOURCE_SELF_REPORT
        memory.pending_approval = 0
        db.add(memory)
        if commit:
            db.commit()
            db.refresh(memory)
        return memory

    @staticmethod
    def delete_memory(
        db: Session, *, user_id: int, memory_id: int, commit: bool = True
    ) -> None:
        """删除条目：用户有权删掉系统记错的东西（D19 的要求）。"""
        memory = UserMemoryService.get_or_404(
            db, user_id=user_id, memory_id=memory_id
        )
        db.delete(memory)
        if commit:
            db.commit()
        else:
            db.flush()

    @staticmethod
    def ingest(
        db: Session,
        *,
        user_id: int,
        entries: list[MemoryEntry],
        source: int,
        pending_approval: bool | None = None,
        max_skills: int = MAX_SKILLS,
        max_weak_topics: int = MAX_WEAK_TOPICS,
        commit: bool = False,
    ) -> list[str]:
        """**统一写入入口**（T9.6）：一批已知条目入库 + 重建派生缓存。

        刷题评分、面试复盘、简历确认三个来源都走这里，不再各写一套
        「写 JSON + 去重」的逻辑。`pending_approval=None` 时按来源自动决定：
        模型推断类需要用户确认，其余直接生效（D20）。

        返回成功写入的条目名。
        """
        if not entries:
            return []

        need_approval = (
            source == SOURCE_INFERENCE if pending_approval is None else pending_approval
        )
        written: list[str] = []
        for entry in entries:
            memory = UserMemoryService.upsert_memory(
                db,
                user_id=user_id,
                category=entry.category,
                name=entry.name,
                mastery=entry.mastery,
                source=source,
                confidence=entry.confidence,
                pending_approval=need_approval,
            )
            written.append(memory.name)

        UserMemoryService.rebuild_profile_cache(
            db, user_id=user_id, max_skills=max_skills, max_weak_topics=max_weak_topics
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return written

    @staticmethod
    def rebuild_profile_cache(
        db: Session,
        *,
        user_id: int,
        max_skills: int = MAX_SKILLS,
        max_weak_topics: int = MAX_WEAK_TOPICS,
    ) -> tuple[list[str], list[str]]:
        """把 `user_profiles` 的两个 JSON 数组按明细表重建（T9.2 定的「派生缓存」）。

        缓存存在的唯一理由是：既有提示词注入与前端展示都读这两个扁平列表，
        一次性改掉所有读者风险大（等 T9.7 重写注入时再收敛）。

        排序刻意保持**改造前的语义**，避免悄悄改变注入给模型的内容顺序：
        技能按掌握度从高到低（先看会的），薄弱点按**加入顺序**（先加入的先出现）。
        容量超出时薄弱点丢弃最早的，与原来的 `merge_weak_topics` 行为一致。
        待确认的条目不进缓存：批准前不该影响对话（D20）。
        """
        skills = [
            row.name
            for row in db.scalars(
                select(UserMemory)
                .where(
                    UserMemory.user_id == user_id,
                    UserMemory.category == CATEGORY_SKILL,
                    UserMemory.pending_approval == 0,
                )
                .order_by(UserMemory.mastery.desc(), UserMemory.id.asc())
            )
        ][:max_skills]

        weak_names = [
            row.name
            for row in db.scalars(
                select(UserMemory)
                .where(
                    UserMemory.user_id == user_id,
                    UserMemory.category == CATEGORY_WEAK_TOPIC,
                    UserMemory.pending_approval == 0,
                )
                .order_by(UserMemory.id.asc())
            )
        ]
        weak_topics = weak_names[-max_weak_topics:] if max_weak_topics > 0 else []

        # 局部导入避免与 user_profile_service 形成循环依赖
        from app.db.models import UserProfile

        profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        if profile is None:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
        profile.target_skills = skills
        profile.weak_topics = weak_topics
        db.add(profile)
        db.flush()
        return skills, weak_topics
