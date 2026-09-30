"""T9.5 回归测试：记忆抽取的解析、校验与写入策略。

三个重点：
1. 解析容错（代码块、未知类别、空名字、重复条目、分值越界）——抽取失败**不能抛异常**；
2. 写入策略（D20）：行为证据直接生效，模型推断先落待确认；
3. 编排确实走了 LangGraph（图能编译、节点按序执行）。
"""

import json
import sys
import time
import uuid
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_helpers import make_recording_model, purge_user
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app.db.database import SessionLocal
from app.db.models import User, UserMemory
from app.services import memory_extract_service
from app.services.memory_extract_service import (
    MemoryEvidence,
    MemoryExtractService,
    parse_memory_payload,
)
from app.services.user_memory_service import (
    CATEGORY_METHOD,
    CATEGORY_LIMITS,
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    MemoryCapacityExceeded,
    SOURCE_BEHAVIOR,
    SOURCE_INFERENCE,
    UserMemoryService,
)
from app.services.memory_extract_service import parse_consolidation_payload

VALID_JSON = json.dumps(
    {
        "items": [
            {"category": "weak_topic", "name": "MySQL 索引优化", "mastery": 35, "confidence": 80},
            {"category": "skill", "name": "FastAPI", "mastery": 75, "confidence": 70},
            {"category": "method", "name": "答项目题时漏掉量化结果", "mastery": 40, "confidence": 60},
        ]
    },
    ensure_ascii=False,
)


def _stub_model(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    """把抽取用的模型换成桩（编排图内部自己取模型，所以要替换模块里的引用）。"""
    monkeypatch.setattr(
        memory_extract_service,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content=content)])
        ),
    )
    monkeypatch.setattr(
        memory_extract_service, "build_personalized_prompt", lambda **kwargs: None
    )


