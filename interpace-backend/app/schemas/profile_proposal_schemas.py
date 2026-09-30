"""画像待确认相关的请求/响应模型。

对应 T6.2（决策 D11）：简历解析出的画像信息先给用户确认，确认后才写 `user_profiles`。
时间字段沿用项目约定：Unix 秒。
"""

from typing import Any

from pydantic import BaseModel, Field


class ProfileProposalItem(BaseModel):
    """一条待确认的画像记录：字段与 `user_profiles` 对齐。

    注意：画像字段在库里是塞在 `profile_proposals.payload` 这个 JSON 列里的，
    不是独立列，所以**不能直接 `model_validate(orm_row)`**，要用
    `from_proposal()` 把 payload 摊平出来。
    """

    id: int
    session_id: int
    message_id: int  # 来源消息 ID，前端据此把确认卡片挂到对应消息下
    target_job: str | None = None
    years_experience: str | None = None
    target_level: str | None = None
    target_skills: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    status: int  # 0=待确认 1=已确认 2=已忽略
    created_at: int

    @classmethod
    def from_proposal(cls, proposal: Any) -> "ProfileProposalItem":
        """把 ORM 行（画像字段在 payload JSON 里）摊平成响应模型。"""
        payload = proposal.payload or {}
        return cls(
            id=proposal.id,
            session_id=proposal.session_id,
            message_id=proposal.message_id,
            target_job=payload.get("target_job"),
            years_experience=payload.get("years_experience"),
            target_level=payload.get("target_level"),
            target_skills=list(payload.get("target_skills") or []),
            weak_topics=list(payload.get("weak_topics") or []),
            status=proposal.status,
            created_at=proposal.created_at,
        )


class ProfileProposalListResponse(BaseModel):
    """按会话列出待确认记录的响应体。"""

    items: list[ProfileProposalItem]
    total: int


class ProfileProposalConfirmRequest(BaseModel):
    """确认写入请求体：传用户**最终认可**的值（可以在前端改过）。

    字段全为可选：没传或传空表示「这个字段不动」，而不是「清空」。
    列表字段会与已有内容合并去重，不会覆盖掉之前积累的技能 / 薄弱点。
    """

    target_job: str | None = Field(default=None, max_length=128)
    years_experience: str | None = Field(default=None, max_length=64)
    target_level: str | None = Field(default=None, max_length=32)
    target_skills: list[str] | None = None
    weak_topics: list[str] | None = None


class ProfileProposalResponse(BaseModel):
    """确认 / 忽略后的响应体。"""

    message: str  # 人类可读提示
    proposal: ProfileProposalItem
