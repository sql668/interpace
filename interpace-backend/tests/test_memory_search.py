"""T9.14 回归测试：L3 全文检索的写入、检索与隔离。

重点：
1. 中文检索真的能搜到（ngram 分词器生效，不是「建了索引但搜不到」）；
2. **检索强制按用户过滤**，别人的内容一条都不返回；
3. 来源删除后索引同步清掉（索引对来源不设外键，不显式清理就是脏数据）。
"""

import sys
import time
from pathlib import Path

import pytest

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import SearchDocument
from app.services.memory_search_service import (
    SOURCE_EVALUATION,
    SOURCE_MESSAGE,
    SOURCE_NOTE,
    MemorySearchService,
)


def _seed(db, user_id: int) -> None:
    MemorySearchService.index_document(
        db,
        user_id=user_id,
        source_type=SOURCE_MESSAGE,
        source_id=1,
        session_id=7,
        title="MySQL 索引优化怎么学",
        content="候选人问过 MySQL 索引失效的场景，我建议先看最左前缀与执行计划。",
        commit=False,
    )
    MemorySearchService.index_document(
        db,
        user_id=user_id,
        source_type=SOURCE_NOTE,
        source_id=2,
        title="笔记：缓存三兄弟",
        content="缓存穿透用布隆过滤器，击穿用互斥锁，雪崩靠过期时间加随机。",
        commit=False,
    )
    MemorySearchService.index_document(
        db,
        user_id=user_id,
        source_type=SOURCE_EVALUATION,
        source_id=3,
        title="面试复盘",
        content="整体偏弱，薄弱点集中在索引与并发模型。",
        commit=False,
    )
    db.commit()


def _purge(db, user_id: int) -> None:
    db.query(SearchDocument).filter(SearchDocument.user_id == user_id).delete()
    db.commit()


def _search_with_retry(db, **kwargs):
    """带短重试的检索：InnoDB 全文索引对刚写入的行有可见性延迟（FTS 缓存按批刷盘）。

    这是 InnoDB 的已知特性，不是我们的 bug。重试只为了测试稳定，
    断言本身没有放宽——搜不到就是搜不到。
    """
    hits = MemorySearchService.search(db, **kwargs)
    for _ in range(10):
        if hits:
            return hits
        time.sleep(0.05)
        db.expire_all()  # 清掉身份映射缓存，确保重新查库
        hits = MemorySearchService.search(db, **kwargs)
    return hits


def test_chinese_fulltext_search_works() -> None:
    """中文关键词能命中——这条在 MySQL 上必须靠 ngram 分词器，否则静默搜不到。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        hits = _search_with_retry(db, user_id=1, query="索引")
        assert hits, "中文关键词搜不到，多半是 FULLTEXT 索引没带 ngram 分词器"
        assert any(hit.document.source_type == SOURCE_MESSAGE for hit in hits)

        # 多字关键词与相关度：命中越多的文档分值越高
        hits_more = _search_with_retry(db, user_id=1, query="缓存击穿")
        assert [hit.document.source_type for hit in hits_more][0] == SOURCE_NOTE
        assert hits_more[0].score is not None
    finally:
        _purge(db, 1)
        db.close()


def test_search_is_scoped_to_current_user() -> None:
    """检索强制按 user_id 过滤：别人搜不到我的内容。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        assert _search_with_retry(db, user_id=1, query="索引")
        assert MemorySearchService.search(db, user_id=2, query="索引") == []
        assert MemorySearchService.search(db, user_id=2, query="缓存击穿") == []
    finally:
        _purge(db, 1)
        db.close()


def test_source_type_filter() -> None:
    """可以只搜某一类来源。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        only_notes = _search_with_retry(
            db, user_id=1, query="缓存", source_types=[SOURCE_NOTE]
        )
        assert [hit.document.source_type for hit in only_notes] == [SOURCE_NOTE]
    finally:
        _purge(db, 1)
        db.close()


def test_single_char_query_falls_back_to_like() -> None:
    """单字查询走 LIKE 兜底：ngram 按 2 字切词，单字到不了全文索引。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        hits = MemorySearchService.search(db, user_id=1, query="锁")
        assert hits
        assert hits[0].score is None  # LIKE 路径没有相关度
    finally:
        _purge(db, 1)
        db.close()


def test_like_wildcards_are_escaped() -> None:
    """用户输入的 % 不能变成「匹配所有」。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        assert MemorySearchService.search(db, user_id=1, query="%") == []
    finally:
        _purge(db, 1)
        db.close()


def test_reindex_is_idempotent_and_delete_cleans_index() -> None:
    """重复索引同一来源只留一条；来源删除后索引也要消失。"""
    db = SessionLocal()
    try:
        _seed(db, user_id=1)
        MemorySearchService.index_document(
            db,
            user_id=1,
            source_type=SOURCE_NOTE,
            source_id=2,
            title="笔记：缓存三兄弟（改过）",
            content="缓存穿透用布隆过滤器。",
            commit=True,
        )
        rows = (
            db.query(SearchDocument)
            .filter(
                SearchDocument.user_id == 1, SearchDocument.source_id == 2
            )
            .all()
        )
        assert len(rows) == 1
        assert "改过" in rows[0].title

        MemorySearchService.delete_document(
            db, user_id=1, source_type=SOURCE_NOTE, source_id=2, commit=True
        )
        assert (
            db.query(SearchDocument)
            .filter(SearchDocument.user_id == 1, SearchDocument.source_id == 2)
            .count()
            == 0
        )
    finally:
        _purge(db, 1)
        db.close()


@pytest.mark.anyio
async def test_search_api_returns_原文(
    async_client, register_and_login
) -> None:
    """接口返回原文（不摘要、不截断），并且只返回自己的内容。"""
    headers = await register_and_login("search")
    other_headers = await register_and_login("searchother")

    created = await async_client.post(
        "/notes",
        json={
            "title": "MySQL 索引笔记",
            "content": "最左前缀原则：查询条件必须从索引最左列开始连续匹配。",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text

    response = await async_client.get(
        "/search", params={"q": "最左前缀"}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    hit = body["items"][0]
    assert hit["source_type"] == 1  # 笔记
    assert hit["source_label"] == "笔记"
    # 原文完整返回，没有被摘要或截断
    assert "最左前缀原则" in hit["content"]

    # 换个用户搜同样的词：搜不到别人的笔记
    other = await async_client.get(
        "/search", params={"q": "最左前缀"}, headers=other_headers
    )
    assert other.json()["total"] == 0

    # 删掉笔记后索引也要消失（不然会搜到已经不存在的笔记）
    await async_client.delete(f"/notes/{created.json()['id']}", headers=headers)
    after = await async_client.get("/search", params={"q": "最左前缀"}, headers=headers)
    assert after.json()["total"] == 0
