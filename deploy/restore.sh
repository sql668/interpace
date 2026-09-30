#!/usr/bin/env sh
# MySQL 恢复脚本（T11.7）
#
# 用法：
#   ./deploy/restore.sh backups/interpace-20260930-030000.sql.gz
#   ./deploy/restore.sh backups/xxx.sql.gz inter-pace-restore-test   # 恢复到另一个库（演练用）
#
# **恢复是破坏性的**：默认会写回生产库。演练时请传第二个参数，恢复到临时库，
# 验证完删掉即可——这样既能证明备份可用，又不会碰到线上数据。

set -eu

DUMP_FILE="${1:?用法: ./deploy/restore.sh <备份文件> [目标库]}"
TARGET_DB="${2:-}"

if [ ! -f "$DUMP_FILE" ]; then
    echo "[恢复] 找不到备份文件：$DUMP_FILE" >&2
    exit 1
fi

if [ -z "$TARGET_DB" ]; then
    TARGET_DB="$(grep '^MYSQL_DATABASE=' .env | cut -d= -f2)"
    echo "[恢复] ⚠️  未指定目标库，将写入 .env 里的 MYSQL_DATABASE=$TARGET_DB"
    echo "[恢复]    要演练请改用：./deploy/restore.sh $DUMP_FILE inter-pace-restore-test"
fi

echo "[恢复] 备份文件：$DUMP_FILE"
echo "[恢复] 目标库：$TARGET_DB"

# 目标库不存在就建（演练场景需要）；排序规则与 compose 里 MySQL 的启动参数保持一致
echo "[恢复] 开始 $(date '+%F %T')"

docker compose exec -T mysql sh -c \
    "exec env MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -e \
     \"CREATE DATABASE IF NOT EXISTS \\\`$TARGET_DB\\\` \
      CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\""

gunzip -c "$DUMP_FILE" | docker compose exec -T mysql sh -c \
    "exec env MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot \"$TARGET_DB\""

echo "[恢复] 完成。核对一下："
docker compose exec -T mysql sh -c \
    "exec env MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -N -e \
     \"select concat('表数量=', count(*)) from information_schema.tables \
      where table_schema='$TARGET_DB';\""
docker compose exec -T mysql sh -c \
    "exec env MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -N -e \
     \"select concat('alembic 版本=', version_num) from \\\`$TARGET_DB\\\`.alembic_version;\""
