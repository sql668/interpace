#!/usr/bin/env bash
#
# 本地开发环境一键启停（后端 8000 + 前端 5173）。
#
#   ./dev.sh start     启动（后台运行，日志写到 .dev-run/）
#   ./dev.sh stop      停止
#   ./dev.sh restart   重启
#   ./dev.sh status    看状态与访问地址
#   ./dev.sh logs [backend|frontend]   跟踪日志（不传参数则两个都跟）
#
# 设计上的几个取舍：
# 1. **只管应用，不管中间件**。MySQL 是系统服务、Redis/MinIO 是 `restart: always`
#    的常驻容器，本来就在跑；而且它们可能被别的项目共用，脚本不该擅自停掉它们。
#    但 `start` 会检查一遍，缺了会告诉你怎么起。
# 2. **后台运行 + PID 文件**，不用一直占着两个终端窗口；日志落在 .dev-run/ 里。
# 3. **不用 `--reload` 的进程组技巧**：uvicorn 的 reloader 会自己管好子进程，
#    stop 时给父进程发 TERM 即可；保险起见还会清理残留子进程。

# -m（job control）：让后台任务各自成为一个进程组。
# 这一步是"能停干净"的关键——`uvicorn --reload` 会 fork 出真正干活的子进程，
# 只 kill 父进程的话子进程会被 reparent 到 init、继续占着端口（实测踩过），
# 有了独立进程组就能整组一起收。
set -umo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.dev-run"
BACKEND_DIR="$ROOT/interpace-backend"
FRONTEND_DIR="$ROOT/interpace-frontend"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# 用哪个环境跑后端：由 APP_ENV 决定（命令行传入的优先级最高）。
# 与 app/core/settings.py 的 _normalize_app_env 保持一致：dev/prod/staging 是别名，
# 认不出来的值会直接报错（后端那边也是这个策略——不让它静默退回开发环境）。
BACKEND_ENV_RAW="${APP_ENV:-development}"
case "$BACKEND_ENV_RAW" in
    dev)     BACKEND_ENV="development" ;;
    prod)    BACKEND_ENV="production" ;;
    staging) BACKEND_ENV="test" ;;
    *)       BACKEND_ENV="$BACKEND_ENV_RAW" ;;
esac

# 先校验环境名本身。不校验的话，`APP_ENV=demoo` 会走到"缺 .env.demoo"那条分支，
# 提示的是"缺配置文件"——而真正的问题是这个环境名压根不存在，提示会把人带偏。
case "$BACKEND_ENV" in
    development|demo|test|production) ;;
    *)
        printf '%s\n' "APP_ENV=${BACKEND_ENV_RAW} 不是合法的环境名。"
        printf '%s\n' "可选：development / demo / test / production（也接受别名 dev / prod / staging）"
        exit 1
        ;;
esac

BACKEND_ENV_FILE="$BACKEND_DIR/.env.$BACKEND_ENV"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
# 记录"后端这次是用哪个环境起的"，用来判断重复启动时是不是换了环境
BACKEND_ENV_FILE_RUN="$RUN_DIR/backend.env"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'

info()  { printf '%s\n' "$*"; }
ok()    { printf '%s%s%s\n' "$GREEN" "$*" "$RESET"; }
warn()  { printf '%s%s%s\n' "$YELLOW" "$*" "$RESET"; }
err()   { printf '%s%s%s\n' "$RED" "$*" "$RESET"; }

mkdir -p "$RUN_DIR"

# ---------- 工具函数 ----------

port_in_use() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

