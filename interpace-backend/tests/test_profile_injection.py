"""T9.7 回归测试：画像注入的按场景裁剪。

背景：画像会长（技能 30 条、薄弱点 50 条），无差别全塞进提示词会把真正重要的
信息稀释掉。所以按场景给不同的条数上限与关注点。
"""

import sys
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.user_profile_service import (
    DEFAULT_INJECTION_RULE,
    SCENE_INJECTION_RULES,
    UserProfileService,
    get_injection_rule,
)


def _long_profile() -> dict:
    return {
        "target_job": "Python 后端",
        "years_experience": "4 年",
        "target_level": "中级",
        "target_skills": [f"技能{i}" for i in range(1, 31)],
        "weak_topics": [f"薄弱{i}" for i in range(1, 51)],
    }


def test_injection_is_trimmed_per_scene() -> None:
    """每个场景按自己的上限裁剪，且只取排序后的前 N 条。"""
    profile = _long_profile()
    for scene, rule in SCENE_INJECTION_RULES.items():
        formatted = UserProfileService.format_profile_for_injection(profile, scene=scene)
        skills = formatted["target_skills"].split("、")
        weak = formatted["weak_topics"].split("、")
        assert len(skills) == rule.max_skills, scene
        assert len(weak) == rule.max_weak_topics, scene
        # 取的是前 N 条（技能由强到弱、薄弱点由弱到强，排序由 get_profile_dict 负责）
        assert skills[0] == "技能1"
        assert weak[0] == "薄弱1"


def test_interview_scene_keeps_fewer_skills_than_quiz() -> None:
    """面试场景重岗位与经验，技能与薄弱点给得比刷题场景少。"""
    assert SCENE_INJECTION_RULES["interview"].max_skills < SCENE_INJECTION_RULES["quiz"].max_skills
    assert SCENE_INJECTION_RULES["quiz"].max_weak_topics >= SCENE_INJECTION_RULES["interview"].max_weak_topics


def test_unknown_scene_falls_back_to_minimal_rule() -> None:
    """未知场景（内部步骤）用最小集合，避免污染内部判断。"""
    assert get_injection_rule(None) is DEFAULT_INJECTION_RULE
    assert get_injection_rule("not-a-scene") is DEFAULT_INJECTION_RULE
    formatted = UserProfileService.format_profile_for_injection(_long_profile(), scene=None)
    assert len(formatted["target_skills"].split("、")) == DEFAULT_INJECTION_RULE.max_skills


def test_empty_lists_render_as_placeholder() -> None:
    """空列表渲染成「未指定」，不要留下空占位或 None。"""
    formatted = UserProfileService.format_profile_for_injection({
        "target_job": "Python 后端",
        "years_experience": "",
        "target_level": "",
        "target_skills": [],
        "weak_topics": [],
    })
    assert formatted["target_skills"] == "未指定"
    assert formatted["weak_topics"] == "未指定"


def test_intent_fields_are_never_trimmed() -> None:
    """意图字段是单值，任何场景都完整注入——它们决定「按什么标准讲」。"""
    for scene in (*SCENE_INJECTION_RULES, None):
        formatted = UserProfileService.format_profile_for_injection(
            _long_profile(), scene=scene
        )
        assert formatted["target_job"] == "Python 后端"
        assert formatted["years_experience"] == "4 年"
        assert formatted["target_level"] == "中级"


def test_every_routable_study_side_scene_has_a_rule() -> None:
    """模式注册表里能路由到的场景都要有注入规则，否则会悄悄退化到最小集合。"""
    from app.agent.scene_registry import SCENE_SPECS

    missing = [
        spec.scene for spec in SCENE_SPECS.values() if spec.scene not in SCENE_INJECTION_RULES
    ]
    assert not missing, f"这些场景缺少注入规则: {sorted(set(missing))}"


@pytest.mark.anyio
async def test_profile_dict_prefers_memories_with_mastery_labels(
    async_client, register_and_login
) -> None:
    """注入用的画像优先读明细表，并带上掌握程度档位。

    「薄弱点：MySQL 索引优化(待加强)」比光有一个名字给模型的信息多得多。
    """
    from app.db.database import SessionLocal
    from app.db.models import User
    from app.services.user_memory_service import (
        CATEGORY_SKILL,
        CATEGORY_WEAK_TOPIC,
        SOURCE_SELF_REPORT,
        MemoryEntry,
        UserMemoryService,
    )

    headers = await register_and_login("inj")
    db = SessionLocal()
    try:
        # 找到刚注册的用户（用户名带随机后缀，取最后一个即可）
        user = db.query(User).order_by(User.id.desc()).first()
        assert user is not None
        UserMemoryService.ingest(
            db,
            user_id=user.id,
            entries=[
                MemoryEntry(category=CATEGORY_SKILL, name="FastAPI", mastery=90),
                MemoryEntry(category=CATEGORY_WEAK_TOPIC, name="索引优化", mastery=20),
            ],
            source=SOURCE_SELF_REPORT,
            commit=True,
        )

        profile_dict = UserProfileService.get_profile_dict(db, user.id)
        assert profile_dict["target_skills"] == ["FastAPI(熟练)"]
        assert profile_dict["weak_topics"] == ["索引优化(待加强)"]
    finally:
        db.close()


def test_answer_methods_only_injected_in_answer_scenes() -> None:
    """L2 答题方法只在「怎么答」有意义的场景注入（T9.12）。

    知识精讲是讲知识点的地方，塞「你上次答题漏了量化结果」纯属噪音——
    这是 Hermes 的「按需加载」，也是不占无关场景提示词预算的做法。
    """
    injecting = {s for s, rule in SCENE_INJECTION_RULES.items() if rule.include_methods}
    assert injecting == {"interview", "evaluation"}
    assert not SCENE_INJECTION_RULES["study"].include_methods
    assert not SCENE_INJECTION_RULES["quiz"].include_methods
    assert not DEFAULT_INJECTION_RULE.include_methods
