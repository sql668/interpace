#!/bin/sh
# 容器启动入口（T11.4）。
#
# 为什么必须有这一步：生产环境**不会**自动建表——`main.py` 里刻意只在非生产环境跑
# `create_all`，表结构的唯一权威是 Alembic 迁移（T10.7 / D24）。少了这一步，
# 新机器上第一次启动会以"表不存在"的形式失败，而且报错位置离真正的原因很远。
#
# 用 `set -e`：迁移失败就让容器直接退出，**不要**带着旧 schema 硬启动——
# 那样会变成"服务活着但功能时好时坏"，比直接挂掉更难排查。
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] 执行数据库迁移：alembic upgrade head"
    alembic upgrade head
else
    echo "[entrypoint] RUN_MIGRATIONS=${RUN_MIGRATIONS}，跳过迁移"
fi

# exec：让 uvicorn 成为 PID 1，容器能正确接收 SIGTERM 并优雅退出。
exec "$@"
