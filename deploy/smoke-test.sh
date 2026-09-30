#!/usr/bin/env sh
# 上线冒烟检查入口（T11.8）
#
# 用法：
#   ./deploy/smoke-test.sh
#   BASE_URL=http://frontend/api/v1 ./deploy/smoke-test.sh
#
# 检查逻辑在 `interpace-backend/scripts/smoke_test.py`，这里只负责把它送进容器执行。
# **必须在容器里跑**：脚本默认打 `http://frontend/api/v1`（compose 服务名），
# 这样才真的经过 Nginx 反代——在宿主机上直接打后端端口会绕过 Nginx，
# 把 SSE 缓冲、反代配置这些问题全漏掉。

set -eu

BASE_URL="${BASE_URL:-http://frontend/api/v1}"
HEALTH_BASE="${HEALTH_BASE:-http://frontend}"

docker compose exec -T backend python /app/scripts/smoke_test.py \
    --base-url "$BASE_URL" \
    --health-base "$HEALTH_BASE"
