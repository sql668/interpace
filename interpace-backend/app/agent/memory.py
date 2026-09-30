"""记忆层：历史记忆构建、用户历史检索（L3）、外部知识检索。

三条链路职责不同，别混：

1. `build_chat_history_from_rows`：**会话内**上下文，取最近 N 条原始消息；
2. `build_memory_context`（T9.15）：**跨会话**找回用户自己的历史（「上次那道题」）——
   数据来自 `search_documents` 全文索引，**强制按 user_id 过滤**；
3. `get_latest_knowledge`：**外部**最新信息（DuckDuckGo），与用户记忆无关。

2 与 3 不冲突：一个找「你说过什么」，一个找「外面有什么新东西」。
但两者都不是每轮都跑——2 只在用户话里有回溯指代时跑，3 只在提示词真的引用了
`{search_result}` 时才跑（T1.9 定的，避免每条消息白搭一次外网检索）。
"""

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.tools import DuckDuckGoSearchRun
from sqlalchemy.orm import Session

from app.db.models import ChatMessage
from app.services.memory_search_service import MemorySearchService

# 轻量搜索工具：用于补充「外部记忆/最新信息」。
_search = DuckDuckGoSearchRun(max_results=3)

# 回溯指代词：命中其一才去检索用户历史（T9.15）。
#
# 为什么不每轮都检索：大部分提问与历史无关，白跑一次全文检索只是徒增延迟；
# 而真正需要历史的场景几乎都会带这类词。宁可漏一点，也不要让每条消息都背上检索成本。
RECALL_KEYWORDS = (
    "之前",
    "上次",
    "上回",
    "刚刚",
    "刚才",
    "前面",
    "以前",
    "历史",
    "聊过",
    "说过",
    "提过",
    "问过",
    "那道题",
    "那个题",
    "我们讨论",
    "回顾一下",
)

# 注入提示词的每条历史长度上限。
#
# 注意与接口的区别：`GET /search` **返回完整原文**（检索结果要可信），
# 而注入提示词必须限长，否则一段长对话就能把提示词顶爆。
RECALL_SNIPPET_MAX_CHARS = 500

# 注入提示词的历史条数上限
RECALL_MAX_ITEMS = 3


def build_chat_history_from_rows(rows: list[ChatMessage]) -> ChatMessageHistory:
    """把数据库问答记录转换成模型可读取的历史消息。"""
    history = ChatMessageHistory()
    for row in rows:
        if row.request_text:
            history.add_user_message(row.request_text)
        if row.response_text:
            history.add_ai_message(row.response_text)
    return history


def should_recall(request_text: str) -> bool:
    """用户这句话是否在指代过去的内容。"""
    text = request_text or ""
    return any(keyword in text for keyword in RECALL_KEYWORDS)


def build_memory_context(
    db: Session,
    *,
    user_id: int,
    query: str,
    limit: int = RECALL_MAX_ITEMS,
) -> str:
    """检索该用户的历史内容并拼成可注入提示词的一段文字；没有命中返回空串。

    **必须带 user_id**：这是三层记忆共同的隔离要求，检索类逻辑不允许只靠相似度返回。
    """
    hits = MemorySearchService.search(db, user_id=user_id, query=query, limit=limit)
    if not hits:
        return ""

    blocks: list[str] = []
    for hit in hits:
        document = hit.document
        content = document.content.strip()
        if len(content) > RECALL_SNIPPET_MAX_CHARS:
            content = (
                content[:RECALL_SNIPPET_MAX_CHARS]
                + "……（已截断，完整内容可用「检索历史」查看）"
            )
        blocks.append(f"[{hit.source_label}] {document.title}\n{content}")
    return "\n\n".join(blocks)


def get_latest_knowledge(topic: str) -> str:
    """检索与当前问题相关的最新信息，失败时返回空串。"""
    query = f"{topic} 2026年 大厂面试题 高频考点 技术官网 招聘要求 排除广告"
    try:
        result = _search.run(query)
    except Exception:
        return ""
    if not result or len(result) < 30:
        return ""
    return result
