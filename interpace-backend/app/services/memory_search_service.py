"""长期记忆 L3：会话与资料的全文检索（T9.14）。

## 选型（D17 已定）

用 **MySQL FULLTEXT + ngram 分词器**，不引入向量库。依据是 Hermes 本身用的就是
SQLite FTS5 全文检索（约 20ms、零模型成本），说明「按关键词找回历史对话」这个需求
不需要语义检索；而向量库要多一个运行组件 + embedding 调用成本，对 2核2G 的部署目标是实打实的负担。

**为什么必须是 ngram**：InnoDB 默认的全文分词按空格与标点切词，对中文等于不工作——
整句会被当成一个词，搜「索引」永远搜不到。`WITH PARSER ngram` 按 2 字窗口切分才对。
这条不做的话，索引能建、查询能跑，就是搜不到东西（静默失效）。

## 隔离与返回

- **检索强制按 `user_id` 过滤**：不允许只靠相似度返回结果（本阶段的隔离要求）。
- **返回原文**：`content` 存完整文本，不做 LLM 摘要、不截断——Hermes 的明确做法，
  摘要会让检索结果不再可信。

## 一个要知道的特性（不是 bug）

InnoDB 的全文索引对**刚写入的行**有短暂的可见性延迟（FTS 索引缓存按批刷盘）。
表现是「刚发完一条消息，立刻搜它的关键词可能搜不到」。对真实使用没影响
（用户不会刚说完就搜自己刚说的话），但**测试里要容忍这一点**：
`tests/test_memory_search.py` 用短重试来规避，而不是把断言放宽到看不出问题。
"""

from dataclasses import dataclass

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import SearchDocument

# source_type 取值与备注
SOURCE_MESSAGE = 0
SOURCE_NOTE = 1
SOURCE_EVALUATION = 2

SOURCE_LABELS = {
    SOURCE_MESSAGE: "历史对话",
    SOURCE_NOTE: "笔记",
    SOURCE_EVALUATION: "面试复盘",
}

# ngram 分词器默认按 2 字切分（ngram_token_size=2），所以单字查询走不到全文索引，
# 这时退回 LIKE——仍然按用户过滤，只是没有相关度排序。
MIN_FULLTEXT_QUERY_LENGTH = 2


@dataclass(frozen=True)
class SearchHit:
    """一条检索结果。`score` 只在全文检索路径上有值。"""

    document: SearchDocument
    score: float | None = None

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.document.source_type, "未知来源")


def _escape_like(value: str) -> str:
    """转义 LIKE 的通配符，避免用户输入的 % 变成「匹配所有」。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MemorySearchService:
    """索引的写入、删除与检索。"""

    @staticmethod
    def index_document(
        db: Session,
        *,
        user_id: int,
        source_type: int,
        source_id: int,
        title: str,
        content: str,
        session_id: int | None = None,
        created_at: int | None = None,
        commit: bool = False,
    ) -> SearchDocument | None:
        """把一条来源记录写进索引（按 (user_id, 来源类型, 来源 ID) 幂等覆盖）。

        `content` 为空时不建索引：空文档进了索引只会占空间、永远搜不到。
        """
        text_content = (content or "").strip()
        if not text_content:
            return None

        existing = db.scalar(
            select(SearchDocument).where(
                SearchDocument.user_id == user_id,
                SearchDocument.source_type == source_type,
                SearchDocument.source_id == source_id,
            )
        )
        if existing is None:
            existing = SearchDocument(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                session_id=session_id,
                title=(title or "").strip()[:255],
                content=text_content,
            )
            db.add(existing)
        else:
            existing.title = (title or "").strip()[:255]
            existing.content = text_content
            existing.session_id = session_id
            db.add(existing)

        if created_at is not None:
            existing.created_at = created_at
        db.flush()
        if commit:
            db.commit()
            db.refresh(existing)
        return existing

    @staticmethod
    def delete_document(
        db: Session,
        *,
        user_id: int,
        source_type: int,
        source_id: int,
        commit: bool = False,
    ) -> None:
        """删除某条来源的索引（来源记录被删时调用）。

        索引表对来源**不设外键**（源记录类型不唯一、加外键会挡删除），
        所以清理必须显式做——否则删掉的对话仍能被搜出来，这是最让人困惑的一类脏数据。
        """
        document = db.scalar(
            select(SearchDocument).where(
                SearchDocument.user_id == user_id,
                SearchDocument.source_type == source_type,
                SearchDocument.source_id == source_id,
            )
        )
        if document is not None:
            db.delete(document)
            if commit:
                db.commit()
            else:
                db.flush()

    @staticmethod
    def delete_by_session(
        db: Session, *, user_id: int, session_id: int, commit: bool = False
    ) -> int:
        """删会话时清掉该会话下所有消息的索引。"""
        documents = list(
            db.scalars(
                select(SearchDocument).where(
                    SearchDocument.user_id == user_id,
                    SearchDocument.session_id == session_id,
                )
            )
        )
        for document in documents:
            db.delete(document)
        if commit:
            db.commit()
        else:
            db.flush()
        return len(documents)

    @staticmethod
    def search(
        db: Session,
        *,
        user_id: int,
        query: str,
        limit: int = 10,
        source_types: list[int] | None = None,
    ) -> list[SearchHit]:
        """按关键词检索该用户的历史内容，相关度高的在前。

        **`user_id` 是强制条件**，不是可选项——这是三层记忆共同的隔离要求：
        检索类接口不允许只靠相似度返回结果。
        """
        keyword = (query or "").strip()
        if not keyword:
            return []

        conditions = [SearchDocument.user_id == user_id]
        if source_types:
            conditions.append(SearchDocument.source_type.in_(source_types))

        if len(keyword) >= MIN_FULLTEXT_QUERY_LENGTH:
            # 全文检索：相关度排序；标题命中比正文命中更值钱，用 score 自然体现
            #
            # 多列 MATCH 没有可移植的 SQLAlchemy 表达式（`column.match()` 只支持单列，
            # 而我们的 FULLTEXT 索引建在 (title, content) 上，列必须完全对应），
            # 所以这里写原生 SQL 片段，参数用**语句级** `.params()` 绑定。
            match_sql = (
                "MATCH(search_documents.title, search_documents.content) "
                "AGAINST (:keyword IN NATURAL LANGUAGE MODE)"
            )
            rows = db.execute(
                select(SearchDocument, text(f"{match_sql} AS score"))
                .where(*conditions, text(match_sql))
                # 相关度高的在前；同分再看时间。`score` 是上面那个列的别名。
                .order_by(text("score DESC"), SearchDocument.created_at.desc())
                .limit(limit)
                .params(keyword=keyword)
            ).all()
            return [SearchHit(document=row[0], score=float(row[1] or 0)) for row in rows]

        # 单字查询：ngram 按 2 字切词，单字走不到索引，退回 LIKE（仍然按用户过滤）
        pattern = f"%{_escape_like(keyword)}%"
        rows = db.scalars(
            select(SearchDocument)
            .where(
                *conditions,
                or_(
                    SearchDocument.title.like(pattern, escape="\\"),
                    SearchDocument.content.like(pattern, escape="\\"),
                ),
            )
            .order_by(SearchDocument.created_at.desc())
            .limit(limit)
        )
        return [SearchHit(document=document) for document in rows]

    @staticmethod
    def count_documents(db: Session, *, user_id: int) -> int:
        """当前用户的索引条数（用于自检与脚本输出）。"""
        return int(
            db.scalar(
                select(func.count(SearchDocument.id)).where(
                    SearchDocument.user_id == user_id
                )
            )
            or 0
        )
