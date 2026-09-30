# 后端规则（interpace-backend）

Python + FastAPI，REST 风格。

## 分层与依赖方向

- `app/main.py`：应用入口、中间件、路由注册。
- `app/api/`：路由层；`app/schemas/`：Pydantic 模型；`app/services/`：业务逻辑；`app/models/`：数据库模型；`app/core/`：配置与通用工具。
- 依赖方向固定为 `api → services → models`，禁止反向依赖和跨层调用。

## 接口规范（REST）

- FastAPI 按路由模块拆分，不同业务分开路由文件
- 数据模型、路由接口、业务逻辑分层编写
- 统一接口返回格式，参数做好基础校验
- 业务逻辑抽离到单独方法，路由只做接收和响应
- 资源用复数名词：`GET /api/v1/interviews`、`POST /api/v1/interviews/{id}/feedbacks`。
- URL 里不出现动词（`/getInterview` 这种写法禁止），动作通过 HTTP 方法和子资源表达。
- 请求体和响应体必须是 Pydantic 模型，禁止直接返回裸 `dict`。
- 路由函数只做参数校验和调用 service，业务逻辑写在 `app/services/`。
- 列表接口统一返回 `{"items": [...], "total": n}`；分页参数用 `limit` / `offset`。
- 错误统一用 `HTTPException`，响应体为 `{"detail": ...}`；不要返回 200 包着错误码。
- 状态码要正确：创建 201、删除 204、参数错误 422、资源不存在 404。

## 代码风格

- 函数签名必须写类型标注；禁止裸 `except:`；用 `logging` 不用 `print`。
- IO 操作用 `async def`，不要在异步函数里写阻塞调用。
- 配置通过环境变量读取（`pydantic-settings`），密钥不进仓库，提供 `.env.example`。
- 时间统一用 UTC 存储，接口返回 ISO 8601 字符串。

## 智能体开发

- 智能体编排统一用 LangGraph，模型、提示词、工具、记忆统一用 LangChain；不要手写编排循环，也不要另造一套 Agent 框架。
- 编排代码放 `app/agent/`，按场景拆分模块（如 `app/agent/scenes/quiz.py`），对外只暴露一个可执行入口。
- 提示词一律走 `prompt_template_service` 读取模板，不在代码里硬编码长提示词。
- 流式接口保持现有 SSE 事件格式（`start` / `delta` / `done` / `error`），编排层只负责产出增量文本。
- 已声明依赖：`langchain`、`langchain-community`、`langchain-openai`、`langgraph`；新增其他智能体相关依赖先按根规则确认。

## 验证

- 每个路由至少一个 `pytest` + `TestClient` 用例，覆盖正常路径和错误路径。
- 命令：`ruff check .`、`pytest`（依赖管理工具接入后在此更新）。

## 尚未确定，不要自行决定

- 依赖管理工具（uv / poetry / pip）与虚拟环境方案。
- 数据库与 ORM（PostgreSQL + SQLAlchemy 之类）。
- 认证方式（JWT / Session）与权限模型。
