"""记忆抽取服务（T9.5）：把一次「证据」变成结构化的画像更新。

## 输入是什么

调用方把各种来源**归一化**成一段证据文本再传进来（`MemoryEvidence`）：
刷题评分结果、面试复盘结果、简历解析结果、用户明确的自述。
归一化放在调用方，是为了让这个服务只关心「文本 → 结构化更新」这一件事，
不用认识每张业务表的字段。

## 为什么要用 LangGraph

流程是 `抽取 → 校验 → 落库` 三步，其中「校验」发现超出容量上限时要插入一个
**整合节点**再重试（T9.8）。用状态图表达后，加那条分支只是加一个节点与一条条件边；
写成串行函数的话，重试逻辑会把三个函数缠在一起。

## 写入策略（D20 的落地）

- **行为证据**（刷题得分、面试表现）**直接生效**：这是用户自己考出来的结果，
  可信度最高，而且用户已经用「提交答案 / 生成复盘」表达了意愿；
- **模型推断**先落**待确认**（`pending_approval=1`），在用户点头前不影响对话。

把「谁说的」和「要不要确认」绑定，比一刀切「全部要确认」更合理：
否则「越用越好用」的闭环会被一串审批弹窗卡死。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.agent.llm import get_chat_model
from app.agent.prompt_layer import build_personalized_prompt
from app.core.logging_config import main_logger
from app.core.request_context import set_scene
from app.services.usage_quota_service import SCENE_MEMORY
from app.services.usage_quota_service import UsageQuotaService
from app.services.user_memory_service import (
    CATEGORY_METHOD,
    CATEGORY_LABELS,
    CATEGORY_LIMITS,
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    MemoryCapacityExceeded,
    SOURCE_INFERENCE,
    SOURCE_WEIGHTS,
    UserMemoryService,
)

# 抽取用的内部 agent / 场景（对应 prompt_templates 里 seed 进去的模板）。
EXTRACTOR_AGENT = "memory_extractor"
MEMORY_SCENE = "memory"

# 提示词与解析器共用的结构约定。
MEMORY_JSON_CONTRACT = (
    '{"items": [{"category": "skill|weak_topic|method", "name": "知识点或方法名", '
    '"mastery": 整数0-100, "confidence": 整数0-100}]}'
)

# 整合环节的结构约定（T9.8）：给出最终要保留的完整列表，以及要淘汰的已有条目。
MEMORY_CONSOLIDATE_JSON_CONTRACT = (
    '{"items": [{"category": "skill|weak_topic|method", "name": "条目名", '
    '"mastery": 整数0-100, "confidence": 整数0-100}], '
    '"drop": [{"category": "skill|weak_topic|method", "name": "要淘汰的已有条目名"}]}'
)

# 整合用的内部 agent / 场景
CONSOLIDATOR_AGENT = "memory_consolidator"

# 类别名与内部取值的映射：提示词里用可读的英文单词，避免模型在数字上出错。
CATEGORY_BY_NAME = {
    "skill": CATEGORY_SKILL,
    "weak_topic": CATEGORY_WEAK_TOPIC,
    "method": CATEGORY_METHOD,
}

NAME_MAX_LENGTH = 128

_CODE_FENCE_MARKERS = ("```json", "```JSON", "```")


@dataclass(frozen=True)
class MemoryEvidence:
    """一条待抽取的证据。

    `summary` 由调用方归一化（把评分结果、复盘结果等拼成一段说明），
    `source` 用 `user_memory_service.SOURCE_*`，决定合并权重与是否需要用户确认。
    """

    kind: str  # quiz / interview / resume / self_report，只用于日志与提示词措辞
    summary: str
    source: int


@dataclass(frozen=True)
class MemoryCandidate:
    """抽取出来、并已通过校验的一条画像更新。"""

    category: int
    name: str
    mastery: int
    confidence: int


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    for marker in _CODE_FENCE_MARKERS:
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :]
            break
    if stripped.endswith("```"):
        stripped = stripped[: -len("```")]
    return stripped.strip()


def _clamp(value: Any, default: int) -> int:
    """把模型给的分值收敛到 0-100；不是数字就用默认值。"""
    if isinstance(value, bool) or value is None:
        return default
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, number))


def parse_memory_payload(text: str) -> list[MemoryCandidate]:
    """从模型输出里解析候选条目；解析不出来返回空列表（**不抛异常**）。

    这里只做「格式层面的收口」：未知类别、空名字、重复条目直接丢，
    分值越界收敛到 0-100。业务层面的合并规则（来源权重等）交给落库环节。
    """
    import json

    if not text or not text.strip():
        return []
    candidate_text = _strip_code_fence(text)
    start = candidate_text.find("{")
    end = candidate_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(candidate_text[start : end + 1])
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        return []

    candidates: list[MemoryCandidate] = []
    seen: set[tuple[int, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        category = CATEGORY_BY_NAME.get(str(item.get("category") or "").strip().lower())
        name = str(item.get("name") or "").strip()[:NAME_MAX_LENGTH]
        if category is None or not name:
            continue
        key = (category, name)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            MemoryCandidate(
                category=category,
                name=name,
                mastery=_clamp(item.get("mastery"), default=50),
                confidence=_clamp(item.get("confidence"), default=60),
            )
        )
    return candidates


def parse_consolidation_payload(
    text: str,
) -> tuple[list[MemoryCandidate], list[tuple[int, str]]]:
    """解析整合结果，返回 (要保留的条目, 要淘汰的已有条目)。

    解析失败时返回 `([], [])`，调用方据此判断「整合没成功」——**不能悄悄当成
    「删光了」**，否则一次模型抽风就会把用户的记忆清空。
    """
    items = parse_memory_payload(text)
    drops: list[tuple[int, str]] = []
    if not items:
        return [], []

    import json

    candidate_text = _strip_code_fence(text)
    start = candidate_text.find("{")
    end = candidate_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return items, []
    try:
        data = json.loads(candidate_text[start : end + 1])
    except Exception:
        return items, []

    raw_drops = data.get("drop")
    if isinstance(raw_drops, list):
        for entry in raw_drops:
            if not isinstance(entry, dict):
                continue
            category = CATEGORY_BY_NAME.get(str(entry.get("category") or "").strip().lower())
            name = str(entry.get("name") or "").strip()[:NAME_MAX_LENGTH]
            if category is None or not name:
                continue
            if (category, name) not in drops:
                drops.append((category, name))
    return items, drops


class MemoryGraphState(TypedDict, total=False):
    """抽取图的状态。"""

    evidence: MemoryEvidence
    user_id: int
    candidates: list[MemoryCandidate]
    drops: list[tuple[int, str]]
    consolidated: bool
    needs_consolidation: bool
    persisted: list[str]


def build_memory_graph(
    db: Session, *, user_id: int, provider: str = "deepseek"
) -> CompiledStateGraph:
    """组装记忆编排图：`抽取 → 校验 → 容量检查 →（超限则整合）→ 落库`。

    这条 `capacity → consolidate` 的条件边就是当初用状态图而不是串行函数的理由：
    「超出上限时先整合再重试」用图表达只是加一条边，写成串行函数会把抽取与落库缠在一起。
    """
    system_prompt = build_personalized_prompt(
        db=db, user_id=user_id, agent_name=EXTRACTOR_AGENT, scene=MEMORY_SCENE
    )
    if not system_prompt:
        # 模板没 seed 时兜底，保证链路可用（与其它链路口径一致）
        system_prompt = (
            "你是信息抽取助手。从给定的证据里抽出用户的技术能力与薄弱点，"
            "只输出约定格式的 JSON。"
        )
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "{evidence}")]
    )

    consolidate_prompt = build_personalized_prompt(
        db=db, user_id=user_id, agent_name=CONSOLIDATOR_AGENT, scene=MEMORY_SCENE
    )
    if not consolidate_prompt:
        consolidate_prompt = (
            "你是记忆整合助手。把相近的能力条目合并、淘汰过时或最不重要的条目，"
            "输出最终要保留的完整列表与要淘汰的已有条目，只输出约定格式的 JSON。"
        )

    def extract_node(state: MemoryGraphState) -> dict[str, Any]:
        """调模型抽取候选条目。"""
        evidence = state["evidence"]
        set_scene(SCENE_MEMORY)
        model = get_chat_model(provider=provider)

        # T9.11：把**已有的答题方法条目**一起给模型，并要求「同一个问题直接复用已有说法」。
        #
        # 为什么必须这么做：L2 的价值在于「反复出现的问题沉淀成一条稳定的方法论」。
        # 如果每次复盘都用新说法记一条（「答项目题漏掉量化结果」/「讲项目没给数字」），
        # 条目会越堆越多却永远不收敛，L2 就退化成另一个垃圾桶。
        # 把已有条目放进上下文比事后再做一次「语义去重」调用更省、也更准。
        existing_methods = [
            item.name
            for item in UserMemoryService.list_memories(
                db,
                user_id=state["user_id"],
                category=CATEGORY_METHOD,
                include_pending=True,
            )
        ]
        human = f"证据类型：{evidence.kind}\n\n{evidence.summary}"
        if existing_methods:
            human += (
                "\n\n用户已有的答题方法条目（如果本次观察到的是**同一个问题**，"
                "请直接复用下面的说法，不要换一个新名字）：\n"
                + "\n".join(f"- {name}" for name in existing_methods)
            )

        message = model.invoke(
            prompt.format_messages(evidence=human)
        )
        content = message.content if isinstance(message.content, str) else str(message.content)
        return {"candidates": parse_memory_payload(content)}

    def validate_node(state: MemoryGraphState) -> dict[str, Any]:
        """校验：同一批次内按 (类别, 名字) 再去一次重，并过滤空白条目。

        容量上限与「超限时先整合再重试」放在 T9.8，那时在这里接一条条件边。
        """
        cleaned: list[MemoryCandidate] = []
        seen: set[tuple[int, str]] = set()
        for item in state.get("candidates", []):
            key = (item.category, item.name)
            if not item.name or key in seen:
                continue
            seen.add(key)
            cleaned.append(item)
        return {"candidates": cleaned}

    def persist_node(state: MemoryGraphState) -> dict[str, Any]:
        """落库：按来源权重合并，模型推断类先落待确认（D20）。"""
        evidence = state["evidence"]
        persisted: list[str] = []

        # 整合节点决定的淘汰项先删，给新条目腾出容量
        for category, name in state.get("drops", []):
            UserMemoryService.delete_by_name(
                db, user_id=state["user_id"], category=category, name=name
            )

        for item in state.get("candidates", []):
            UserMemoryService.upsert_memory(
                db,
                user_id=state["user_id"],
                category=item.category,
                name=item.name,
                mastery=item.mastery,
                source=evidence.source,
                confidence=item.confidence,
                # 只有「模型自己猜的」才需要用户点头；行为证据直接生效
                pending_approval=evidence.source == SOURCE_INFERENCE,
            )
            persisted.append(item.name)
        return {"persisted": persisted}

    def capacity_node(state: MemoryGraphState) -> dict[str, Any]:
        """容量检查：有没有「新增」条目会超过该类别上限。

        只有**新增**才算超限——命中已有条目属于合并，不增加条数。
        已整合过一次就不再重复触发（避免模型来回整合、越整越多）。
        """
        if state.get("consolidated"):
            return {"needs_consolidation": False}

        user_id = state["user_id"]
        existing = {
            (row.category, row.name)
            for row in UserMemoryService.list_memories(
                db, user_id=user_id, include_pending=True
            )
        }
        # 同一批次内可能出现多条形如 (类别, 名字) 的新条目，要一起计入增量
        increments: dict[int, int] = {}
        for item in state.get("candidates", []):
            if (item.category, item.name) in existing:
                continue
            increments[item.category] = increments.get(item.category, 0) + 1

        for category, added in increments.items():
            limit = CATEGORY_LIMITS.get(category)
            if limit is None:
                continue
            current = UserMemoryService.count_entries(
                db, user_id=user_id, category=category
            )
            if current + added > limit:
                main_logger.info(
                    f"[记忆抽取] {CATEGORY_LABELS.get(category)} 将超限"
                    f"（{current}+{added}>{limit}），先做一次整合"
                )
                return {"needs_consolidation": True}
        return {"needs_consolidation": False}

    def consolidate_node(state: MemoryGraphState) -> dict[str, Any]:
        """整合节点：把「已有效条目 + 本轮新条目」交给模型，产出去重后的最终集合。

        这是 T9.5 那个状态图预留的条件分支真正被用上的地方——写成串行函数的话，
        「先整合再重试」会把抽取与落库两段缠在一起。
        """
        user_id = state["user_id"]
        existing_rows = UserMemoryService.list_memories(
            db, user_id=user_id, include_pending=True
        )
        existing_lines = [
            f"- [{CATEGORY_LABELS.get(row.category)}] {row.name}"
            f"（掌握度 {row.mastery}，来源 {row.source}，证据 {row.evidence_count} 次）"
            for row in existing_rows
        ]
        candidate_lines = [
            f"- [{CATEGORY_LABELS.get(item.category)}] {item.name}"
            f"（掌握度 {item.mastery}，置信度 {item.confidence}）"
            for item in state.get("candidates", [])
        ]
        limits = "\n".join(
            f"- {CATEGORY_LABELS.get(cat, cat)}：最多 {lim} 条"
            for cat, lim in CATEGORY_LIMITS.items()
        )
        human = (
            "已有条目：\n" + ("\n".join(existing_lines) or "（空）")
            + "\n\n本轮新抽到的条目：\n" + ("\n".join(candidate_lines) or "（空）")
            + f"\n\n各类别上限：\n{limits}\n"
            + "\n请把相近的条目合并、淘汰过时或最不重要的条目，给出**最终要保留的完整列表**，"
            "并列出要淘汰的已有条目名。"
        )

        prompt = ChatPromptTemplate.from_messages(
            [("system", consolidate_prompt), ("human", "{payload}")]
        )
        set_scene(SCENE_MEMORY)
        model = get_chat_model(provider=provider)
        message = model.invoke(prompt.format_messages(payload=human))
        content = message.content if isinstance(message.content, str) else str(message.content)
        items, drops = parse_consolidation_payload(content)
        return {"candidates": items, "drops": drops, "consolidated": True}

    graph = StateGraph(MemoryGraphState)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.add_node("capacity", capacity_node)
    graph.add_node("consolidate", consolidate_node)
    graph.add_node("persist", persist_node)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "capacity")
    # 超限就先整合一次再落库；否则直接落库（这条边就是 T9.5 预留那个分支）
    graph.add_conditional_edges(
        "capacity",
        lambda state: "consolidate" if state.get("needs_consolidation") else "persist",
        {"consolidate": "consolidate", "persist": "persist"},
    )
    graph.add_edge("consolidate", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


class MemoryExtractService:
    """对外入口：给定一条证据，抽取并落库。"""

    @staticmethod
    def extract(
        db: Session,
        *,
        user_id: int,
        evidence: MemoryEvidence,
        provider: str = "deepseek",
        commit: bool = True,
    ) -> list[str]:
        """抽取并写入，返回落库成功的条目名。

        抽取失败（模型没吐约定结构）时返回空列表，**不写脏数据也不抛异常**：
        记忆抽取是「锦上添花」的后置步骤，不该把主流程（评分、复盘）带崩。
        """
        if not evidence.summary or not evidence.summary.strip():
            return []

        # 演示环境的降本开关（T12.5）：记忆抽取是用户看不见的额外模型调用，
        # 对「尝鲜体验」几乎没有贡献，演示环境直接跳过。
        if UsageQuotaService.background_extraction_disabled():
            main_logger.debug("[记忆抽取] 演示环境已关闭后台抽取，跳过")
            return []

        graph = build_memory_graph(db, user_id=user_id, provider=provider)
        state = graph.invoke({"user_id": user_id, "evidence": evidence})
        persisted = list(state.get("persisted") or [])

        if commit:
            db.commit()
        else:
            db.flush()

        if persisted:
            main_logger.info(
                f"[记忆抽取] user_id={user_id} 来源={evidence.source} "
                f"kind={evidence.kind} 写入 {len(persisted)} 条：{persisted}"
            )
        else:
            main_logger.info(
                f"[记忆抽取] user_id={user_id} kind={evidence.kind} 本轮没有可写入的条目"
            )
        return persisted

    @staticmethod
    def build_quiz_evidence(
        *, target_job: str | None, difficulty: str | None, weak_topics: Iterable[str], summary: str = ""
    ) -> MemoryEvidence:
        """把一次刷题评分结果归一化成证据（行为证据，权重最高）。"""
        from app.services.user_memory_service import SOURCE_BEHAVIOR

        topics = "、".join(list(weak_topics)) or "（未给出）"
        parts = [
            "来源：一次刷题评测的结果。",
            f"岗位：{target_job or '未指定'}；难度：{difficulty or '未指定'}。",
            f"模型判定暴露的薄弱知识点：{topics}。",
        ]
        if summary:
            parts.append(f"评分说明：{summary}")
        return MemoryEvidence(kind="quiz", summary="\n".join(parts), source=SOURCE_BEHAVIOR)

    @staticmethod
    def build_interview_evidence(
        *, target_job: str | None, qa_count: int, weak_topics: Iterable[str], summary: str = ""
    ) -> MemoryEvidence:
        """把一次面试复盘归一化成证据（行为证据）。"""
        from app.services.user_memory_service import SOURCE_BEHAVIOR

        topics = "、".join(list(weak_topics)) or "（未给出）"
        parts = [
            "来源：一场模拟面试的复盘结果。",
            f"岗位：{target_job or '未指定'}；问答轮数：{qa_count}。",
            f"复盘判定暴露的薄弱点：{topics}。",
        ]
        if summary:
            parts.append(f"复盘总结：{summary}")
        return MemoryEvidence(
            kind="interview", summary="\n".join(parts), source=SOURCE_BEHAVIOR
        )
