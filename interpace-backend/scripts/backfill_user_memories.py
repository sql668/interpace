"""一次性回填：把只存在于 `user_profiles` JSON 列里的画像数据补进 `user_memories`。

**为什么需要它**：T9.2 起 `target_skills` / `weak_topics` 两个 JSON 列被降级为
**派生缓存**——由 `user_memories` 重建。而重建是「覆盖」语义，所以升级之后
第一次写入就会把**只在 JSON 里、明细表里没有**的旧数据抹掉。

历史背景：T5.8（刷题评分）、T8.4（复盘）当初是直接写 JSON 列的；T9.2 之后才
同时写明细表。也就是说 T9.2 之前产生的数据都只躺在 JSON 里。

用法（幂等，可重复执行）：
    cd interpace-backend
    python scripts/backfill_user_memories.py
    python scripts/backfill_user_memories.py --dry-run   # 只看要补多少，不写库

来源标记：技能标「用户自述」，薄弱点标「行为证据」——因为薄弱点在历史上都是
刷题评分与面试复盘写进来的，属于行为证据；技能来源无法追溯，按自述处理更保守。
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.db.models import UserMemory, UserProfile
from app.services.user_memory_service import (
    CATEGORY_SKILL,
    CATEGORY_WEAK_TOPIC,
    SOURCE_BEHAVIOR,
    SOURCE_SELF_REPORT,
    MemoryEntry,
    UserMemoryService,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="把 JSON 画像回填进明细表（幂等）")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = parser.parse_args()

    db = SessionLocal()
    scanned = 0
    filled_profiles = 0
    filled_entries = 0
    try:
        for profile in db.query(UserProfile).all():
            skills = [str(s).strip() for s in (profile.target_skills or []) if str(s).strip()]
            weak = [str(w).strip() for w in (profile.weak_topics or []) if str(w).strip()]
            if not skills and not weak:
                continue
            scanned += 1

            existing = {
                (row.category, row.name)
                for row in db.query(UserMemory)
                .filter(UserMemory.user_id == profile.user_id)
                .all()
            }
            entries = [
                MemoryEntry(
                    category=CATEGORY_SKILL, name=name, mastery=50, confidence=60
                )
                for name in skills
                if (CATEGORY_SKILL, name) not in existing
            ] + [
                MemoryEntry(
                    category=CATEGORY_WEAK_TOPIC, name=name, mastery=30, confidence=70
                )
                for name in weak
                if (CATEGORY_WEAK_TOPIC, name) not in existing
            ]
            if not entries:
                continue

            filled_profiles += 1
            filled_entries += len(entries)
            print(
                f"  user_id={profile.user_id} 补 {len(entries)} 条: "
                f"{[e.name for e in entries]}"
            )
            if args.dry_run:
                continue

            # 技能与薄弱点来源不同，分两次 ingest（否则来源标记会被写成一个）
            UserMemoryService.ingest(
                db,
                user_id=profile.user_id,
                entries=[e for e in entries if e.category == CATEGORY_SKILL],
                source=SOURCE_SELF_REPORT,
                commit=False,
            )
            UserMemoryService.ingest(
                db,
                user_id=profile.user_id,
                entries=[e for e in entries if e.category == CATEGORY_WEAK_TOPIC],
                source=SOURCE_BEHAVIOR,
                commit=False,
            )
            # ingest 会重建派生缓存；此时明细表已包含全部条目，重建不会丢数据
            db.commit()

        mode = "（dry-run，未写库）" if args.dry_run else ""
        print(
            f"\n扫描有数据的画像 {scanned} 行，需回填 {filled_profiles} 行、"
            f"共 {filled_entries} 条{mode}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
