"""T1.1 回归测试：模式注册表的取值映射、非法值回退，以及几条不变量。

这份用例同时也是一份「契约」：改注册表却忘记同步 AGENT_CONFIG、
或让两个模式撞到同一个 (agent_name, scene) 时，这里会先失败。
"""

import sys
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.scene_registry import DEFAULT_SCENE_SPEC, SCENE_SPECS, resolve_scene
from app.services.prompt_template_service import AGENT_CONFIG

# 与 docs/TODO.md 阶段 1 的映射表保持一致：select_model -> (agent_name, scene)
EXPECTED_MAPPING: dict[int, tuple[str, str]] = {
    0: ("general_assistant", "chat"),
    1: ("difficulty_learner", "study"),
    2: ("quiz_generate_workflow", "quiz"),
    3: ("resume_parser", "resume"),
    4: ("interview_host", "interview"),
    5: ("interview_evaluator", "evaluation"),
}


@pytest.mark.parametrize("select_model, expected", sorted(EXPECTED_MAPPING.items()))
def test_resolve_scene_maps_each_select_model(
    select_model: int, expected: tuple[str, str]
) -> None:
    """每个合法取值都应解析出约定的 agent 与场景。"""
    spec = resolve_scene(select_model)
    assert spec.select_model == select_model
    assert (spec.agent_name, spec.scene) == expected
    assert spec.label


@pytest.mark.parametrize("bad_value", [-1, 6, 99, None])
def test_resolve_scene_falls_back_to_default(bad_value: int | None) -> None:
    """非法取值与缺失取值都应回退到默认模式，而不是抛异常。"""
    assert resolve_scene(bad_value) is DEFAULT_SCENE_SPEC


def test_registry_covers_exactly_the_declared_select_models() -> None:
    """注册表的键集合应与约定一致，不多不少。"""
    assert set(SCENE_SPECS) == set(EXPECTED_MAPPING)


def test_every_registered_agent_exists_in_agent_config() -> None:
    """注册表里的 agent_name 必须都是 AGENT_CONFIG 的键，否则提示词永远查不到。"""
    for spec in SCENE_SPECS.values():
        assert spec.agent_name in AGENT_CONFIG, f"{spec.agent_name} 不在 AGENT_CONFIG 中"


def test_internal_agents_are_not_registered() -> None:
    """flow_controller / note_archiver 是内部 agent，不应出现在用户可选模式里。"""
    registered_agents = {spec.agent_name for spec in SCENE_SPECS.values()}
    assert "flow_controller" not in registered_agents
    assert "note_archiver" not in registered_agents


def test_each_mode_has_a_unique_template_key() -> None:
    """每个模式的 (agent_name, scene) 组合必须唯一，否则模板会互相覆盖。"""
    pairs = [(spec.agent_name, spec.scene) for spec in SCENE_SPECS.values()]
    assert len(pairs) == len(set(pairs))
