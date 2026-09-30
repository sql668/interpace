"""画像待确认服务：落库、列出、确认写入、忽略。

对应 T6.2（决策 D11）：简历解析出的画像信息**先落成待确认**，
用户确认（可改）后才写进 `user_profiles`。

为什么写入要单独走一步：画像每轮对话都会注入提示词（见 `build_personalized_prompt`），
一次解析错误会污染之后所有回答，所以宁可让用户多点一下。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import ProfileProposal, UserProfile
from app.services.profile_extraction_service import ProfilePayload
from app.services.user_memory_service import (
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    SOURCE_SELF_REPORT,
    MemoryEntry,
    UserMemoryService,
)

# profile_proposals.status 取值。
PROPOSAL_STATUS_PENDING = 0
PROPOSAL_STATUS_CONFIRMED = 1
PROPOSAL_STATUS_DISMISSED = 2


def _normalize_text(value: str | None) -> str | None:
    """确认时用户可能把字段清空，归一成 None（表示「不改这个字段」）。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_list(value: list[str] | None) -> list[str]:
    """字符串列表：去空白、去重、保持顺序。"""
    if not value:
        return []
    items: list[str] = []
    for entry in value:
        text = str(entry).strip()
        if text and text not in items:
            items.append(text)
    return items


class ProfileProposalService:
    """画像待确认记录的增查与确认。"""

    @staticmethod
    def create_proposal(
        db: Session,
        *,
        user_id: int,
        session_id: int,
        message_id: int,
        payload: ProfilePayload,
    ) -> ProfileProposal:
        """落一条待确认记录；同一入口消息已有时直接返回旧的（幂等）。

        只 flush 不 commit，事务边界交给调用方。
        """
        existing = db.scalar(
            select(ProfileProposal).where(ProfileProposal.message_id == message_id)
        )
        if existing is not None:
            return existing

        proposal = ProfileProposal(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            payload=payload.to_payload(),
            status=PROPOSAL_STATUS_PENDING,
        )
        db.add(proposal)
        db.flush()
        return proposal

    @staticmethod
    def list_by_session(
        db: Session, *, user_id: int, session_id: int
    ) -> list[ProfileProposal]:
        """列出某会话的全部待确认记录（按创建顺序）。"""
        return list(
            db.scalars(
                select(ProfileProposal)
                .where(
                    ProfileProposal.user_id == user_id,
                    ProfileProposal.session_id == session_id,
                )
                .order_by(ProfileProposal.id)
            )
        )

    @staticmethod
    def get_or_404(db: Session, *, user_id: int, proposal_id: int) -> ProfileProposal:
        """按 ID 取；不存在或不属于当前用户一律 404。"""
        proposal = db.scalar(
            select(ProfileProposal).where(
                ProfileProposal.id == proposal_id,
                ProfileProposal.user_id == user_id,
            )
        )
        if proposal is None:
            raise_error(code=404, message="待确认记录不存在")
        return proposal

    @staticmethod
    def confirm(
        db: Session,
        *,
        user_id: int,
        proposal_id: int,
        target_job: str | None,
        years_experience: str | None,
        target_level: str | None,
        target_skills: list[str] | None,
        weak_topics: list[str] | None,
    ) -> ProfileProposal:
        """把（用户可以改过的）画像字段写进 `user_profiles`，并标记已确认。

        写入规则：**只覆盖显式给出的字段**——用户把某个输入框清空，等于「这个字段不改」，
        而不是「把它删掉」。列表字段（技能 / 薄弱点）采用**合并去重**，不会因为
        确认一次就把之前积累的内容冲掉。
        """
        proposal = ProfileProposalService.get_or_404(
            db=db, user_id=user_id, proposal_id=proposal_id
        )
        if proposal.status != PROPOSAL_STATUS_PENDING:
            raise_error(code=409, message="这条画像信息已经处理过了")

        profile = db.scalar(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        if profile is None:
            profile = UserProfile(user_id=user_id, target_skills=[], weak_topics=[])
            db.add(profile)
            db.flush()

        if (job := _normalize_text(target_job)) is not None:
            profile.target_job = job
        if (years := _normalize_text(years_experience)) is not None:
            profile.years_experience = years
        if (level := _normalize_text(target_level)) is not None:
            profile.target_level = level
        # 技能与薄弱点走 T9.6 的统一记忆入口（合并规则、来源权重、去重都在那一处）。
        # 简历是「声明」，但这里是**用户确认过**的值，所以来源记成「你的自述」而不是
        # 「简历」——用户点头之后，这条就是他自己认可的，可信度也更高。
        entries = [
            MemoryEntry(category=CATEGORY_SKILL, name=name, mastery=50, confidence=70)
            for name in _normalize_list(target_skills)
        ] + [
            MemoryEntry(category=CATEGORY_WEAK_TOPIC, name=name, mastery=30, confidence=70)
            for name in _normalize_list(weak_topics)
        ]
        if entries:
            UserMemoryService.ingest(
                db,
                user_id=user_id,
                entries=entries,
                source=SOURCE_SELF_REPORT,
                commit=False,
            )
        # ingest 已经重建过派生缓存；这里读回来落到 proposal.payload 里供前端回显

        proposal.status = PROPOSAL_STATUS_CONFIRMED
        proposal.payload = {
            "target_job": profile.target_job,
            "years_experience": profile.years_experience,
            "target_level": profile.target_level,
            "target_skills": list(profile.target_skills or []),
            "weak_topics": list(profile.weak_topics or []),
        }
        db.add(profile)
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        main_logger.info(
            f"[画像确认] proposal_id={proposal.id} user_id={user_id} "
            f"岗位={profile.target_job} 级别={profile.target_level} "
            f"技能数={len(profile.target_skills or [])}"
        )
        return proposal

    @staticmethod
    def dismiss(db: Session, *, user_id: int, proposal_id: int) -> ProfileProposal:
        """忽略这条待确认记录：**不写画像**，只把状态标记掉。"""
        proposal = ProfileProposalService.get_or_404(
            db=db, user_id=user_id, proposal_id=proposal_id
        )
        if proposal.status != PROPOSAL_STATUS_PENDING:
            raise_error(code=409, message="这条画像信息已经处理过了")

        proposal.status = PROPOSAL_STATUS_DISMISSED
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        main_logger.info(f"[画像确认] proposal_id={proposal.id} 已忽略")
        return proposal

    @staticmethod
    def _merge_list(existing: list[str] | None, incoming: list[str] | None) -> list[str]:
        """合并字符串列表：已有顺序不变，新的去重后追加。"""
        merged = [str(item).strip() for item in (existing or []) if str(item).strip()]
        for item in _normalize_list(incoming):
            if item not in merged:
                merged.append(item)
        return merged
