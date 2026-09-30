"""笔记业务服务：增删改查与归属校验。

所有方法都要求传入 `user_id`，查询一律带上该条件——别人的笔记一律当作不存在（404），
不区分「没有这条」与「不是你的」，避免通过状态码探测他人数据。
"""

import html
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import raise_error
from app.db.models import ChatMessage, Note
from app.services.memory_search_service import (
    SOURCE_NOTE,
    MemorySearchService,
)

# 标题为空或只有空白时的兜底文案。
DEFAULT_NOTE_TITLE = "未命名笔记"

# 笔记来源标记，与 Note.source_type 对齐。
NOTE_SOURCE_MANUAL = 0
NOTE_SOURCE_MESSAGE = 1
NOTE_SOURCE_REVIEW = 2

# 从对话生成笔记时的兜底标题与标题截断长度。
DEFAULT_IMPORT_TITLE = "来自对话的笔记"
IMPORT_TITLE_MAX_LENGTH = 30

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _inline_html(text: str) -> str:
    """行内元素：先整体转义、再套标签，保证回答里的尖括号不会被当成 HTML 注入。"""
    escaped = html.escape(text)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = _INLINE_CODE_RE.sub(r"<code>\1</code>", escaped)
    return escaped


def markdown_lite_to_html(text: str) -> str:
    """把 AI 回答的 Markdown 做一次「轻量」转换，用作笔记初稿。

    只处理标题、加粗、行内代码、段落与换行——不是完整的 Markdown 渲染器。
    目标是让存进来的初稿可读，而不是 100% 还原排版；真要完整渲染得引入
    Markdown 库，属于后续的事。
    """
    blocks: list[str] = []
    buffer: list[str] = []

    def flush_paragraph() -> None:
        if buffer:
            blocks.append("<p>" + "<br/>".join(buffer) + "</p>")
            buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading = _HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            level = min(len(heading.group(1)), 4)
            blocks.append(f"<h{level}>{_inline_html(heading.group(2))}</h{level}>")
        elif not line.strip():
            flush_paragraph()
        else:
            buffer.append(_inline_html(line))
    flush_paragraph()
    return "".join(blocks) or "<p><br></p>"


def _build_title_from_message(message: ChatMessage) -> str:
    """用问题文本生成标题；太长就截断，没有问题文本时用兜底文案。"""
    lines = (message.request_text or "").strip().splitlines()
    question = lines[0].strip() if lines else ""
    if not question:
        return DEFAULT_IMPORT_TITLE
    if len(question) <= IMPORT_TITLE_MAX_LENGTH:
        return question
    return question[:IMPORT_TITLE_MAX_LENGTH] + "…"


def _build_content_from_message(message: ChatMessage) -> str:
    """把一条消息的「问 + 答」拼成笔记正文的富文本初稿。"""
    blocks: list[str] = []
    if message.request_text:
        blocks.append("<p><strong>问题</strong></p>")
        blocks.append(markdown_lite_to_html(message.request_text))
    if message.response_text:
        blocks.append("<p><strong>回答</strong></p>")
        blocks.append(markdown_lite_to_html(message.response_text))
    return "".join(blocks) or "<p><br></p>"


