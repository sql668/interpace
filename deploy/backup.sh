#!/usr/bin/env sh
# MySQL 备份脚本（T11.7）
#
# 用法：
#   ./deploy/backup.sh                     # 备份到 ./backups，默认保留最近 7 份
#   BACKUP_DIR=/data/backups KEEP=14 ./deploy/backup.sh
#
# 配合 crontab（服务器上每天凌晨 3 点）：
#   0 3 * * * cd /opt/interpace && ./deploy/backup.sh >> /var/log/interpace-backup.log 2>&1
#
# 为什么用 `docker compose exec` 而不是连宿主机端口：
# compose 里 MySQL **没有发布端口**（安全要求，见 docker-compose.yml），
# 宿主机根本连不上它——这本身就是有意的设计。

set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-7}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/interpace-$STAMP.sql.gz"

echo "[备份] 开始 $(date '+%F %T')"

# --single-transaction：InnoDB 下拿到一致性快照且不锁表（期间服务可以继续用）
# --no-tablespaces：避免因为缺少 PROCESS 权限而报错
# 不加 --databases：导出的内容不含 CREATE DATABASE，恢复时可以指定目标库
docker compose exec -T mysql sh -c \
    'exec env MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump --single-transaction \
     --no-tablespaces --routines --triggers -uroot "$MYSQL_DATABASE"' \
    | gzip > "$TARGET"

# 用 MYSQL_PWD 而不是 -p"密码"：后者会在命令行里暴露密码（进程列表能看到），
# 而且 mysqldump 每次都打一句 "Using a password on the command line interface can be insecure"。

# 完整性检查：gzip 能解压、且里面确实有建表语句。
# 只检查"文件非空"是不够的——导出中途失败也会留下一个非空的坏文件。
if ! gzip -t "$TARGET" 2>/dev/null; then
    echo "[备份] 失败：生成的文件不是合法的 gzip" >&2
    rm -f "$TARGET"
    exit 1
fi
if ! gunzip -c "$TARGET" | grep -q "CREATE TABLE"; then
    echo "[备份] 失败：备份里没有建表语句，可能导出的库是空的" >&2
    exit 1
fi

SIZE="$(du -h "$TARGET" | cut -f1)"
# 注意写成 ${VAR}：变量后面紧跟中文标点时，shell 可能把标点当成变量名的一部分
# （实测 `${TARGET}（` 会报 "TARGET（: unbound variable"，因为全角括号被吃了进去）。
echo "[备份] 完成：${TARGET}（${SIZE}）"

# 轮转：按文件名倒序，只保留最近 $KEEP 份
COUNT="$(ls -1 "$BACKUP_DIR"/interpace-*.sql.gz 2>/dev/null | wc -l | tr -d ' ')"
if [ "$COUNT" -gt "$KEEP" ]; then
    ls -1 "$BACKUP_DIR"/interpace-*.sql.gz | sort | head -n "$((COUNT - KEEP))" | while read -r old; do
        echo "[备份] 清理旧备份：$old"
        rm -f "$old"
    done
fi

echo "[备份] 当前保留 $(ls -1 "$BACKUP_DIR"/interpace-*.sql.gz 2>/dev/null | wc -l | tr -d ' ') 份"
