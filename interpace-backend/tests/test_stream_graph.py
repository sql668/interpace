"""T1.0 回归测试：LangGraph 单节点编排图与改造前的单链行为等价。

用假模型跑，验证三件事：
1. 历史消息按时间升序、且不含本轮占位消息地注入；
2. graph.stream(stream_mode="messages") 产出的 delta 拼接后与模型输出逐字一致（不丢字、不重复）；
3. 输入里保留了 local_kb / search_result 两个扩展变量。
4. search_result 只在提示词真的引用 {search_result} 时才触发外部检索（T1.9）。
"""

import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from sqlalchemy.orm import Session

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent import prompt_layer
from app.db.database import SessionLocal
from app.db.models import ChatMessage, Session as SessionModel, User

# 改造前用同一个假模型抓到的基线：delta 序列拼起来正好是这句。
EXPECTED_TEXT = "你好，这是流式输出"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """用事务包裹测试数据，结束时回滚，不在库里留残留。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _seed_conversation(db: Session, now: int) -> tuple[User, SessionModel, ChatMessage]:
    """造一条会话：两轮历史 + 一条本轮占位消息，全部只 flush 不提交。"""
    user = User(
        username=f"t1_{uuid.uuid4().hex[:8]}",
        password="x" * 12,
        avatar=None,
        create_time=now,
    )
    db.add(user)
    db.flush()

    conversation = SessionModel(
        user_id=user.id, session_model=0, title="t1_0_test", created_at=now
    )
    db.add(conversation)
    db.flush()

    def add_message(request_text: str, response_text: str) -> ChatMessage:
        row = ChatMessage(
            user_id=user.id,
            session_id=conversation.id,
            select_model=0,
            request_id=uuid.uuid4().hex,
            request_text=request_text,
            response_text=response_text,
            request_segments=[],
            response_segments=[],
            status=0,
            interview_id=None,
            file_extracted_text="",
            created_at=now,
        )
        db.add(row)
        db.flush()
        return row

    add_message("我之前问过 Redis", "Redis 是内存数据库")
    return user, conversation, add_message("现在的问题", "")


def test_stream_graph_matches_legacy_chain(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """单节点图的流式输出应与改造前的链式调用逐字一致。"""
    now = int(time.time())
    user, conversation, current = _seed_conversation(db_session, now)

    # 换掉真实模型与外部检索，保证测试确定性、也不产生网络调用。
    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content=EXPECTED_TEXT)])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", lambda topic: "")

    graph, inputs = prompt_layer.build_stream_graph(
        db=db_session,
        user_id=user.id,
        session_id=conversation.id,
        current_message_id=current.id,
        provider="deepseek",
        request_text="现在的问题",
        system_prompt="你是助手",
    )

    # 历史按时间升序注入，且不包含本轮那条占位消息。
    assert [message.type for message in inputs["history"]] == ["human", "ai"]
    assert inputs["history"][0].content == "我之前问过 Redis"
    # 扩展变量继续透传；本轮用户消息改为 user_messages（带图片时它是多模态内容块）
    assert sorted(inputs.keys()) == ["history", "local_kb", "search_result", "user_messages"]

    deltas = [
        chunk.content
        for chunk, _meta in graph.stream(inputs, stream_mode="messages")
        if isinstance(chunk, AIMessageChunk)
    ]
    assert "".join(deltas) == EXPECTED_TEXT


def test_search_only_runs_when_prompt_references_it(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """外部检索只在提示词真的引用 {search_result} 时才触发，避免每条消息白跑一次。"""
    now = int(time.time())
    user, conversation, current = _seed_conversation(db_session, now)

    searched_topics: list[str] = []

    def fake_search(topic: str) -> str:
        searched_topics.append(topic)
        return "检索结果"

    monkeypatch.setattr(
        prompt_layer,
        "get_chat_model",
        lambda provider="deepseek": GenericFakeChatModel(
            messages=iter([AIMessage(content="好的")])
        ),
    )
    monkeypatch.setattr(prompt_layer, "get_latest_knowledge", fake_search)

    def build_inputs(system_prompt: str) -> dict:
        _graph, inputs = prompt_layer.build_stream_graph(
            db=db_session,
            user_id=user.id,
            session_id=conversation.id,
            current_message_id=current.id,
            provider="deepseek",
            request_text="现在的问题",
            system_prompt=system_prompt,
        )
        return inputs

    # 内置模板不引用 search_result，不该触发任何外部检索。
    inputs = build_inputs("你是助手")
    assert searched_topics == []
    assert inputs["search_result"] == ""

    # 自定义模板真的引用了，才取一次。
    inputs = build_inputs("你是助手，参考资料：{search_result}")
    assert searched_topics == ["现在的问题"]
    assert inputs["search_result"] == "检索结果"

    # local_kb 是常量，无论用不用都给出来，代价为零。
    assert "Python" in inputs["local_kb"]
