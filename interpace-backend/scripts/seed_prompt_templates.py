"""预置提示词模板的入口脚本（T1.3）。

幂等、可重复执行。默认只补「一条记录都没有」的场景，不动已有版本；
需要强制新增版本时加 `--force`。

用法：
    cd interpace-backend
    python scripts/seed_prompt_templates.py
    python scripts/seed_prompt_templates.py --force
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import SessionLocal
from app.services.prompt_template_seed_service import seed_prompt_templates
from app.services.prompt_template_service import prompt_template_manager


def main() -> None:
    parser = argparse.ArgumentParser(description="预置提示词模板（幂等，可重复执行）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已有版本也新增一版并置为生效；默认不覆盖已有版本",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        for message in seed_prompt_templates(db, force=args.force):
            print(message)
        db.commit()

        # seed 之后把 Redis 缓存捂热，避免每次查模板都回落到数据库。
        prompt_template_manager.load_all_effective_to_redis(db)
        print("已刷新提示词缓存")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
