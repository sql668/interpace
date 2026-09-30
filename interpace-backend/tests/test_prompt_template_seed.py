"""T1.3 回归测试：提示词模板预置的幂等性、可检索性，以及模板正文的安全性。

幂等性用一组专属的探针 (agent_name, scene) 验证，避免与开发库里真实预置的数据互相干扰。
"""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.prompt_layer import build_personalized_prompt, inject_user_info_to_template
from app.db.database import SessionLocal
from app.db.models import PromptTemplate
from app.services.prompt_template_seed_service import SEED_TEMPLATES, seed_prompt_templates
from app.services.prompt_template_service import prompt_template_manager
from app.services.user_profile_service import UserProfileService

# 只在测试事务里存在的探针场景，避免污染真实预置数据。
PROBE_AGENT = "t13_probe_agent"
PROBE_SCENE = "t13_probe_scene"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """测试用数据库会话；全部改动只 flush 不提交，结束时回滚。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def probe_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    """把预置清单换成探针场景，隔离真实数据。"""
    monkeypatch.setattr(
        "app.services.prompt_template_seed_service.SEED_TEMPLATES",
        [
            {
                "agent_name": PROBE_AGENT,
                "scene": PROBE_SCENE,
                "template_type": 1,
                "name": "探针模板",
                "description": "仅用于测试",
                "template_content": "你是助手，目标是 {target_job}。",
                "variables": '["target_job"]',
            }
        ],
    )


def _probe_rows(db: Session) -> list[PromptTemplate]:
    return (
        db.query(PromptTemplate)
        .filter(PromptTemplate.agent_name == PROBE_AGENT, PromptTemplate.scene == PROBE_SCENE)
        .order_by(PromptTemplate.version)
        .all()
    )


def test_seed_is_idempotent(db_session: Session, probe_templates: None) -> None:
    """连续执行两次只写入一条，第二次明确跳过，且不改变 is_active。"""
    first = seed_prompt_templates(db_session)
    db_session.flush()
    assert "写入 v1" in first[0]

    second = seed_prompt_templates(db_session)
    db_session.flush()
    assert "跳过" in second[0]

    rows = _probe_rows(db_session)
    assert len(rows) == 1
    assert rows[0].version == 1
    assert rows[0].is_active == 1


def test_force_creates_new_active_version(db_session: Session, probe_templates: None) -> None:
    """--force 会新增一版并置为生效，同时把旧版本下线。"""
    seed_prompt_templates(db_session)
    db_session.flush()
    forced = seed_prompt_templates(db_session, force=True)
    db_session.flush()
    assert "写入 v2" in forced[0]

    rows = _probe_rows(db_session)
    assert [row.version for row in rows] == [1, 2]
    assert [row.is_active for row in rows] == [0, 1]


def test_seeded_template_is_found_by_prompt_builder(
    db_session: Session, probe_templates: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """预置后的模板能被 build_personalized_prompt 查到（强制走数据库路径，绕开缓存）。"""
    seed_prompt_templates(db_session)
    db_session.flush()
    monkeypatch.setattr(prompt_template_manager, "use_redis", False)

    prompt = build_personalized_prompt(
        db=db_session,
        user_id=0,  # 没有画像记录时走默认值，不影响模板查找
        agent_name=PROBE_AGENT,
        scene=PROBE_SCENE,
    )
    assert prompt is not None
    assert "{target_job}" not in prompt


def test_seed_templates_only_have_escaped_braces() -> None:
    """模板经画像注入后，剩下的花括号必须都是成对转义的。

    单个 `{` 会被 `ChatPromptTemplate` 当成模板变量、调用时抛 KeyError；所以模板里
    写 JSON 示例必须写成 `{{` / `}}`，渲染出来才是真正的花括号。
    """
    sample_profile = UserProfileService.format_profile_for_injection(
        {
            "target_job": "Python 后端工程师",
            "years_experience": "3 年",
            "target_level": "中级",
            "target_skills": ["Python", "FastAPI"],
            "weak_topics": ["数据库索引"],
        }
    )
    for spec in SEED_TEMPLATES:
        rendered = inject_user_info_to_template(spec["template_content"], sample_profile)
        # 去掉合法的双写转义，再看有没有落单的花括号
        remaining = rendered.replace("{{", "").replace("}}", "")
        assert "{" not in remaining, f"{spec['name']} 里有未转义的左花括号"
        assert "}" not in remaining, f"{spec['name']} 里有未转义的右花括号"


def test_every_routable_scene_has_a_seeded_template() -> None:
    """**凡是模式注册表能路由到的场景，都必须有对应的私有模板。**

    这是真机问题的回归防线：`get_full_prompt(agent, scene)` 查不到私有模板时会返回
    None，链路随即**静默回落到代码里那句兜底提示词**——默认模式（快速回答）就曾
    因此完全没有任何约束，模型把英文思考过程都吐了出来。
    这类「少了东西」的故障不会报错，只能靠测试盯着。
    """
    from app.agent.scene_registry import SCENE_SPECS

    seeded = {(spec["agent_name"], spec["scene"]) for spec in SEED_TEMPLATES}
    missing = [
        f"{scene.agent_name}/{scene.scene}"
        for scene in SCENE_SPECS.values()
        if (scene.agent_name, scene.scene) not in seeded
    ]
    assert not missing, f"这些模式的模板缺失，会静默回落到兜底提示词: {missing}"
