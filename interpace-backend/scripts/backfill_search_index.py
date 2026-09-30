"""一次性回填：把已有的对话消息 / 笔记 / 复盘结果写进 L3 检索索引（T9.14）。

**为什么需要它**：索引是在写入时建立的（T9.14 起），所以**升级之前产生的历史内容
不在索引里**——用户搜「上次那道题」时正好搜不到最该搜到的东西。

用法（幂等，可重复执行）：
    cd interpace-backend
    python scripts/backfill_search_index.py
    python scripts/backfill_search_index.py --dry-run    # 只统计不写库
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import ChatMessage, InterviewEvaluation, Note
from app.services.memory_search_service import (
    SOURCE_EVALUATION,
    SOURCE_MESSAGE,
    SOURCE_NOTE,
    MemorySearchService,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 L3 检索索引（幂等）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = parser.parse_args()

    db = SessionLocal()
    counts = {"messages": 0, "notes": 0, "evaluations": 0}
    try:
        for message in db.query(ChatMessage).all():
            content = f"{message.request_text or ''}\n\n{message.response_text or ''}".strip()
            if not content:
                continue
            counts["messages"] += 1
            if args.dry_run:
                continue
            MemorySearchService.index_document(
                db,
                user_id=message.user_id,
                source_type=SOURCE_MESSAGE,
                source_id=message.id,
                session_id=message.session_id,
                title=message.request_text or "",
                content=content,
                created_at=message.created_at,
            )

        for note in db.query(Note).all():
            if not (note.content or "").strip() and not (note.title or "").strip():
                continue
            counts["notes"] += 1
            if args.dry_run:
                continue
            MemorySearchService.index_document(
                db,
                user_id=note.user_id,
                source_type=SOURCE_NOTE,
                source_id=note.id,
                title=note.title or "",
                content=note.content or note.title or "",
                created_at=note.created_at,
            )

        for evaluation in db.query(InterviewEvaluation).all():
            content = "\n".join(
                [
                    evaluation.summary or "",
                    "薄弱点：" + "、".join(evaluation.weak_topics or []),
                    "改进建议：" + "；".join(evaluation.suggestions or []),
                ]
            ).strip()
            if not content:
                continue
            counts["evaluations"] += 1
            if args.dry_run:
                continue
            MemorySearchService.index_document(
                db,
                user_id=evaluation.user_id,
                source_type=SOURCE_EVALUATION,
                source_id=evaluation.id,
                title=f"面试复盘（{evaluation.qa_count} 轮）",
                content=content,
                created_at=evaluation.created_at,
            )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        mode = "（dry-run，未写库）" if args.dry_run else ""
        print(
            f"对话消息 {counts['messages']} 条、笔记 {counts['notes']} 条、"
            f"复盘 {counts['evaluations']} 条已处理{mode}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
