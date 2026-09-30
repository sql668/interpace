"""长期记忆 L3 检索的响应模型（T9.14）。

`content` 返回**原文**，不做摘要、不截断——检索结果要可信，摘要会让它不再可信。
"""

from pydantic import BaseModel, Field


class SearchHitItem(BaseModel):
    """一条检索结果。"""

    source_type: int  # 0=对话消息 1=笔记 2=面试复盘
    source_label: str  # 展示用中文
    source_id: int  # 来源记录 ID（前端可据此跳转）
    session_id: int | None = None
    title: str
    content: str  # 原文，完整返回
    score: float | None = None  # 相关度（单字查询走 LIKE 时为 null）
    created_at: int  # 来源时间 Unix 秒


class SearchResponse(BaseModel):
    """检索响应。"""

    query: str
    total: int
    items: list[SearchHitItem] = Field(default_factory=list)
