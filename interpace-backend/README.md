# FastAPI

## 1) 包管理器

使用 uv 作为包管理器器

## 2) 安装依赖

```bash
uv sync
```

## 3) 配置环境变量（敏感信息分层）

项目支持按环境分层读取配置，避免将敏感数据写入代码：

1. 复制模板并按环境创建文件。
   - `.env.development`
   - `.env.testing`
   - `.env.production`
2. 通过 `APP_ENV` 选择当前环境（默认 `development`）。

示例（Windows cmd）：

```bash
set APP_ENV=development
```

示例（PowerShell）：

```bash
$env:APP_ENV="development"
```

MinIO 对象存储配置（可写入 `.env.development`）：

```bash
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=ai-resources
MINIO_SECURE=false
```

## 4) 启动服务（自动建表）

```bash
uvicorn app.main:app --reload
```

服务启动时会基于 SQLAlchemy 模型自动执行建表（`create_all`）。

## 5) Alembic 管理表结构变更

初始化/同步数据库：

```bash
alembic upgrade head
```

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

详细实现说明见：[docs/resource_upload_design.md](docs/resource_upload_design.md)
数据完整性验收清单见：[docs/resource_data_integrity_acceptance.md](docs/resource_data_integrity_acceptance.md)

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