pid_alive() {
    [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null
}

read_pid() {
    [ -f "$1" ] && tr -d '[:space:]' < "$1" || true
}

# 当前运行中的后端用的是哪个环境（没记录时为空）
running_backend_env() {
    [ -f "$BACKEND_ENV_FILE_RUN" ] && tr -d '[:space:]' < "$BACKEND_ENV_FILE_RUN" || true
}

# 等待某个 HTTP 地址可用；成功返回 0
wait_http() {
    local url="$1" seconds="$2" name="$3" i=0
    while [ "$i" -lt "$seconds" ]; do
        if curl -s -o /dev/null --max-time 2 "$url"; then
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done
    err "$name 在 ${seconds} 秒内没有就绪，看日志：$RUN_DIR"
    return 1
}

check_middleware() {
    local hint=""
    if ! nc -z -G 2 127.0.0.1 3306 >/dev/null 2>&1; then
        hint="$hint\n  - MySQL(3306) 没起：sudo /usr/local/mysql/support-files/mysql.server start"
    fi
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "redis"; then
        hint="$hint\n  - Redis 容器没起：docker start redis"
    fi
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "minio"; then
        hint="$hint\n  - MinIO 容器没起：docker start minio（不起也能开发，但附件上传会失败）"
    fi
    if [ -n "$hint" ]; then
        warn "中间件有问题："
        printf '%b\n' "$hint"
        printf '%s\n' "${DIM}（脚本不会替你启停中间件：MySQL 是系统服务，Redis/MinIO 可能被别的项目共用）${RESET}"
    fi
}

# ---------- start ----------

start_backend() {
    local pid
    pid="$(read_pid "$BACKEND_PID_FILE")"
    if pid_alive "$pid"; then
        local cur
        cur="$(running_backend_env)"
        if [ -n "$cur" ] && [ "$cur" != "$BACKEND_ENV" ]; then
            err "后端已在运行，但它用的是 APP_ENV=${cur}，而你这次指定的是 ${BACKEND_ENV}。"
            printf '%s\n' "  要换环境：./dev.sh stop 之后再 start"
            printf '%s\n' "  想两个环境同时跑：另起一个端口（见 docs/开发/本地开发环境.md 的“路径 A”）"
            return 1
        fi
        info "后端已在运行（PID ${pid}，APP_ENV=${cur:-未知}）"
        return 0
    fi
    if port_in_use "$BACKEND_PORT"; then
        warn "端口 $BACKEND_PORT 已被占用，但没有本脚本的 PID 记录——应该是你手工起的。先停掉它再用脚本启动。"
        return 1
    fi

    # 直接用 venv 里的 uvicorn，而不是 `uv run uvicorn`：
    # `uv run` 会先起一个 uv 进程再拉子进程，PID 文件里记的就是那个"包装进程"，
    # 停的时候 kill 它未必能带走真正的服务（同类问题 `pnpm run dev` 也有）。
    local uvicorn_bin="$BACKEND_DIR/.venv/bin/uvicorn"
    if [ ! -x "$uvicorn_bin" ]; then
        err "找不到 $uvicorn_bin —— 先在 $BACKEND_DIR 里执行 uv sync"
        return 1
    fi

    # 提前检查配置文件，而不是等后端启动超时再猜。
    # `.env.{APP_ENV}` 是**唯一**的配置来源（没有基础 .env 兜底），缺了必然起不来。
    if [ ! -f "$BACKEND_ENV_FILE" ]; then
        err "APP_ENV=${BACKEND_ENV} 需要配置文件 ${BACKEND_ENV_FILE}，但它不存在。"
        printf '%s\n' "  先造一份（记得把库名换成独立的，别和开发库共用）："
        printf '%s\n' "    cd interpace-backend && cp .env.development .env.${BACKEND_ENV}"
        printf '%s\n' "  现有：$(cd "$BACKEND_DIR" && ls .env.* 2>/dev/null | tr '\n' ' ')"
        return 1
    fi

    info "启动后端（APP_ENV=${BACKEND_ENV}）…"
    ( cd "$BACKEND_DIR" && nohup "$uvicorn_bin" app.main:app --reload --port "$BACKEND_PORT" \
        > "$BACKEND_LOG" 2>&1 & echo $! > "$BACKEND_PID_FILE" )
    wait_http "http://127.0.0.1:$BACKEND_PORT/health/live" 45 "后端" || return 1
    echo "$BACKEND_ENV" > "$BACKEND_ENV_FILE_RUN"
    ok "后端已就绪  http://127.0.0.1:${BACKEND_PORT}（APP_ENV=${BACKEND_ENV}，接口文档 /docs）"
}

start_frontend() {
    local pid
    pid="$(read_pid "$FRONTEND_PID_FILE")"
    if pid_alive "$pid"; then
        info "前端已在运行（PID ${pid}）"
        return 0
    fi
    if port_in_use "$FRONTEND_PORT"; then
        warn "端口 $FRONTEND_PORT 已被占用，但没有本脚本的 PID 记录——应该是你手工起的。先停掉它再用脚本启动。"
        return 1
    fi

    # 同理：直接跑 vite，而不是 `pnpm run dev`
    local vite_bin="$FRONTEND_DIR/node_modules/.bin/vite"
    if [ ! -x "$vite_bin" ]; then
        err "找不到 $vite_bin —— 先在 $FRONTEND_DIR 里执行 pnpm install"
        return 1
    fi

    info "启动前端 …"
    ( cd "$FRONTEND_DIR" && nohup "$vite_bin" \
        > "$FRONTEND_LOG" 2>&1 & echo $! > "$FRONTEND_PID_FILE" )
    wait_http "http://127.0.0.1:$FRONTEND_PORT/" 60 "前端" || return 1
    ok "前端已就绪  http://localhost:$FRONTEND_PORT"
}

# ---------- stop ----------

stop_one() {
    local name="$1" pid_file="$2" port="$3" extra_file="${4:-}" pid
    pid="$(read_pid "$pid_file")"
    [ -n "$extra_file" ] && rm -f "$extra_file"

    if ! pid_alive "$pid"; then
        rm -f "$pid_file"
        if port_in_use "$port"; then
            warn "$name 不是本脚本启动的（端口 $port 仍被占用），没动它"
        else
            info "$name 未运行"
        fi
        return 0
    fi

    info "停止 ${name}（PID ${pid}）…"
    # 关键：**先记下子进程再杀父进程**。
    # uvicorn --reload / vite 都会 fork 出真正干活的子进程，只 kill 父进程的话，
    # 子进程会被 reparent 到 init，之后 `pkill -P 父PID` 就找不到它了，
    # 结果是"脚本说停了，端口还占着"（实测踩过）。
    local children
    children="$(pgrep -P "$pid" 2>/dev/null | tr '\n' ' ' || true)"
    kill -TERM "$pid" 2>/dev/null || true
    if [ -n "${children// /}" ]; then
        # shellcheck disable=SC2086  # 这里就是要按空格拆成多个 PID
        kill -TERM $children 2>/dev/null || true
    fi
    local i=0
    while port_in_use "$port" && [ "$i" -lt 10 ]; do
        sleep 0.5
        i=$((i + 1))
    done

    # 兜底：端口还占着就按端口揪出残留进程收掉。
    # 只在"确实有本脚本的 PID 记录"这一支里做，避免误杀别人手工起的服务。
    if port_in_use "$port"; then
        local leftovers
        leftovers="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true)"
        if [ -n "${leftovers// /}" ]; then
            warn "端口 ${port} 仍有残留进程（${leftovers}），收掉"
            kill -TERM $leftovers 2>/dev/null || true
            sleep 1
            if port_in_use "$port"; then
                leftovers="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | tr '\n' ' ' || true)"
                kill -9 $leftovers 2>/dev/null || true
            fi
        fi
    fi
    rm -f "$pid_file"
    ok "$name 已停止"
}

# ---------- 子命令 ----------

cmd_start() {
    check_middleware
    start_backend && start_frontend
    echo
    cmd_status
}

cmd_stop() {
    # 先停前端再停后端：避免前端还在代理请求时后端已经没了
    stop_one "前端" "$FRONTEND_PID_FILE" "$FRONTEND_PORT"
    stop_one "后端" "$BACKEND_PID_FILE" "$BACKEND_PORT" "$BACKEND_ENV_FILE_RUN"
}

cmd_restart() {
    cmd_stop
    echo
    cmd_start
}

cmd_status() {
    local bpid fpid bcur
    bpid="$(read_pid "$BACKEND_PID_FILE")"
    fpid="$(read_pid "$FRONTEND_PID_FILE")"
    bcur="$(running_backend_env)"

    if pid_alive "$bpid"; then
        printf '后端  %s运行中%s  PID %-7s APP_ENV=%-12s http://127.0.0.1:%s\n' "$GREEN" "$RESET" "$bpid" "${bcur:-未知}" "$BACKEND_PORT"
    elif port_in_use "$BACKEND_PORT"; then
        printf '后端  %s占用中（非本脚本）%s 端口 %s\n' "$YELLOW" "$RESET" "$BACKEND_PORT"
    else
        printf '后端  %s未运行%s\n' "$DIM" "$RESET"
    fi

    if pid_alive "$fpid"; then
        printf '前端  %s运行中%s  PID %-7s http://localhost:%s\n' "$GREEN" "$RESET" "$fpid" "$FRONTEND_PORT"
    elif port_in_use "$FRONTEND_PORT"; then
        printf '前端  %s占用中（非本脚本）%s 端口 %s\n' "$YELLOW" "$RESET" "$FRONTEND_PORT"
    else
        printf '前端  %s未运行%s\n' "$DIM" "$RESET"
    fi

    printf '日志  %s/\n' "$RUN_DIR"
    printf '提示  本次命令指定 APP_ENV=%s（配置 %s）；若未运行则 start 会用它\n' "$BACKEND_ENV" "$(basename "$BACKEND_ENV_FILE")"
}

cmd_logs() {
    case "${1:-}" in
        backend)  tail -f "$BACKEND_LOG" ;;
        frontend) tail -f "$FRONTEND_LOG" ;;
        "")       tail -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
        *)        err "用法：./dev.sh logs [backend|frontend]"; exit 1 ;;
    esac
}

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${2:-}" ;;
    *)
        cat <<'USAGE'
本地开发环境一键启停

  ./dev.sh start             启动后端(8000) + 前端(5173)
  ./dev.sh stop              停止
  ./dev.sh restart           重启
  ./dev.sh status            看状态
  ./dev.sh logs [backend|frontend]   跟踪日志

指定环境：在命令前加 APP_ENV，例如
  APP_ENV=demo ./dev.sh start        用 .env.demo 起后端（该文件必须存在）
  APP_ENV=production ./dev.sh start  用 .env.production 起后端
环境名也接受别名 dev / prod / staging；写错会直接报错，不会静默退回开发环境。

日志与 PID 文件在 .dev-run/（已加入 .gitignore）。
中间件（MySQL/Redis/MinIO）不由本脚本管理，但 start 时会检查。
USAGE
        ;;
esac