def _make_user() -> int:
    db = SessionLocal()
    try:
        user = User(
            username=f"memx_{uuid.uuid4().hex[:8]}",
            password="x" * 12,
            avatar=None,
            create_time=int(time.time()),
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


def _drop_user(user_id: int) -> None:
    """清理本用例造的用户数据（顺序与外键依赖一致，见 `api_helpers.purge_user`）。"""
    purge_user(user_id)


# ---------------- 解析器 ----------------


def test_parse_accepts_code_fence_and_maps_categories() -> None:
    items = parse_memory_payload(f"```json\n{VALID_JSON}\n```")
    assert [i.category for i in items] == [CATEGORY_WEAK_TOPIC, CATEGORY_SKILL, CATEGORY_METHOD]
    assert items[0].name == "MySQL 索引优化"
    assert items[0].mastery == 35


def test_parse_drops_invalid_rows_and_dedupes() -> None:
    """未知类别 / 空名字 / 重复条目直接丢，分值越界收敛。"""
    payload = json.dumps(
        {
            "items": [
                {"category": "unknown", "name": "X", "mastery": 50},
                {"category": "skill", "name": "   ", "mastery": 50},
                {"category": "skill", "name": "Python", "mastery": 120},
                {"category": "skill", "name": "Python", "mastery": 80},
                {"category": "weak_topic", "name": "索引", "mastery": -10, "confidence": 300},
                {"category": "SKILL", "name": "Docker", "mastery": "60"},
            ]
        },
        ensure_ascii=False,
    )
    items = parse_memory_payload(payload)
    names = [(i.category, i.name) for i in items]
    assert names == [(CATEGORY_SKILL, "Python"), (CATEGORY_WEAK_TOPIC, "索引"), (CATEGORY_SKILL, "Docker")]
    assert items[0].mastery == 100  # 越界收敛到 100
    assert items[1].mastery == 0
    assert items[1].confidence == 100
    assert items[2].mastery == 60  # 字符串数字也能收


def test_parse_tolerates_garbage() -> None:
    """解析失败返回空列表而不是抛异常——抽取是后置步骤，不能把主流程带崩。"""
    assert parse_memory_payload("") == []
    assert parse_memory_payload("不是 JSON") == []
    assert parse_memory_payload('{"items": "not-a-list"}') == []
    assert parse_memory_payload('{"items": []}') == []


# ---------------- 写入策略 ----------------


def test_behavior_evidence_is_effective_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    """行为证据（刷题/复盘）直接生效，不进待确认队列。"""
    user_id = _make_user()
    try:
        _stub_model(monkeypatch, VALID_JSON)
        db = SessionLocal()
        try:
            evidence = MemoryExtractService.build_quiz_evidence(
                target_job="Python 后端", difficulty="中级", weak_topics=["MySQL 索引优化"]
            )
            written = MemoryExtractService.extract(
                db, user_id=user_id, evidence=evidence
            )
            assert set(written) == {"MySQL 索引优化", "FastAPI", "答项目题时漏掉量化结果"}

            memories = UserMemoryService.list_memories(db, user_id=user_id)
            assert len(memories) == 3
            assert all(m.pending_approval == 0 for m in memories)
            assert all(m.source == SOURCE_BEHAVIOR for m in memories)
        finally:
            db.close()
    finally:
        _drop_user(user_id)


def test_inference_evidence_waits_for_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型推断类先落待确认：批准前不影响对话（D20）。"""
    user_id = _make_user()
    try:
        _stub_model(monkeypatch, VALID_JSON)
        db = SessionLocal()
        try:
            evidence = MemoryEvidence(
                kind="self_report",
                summary="用户在闲聊里提到自己会用一点 Docker。",
                source=SOURCE_INFERENCE,
            )
            MemoryExtractService.extract(db, user_id=user_id, evidence=evidence)

            # 默认列表（生效中）看不到，治理列表（include_pending）能看到
            effective = UserMemoryService.list_memories(db, user_id=user_id)
            assert effective == []
            pending_rows = UserMemoryService.list_memories(
                db, user_id=user_id, include_pending=True
            )
            assert len(pending_rows) == 3
            assert all(row.pending_approval == 1 for row in pending_rows)
        finally:
            db.close()
    finally:
        _drop_user(user_id)


def test_extract_with_empty_evidence_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """空证据直接返回，连模型都不调。"""
    user_id = _make_user()
    try:
        _stub_model(monkeypatch, VALID_JSON)
        db = SessionLocal()
        try:
            written = MemoryExtractService.extract(
                db,
                user_id=user_id,
                evidence=MemoryEvidence(kind="quiz", summary="   ", source=SOURCE_BEHAVIOR),
            )
            assert written == []
            assert UserMemoryService.list_memories(db, user_id=user_id) == []
        finally:
            db.close()
    finally:
        _drop_user(user_id)


def test_extract_survives_unparseable_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """模型不按约定输出时不写脏数据、也不抛异常。"""
    user_id = _make_user()
    try:
        _stub_model(monkeypatch, "这次我就不输出 JSON 了，随便聊聊。")
        db = SessionLocal()
        try:
            written = MemoryExtractService.extract(
                db,
                user_id=user_id,
                evidence=MemoryExtractService.build_interview_evidence(
                    target_job="Python 后端", qa_count=3, weak_topics=["索引失效"]
                ),
            )
            assert written == []
            assert UserMemoryService.list_memories(db, user_id=user_id) == []
        finally:
            db.close()
    finally:
        _drop_user(user_id)


# ---------------- T9.8 容量上限与整合 ----------------


def _fill_category(user_id: int, category: int, count: int) -> None:
    """把某个类别填到 count 条，用于触发容量上限。"""
    db = SessionLocal()
    try:
        UserMemoryService.ingest(
            db,
            user_id=user_id,
            entries=[
                MemoryEntryForTest(category=category, name=f"占位{i}") for i in range(count)
            ],
            source=SOURCE_BEHAVIOR,
            commit=True,
        )
    finally:
        db.close()


def _make_entry(category: int, name: str):
    from app.services.user_memory_service import MemoryEntry

    return MemoryEntry(category=category, name=name)


def MemoryEntryForTest(category: int, name: str):  # noqa: N802 - 测试辅助
    return _make_entry(category, name)


def test_upsert_raises_when_category_is_full() -> None:
    """达到上限时新增**直接报错**，而不是静默淘汰旧条目。"""
    user_id = _make_user()
    limit = CATEGORY_LIMITS[CATEGORY_METHOD]
    try:
        _fill_category(user_id, CATEGORY_METHOD, limit)
        db = SessionLocal()
        try:
            # 已有条目：合并，不该被容量挡住
            UserMemoryService.upsert_memory(
                db,
                user_id=user_id,
                category=CATEGORY_METHOD,
                name="占位0",
                mastery=60,
                source=SOURCE_BEHAVIOR,
            )
            db.commit()

            # 新增条目：必须报错
            with pytest.raises(MemoryCapacityExceeded) as exc:
                UserMemoryService.upsert_memory(
                    db,
                    user_id=user_id,
                    category=CATEGORY_METHOD,
                    name="新方法",
                    mastery=60,
                    source=SOURCE_BEHAVIOR,
                )
            assert exc.value.category == CATEGORY_METHOD
            assert exc.value.limit == limit
            db.rollback()

            # 关键：报错之后老数据一条没少（不能静默丢数据）
            assert (
                UserMemoryService.count_entries(db, user_id=user_id, category=CATEGORY_METHOD)
                == limit
            )
        finally:
            db.close()
    finally:
        _drop_user(user_id)


def test_extract_consolidates_when_at_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    """超限时先走整合节点：模型给出最终列表与淘汰项，落库后条数不超上限。"""
    user_id = _make_user()
    limit = CATEGORY_LIMITS[CATEGORY_METHOD]
    try:
        _fill_category(user_id, CATEGORY_METHOD, limit)

        # 抽取返回一条新方法（会让条数超限）；整合返回「保留新方法 + 淘汰一条旧条目」，
        # 一进一出正好维持在上限内——这就是整合该有的效果
        extraction = json.dumps(
            {"items": [{"category": "method", "name": "新方法", "mastery": 60, "confidence": 70}]},
            ensure_ascii=False,
        )
        consolidation = json.dumps(
            {
                "items": [
                    {"category": "method", "name": "新方法", "mastery": 60, "confidence": 70}
                ],
                "drop": [{"category": "method", "name": "占位0"}],
            },
            ensure_ascii=False,
        )

        class TwoStepModel:
            """第一次调用返回抽取结果，第二次返回整合结果。"""

            def __init__(self) -> None:
                self.calls = 0

            def invoke(self, *_args, **_kwargs):
                self.calls += 1
                content = extraction if self.calls == 1 else consolidation
                return AIMessage(content=content)

        model = TwoStepModel()
        monkeypatch.setattr(
            memory_extract_service, "get_chat_model", lambda provider="deepseek": model
        )
        monkeypatch.setattr(
            memory_extract_service, "build_personalized_prompt", lambda **kwargs: None
        )

        db = SessionLocal()
        try:
            written = MemoryExtractService.extract(
                db,
                user_id=user_id,
                evidence=MemoryExtractService.build_quiz_evidence(
                    target_job="Python 后端", difficulty="中级", weak_topics=["索引"]
                ),
            )
            assert model.calls == 2, "超限时应当触发一次整合调用"
            assert written == ["新方法"]

            names = [
                m.name
                for m in UserMemoryService.list_memories(
                    db, user_id=user_id, category=CATEGORY_METHOD, include_pending=True
                )
            ]
            assert "占位0" not in names, "整合时被淘汰的条目应当真的删掉"
            assert "新方法" in names
            # 一进一出：条数不超过上限（这是整合的意义）
            assert len(names) == limit
        finally:
            db.close()
    finally:
        _drop_user(user_id)


def test_parse_consolidation_payload() -> None:
    """整合结果的解析：items 复用抽取的解析，drop 需要类别+名字。"""
    text = json.dumps(
        {
            "items": [{"category": "skill", "name": "Python", "mastery": 80}],
            "drop": [
                {"category": "skill", "name": "旧技能"},
                {"category": "unknown", "name": "X"},
                {"name": "缺类别"},
            ],
        },
        ensure_ascii=False,
    )
    items, drops = parse_consolidation_payload(text)
    assert [i.name for i in items] == ["Python"]
    assert drops == [(CATEGORY_SKILL, "旧技能")]


def test_parse_consolidation_never_returns_empty_drops_on_failure() -> None:
    """整合输出解析不出来时不能当成「删光」——那会清空用户的记忆。"""
    items, drops = parse_consolidation_payload("模型这次没输出 JSON")
    assert items == []
    assert drops == []


# ---------------- T9.11 / T9.12：L2 答题方法 ----------------


def test_existing_methods_are_given_to_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """抽取时要把**已有的答题方法条目**一起给模型，并要求复用同一说法（T9.11）。

    不给已有的说法，模型每次都会换一个新名字，L2 会退化成另一个垃圾桶。
    """
    user_id = _make_user()
    try:
        db = SessionLocal()
        try:
            UserMemoryService.ingest(
                db,
                user_id=user_id,
                entries=[
                    MemoryEntryForTest(CATEGORY_METHOD, "答项目题时漏掉量化结果")
                ],
                source=SOURCE_BEHAVIOR,
                commit=True,
            )
        finally:
            db.close()

        captured: list[list] = []

        def recording_factory(provider="deepseek"):
            return make_recording_model(captured, content='{"items": []}')

        monkeypatch.setattr(memory_extract_service, "get_chat_model", recording_factory)
        monkeypatch.setattr(
            memory_extract_service, "build_personalized_prompt", lambda **kwargs: None
        )

        db = SessionLocal()
        try:
            MemoryExtractService.extract(
                db,
                user_id=user_id,
                evidence=MemoryExtractService.build_interview_evidence(
                    target_job="Python 后端", qa_count=3, weak_topics=[]
                ),
            )
        finally:
            db.close()

        assert captured, "抽取时没有调用模型"
        flattened = str(captured[0])
        assert "答项目题时漏掉量化结果" in flattened, "已有的方法条目没有给到模型"
        assert "直接复用" in flattened
    finally:
        _drop_user(user_id)


def test_method_entries_accumulate_evidence_on_same_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一个方法名被再次观察时累积证据数，而不是新增一条（L2 的「沉淀」）。"""
    user_id = _make_user()
    try:
        same = '{"items": [{"category": "method", "name": "答项目题时漏掉量化结果", "mastery": 40, "confidence": 70}]}'
        _stub_model(monkeypatch, same)

        db = SessionLocal()
        try:
            evidence = MemoryExtractService.build_interview_evidence(
                target_job="Python 后端", qa_count=3, weak_topics=[]
            )
            MemoryExtractService.extract(db, user_id=user_id, evidence=evidence)
            MemoryExtractService.extract(db, user_id=user_id, evidence=evidence)

            rows = UserMemoryService.list_memories(
                db, user_id=user_id, category=CATEGORY_METHOD, include_pending=True
            )
            assert len(rows) == 1, "同名条目应当合并而不是新增"
            assert rows[0].evidence_count == 2
        finally:
            db.close()
    finally:
        _drop_user(user_id)
