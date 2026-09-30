# 面途 InterPace · 后端

FastAPI + SQLAlchemy + LangGraph。接口统一带 **`/api/v1`** 前缀（探活 `/health/*` 除外）。
项目总览与本地启动见根目录 [README](../README.md)。

## 1) 包管理器

使用 uv 作为包管理器。

## 2) 安装依赖

```bash
uv sync
```

## 3) 配置环境变量（敏感信息分层）

项目支持按环境分层读取配置，避免将敏感数据写入代码：

1. 复制模板并按环境创建文件，**四套环境各一个**：
   - `.env.development`（本机开发）
   - `.env.demo`（对外演示，启用配额）
   - `.env.test`（测试）
   - `.env.production`（正式）
2. 通过 `APP_ENV` 选择当前环境（默认 `development`，也接受 `dev` / `prod` / `staging` 别名）。

```bash
APP_ENV=demo uv run uvicorn app.main:app --reload
```

**两个容易踩的点**：

- `APP_ENV` 指向的 `.env.{APP_ENV}` 是**唯一**的配置来源，**没有基础 `.env` 兜底**——
  文件不存在会直接报 `MYSQL_URL is required`。
- `APP_ENV` 写错会**启动即失败**并列出可选值（刻意如此：静默退回开发环境会让人误以为配额开着）。

MinIO 对象存储配置（可写入 `.env.development`）：

```bash
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=ai-resources
MINIO_SECURE=false
```

## 4) 启动服务

```bash
uv run uvicorn app.main:app --reload
```

**建表行为按环境区分**：`development` 会跑一次 `create_all` 补齐缺失的表（图方便）；
**其余环境都不跑**，表结构的唯一权威是 Alembic 迁移。别指望 `create_all` 改列或改索引——
它只建缺失的表。

## 5) Alembic 管理表结构变更

初始化/同步数据库：

```bash
alembic upgrade head
```

> 容器部署时这一步由 `docker-entrypoint.sh` 在启动前自动执行。
> 详细流程（含 autogenerate 的三个盲区、已有库如何首次接入）见
> [数据库变更流程](../docs/开发/数据库变更流程.md)。

## 6) 测试

```bash
uv run pytest          # 需要 MySQL 在运行（测试连真实数据库）
```

## 演示环境配额

演示环境的限制（按 IP 限 token、每日轮数/出题/复盘次数、单场面试时长、降本开关）
写在 **`config/demo_limits.json`**，改完最多 5 秒热生效、不用重启。
当前生效值可以问接口：`GET /api/v1/config/runtime`。

为什么配额卡在 `app/agent/llm.py`：那是全项目**唯一**的模型出口，
在接口入口按次数限流和真实 token 消耗完全不是一回事（详见 `docs/TODO.md` 阶段 12）。

模型修改后一键同步：

```bash
alembic revision --autogenerate -m "update user table"
alembic upgrade head
```

## 分层结构

- `app/routes/`: API 路由层
- `app/schemas/`: 请求/响应校验层 (Pydantic v2)
- `app/services/`: 业务逻辑层
- `app/db/`: SQLAlchemy 数据层
- `alembic/`: 迁移脚本

## 文件资源上传管理

项目已支持统一资源管理（文件/图片/音频）：

- 接口：`POST /upload/file`（需 Bearer Token）
- 上传字段（`multipart/form-data`）：
  - `file`: 上传文件（必填）
  - `storage_scene`: 存储场景（可选，默认 `0`）
    - `0` 长过期（30天）
    - `1` 短过期（2小时）
    - `2` 仅提取内容，不落盘原文件
    - `3` 永久存储
  - `upload_purpose`: 上传用途（可选，默认 `0`）
    - `0` 普通资源（不更新头像）
    - `1` 用户头像（图片类型时更新 `users.avatar`）

上传行为：

- 按扩展名识别资源类型：文件（0）/图片（1）/音频（2）
- 使用 `MD5 + user_id` 做用户级去重
- 原文件上传到 MinIO（`storage_scene=2` 除外）
- 资源元数据写入 `resources` 表（`storage_path` 为 `minio://bucket/object_key`）
- 仅当 `upload_purpose=1` 且图片类型时，更新 `users.avatar`
- 教学版旧逻辑保留在 `app/services/upload_service.py`（不参与运行）
- 实际运行逻辑在 `app/services/upload_service_minio.py`

接口契约（参数、错误码、去重规则）见 [接口文档 · 资源与上传](../docs/接口/学习与素材.md)；
相关的设计取舍与踩过的坑记在 [docs/TODO.md](../docs/TODO.md) 阶段 3。

> 注：上面两处原来指向 `docs/resource_upload_design.md` 与
> `docs/resource_data_integrity_acceptance.md`，这两个文件在仓库里**并不存在**
> （已改为指向现有文档）。链接指向不存在的文件比没有链接更误导。

## 过期资源定时清理（每天 03:00）

已提供定时清理脚本：`scripts/run_expired_resource_cleanup.py`

- 运行一次（用于手动验证）：

```bash
python scripts/run_expired_resource_cleanup.py --once
```

- 持续运行（每天凌晨 3 点执行）：

```bash
python scripts/run_expired_resource_cleanup.py
```

可选参数：

- `--hour`：执行小时（默认 `3`）
- `--minute`：执行分钟（默认 `0`）
- `--timezone`：时区（默认 `Asia/Shanghai`）
