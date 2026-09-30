"""模拟面试服务：创建面试记录、追加一问一答（对应 T7.4 / T7.5）。

状态迁移的约定写在 `docs/TODO.md` 的 T7.2 里，这里只列最关键的三条：

1. **提问来自面试官（助手），回答来自候选人（用户）**；
2. 一次请求里先「回填上一题的答案」，再「追加这一轮的新问题」；
3. 用户中途停止生成**不算异常**，已生成的问答照常保留。

这个模块只处理文本。语音层将来只是把「用户说的话」变成 request_text、
把「面试官的话」变成音频播放，数据层不用改。
"""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.core.logging_config import main_logger
from app.db.models import ChatMessage, Interview

# interviews.status 取值。
INTERVIEW_STATUS_RUNNING = 0
INTERVIEW_STATUS_FINISHED = 1
INTERVIEW_STATUS_ERROR = 2


def _now() -> int:
    """Unix 秒，与表里其它时间字段口径一致。"""
    return int(time.time())


class InterviewService:
    """面试记录的创建与增量写入。"""

    @staticmethod
    def get_or_404(db: Session, *, user_id: int, interview_id: int) -> Interview:
        """按 interview_id 取面试记录；不存在或不属于当前用户一律 404。

        不区分「没有这条」与「不是你的」，避免用状态码探测他人数据。
        """
        interview = db.scalar(
            select(Interview).where(
                Interview.id == interview_id, Interview.user_id == user_id
            )
        )
        if interview is None:
            raise_error(code=404, message="面试记录不存在")
        return interview

    @staticmethod
    def finish(db: Session, *, user_id: int, interview_id: int) -> tuple[Interview, bool]:
        """结束面试并冻结时长（T7.8）。返回 (面试记录, 是否本来就已结束)。

        **幂等**：重复点「结束面试」不报错也不改数据——用户手滑点两下是常事，
        第二次报 409 只会让人以为出错了。
        """
        interview = InterviewService.get_or_404(
            db, user_id=user_id, interview_id=interview_id
        )
        if interview.status == INTERVIEW_STATUS_FINISHED:
            return interview, True

        InterviewService.finish_interview(db, interview=interview)
        db.commit()
        db.refresh(interview)
        main_logger.info(
            f"[模拟面试] interview_id={interview_id} 已结束，"
            f"时长={interview.interview_duration}s 问答={len(interview.qa_object or [])}"
        )
        return interview, False

    @staticmethod
    def get_running_interview(
        db: Session, *, user_id: int, session_id: int
    ) -> Interview | None:
        """取当前会话里「进行中」的面试记录；没有就返回 None。"""
        return db.scalar(
            select(Interview)
            .where(
                Interview.user_id == user_id,
                Interview.session_id == session_id,
                Interview.status == INTERVIEW_STATUS_RUNNING,
            )
            .order_by(Interview.id.desc())
        )

    @staticmethod
    def create_interview(
        db: Session, *, user_id: int, session_id: int, message_id: int
    ) -> Interview:
        """新建一场面试，并把入口消息标记出来（消息 status=1 + interview_id）。

        只 flush 不 commit，事务边界交给调用方。
        """
        interview = Interview(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            qa_object=[],
            interview_duration=0,
            status=INTERVIEW_STATUS_RUNNING,
        )
        db.add(interview)
        db.flush()

        # 入口消息打标：前端已有的「查看面试记录详情」卡片靠它亮起来。
        message = db.get(ChatMessage, message_id)
        if message is not None:
            message.status = 1
            message.interview_id = interview.id
            db.add(message)
        db.flush()
        main_logger.info(
            f"[模拟面试] 新建面试 interview_id={interview.id} "
            f"session_id={session_id} 入口消息={message_id}"
        )
        return interview

    @staticmethod
    def append_question(
        db: Session, *, interview: Interview, question: str
    ) -> dict | None:
        """把面试官这一轮的问题追加进 `qa_object`。

        问题为空（模型没吐内容）时跳过，避免留下空条目。
        返回新追加的条目，跳过时返回 None。
        """
        text = (question or "").strip()
        if not text:
            return None

        entry = {
            "id": uuid.uuid4().hex,
            "question": text,
            "answer": "",
            "created_at": _now(),
        }
        interview.qa_object = [*(interview.qa_object or []), entry]
        InterviewService._touch(db, interview=interview)
        return entry

    @staticmethod
    def fill_pending_answer(
        db: Session, *, interview: Interview, answer: str
    ) -> bool:
        """把用户这条消息回填到「最后一条 answer 为空」的提问上。

        返回是否真的填上了。用户连续发两条消息（中间没有面试官提问）时第二条无处可挂，
        这里返回 False，由调用方记日志——不新建「空提问」条目污染数据。
        """
        text = (answer or "").strip()
        if not text:
            return False

        # 注意：SQLAlchemy 判断 JSON 列有没有变，靠的是「新旧值比较」。
        # 如果在原字典上原地改、再把同一个列表赋回去，前后值相等 → 不会产生 UPDATE。
        # 所以这里先把每条复制成新字典，改副本后整体赋回。
        qa_list = [
            dict(item) if isinstance(item, dict) else item
            for item in (interview.qa_object or [])
        ]
        for entry in reversed(qa_list):
            if isinstance(entry, dict) and not str(entry.get("answer") or "").strip():
                entry["answer"] = text
                entry["answered_at"] = _now()
                interview.qa_object = qa_list
                InterviewService._touch(db, interview=interview)
                return True
        return False

    @staticmethod
    def finish_interview(db: Session, *, interview: Interview) -> Interview:
        """结束面试并冻结时长。"""
        interview.status = INTERVIEW_STATUS_FINISHED
        InterviewService._touch(db, interview=interview)
        return interview

    @staticmethod
    def _touch(db: Session, *, interview: Interview) -> None:
        """更新时长并落库。

        时长口径：当前时间 − 创建时间（即「最后活动时间」），面试结束时冻结。
        JSON 列的原地修改不会被 SQLAlchemy 自动识别，所以这里显式赋值 + add。
        """
        interview.interview_duration = max(0, _now() - int(interview.created_at or 0))
        db.add(interview)
        db.flush()

    @staticmethod
    def record_round(
        db: Session,
        *,
        user_id: int,
        session_id: int,
        message_id: int,
        request_text: str,
        response_text: str,
        response_ok: bool,
    ) -> int | None:
        """处理一轮面试消息：建记录（首次）→ 回填上一题答案 → 追加这一轮的问题。

        `response_ok=False`（用户中途停止或模型报错）时仍然回填答案——用户确实答了话——
        但**不追加问题**（那半截内容不该成为面试题）。返回面试记录 id。

        只 flush 不 commit，事务边界交给调用方。
        """
        interview = InterviewService.get_running_interview(
            db, user_id=user_id, session_id=session_id
        )
        is_new = interview is None
        if interview is None:
            # 首条消息就被停止 / 报错时，这场面试什么都没有，不值得建记录。
            if not response_ok:
                return None
            interview = InterviewService.create_interview(
                db, user_id=user_id, session_id=session_id, message_id=message_id
            )

        # 首条消息只负责开场（还没有上一题要回填）。
        if not is_new:
            filled = InterviewService.fill_pending_answer(
                db, interview=interview, answer=request_text
            )
            if not filled:
                main_logger.warning(
                    f"[模拟面试] interview_id={interview.id} message_id={message_id} "
                    f"没有待回答的提问，本条用户消息未计入问答（可能是连续发言）"
                )

        if response_ok:
            InterviewService.append_question(
                db, interview=interview, question=response_text
            )

        return interview.id
