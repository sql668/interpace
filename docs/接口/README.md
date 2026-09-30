# 接口文档

面途（InterPace）后端接口说明。**以代码为准，文档跟随改动**——改接口要同时改这里
（`AGENTS.md` 的接口变更纪律）。

本目录的组织方式：先写通用约定与全量索引，再按业务模块出详细文档。
当前详细版覆盖 **会话与对话**、**笔记** 两组；其余模块先看下面的索引，
详细文档按 `docs/TODO.md` 的 T10.2 逐个补齐。

## 通用约定

### 基地址与版本前缀

所有业务接口统一挂在 **`/api/v1`** 之下（T10.1）。本地开发默认地址是 `http://127.0.0.1:8000`，
前端通过 `VITE_API_BASE_URL=/api/v1` 请求，开发环境由 Vite 代理转发（只转发、不改写路径）。

| 类别 | 路径 | 是否带版本前缀 |
| --- | --- | --- |
| 业务接口 | `/api/v1/...` | 带 |
| 探活 | `/health/live`、`/health/ready` | **不带** |
| 接口文档 | `/docs`、`/openapi.json` | **不带** |
| 根路径 | `/` | **不带** |
| 静态资源目录 | `/uploads/...` | **不带** |

### 鉴权

除注册、登录、刷新令牌、探活、文档外，其余接口都要求：

```
Authorization: Bearer <access_token>
```

未携带或令牌失效返回 **401**。业务接口一律按「当前登录用户」隔离数据：
**别人的资源、不存在的资源，都返回 404**（不区分，避免泄露资源是否存在）。

### 统一错误结构

业务异常、参数校验失败、FastAPI 原生 `HTTPException`、未捕获异常都由全局处理器
收敛成同一个结构：

```json
{
  "code": 404,
  "message": "用户不存在",
  "detail": { "user_id": 123, "path": "/api/v1/users/123", "method": "GET" }
}
```

- `code` 与 HTTP 状态码一致；
- `message` 是可直接展示给用户的中文文案；
- `detail` 里额外注入 `path` / `method` 便于定位；参数校验失败时为
  `{"errors": [{"field": "...", "message": "...", "type": "..."}]}`。

### 常用状态码

| 状态码 | 含义 |
| --- | --- |
| 200 | 成功（**创建会话、创建用户之外的多数接口用 200**） |
| 201 | 创建成功（注册、创建用户、上传文件、创建笔记） |
| 400 | 请求参数错误（业务层判断，例如"请至少提供一个需要更新的字段"） |
| 401 | 未登录 / 令牌无效 |
| 404 | 资源不存在或不属于当前用户 |
| 409 | 冲突（如用户名已被占用） |
| 422 | 框架层参数校验失败 |
| 429 | 触发限流（注册 5 次/分钟、登录 10 次/分钟、刷新 30 次/分钟） |
| 500 | 未预期异常 |

> 注意：**创建会话返回的是 200 而不是 201**，与 `AGENTS.md` 的"创建返回 201"不一致，
> 属于已知遗留，已记在 `docs/TODO.md` 的阶段 10 遗留清单里。

### 时间与分页

- 时间字段统一是 **Unix 秒**（整数），不是 ISO 8601 字符串。
- 分页有两种形态：`page` + `page_size` 返回 `page`/`page_size`/`has_more`，
  `limit` + `offset` 返回 `total`。具体以各接口为准。

### 流式接口

- **SSE**：`POST /api/v1/sessions/{session_id}/stream-chat`。
  请求体是普通 JSON，响应是 `text/event-stream`。
- **WebSocket**：`/api/v1/sessions/{session_id}/speech/stream`（语音面试）。
  详见 [会话与对话](./会话与对话.md)。

### 运行时能力开关

`GET /api/v1/config/runtime`（**不鉴权**，登录页也会调用）返回当前环境开放了哪些功能，
前端据此决定界面上显示什么：