class NoteService:
    """笔记相关业务服务。"""

    @staticmethod
    def list_notes(
        db: Session, user_id: int, limit: int, offset: int
    ) -> tuple[list[Note], int]:
        """按最近更新时间倒序分页查询当前用户的笔记，返回 (当页数据, 总数)。"""
        total = db.scalar(
            select(func.count(Note.id)).where(Note.user_id == user_id)
        ) or 0
        stmt = (
            select(Note)
            .where(Note.user_id == user_id)
            # 最近改过的排前面，更符合笔记的使用习惯；id 兜底保证顺序稳定。
            .order_by(Note.updated_at.desc(), Note.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(stmt)), total

    @staticmethod
    def create_note(
        db: Session,
        user_id: int,
        title: str,
        content: str,
        source_type: int = 0,
        source_message_id: int | None = None,
    ) -> Note:
        """创建笔记并返回。标题是空白时用默认文案兜底。"""
        note = Note(
            user_id=user_id,
            title=title.strip() or DEFAULT_NOTE_TITLE,
            content=content,
            source_type=source_type,
            source_message_id=source_message_id,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        # T9.14：笔记也要进 L3 检索索引，否则「之前记过什么」搜不到
        MemorySearchService.index_document(
            db,
            user_id=user_id,
            source_type=SOURCE_NOTE,
            source_id=note.id,
            title=note.title,
            content=note.content,
            created_at=note.created_at,
            commit=True,
        )
        return note

    @staticmethod
    def get_note_or_404(db: Session, user_id: int, note_id: int) -> Note:
        """按 note_id + user_id 取笔记，不存在（或不属于该用户）抛 404。"""
        note = db.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        if not note:
            raise_error(code=404, message="笔记不存在")
        return note

    @staticmethod
    def update_note(
        db: Session,
        user_id: int,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> Note:
        """更新标题与正文；只处理显式传入的字段。"""
        note = NoteService.get_note_or_404(db=db, user_id=user_id, note_id=note_id)
        if title is not None:
            # 标题被清成空白时保持原标题，避免出现没有标题的笔记。
            note.title = title.strip() or note.title
        if content is not None:
            note.content = content
        db.commit()
        db.refresh(note)
        MemorySearchService.index_document(
            db,
            user_id=user_id,
            source_type=SOURCE_NOTE,
            source_id=note.id,
            title=note.title,
            content=note.content,
            created_at=note.created_at,
            commit=True,
        )
        return note

    @staticmethod
    def delete_note(db: Session, user_id: int, note_id: int) -> None:
        """删除笔记；不存在或不属于当前用户抛 404。"""
        note = NoteService.get_note_or_404(db=db, user_id=user_id, note_id=note_id)
        db.delete(note)
        db.commit()
        # 索引对来源不设外键，删除必须显式清理，否则删掉的笔记还会被搜出来
        MemorySearchService.delete_document(
            db,
            user_id=user_id,
            source_type=SOURCE_NOTE,
            source_id=note_id,
            commit=True,
        )

    @staticmethod
    def import_from_message(
        db: Session, user_id: int, message_id: int, title: str | None = None
    ) -> tuple[Note, bool]:
        """把一条对话消息的问答存成笔记，返回 (笔记, 是否本次新建)。

        幂等策略（D6）：同一条消息只对应一条笔记。已经存过就直接返回那一条，
        **不覆盖用户后来改过的内容**——AI 回答本身不会再变，重复「存入」带不来
        新信息，覆盖只会让用户之前的编辑白费。

        注意：`notes.source_message_id` 没有唯一约束（表已建好、`create_all`
        不会给已有表加约束），所以这里的「查了再写」在并发双击下理论上可能
        产生两条。前端按钮在请求期间置灰，正常操作碰不到。
        """
        existing = db.scalar(
            select(Note).where(
                Note.user_id == user_id,
                Note.source_type == NOTE_SOURCE_MESSAGE,
                Note.source_message_id == message_id,
            )
        )
        if existing:
            return existing, False

        # 归属校验：消息必须属于当前用户，否则一律当作不存在。
        message = db.scalar(
            select(ChatMessage).where(
                ChatMessage.id == message_id, ChatMessage.user_id == user_id
            )
        )
        if not message:
            raise_error(code=404, message="消息不存在")

        note = Note(
            user_id=user_id,
            title=(title or _build_title_from_message(message)).strip() or DEFAULT_NOTE_TITLE,
            content=_build_content_from_message(message),
            source_type=NOTE_SOURCE_MESSAGE,
            source_message_id=message_id,
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return note, True
