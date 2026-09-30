"""用户个人信息服务：处理UserProfile表的CRUD操作。"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models import UserProfile
from app.services.user_memory_service import (
    CATEGORY_METHOD,
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    MAX_WEAK_TOPICS,
    MemoryEntry,
    SOURCE_BEHAVIOR,
    UserMemoryService,
    mastery_label,
)


@dataclass(frozen=True)
class InjectionRule:
    """一个场景该怎样把画像注入提示词（T9.7）。

    存在的理由：画像会长（技能到 30 条、薄弱点 50 条），**无差别全塞进去会把
    真正重要的信息稀释掉**，还把提示词顶长。不同场景关心的东西本来就不一样：
    面试看岗位与经验深度，刷题看技能与薄弱点，所以按场景给不同的条数上限与关注点。
    """

    max_skills: int
    max_weak_topics: int
    focus: str  # 追加到提示词末尾的一句话，告诉模型这个场景该重点参考什么
    # 是否注入 L2 的答题方法条目（T9.12）。只在对「怎么答」有意义的场景打开：
    # 模拟面试（点评候选人的回答方式）与面试复盘。知识精讲是讲知识点的地方，
    # 在那里塞「你上次答题漏了量化结果」纯属噪音——**按需加载，不占无关场景的预算**。
    include_methods: bool = False


SCENE_INJECTION_RULES: dict[str, InjectionRule] = {
    "study": InjectionRule(8, 8, "讲解深度按目标级别与经验调整；命中已知薄弱点时，多给一个具体例子。"),
    "quiz": InjectionRule(10, 10, "出题难度与范围按目标级别和已知薄弱点来定；薄弱点要优先覆盖。"),
    "resume": InjectionRule(8, 5, "改简历时对齐目标岗位与级别；技能清单用来判断哪些经历值得突出。"),
    "interview": InjectionRule(
        5,
        8,
        "提问围绕目标岗位与经验深度展开；已知薄弱点用来决定追问方向；"
        "如果给了「答题方法」条目，点评时**具体指出**他这次有没有再犯。",
        include_methods=True,
    ),
    "evaluation": InjectionRule(
        5,
        10,
        "评判标准对齐目标岗位与级别；已知薄弱点是复盘的重点；"
        "如果给了「答题方法」条目，要在总结里点出这些反复出现的问题。",
        include_methods=True,
    ),
    "chat": InjectionRule(8, 5, "回答深度按目标级别调整；命中已知薄弱点时补充必要的背景。"),
}

# 未知场景（例如内部步骤）用这一组：给少一点，避免污染内部抽取的判断
DEFAULT_INJECTION_RULE = InjectionRule(5, 5, "")


def get_injection_rule(scene: str | None) -> InjectionRule:
    """按场景取注入规则；未知场景回退到最小集合。"""
    return SCENE_INJECTION_RULES.get(scene or "", DEFAULT_INJECTION_RULE)

class UserProfileService:
    """用户个人信息服务。"""
    
    @staticmethod
    def get_user_profile(db: Session, user_id: int) -> Optional[UserProfile]:
        """读取用户个人信息"""
        return db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
    
    @staticmethod
    def create_user_profile(
        db: Session,
        user_id: int,
        target_job: Optional[str] = None,
        years_experience: Optional[str] = None,
        target_level: Optional[str] = None,
        target_skills: Optional[list[str]] = None,
        weak_topics: Optional[list[str]] = None,
    ) -> UserProfile:
        """创建用户个人信息"""
        profile = UserProfile(
            user_id=user_id,
            target_job=target_job,
            years_experience=years_experience,
            target_level=target_level,
            target_skills=target_skills or [],
            weak_topics=weak_topics or [],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    
    @staticmethod
    def update_user_profile(
        db: Session,
        user_id: int,
        target_job: Optional[str] = None,
        years_experience: Optional[str] = None,
        target_level: Optional[str] = None,
        target_skills: Optional[list[str]] = None,
        weak_topics: Optional[list[str]] = None,
    ) -> Optional[UserProfile]:
        """更新用户个人信息（仅更新非None字段）"""
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if not profile:
            return None
        
        if target_job is not None:
            profile.target_job = target_job
        if years_experience is not None:
            profile.years_experience = years_experience
        if target_level is not None:
            profile.target_level = target_level
        if target_skills is not None:
            profile.target_skills = target_skills
        if weak_topics is not None:
            profile.weak_topics = weak_topics
        
        db.commit()
        db.refresh(profile)
        return profile
    
    @staticmethod
    def delete_user_profile(db: Session, user_id: int) -> bool:
        """删除用户个人信息"""
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if not profile:
            return False
        
        db.delete(profile)
        db.commit()
        return True

    @staticmethod
    def merge_weak_topics(
        db: Session,
        user_id: int,
        new_topics: list[str],
        *,
        commit: bool = True,
        max_items: int = MAX_WEAK_TOPICS,
    ) -> list[str]:
        """把一批薄弱点合并进画像，返回合并后的薄弱点列表。

        **T9.6 起这里是统一写入入口的薄封装**：真正的合并逻辑（来源权重、证据计数、
        派生缓存重建、容量上限）都在 `UserMemoryService.ingest` 里，三个业务场景
        （刷题评分、面试复盘、简历确认）共用同一套规则，不再各写一遍。

        保留这个函数是因为它的签名更贴近调用方想表达的意思（「我有一批薄弱点」），
        调用方不需要自己去构造 `MemoryEntry`。
        """
        entries = [
            MemoryEntry(category=CATEGORY_WEAK_TOPIC, name=str(topic).strip(), mastery=30, confidence=70)
            for topic in new_topics
            if str(topic).strip()
        ]
        UserMemoryService.ingest(
            db,
            user_id=user_id,
            entries=entries,
            source=SOURCE_BEHAVIOR,
            max_weak_topics=max_items,
            commit=commit,
        )
        profile = UserProfileService.get_user_profile(db, user_id)
        return list(profile.weak_topics) if profile and profile.weak_topics else []

    @staticmethod
    def get_profile_dict(db: Session, user_id: int) -> dict:
        """读取用户信息转字典（缺失字段使用默认值）。

        **技能与薄弱点优先从 `user_memories` 读**（T9.2 起它才是真源），
        并带上掌握程度档位——「薄弱点：MySQL 索引优化(待加强)」比光有一个名字
        给模型的信息多得多。明细表还没有数据时（例如没跑过回填的旧环境）
        回退到 `user_profiles` 的两个 JSON 派生列。
        """
        profile = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()

        memories = UserMemoryService.list_memories(db, user_id=user_id)
        # 技能：掌握度高的排前面（先看会的）
        skills = [
            f"{m.name}({mastery_label(m.mastery)})"
            for m in memories
            if m.category == CATEGORY_SKILL
        ]
        # 薄弱点：掌握度低的排前面（先看最该补的）
        weak = [
            f"{m.name}({mastery_label(m.mastery)})"
            for m in sorted(
                (m for m in memories if m.category == CATEGORY_WEAK_TOPIC),
                key=lambda m: m.mastery,
            )
        ]
        if not skills:
            skills = list(profile.target_skills) if profile and profile.target_skills else []
        if not weak:
            weak = list(profile.weak_topics) if profile and profile.weak_topics else []

        # L2 答题方法（T9.12）：单独一项，是否注入由场景规则决定
        answer_methods = [
            f"{m.name}({mastery_label(m.mastery)})"
            for m in memories
            if m.category == CATEGORY_METHOD
        ]

        return {
            "target_job": profile.target_job if profile and profile.target_job else "未指定",
            "years_experience": profile.years_experience if profile and profile.years_experience else "未指定",
            "target_level": profile.target_level if profile and profile.target_level else "未指定",
            "target_skills": skills,
            "weak_topics": weak,
            "answer_methods": answer_methods,
        }
    
    @staticmethod
    def format_profile_for_injection(
        profile_dict: dict, scene: str | None = None
    ) -> dict:
        """格式化用户信息用于提示词注入（数组→文本），并按场景裁剪条数（T9.7）。

        转换规则：["Python", "FastAPI"] → "Python、FastAPI"。
        裁剪规则来自 `SCENE_INJECTION_RULES`：不传 scene 时用最小集合。
        """
        rule = get_injection_rule(scene)

        def _join(values: object, limit: int) -> str:
            if not isinstance(values, list) or not values:
                return "未指定"
            # 已经排好序（技能由强到弱、薄弱点由弱到强），裁剪只取前 limit 条
            picked = [str(v) for v in values[:limit]] if limit > 0 else []
            return "、".join(picked) if picked else "未指定"

        return {
            "target_job": str(profile_dict.get("target_job", "未指定")),
            "years_experience": str(profile_dict.get("years_experience", "未指定")),
            "target_level": str(profile_dict.get("target_level", "未指定")),
            "target_skills": _join(profile_dict.get("target_skills"), rule.max_skills),
            "weak_topics": _join(profile_dict.get("weak_topics"), rule.max_weak_topics),
        }