```json
{
  "app_env": "demo",
  "quota_enforced": true,
  "features": { "voice_interview": false, "file_upload": true },
  "interview_max_minutes": 3,
  "notice": { "banner_text": "演示环境：有调用次数上限、数据每日重置" },
  "limits": {
    "tokens_per_ip": 3000000,
    "turns_per_day": 10,
    "quizzes_per_day": 2,
    "evaluations_per_day": 1,
    "voice_minutes_per_day": 3,
    "max_turns_per_session": 5,
    "max_sessions": 3,
    "max_notes": 10
  }
}
```

**为什么要专门开一个接口**：这些开关的唯一事实来源是后端的 `config/demo_limits.json`
（可热改，不用重启）。如果前端自己维护一份构建期的环境判断，两边迟早不一致——
最典型的坏结果就是「按钮显示着，点了连不上」。只暴露**真实生效**的项，不做占位字段。

- `features.voice_interview=false` → 前端不显示「语音面试」入口，**且后端拒绝语音 WebSocket 连接**。
- `features.file_upload=false` → 前端不显示「+ 附件」入口，**且 `POST /upload/file` 返回 403**。
- `limits` **只在启用配额时有值**（否则为 `null`）：首页的"演示环境能试到什么"
  直接渲染这份数字。放在接口里而不是前端写死，是为了配置改了页面就跟着变。

两个开关都是"两边读同一份配置"：只藏按钮挡不住绕过界面直接发请求的人，
而语音（双计费）与附件（解析全文很吃 token）恰好是最贵的两条链路。

## 全量接口索引

