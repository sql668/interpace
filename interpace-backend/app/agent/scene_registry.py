"""模式注册表：把 `chat_messages.select_model` 映射到执行该模式的 agent 与场景。

这是「选模式 → 不同 Agent 回答」的唯一事实来源，路由层和服务层都从这里取配置，
不要再各自硬编码 agent_name / scene。

设计约定（对应 docs/TODO.md 阶段 1）：

1. `agent_name` 必须是 `prompt_template_service.AGENT_CONFIG` 里已有的键，
   否则 `get_full_prompt` 永远查不到模板，只能走兜底提示词。
2. 两张流程图里的「知识精讲」描述一致，**两个房间共用 `select_model=1`**，
   靠会话的 `session_model` 区分落库归属，不为面试间另开编号。
3. 默认模式（`select_model=0`）在两个房间共用同一套模板。若将来「学习室答疑」
   与「面试间给参考回答」确实需要区分，加一个 scene 值即可，不动表结构。
4. `flow_controller`（workflow）、`note_archiver`（note）、`quiz_evaluator`（quiz 评分）
   与 `resume_extractor`（简历画像抽取）是**内部 agent，不是用户可选模式**，不登记在这里。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SceneSpec:
    """一个用户可选模式对应的执行配置。"""

    select_model: int
    agent_name: str
    scene: str
    label: str


# 默认模式：未知或缺失的 select_model 一律回退到这里。
DEFAULT_SCENE_SPEC = SceneSpec(
    select_model=0,
    agent_name="general_assistant",
    scene="chat",
    label="快速回答（默认）",
)

# select_model -> 模式配置，键与 chat_messages.select_model 的既有注释一一对应。
SCENE_SPECS: dict[int, SceneSpec] = {
    0: DEFAULT_SCENE_SPEC,
    1: SceneSpec(1, "difficulty_learner", "study", "知识精讲"),
    2: SceneSpec(2, "quiz_generate_workflow", "quiz", "刷题评测"),
    3: SceneSpec(3, "resume_parser", "resume", "简历优化"),
    4: SceneSpec(4, "interview_host", "interview", "模拟面试"),
    5: SceneSpec(5, "interview_evaluator", "evaluation", "面试复盘"),
}


def resolve_scene(select_model: int | None) -> SceneSpec:
    """按 select_model 解析出执行配置；未知或缺失的取值回退到默认模式。

    返回 `SceneSpec`（含 select_model / agent_name / scene / label），
    比裸元组更容易在调用处读懂，后续要加字段也不用改调用签名。
    """
    if select_model is None:
        return DEFAULT_SCENE_SPEC
    return SCENE_SPECS.get(select_model, DEFAULT_SCENE_SPEC)
