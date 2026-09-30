# 后端镜像（T11.2）
#
# 设计要点：
# 1. **两阶段**：builder 里装依赖，runtime 只带"能跑起来的那些东西"，
#    构建工具、缓存、下载物都不进最终镜像。
# 2. **非 root 运行**：容器被攻破时不至于直接拿到 root。
# 3. **单 worker**：2核2G 上多 worker 只会互相抢内存（阶段 11 的硬约束 2）。
#    worker 数写死在 CMD 里而不是交给环境变量，避免有人"顺手调大"。
# 4. `.env` **不进镜像**（由 .dockerignore 挡掉），配置一律从 compose 的环境变量注入。

# ---------- 构建阶段 ----------
FROM python:3.11-slim AS builder

# uv 版本与开发机保持一致，避免 lock 解析行为在不同版本间漂移。
RUN pip install --no-cache-dir uv==0.12.9

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 先只拷依赖清单，让"改代码"不会让依赖层缓存失效。
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 再拷源码与迁移脚本。
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
# 演示环境配额配置（T12.4）。**必须打进镜像**：读不到文件时会退回"不限制"，
# 演示环境就在无人察觉的情况下失去了防护。想在服务器上热改而不重建镜像，
# 用 compose 把宿主机目录挂到 /app/config 覆盖即可。
COPY config ./config
COPY docker-entrypoint.sh ./

# ---------- 运行阶段 ----------
FROM python:3.11-slim AS runtime

# 时区数据：日志与业务时间都按 Asia/Shanghai 展示，缺 tzdata 会退化成 UTC。
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /app /app

# logs/ 与 uploads/ 是运行期要写的目录：
# - logs/：loguru 的文件 sink（代码里会 mkdir，但属主必须是 appuser）；
# - uploads/：main.py 里 `StaticFiles(directory="uploads")` 默认 check_dir=True，
#   **目录不存在会直接启动失败**，所以镜像里必须预建。
RUN mkdir -p /app/logs /app/uploads \
    && chmod +x /app/docker-entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# 探活走 /health/live（不带 /api/v1 前缀，见 T10.1）。
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"

# 入口脚本先跑迁移，再把控制权交给 uvicorn（exec 保证信号能传到进程）。
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