下表由 `app.openapi()` 导出核对过（生成方式见文末）。「鉴权」列指是否强制登录。

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册 | 否 |
| POST | `/api/v1/auth/login` | 登录，返回访问令牌 + 刷新令牌 | 否 |
| POST | `/api/v1/auth/refresh` | 用刷新令牌换新令牌 | 否 |
| GET | `/api/v1/config/runtime` | 当前环境的能力开关（是否开放语音面试、面试时长上限、横幅文案） | 否 |
| GET | `/api/v1/users` | 用户列表 | 是 |
| POST | `/api/v1/users` | 创建用户 | 是 |
| GET | `/api/v1/users/{user_id}` | 用户详情 | 是 |
| PUT | `/api/v1/users/{user_id}` | 更新用户（部分更新） | 是 |
| DELETE | `/api/v1/users/{user_id}` | 删除用户及其全部数据 | 是 |
| POST | `/api/v1/upload/file` | 上传附件（multipart） | 是 |
| GET | `/api/v1/resources/{resource_id}/content` | 读取资源内容（仅本人） | 是 |
| GET | `/api/v1/resources/content` | 按 `storage_path` 读取资源内容 | 是 |
| GET | `/api/v1/sessions` | 会话列表（分页，按 `session_model` 过滤） | 是 |
| POST | `/api/v1/sessions` | 创建会话 | 是 |
| PUT | `/api/v1/sessions/{session_id}` | 修改会话标题 | 是 |
| DELETE | `/api/v1/sessions/{session_id}` | 删除会话（级联清消息/面试/题库/资源） | 是 |
| GET | `/api/v1/sessions/{session_id}/messages` | 消息分页 | 是 |
| POST | `/api/v1/sessions/{session_id}/stream-chat` | 流式对话（SSE） | 是 |
| POST | `/api/v1/sessions/{session_id}/stream-chat/stop` | 停止流式回答 | 是 |
| WS | `/api/v1/sessions/{session_id}/speech/stream` | 语音面试（ASR→LLM→TTS） | 是（token 走查询参数） |
| GET | `/api/v1/interviews/{interview_id}` | 面试详情（问答明细） | 是 |
| POST | `/api/v1/interviews/{interview_id}/finish` | 结束面试 | 是 |
| POST | `/api/v1/interviews/{interview_id}/evaluations` | 生成面试复盘 | 是 |
| GET | `/api/v1/interviews/{interview_id}/evaluations` | 查询复盘（**没生成过返回 200 + `evaluation: null`**） | 是 |
| POST | `/api/v1/interviews/{interview_id}/evaluations/from-audio` | 用录音生成复盘 | 是 |
| GET | `/api/v1/notes` | 笔记列表（不含正文） | 是 |
| POST | `/api/v1/notes` | 创建笔记 | 是 |
| GET | `/api/v1/notes/{note_id}` | 笔记详情（含正文） | 是 |
| PUT | `/api/v1/notes/{note_id}` | 更新笔记 | 是 |
| DELETE | `/api/v1/notes/{note_id}` | 删除笔记 | 是 |
| POST | `/api/v1/notes/import` | 把一条对话消息一键存成笔记（幂等） | 是 |
| GET | `/api/v1/quiz-papers` | 按会话列出卷子 | 是 |
| GET | `/api/v1/quiz-papers/{paper_id}` | 卷子详情（含题目） | 是 |
| POST | `/api/v1/quiz-papers/{paper_id}/submissions` | 提交答卷并评分 | 是 |
| POST | `/api/v1/resumes/export` | 导出优化后的简历（docx） | 是 |
| GET | `/api/v1/search` | 全库检索（笔记 / 消息 / 面试记录） | 是 |
| GET | `/api/v1/profile` | 我的画像 | 是 |
| PUT | `/api/v1/profile` | 更新求职意向 | 是 |
| GET | `/api/v1/profile/memories` | 记忆条目列表（可按 `category` 过滤） | 是 |
| POST | `/api/v1/profile/memories` | 手动新增记忆条目 | 是 |
| GET | `/api/v1/profile/memories/pending` | 待确认的记忆条目 | 是 |
| PUT | `/api/v1/profile/memories/{memory_id}` | 修改记忆条目 | 是 |
| DELETE | `/api/v1/profile/memories/{memory_id}` | 删除记忆条目 | 是 |
| POST | `/api/v1/profile/memories/{memory_id}/approve` | 批准记忆条目 | 是 |
| POST | `/api/v1/profile/memories/{memory_id}/reject` | 拒绝记忆条目 | 是 |
| GET | `/api/v1/profile/memory-logs` | 记忆变更日志 | 是 |
| GET | `/api/v1/profile-proposals` | 按会话列出待确认的画像提案 | 是 |
| POST | `/api/v1/profile-proposals/{proposal_id}/confirm` | 确认提案并写入画像 | 是 |
| POST | `/api/v1/profile-proposals/{proposal_id}/dismiss` | 忽略提案 | 是 |
| GET | `/api/v1/prompt/templates/{agent_name}/{scene}` | 提示词模板版本列表 | **否（见下方风险）** |
| POST | `/api/v1/prompt/rollback` | 回滚提示词版本 | **否** |
| GET | `/api/v1/prompt/config/agents` | 智能体清单 | **否** |
| GET | `/health/live` | 服务存活检查 | 否 |
| GET | `/health/ready` | 服务就绪检查（含数据库连通性） | 否 |
| GET | `/` | 服务信息 | 否 |

> **风险提示**：`/api/v1/prompt/*` 三个接口目前**没有鉴权**，其中
> `GET /prompt/templates/{agent}/{scene}` 会返回模板正文全文。前端不调用它们，
> 属于内部管理接口，但公网可匿名访问。已记为待办 **T10.8**。
>
> 另外注意：`GET /api/v1/interviews/{id}/evaluations` 在**没生成过复盘**时返回的是
> `200 + evaluation: null`，**不是 404**——前端全局拦截器对 404 会弹"资源不存在"，
> 这条约定是刻意保留的。

## 索引是怎么生成的

上面这张表不是手抄的，是从 FastAPI 的 OpenAPI 里导出的：

```bash
cd interpace-backend
uv run python -c "
from app.main import app
for path, ops in sorted(app.openapi()['paths'].items()):
    for method in ops:
        print(method.upper(), path)
"
```

新增接口后请重新导出核对，并同步更新本表。

## 模块详细文档

- [会话与对话](./会话与对话.md)（含 SSE 与语音 WebSocket 协议）
- [笔记](./笔记.md)
- [面试记录与复盘](./面试与复盘.md)
- [题库、简历导出、检索、资源与上传](./学习与素材.md)
- [画像、长期记忆、用户与鉴权、提示词管理](./画像与记忆.md)
