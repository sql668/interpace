# 待办事项

本文档是项目剩余工作的唯一清单，按阶段推进。每个任务都要能单独交付、单独验收；跨阶段的强依赖会写在任务的「依赖」里。

## 0. 使用约定

- **编号**：`T<阶段>.<序号>`，例如 `T1.3`。新增任务追加在本阶段末尾，不重排既有编号。
- **状态**：`待办` / `进行中` / `已完成` / `已搁置`。
- **粒度**：单个任务原则上控制在半天到两天；预计超过两天的，必须再拆一层。拆不动说明需求还没想清楚，先补到第 15 节「待确认的产品/技术决策」。
- **完成标准**：每个任务都有「验收」，验收没跑通不算完成。
- **验证命令**：前端 `cd interpace-frontend && pnpm run build`；后端 `cd interpace-backend && pytest`。跑不动或跑不过要如实写明原因，不能含糊带过。
- **接口类任务**：按根 `AGENTS.md` 要求，同时改三处——后端路由与 Pydantic 模型、前端 `src/api/` 与类型定义、`docs/` 下的接口文档。
- **改动纪律**：只改与当前任务相关的文件，不顺手重构、不格式化无关文件、不擅自引入新依赖。

## 1. 总览

### 1.1 阶段一览

| 阶段 | 主题 | 任务数 | 依赖 | 主要产出 |
| --- | --- | --- | --- | --- |
| 0 | 地基与一致性修正 | 7 | — | 测试能跑、口径统一、已知小 bug 修掉 |
| 1 | 模式路由打通 | 10 | 阶段 0 | 「选模式 → 不同 Agent 回答」跑通 |
| 2 | 笔记模块持久化 | 7 | 阶段 1 | 笔记落库 + 一键存入 |
| 3 | 通用附件与文件解析 | 7 | 阶段 1 | 文件内容能进对话上下文（轻量解析 + 多模态读扫描件） |
| 4 | 学习模块 · 知识精讲 | 4 | 阶段 1 | 知识精讲链路跑通 |
| 5 | 学习模块 · 刷题评测 | 9 | 阶段 1、3 | 出题 → 答题 → 评分闭环 |
| 6 | 面试模块 · 简历优化 | 6 | 阶段 3 | 简历解析 + 优化 + 导出 |
| 7 | 面试模块 · 模拟面试 | 10 | 阶段 1、3、6 | 语音面试 + 问答落库（含可选的面试官形象） |
| 8 | 面试模块 · 面试复盘 | 5 | 阶段 7 | 复盘生成 + 跨模块联动 |
| 9 | 长期记忆（越用越好用） | 17 | 阶段 1；部分依赖 5 / 6 / 8 | 持久事实 + 程序性技能 + 会话检索 |
| 10 | 收尾 | 7 | 各阶段 | 接口文档、版本前缀、性能 |
| 11 | Docker 化与部署上线 | 9 | 阶段 0；建议在阶段 8 之后上线前做 | 可复现镜像 + 编排 + 上线检查清单 |
| 12 | 多环境配置与演示环境限制 | 9 | 阶段 11（部署形态）、阶段 10（配置基线） | 开发/演示/测试/正式四套配置 + 演示环境防滥用（配额、熔断、重置） |

### 1.2 里程碑

每个里程碑做完就停下来确认一次，不要一口气推到底。

- **M1 = 阶段 0 + 1**：学习室和面试间能选择模式，由不同 Agent 和提示词回答；构建与测试可跑。这是最小可验证能力，风险最低、收益最大。
- **M2 = 阶段 2 + 3**：笔记能落库并「一键存入」；上传的文件能进入对话上下文。这两项是后面所有模块的公共出口和公共入口。
- **M3 = 阶段 4 + 5**：学习模块闭环（知识精讲 + 刷题评测）。
- **M4 = 阶段 6 + 7 + 8**：面试模块闭环（简历优化 + 模拟面试 + 面试复盘）。语音是这里最大的不确定性，先做 T7.1 选型。
- **M5 = 阶段 9**：长期记忆落地，实现「越用越好用」。其中 L1 的画像部分（T9.2~T9.9）不依赖业务模块，可以在阶段 1 完成后就并行开工，不必等到阶段 8 做完；L3 的选型（T9.13）也可并行。
- **M6 = 阶段 10**：上线前收尾。
- **M7 = 阶段 11**：Docker 化 + 部署到腾讯轻量云 2核2G，并跑通上线冒烟清单。这一阶段不依赖阶段 6~10 的代码，**想提前验证部署随时可以插队**；但正式上线建议排在阶段 8 之后，避免上线的是什么还没做完的东西。
- **M8 = 阶段 12**：多环境配置落地 + 演示环境防滥用。给别人尝鲜**必须先把配额和熔断做上**再去推广，否则等于把自己的模型额度公开挂出去。

### 1.3 现状与本清单的对应关系

已完成、不在本清单范围内的能力（详见代码）：用户注册登录与 JWT 双令牌刷新、用户 CRUD、会话增删改查与级联删除、消息分页查询、SSE 流式对话、提示词模板表与回滚接口、用户画像表与注入逻辑、MinIO 上传与去重、前端三个房间页面与流式打字机渲染。

两张流程图（`docs/流程图/学习模块.drawio`、`docs/流程图/面试模块.drawio`）里的「模式分支」目前前后端都不存在，这是阶段 1 要解决的核心问题。

长期记忆的现状（2026-09-29 更新）：`user_profiles` 的五个字段已经有**两条写入路径**——刷题评分写回 `weak_topics`（T5.8）、简历抽取经用户确认后写入（T6.2），并且能通过 `build_personalized_prompt` 注入提示词；但**还没有「查看 / 编辑自己画像」的界面**（T9.4 要解决），画像也还没有掌握程度、来源与置信度这些明细结构。`app/agent/memory.py` 里的 `get_latest_knowledge` 走的是 DuckDuckGo 外网检索，跟用户记忆无关；项目里没有任何向量存储或 embedding 依赖。也就是说现在只有「最近 10 条消息」的临时上下文加一份粗粒度画像，没有完整的长期记忆。这是阶段 9 要解决的问题。

---

## 2. 阶段 0：地基与一致性修正

本阶段不新增功能，只把已知的坑填掉，为后面所有阶段省事。

### T0.1 修复后端 smoke 测试的鉴权断言

- **状态**：已完成（2026-09-29）
- **优先级**：高
- **现状**：`/users` 路由已挂 `get_current_user`，但 `tests/test_smoke.py` 仍按匿名访问断言 `200`/`201`，导致 3 个用例必失败。这部分失败与数据库无关，是真实的用例过时。
- **做法**：抽出 `register_and_login` 辅助函数（注册 + 登录取 `access_token`），`/users` 与 `/upload` 相关用例统一复用它带 `Authorization` 头请求；另外补了一条「匿名访问 `/users` 返回 401」的断言，防止这个回归再次出现。
- **涉及文件**：`interpace-backend/tests/test_smoke.py`
- **验收**：`pytest` 全绿 —— 实测 **5 passed**（本机 MySQL 可连，之前沙箱内的连接失败是网络限制，不是环境缺失）。

### T0.2 前端接口地址统一从 `@/config/env` 读取

- **状态**：已完成（2026-09-29）
- **现状**：`src/config/env.ts` 已经是统一出口，但 `api/http.ts`、`api/streamChat.ts`、`components/layout/AppHeader.vue` 仍直接读 `import.meta.env`，绕过了统一出口。
- **做法**：三处改走 `env.apiBaseUrl`；`streamChat.ts` 里 `|| '/api'` 的隐式兜底删掉，缺变量时直接报错，语义更明确。
- **涉及文件**：`interpace-frontend/src/api/http.ts`、`src/api/streamChat.ts`、`src/components/layout/AppHeader.vue`
- **验收结果**：`pnpm run build` 通过。`rg "import.meta.env" interpace-frontend/src` 现在只剩 `config/env.ts` 自己那三处，业务代码不再绕过统一出口。

### T0.3 对齐环境变量与版本前缀的口径

- **状态**：已完成（2026-09-29）
- **现状**：`interpace-frontend/.env.example` 写的是 `VITE_API_BASE_URL=/api/v1`，实际 `.env.development` / `.env.production` 是 `/api`；后端路由本身不带前缀，靠 `vite.config.ts` 的 `rewrite` 剥掉 `/api`。三处描述互相矛盾。
- **做法**：本次只统一**文档与注释口径**，把「后端路由不带前缀 + 前端用 `/api` + 代理剥离」这一事实写清楚。真正的 `/api/v1` 前缀统一放到 T10.1，不在这里做。
- **涉及文件**：`interpace-frontend/.env.example`、`interpace-frontend/vite.config.ts`（注释）、根 `AGENTS.md`（如需补充说明）
- **实际改动**：`.env.example` 的 `VITE_API_BASE_URL` 从 `/api/v1` 改为 `/api` 并注明原因；`vite.config.ts` 的代理注释补上「T10.1 之后不再需要 rewrite」；根 `AGENTS.md` 的「接口路径统一带版本前缀」下面加了一条**现状提醒**，明确说明这条尚未落实。
- **验收结果**：三处口径一致，不再有 `/api/v1` 的错误示例。

### T0.4 修复注册时的头像上传链路

- **状态**：已完成（2026-09-29，浏览器实机验证待补）
- **优先级**：低（不阻塞其他任务）
- **现状**：前端 `LoginCard.vue` 读 `res.avatar_url`，但后端 `UploadResponse` 只返回 `file_path`；且上传时没有传 `upload_purpose=1`，后端不会回写 `users.avatar`。也就是说注册时选的头像实际不会生效。
- **做法**：前端上传时带 `upload_purpose=1` 并改读 `file_path`；确认后端 `UPLOAD_PURPOSE_AVATAR` 分支确实写回 `users.avatar`，若没有则补上。
- **涉及文件**：`interpace-frontend/src/api/upload.ts`、`src/components/LoginCard.vue`、`interpace-backend/app/services/upload_service_minio.py`
- **实际改动**：`api/upload.ts` 补 `upload_purpose=1`，并**额外补了 `storage_scene=3`（永久存储）**——默认的 0 是「长过期」（30 天），到期会被资源清理服务回收，头像对象就没了；返回类型改为与后端 `UploadResponse` 对齐；`LoginCard.vue` 改读 `res.file_path`。后端 `UPLOAD_PURPOSE_AVATAR` 分支本来就是对的（`upload_service_minio.py:143`、`:276`），无需改动。
- **验收结果（数据链路，已通过）**：新增 `test_avatar_upload_writes_user_avatar`——以头像用途上传图片后，`GET /users/{id}` 返回的 `avatar` 等于上传接口返回的 `file_path`，且 `expire_time` 为 `null`。`pytest` **29 passed**。
- **验收结果（显示）**：**已解决（2026-09-29）**。原先的断点是：后端存的是 `minio://bucket/object_key`，而 `AppHeader` 拼的是 `${apiBaseUrl}/${avatar}`（等于 `/api/minio://...`），必然 404；后端当时也没有任何取图能力。
  - 这个断点在 T3.4 里被一并解决了——新增资源内容接口 `GET /resources/{resource_id}/content`。
  - 但头像不能直接用那个接口：`users.avatar` 存的是**路径**不是资源 ID。所以给资源接口**补了第二种寻址方式** `GET /resources/content?storage_path=...`（查找同样按当前用户过滤，读不到别人的资源）。
  - 前端（`AppHeader.vue`）改为用 axios 取成 Blob → `URL.createObjectURL` 渲染——因为资源接口需要 `Authorization` 头，而 `<img src>` 带不了。切换用户或卸载时释放 object URL；取不到就回退默认头像。
  - 顺带把头像的兜底图从第三方地址（`cube.elemecdn.com`）换成本地 `assets/image/logo.png`，去掉一个外部依赖。
- **验收结果**：`pytest` **49 passed**——上传头像后 `GET /users/{id}` 的 `avatar` 等于上传返回的 `file_path`，再用这条路径请求 `/resources/content` 能取回**与上传逐字节一致**的图片、content-type 正确；他人的路径返回 404。
- **未验证**：**浏览器实机**——头像是否真的显示出来，需要真人看一眼。

### T0.5 清理前端死代码与失实注释

- **状态**：已完成（2026-09-29）
- **现状**：`src/composables/useRoomShell.ts` 是早期 mock 版本，现在只有 `tabs` 常量被三个页面使用，其余函数体是死代码；`AppHeader.vue` 的注释写「`clearTokens()` 会自动调用 `userStore.clearUser()`」，实际不会。
- **做法**：把导航常量收缩成单一职责的模块（可移到 `src/constants/`，同步三个页面的 import）；登出改为显式清理 store，注释与实现对齐。
- **实际改动**：新增 `src/constants/nav-tabs.ts`（`NavTab` 类型 + `tabs`），三个房间页改从这里导入；**删除** `composables/useRoomShell.ts`；`AppHeader.vue` 登出改为 `userStore.clearUser()`（内部会清 token 并跳登录页），同时删掉随之不再使用的 `useRouter` / `clearTokens` 导入和文件内重复定义的 `NavTab`。
- **验收结果**：`pnpm run build` 通过；`rg "useRoomShell" interpace-frontend/src` 已无代码引用。**登出后换账号头部不串号这条没有实测**（需要浏览器），但改动方向是明确的：原来只清 token、store 里的 `profile` 留着，现在两者都清。
- **注意**：不要顺手改 `SideBar` / `HistoryList` 的 props 与事件接口。

### T0.6 后端日志规范清理

- **状态**：已完成（2026-09-29）
- **现状**：`app/services/prompt_template_service.py` 的 `rollback_prompt_version` 用 `print` 输出（违反 `AGENTS.md` 的 logging 要求）；`get_next_version` 里写了 `db.func.max(...)`，Session 对象上没有 `func`，一旦被调用就会报错（当时无人调用，所以没暴露）。
- **做法**：三处 `print` 改为 `main_logger.info`；`db.func.max` 改为 `sqlalchemy` 的 `func.max`。业务逻辑未动。
- **涉及文件**：`interpace-backend/app/services/prompt_template_service.py`
- **验收**：`pytest` **5 passed**；`get_next_version` 实测可用（对空表返回 1）。修复前该调用必抛 `AttributeError`——已确认 `hasattr(Session, "func")` 为 `False`。
- **说明**：`ruff` 未安装、也不在 `pyproject.toml` 依赖中，所以「无新增告警」这条没跑成，属工具缺失。

### T0.7 清理其余 print 输出

- **状态**：已完成（2026-09-29）
- **来源**：执行 T0.6 时发现，违规的 `print` 不止那三处。
- **现状**：`app/utils/prompt_logger.py` 有 15 处 `print`（`log_personalized_prompt_generated`、`log_chain_ready`、`log_redis_status`），`app/core/settings.py:31` 还有 1 处。其中 `log_personalized_prompt_generated` 会把**完整提示词正文**打到标准输出，每次流式对话都触发——既是日志噪音，也意味着用户画像等数据会未经管理地进 stdout。
- **做法**：统一改走 `main_logger`；提示词正文降到 `DEBUG` 级别，避免生产环境默认打印全文。
- **涉及文件**：`interpace-backend/app/utils/prompt_logger.py`、`interpace-backend/app/core/settings.py`
- **实际改动**：`prompt_logger.py` 三个函数全部改走 `main_logger`，正文单独走 `DEBUG`；`settings.py` 那处改用 loguru 的 `logger`（不能直接用 `main_logger`——`logging_config` 依赖 `settings`，反向导入会成环），并在注释里说明。
- **验收结果**：`rg "print\(" interpace-backend/app` **无结果**（`scripts/` 下的 `print` 是 CLI 给运维看的输出，保留合理）；`pytest` 29 passed。
  - 关于「默认日志级别下不再出现提示词正文」，落地后核对发现要分环境说：**生产环境 console 级别是 WARNING**，正文不再出现；**开发环境 console 级别本来就是 DEBUG**，正文仍会在控制台显示——这是刻意的，方便调提示词。日志文件级别是 WARNING，所以正文**从不写进 `app.log`**。
- **依赖**：无。

---

## 3. 阶段 1：模式路由打通（核心主线）

两张流程图的所有分支都挂在「用户是否选择了模式」这个判断上。现状是前端不传模式（`selectModel` 恒为 0）、后端不认模式（`agent_name` / `scene` 是写死默认值），所以这个阶段是后面所有阶段的前置条件。

**技术选型约束**：按根 `AGENTS.md` 的「AI / 智能体开发」规则，本阶段的编排层统一用 LangGraph、模型与提示词用 LangChain，不手写编排循环。**已确认统一改走 LangGraph 基座**（原 D15）：由 T1.0 做等价改造，T1.2 起所有场景都在图上跑。现状 `app/agent/prompt_layer.py` 是 LangChain 单链（`RunnableWithMessageHistory`），`langgraph 1.2.11` 虽已声明但全项目未使用。

**本阶段执行顺序**：先做 T1.0（编排基座）与 T1.1（模式注册表），两者无依赖、可并行；T1.2 依赖这两者，其余任务依次向后。

### T1.0 搭建 LangGraph 单节点编排基座

- **状态**：已完成（2026-09-29）
- **目标**：把现有的 LangChain 单链包成一张 LangGraph 单节点图，**行为完全等价**，为后续多轮场景留出编排空间。
- **做法**：已用最小样例实测可行，要点如下。
  - 图用 `StateGraph`，只有一个节点，节点体直接复用现有的 `prompt | model` 链——写 `chain.invoke(...)` 即可，不需要改写成异步或流式节点，LangGraph 的 `stream_mode="messages"` 会从模型回调里抽出 token 流。
  - 流式改为 `graph.stream(inputs, stream_mode="messages")`，返回 `(chunk, metadata)`；`chunk` 仍是 `AIMessageChunk`，所以 `_extract_text_delta` 不用改。
  - 顺带去掉 `RunnableWithMessageHistory`：它的 `history_store` 是函数内当场新建的局部字典，实际没有记忆作用，只是把数据库读出的历史注入了一遍。图里直接把消息放进 state 更直白。
  - SSE 的 `start` / `delta` / `done` / `error` 四种事件格式**保持不变**，前端零改动。
- **实际改动**：`app/agent/prompt_layer.py`（`build_stream_chain_context` → `build_stream_graph`，新增 `ChatGraphState`）、`app/services/stream_chat_service.py`、`app/agent/__init__.py`（导出名同步）。顺带删掉了 `prompt_layer.py` 里未被使用的 `import re`。
- **不做**：不加第二个节点、不引入 checkpointer、不改多轮逻辑。这一版只要等价。
- **验收结果**：
  - **真实 DeepSeek**（`DEEPSEEK_API_KEY` 已配置，按验收要求优先用它）：单次运行内「流式 delta 拼接」与「节点终态文本」逐字一致（`你叫张三。`），说明 `stream_mode="messages"` 既不丢字也不重复；历史注入生效——把「记住：我的名字是张三」放进上一轮，模型正确答出「你叫张三。」。
  - **`GenericFakeChatModel`** + 同一份 2 条历史：改造前后 delta 序列完全一致，都是 `'你好，这是流式输出'`。
  - **端到端 SSE**：`start → delta → done` 帧格式不变，`chat_messages.select_model` 与 `response_text` 落库正确。
  - `pytest` **6 passed**，新增 `tests/test_stream_graph.py` 把等价性与输入契约固化下来。
- **附带收益**：`stream_mode="messages"` 的 metadata 里带 `langgraph_node`（实测值为 `chat`），后续多节点场景可以据此区分文本由哪个节点产出。另外改造前跑任何一次都会报 `RunnableWithMessageHistory is deprecated. Use LangGraph's built-in persistence instead.`，改造后这个告警消失。
- **依赖**：无（可与 T1.1 并行）。

### T1.1 后端新增「模式注册表」常量模块

- **状态**：已完成（2026-09-29）
- **目标**：把 `select_model` 到 `agent_name` / `scene` 的映射收敛成一份配置，避免散落在路由和服务里。
- **做法**：新增 `interpace-backend/app/agent/scene_registry.py`，按 `chat_messages.select_model` 的既有注释定义映射，并提供 `resolve_scene(select_model)`，非法值回退到 0。
- **映射表**：

  | select_model | agent_name | scene | 前端展示 | 适用房间 |
  | --- | --- | --- | --- | --- |
  | 0 | `general_assistant` | `chat` | 快速回答（默认） | 学习室 + 面试间 |
  | 1 | `difficulty_learner` | `study` | 知识精讲 | 学习室 + 面试间 |
  | 2 | `quiz_generate_workflow` | `quiz` | 刷题评测 | 学习室 |
  | 3 | `resume_parser` | `resume` | 简历优化 | 面试间 |
  | 4 | `interview_host` | `interview` | 模拟面试 | 面试间 |
  | 5 | `interview_evaluator` | `evaluation` | 面试复盘 | 面试间 |

- **注意**：
  - `agent_name` 必须与 `prompt_template_service.AGENT_CONFIG` 中的键保持一致，否则提示词永远查不到。其中 `general_assistant` 是新增的键，其余五个已存在。
  - `flow_controller`（workflow）与 `note_archiver`（note）是**内部 agent，不是用户可选模式**，不要登记进注册表。前者留给后续的流程总控，后者对应 T2.6 的「一键存入笔记」。
  - 两个房间的「知识精讲」共用 `select_model=1`，靠会话的 `session_model` 区分落库归属。
  - 默认模式（`select_model=0`）在两个房间共用同一套模板。如果以后发现「学习室答疑」和「面试间给参考回答」确实需要区分，加一个 scene 值即可，不动表结构。
- **实际改动**：新增 `app/agent/scene_registry.py`（`SceneSpec` + `SCENE_SPECS` + `resolve_scene`）；`app/services/prompt_template_service.py` 的 `AGENT_CONFIG` 补了 `general_assistant`（不补的话「注册表里的 agent 必须在 AGENT_CONFIG 中」这条不变量就不成立）；新增 `tests/test_scene_registry.py`。
- **与计划的偏差**：`resolve_scene` 返回 `SceneSpec` 冻结数据类，而不是任务里写的 3 元组——三个字段（`agent_name` / `scene` / `label`）与计划一致，但数据类更自解释，后续要加字段也不用改调用签名。
- **验收结果**：`pytest` **20 passed**（本任务新增 14 个用例）。覆盖全部合法取值的映射、非法值与 `None` 回退、键集合不多不少，以及三条不变量——agent_name 必须存在于 `AGENT_CONFIG`、内部 agent（`flow_controller` / `note_archiver`）不得登记、每个模式的 `(agent_name, scene)` 必须唯一。新用例不依赖数据库，纯沙箱即可运行。
- **依赖**：无。这是纯新增模块，不改任何现有行为（`AGENT_CONFIG` 多一个键只影响 `/prompt/config/agents` 的列表输出）。

### T1.2 后端 stream-chat 按 select_model 解析 agent/scene

- **状态**：已完成（2026-09-29）
- **现状**：`POST /sessions/{id}/stream-chat` 的 `agent_name` / `scene` 是 query 参数，默认写死 `interview_host` / `interview`，与 `select_model` 完全无关。也就是说学习室的默认对话现在走的也是面试场景的 Agent。
- **做法**：把 `agent_name` / `scene` 改成可选 query（显式传了优先，保持向后兼容），没传时查 T1.1 的注册表；同时把解析结果打进日志，便于联调核对。
- **编排方式**：走 T1.0 建立的 LangGraph 基座，本阶段所有场景都还是单节点图；多节点编排留给阶段 5、7、8，那时直接往图里加节点，不另起一套。
- **实际改动**：`app/routes/session_routes.py`（两个 query 参数改为可选并注明优先级）、`app/services/stream_chat_service.py`（引入 `resolve_scene`，解析结果既进日志也用于提示词构建与链路日志）、新增 `tests/test_stream_chat_routing.py`。
- **接口变更**：是（query 参数默认值语义变化，不破坏现有调用方式）。
- **验收结果**：`pytest` **21 passed**（本任务新增 1 个）。用例覆盖三条——不传 agent/scene 时按 `select_model` 解析（`0 → general_assistant/chat`、`1 → difficulty_learner/study`）、显式传入时以传入值优先、三条消息的 `select_model` 按 `0/1/1` 正确落库。另查了 OpenAPI：`agent_name` / `scene` 已由必填变为可选（`required=false`，类型 `string | null`），`session_model` 仍必填。
- **依赖**：T1.0、T1.1。

### T1.3 后端为各场景预置提示词模板（seed）

- **状态**：已完成（2026-09-29）
- **现状**：`prompt_templates` 表里没有任何数据（全项目没有任何 `PromptTemplate(...)` 写入点），`get_full_prompt` 永远返回 `None`，个性化提示词一直走兜底默认值。这是「每个模式回答都一样」的直接原因之一。
- **落地方式（已定，原 D1）**：独立的可重复执行脚本 `scripts/seed_prompt_templates.py`，写法对齐已有的 `scripts/insert_sample_records.py`（`PROJECT_ROOT` 入 `sys.path` → `SessionLocal` → 写库 → 打印结果）。**不用 Alembic**（理由见 T10.7），**不在启动时自动 seed**。
- **幂等策略**：
  - `(agent_name, scene)` 完全没有记录 → 插入 v1 且 `is_active=1`；
  - 已有记录 → 跳过，不新增版本、不动 `is_active`，保护线上调优过的版本；
  - 需要强制更新时走 `--force` 显式传参，默认不生效。
- **为什么不启动时自动 seed**：`prompt_templates` 有 `version` + `is_active`，且已有版本回滚功能会翻转 `is_active`。启动时自动写入会让「重启」变成「可能冲掉运营调好的 active 版本」的事件，多实例部署还会并发写。
- **做法**：先只 seed 本阶段需要的内容（`study` 场景公共模板 + `difficulty_learner` 私有模板），其余场景在各自阶段随任务补。
- **顺带修复**：`load_all_effective_to_redis` 的 docstring 写的是「启动时加载」，但全项目只在 `rollback_prompt_version` 里调用过，Redis 缓存 `prompt:templates:active` 一直是空的，每次查模板都走数据库兜底。seed 完成后需要把缓存捂热——在 seed 脚本里调用，或明确改成惰性缓存并把注释改对，本任务一并处理。
- **实际改动**：逻辑按根 `AGENTS.md`「业务逻辑和入口分离」拆成两层——
  - 新增 `app/services/prompt_template_seed_service.py`：模板正文（`study` 公共模板 + `difficulty_learner` 私有模板）、`SEED_TEMPLATES` 清单、`seed_prompt_templates(db, force)`（只写不提交，事务交给调用方）；
  - 新增 `scripts/seed_prompt_templates.py`：只做 CLI 入口——解析 `--force`、开事务、提交、然后调用 `load_all_effective_to_redis` 把缓存捂热（顺带修掉「缓存从来没被预热」那个问题）；
  - 新增 `tests/test_prompt_template_seed.py`。
- **验收结果**：`pytest` **25 passed**（本任务新增 4 个）。
  - 脚本真实执行：首次输出「写入 v1」，再执行一次输出「跳过，已有 1 个版本，最新 v1」——重复执行不产生重复数据、不动 `is_active`。
  - `build_personalized_prompt(db, 0, "difficulty_learner", "study")` 返回非 `None`（长度 634），且不含未替换的占位符；把该提示词送进 T1.0 的编排图能正常出词，没有 `ChatPromptTemplate` 的 `KeyError`。
- **备注**：按计划本任务只 seed 了 `study` 场景，**默认模式（`select_model=0`）仍然走兜底提示词**。要让 M1 的「换模式，回答真的不一样」更明显，在 `SEED_TEMPLATES` 里追加一条 `agent_name=None, scene="chat"` 的公共模板再跑一次脚本即可。
- **后续补齐（2026-09-29，由真机问题触发）**：**这个「备注」当时没人跟，一直拖到真机出问题才补上。** 用户反馈「第一轮中文对答，我回了个 `a[:]`，回复里中英文都有」（截图 `docs/img_1.png`）——根因就是默认模式 `scene=chat` **一条模板都没有**（查库确认 `scene=chat` 模板数为 0），一直跑代码里那句兜底提示词「你是一个简洁、可靠的单Agent助手……」，**没有任何语言与输出纪律约束**，模型于是把英文的内心思考、自我纠正、重复段落都写进了回复（例如「That's two questions in one… Hmm, I wrote it twice.」）。
  - 补了两条模板：`(None, "chat")` 公共模板（两个房间的快速回答共用，含语言要求与画像注入）+ `(general_assistant, "chat")` 私有模板（**输出纪律**：不吐思考过程/自我纠正/英文推理、不重复、不整句英文、输入像误触时先问清）。
  - 面试官模板也补了同款纪律——它的输出**会被 TTS 念出来**，英文独白对用户是纯噪音。
  - **回归防线**：新增 `test_every_routable_scene_has_a_seeded_template()`，遍历 `SCENE_SPECS` 断言每个可路由场景都有私有模板。这类「少了东西」的故障不会报错、只会静默降级，必须靠测试盯着。
  - **验证**：真实模型复现用户场景（第一轮中文问答 → 回 `a[:]`）**合规 3/3**（无元评论、无英文独白、无重复段落），回复直接给出 `a[:]` 是浅拷贝的解释与代码示例。
- **注意（给以后写模板的人）**：模板正文最终会交给 `ChatPromptTemplate` 当作文本模板解析，所以**正文里不能出现裸露的花括号**（例如 JSON 示例、`{key: value}` 这类写法），否则会在构造或调用提示词时抛 `KeyError`。测试 `test_seed_templates_have_no_unresolved_braces` 会拦这个，写新模板后跑一次 pytest 即可。
- **依赖**：T1.1。

### T1.4 前端新增模式的常量与类型定义

- **状态**：已完成（2026-09-29）
- **做法**：新增 `src/constants/chat-modes.ts`，导出 `ChatMode` 类型、`DEFAULT_CHAT_MODE` 与两个列表，取值与 T1.1 的注册表一一对应：`STUDY_MODES`（快速回答 `0` / 知识精讲 `1` / 刷题评测 `2`）、`INTERVIEW_MODES`（快速回答 `0` / 简历优化 `3` / 模拟面试 `4` / 面试复盘 `5` / 知识精讲 `1`）。
- **与计划的偏差**：任务原文写的文件名是 `chatModes.ts`，实际用了 `chat-modes.ts`——前端 `AGENTS.md` 规定「组件文件用 `PascalCase.vue`，其他文件用 `kebab-case.ts`」，按规则走。（顺带记录：现有的 `api/streamChat.ts`、`composables/useRoomShell.ts`、`utils/typewriterStream.ts`、`utils/markdownUtil.ts` 也是驼峰命名，与规则不符，但不在本任务范围内，没有改动。）
- **注意**：「知识精讲」在两个房间共用 `select_model=1`，两个列表里它指向同一个值，差异只体现在会话的 `session_model` 上。
- **验收结果**：`pnpm run build` 通过。此时还没有组件引用这个文件，所以产物哈希没有变化（被 tree-shake 掉），但 `vue-tsc` 的类型检查覆盖到了它。

### T1.5 前端新增模式选择 UI（只做展示与选中）

- **状态**：已完成（2026-09-29）
- **做法**：新增 `src/components/chat/ModeSelector.vue`（`ChatInput.vue` 原本 124 行，按前端规则拆出的子组件），在输入框上方渲染模式按钮，标准 `v-model` 双向绑定；`ChatInput` 新增 `modes` / `mode` 两个 props 与 `update:mode` 事件并透传。
- **实际改动**：新增 `src/components/chat/ModeSelector.vue`；`src/components/chat/ChatInput.vue`——`modes` 默认空数组、`mode` 默认 `DEFAULT_CHAT_MODE`，并把 `.chat-input` 从横向 flex 改为纵向 flex（`flex-direction: column; align-items: center`）。后者是为了把模式按钮放到输入框上方，横向居中行为与原来一致，`__actions` 仍是绝对定位、锚在容器底部。
- **注意**：这一步只做 UI，不接发送逻辑，避免一次改太多。
- **与计划的偏差**：`modes` 走默认空数组，所以在 T1.6 接线之前**界面不会出现模式按钮**——这样不会留下「按钮看得见、点了却没反应」的中间态。代价是本任务没有肉眼可见的产物，只能靠构建验证。
- **验收结果**：`pnpm run build` 通过，产物哈希由 `index-DLT7rbX8.js` 变为 `index-BN9nSPqy.js`，说明 `ModeSelector` 确实被打进包里（不再是 tree-shake 掉）。**浏览器实机验证已补做**（见 T1.6 的验收结果）：模式按钮居中渲染在输入框上方，输入框与左右两个圆形按钮位置都正常，`.chat-input` 改纵向 flex 没有造成跑偏。

### T1.6 前端把选中模式透传到 stream-chat

- **状态**：已完成（2026-09-29）
- **做法**：把 `selectModel` 从 `ChatInput` → `ChatWindow` → 各 Room → `useSessionStreamSender` → `api/streamChat.ts` 一路传下去。`useSessionStreamSender` 的 `send` 需要带上模式参数（或由 `createPending` 一并记录）。
- **实际改动**：`ChatWindow.vue` 新增 `modes` / `mode` 两个必填 props 与 `update:mode` 事件并透传给 `ChatInput`；`useSessionStreamSender.ts` 的 `send` 增加 `selectModel` 参数（默认 `DEFAULT_CHAT_MODE`）并传给 `streamChat`；`StudyRoom.vue` / `InterviewRoom.vue` 各自新增 `selectedMode` ref，用 `v-model:mode` 双向绑定、发送时 `send(text, selectedMode.value)`。
- **`api/streamChat.ts` 没改**：它在之前就已经接收 `selectModel` 并发出 `select_model`（`options.selectModel ?? 0`），本任务只是把上游接上，所以任务里列的这处涉及文件实际不需要改动。
- **补充说明**：切换会话不会重置模式选择，保持在当前房间内选中的值。
- **验收结果（部分）**：`pnpm run build` 通过，`vue-tsc` 对整条 props / emits 链做了类型检查。逐段核对了链路：房间 `v-model:mode` / `:modes` → `ChatWindow` `:mode` / `:modes` / `@update:mode` → `ChatInput` → `ModeSelector`；发送侧 `send(text, selectedMode.value)` → `streamChat({ selectModel })` → 请求体 `select_model`。
- **验收结果（浏览器实机，2026-09-29 已补做）**：在 Chrome 里对 `localhost:5173` 的面试间做了完整走查——
  - 模式按钮正确渲染，默认「快速回答」高亮；发送中所有模式按钮变灰禁用，回答结束后恢复；
  - 点「知识精讲」→ 输入「什么是索引覆盖？」→ 发送，回答的小节序列是**一句话回答 / 原理 / 示例 / 面试怎么答 / 常见追问 / 本节要点**，与 T1.3 seed 的 `DIFFICULTY_LEARNER_TEMPLATE` 完全一致，说明 `select_model=1` 确实穿过整条链路并在后端路由到 `difficulty_learner` / `study`；
  - 刷新页面后消息与模式标签都能从接口重新渲染出来。
  **这一步把 M1 闭环了。** 验证用的会话是已有的「面试测试1」，我在里面留下了一条测试消息（`什么是索引覆盖？`），需要的话可以删掉。
- **依赖**：T1.2、T1.5。

### T1.7 前端消息气泡展示所属模式

- **状态**：已完成（2026-09-29）
- **做法**：前端 `UiMessage` 增加 `selectModel` 字段，`mapRecordsToUiMessages` 从消息记录取值。后端 `ChatMessageItem` 目前没有返回 `select_model`，需要先补上。
- **实际改动**：后端 `app/schemas/chat_schemas.py` 的 `ChatMessageItem` 新增 `select_model`，`app/services/chat_service.py` 组装时带上该字段；前端 `src/types/chat.ts` 的 `SessionRecord` 新增 `select_model`、`UiMessage` 新增 `selectModel`；`src/constants/chat-modes.ts` 新增 `findChatMode(value)` 供按值反查标签；`src/components/chat/MessageBubble.vue` 在时间戳旁渲染模式标签；两个房间的 `mapRecordsToUiMessages` 带上 `selectModel`。
- **两个实现细节**：
  - 标签**只在助手侧、且模式不是默认值（`select_model=0`）时展示**，否则每条消息都会顶着一个「快速回答」，纯噪音。这条是我自己定的，D3 里没写。
  - `createPending` 里也给占位消息写上了 `selectModel`，否则刚发完的消息要刷新页面才看得到标签。
- **接口变更**：是（`ChatMessageItem` 新增字段）。
- **验收结果**：
  - 后端 `pytest` **25 passed**：`test_stream_chat_routing.py` 扩展了一条断言——`ChatService.get_session_messages` 读回的消息 `select_model` 序列应为 `[0, 1, 1]`，确保不只是落库正确、读出来也带着。
  - 前端 `pnpm run build` 通过。
  - **浏览器实机验证已补做**：标签以胶囊样式显示在时间戳左侧（「知识精讲 13:43:42」）；发送中即时出现，**刷新页面后仍能从接口读回并重新渲染**，说明后端 `select_model` 字段与前端回显都正常。默认模式（`select_model=0`）不发消息时看不出差别，符合预期。
- **待确认**：标签的视觉形式见 D3——本任务按 D3 的建议方案（轻量文字标签、放在时间戳旁边）实现，D3 保留在待确认表里，想换形式直接改 `MessageBubble.vue`。

### T1.8 支持手动停止流式回答

- **状态**：已完成（2026-09-29，含浏览器实机验证）
- **说明**：这是 2026-09-17 记录的原始待办，方案见本文档「附录 A」。
- **采用的默认决策**（原 D14，附录 A.4 里挂着的四个问题）：
  - **停止协议 = 双保险**：「显式停止接口 + 前端断连」，与文档建议一致；
  - **部分内容 = 保留**：不丢弃已生成的内容，用户能看到半截回答；
  - **消息状态 = 新增 `status=2`（用户主动停止）**。落地前查过：`status=1`（面试转写入口）虽然定义了但**全项目没有任何写入点**，属于阶段 7 的事，所以现在加 2 不存在冲突；
  - **面试场景**：当前没有任何面试记录写入，无需处理，等阶段 7 再对齐。
- **实际改动（后端）**：新增 `app/services/stream_cancel_service.py`（线程安全的进程内停止登记表，LRU 上限 1 万条）；`stream_chat_service.py` 的生成器改为逐块轮询取消标志、命中即 `break`，并在 `finally` 里 `close()` 模型流以立刻释放底层连接，同时把已生成文本回写、状态置 2；新增 `StreamChatService.stop_stream`（做消息归属校验，越权/不存在抛 404）；新增 `POST /sessions/{session_id}/stream-chat/stop` 路由与配套 Pydantic 模型；`done` 事件增加 `stopped` 字段；`db/models.py` 的 status 注释补上取值 2。
- **实际改动（前端）**：`api/streamChat.ts` 支持 `AbortSignal` 并把 `stopped` 加进事件类型；`api/chat.ts` 新增 `stopStreamChat`；`useSessionStreamSender.ts` 改为真正中断——记录 `start` 事件返回的 `message_id`，停止时先调停止接口再 `abort()`；`ChatInput.vue` 生成中把发送按钮换成带中文文案的「停止」按钮（胶囊样式，不受 `disabled` 影响），`ChatWindow` 与两个房间透传 `sending` 与 `stop` 事件。
- **验收结果（后端，已验证）**：`pytest` **27 passed**，其中 `tests/test_stream_stop.py` 新增 2 个用例——读到第一块增量后停止：确认不再产出后续 delta、事件流以 `done` 收尾且 `stopped=true`、部分文本被保留（非空且短于完整回答）、落库 `status=2` 且 `response_text` 等于片段；重复停止返回 `first_request=false`（幂等）；停止不存在的消息抛 404。
- **验收结果（前端，已实测通过 2026-09-29）**：`pnpm run build` 通过（整条 props/emits 链有类型检查），随后由你在浏览器里点「停止」实测通过。后端日志也留下了佐证：`[流式停止] 收到停止请求 message_id=109 first_time=True` → `[流式停止] message_id=109 已按用户请求停止`。
- **附带确认**：同一批日志里还有 `[模式路由] select_model=0（快速回答（默认）） -> agent_name=general_assistant scene=chat`——**默认模式的路由映射（T1.1/T1.2）也在真实请求里生效了**，不再是我们之前担心的「学习室默认走面试 Agent」。
- **依赖**：T1.6（需要先确认流式请求的参数结构稳定）。

### T1.9 清理编排图里未被使用的输入（含一次无用外网检索）

- **状态**：已完成（2026-09-29）
- **来源**：执行 T1.0 时发现。
- **现状**：`build_stream_graph` 的输入里有 `local_kb`（硬编码的 Python / Java / 前端三条字符串）和 `search_result`，但代码内置的 `ChatPromptTemplate` 只声明了 `history` 与 `user_input`，这两个变量从来没有进过提示词。更麻烦的是 `search_result` 的值来自 `get_latest_knowledge(request_text)`——**每次流式对话都会打一次 DuckDuckGo 外网检索，然后把结果丢掉**。
- **影响**：每条消息白白增加一次外部网络调用的延迟与失败面，外网抖动会直接拖慢对话。
- **做法（已采用「保留能力、去掉成本」）**：`search_result` 改为**惰性求值**——只有解析出的 `system_prompt` 真的包含 `{search_result}` 时才调用 `get_latest_knowledge`，否则直接给空串；`local_kb` 是常量字典，代价为零，原样保留。
- **为什么不直接删掉**：`get_latest_knowledge` 的最终去留已经排在 T9.15（长期记忆阶段）里决定——要跟用户记忆检索收敛还是共存。现在删会抢跑那个决策，本任务只负责消除「每条消息白跑一次」的成本。
- **注意**：T1.0 为了让改造**严格等价**，故意保留了这两个输入不动，所以这是独立的一步。
- **验收结果**：
  - `pytest` **28 passed**。`tests/test_stream_graph.py` 新增 `test_search_only_runs_when_prompt_references_it`：默认模板不引用 `{search_result}` → 零次调用、`search_result` 为空串；自定义模板引用了 → 恰好调用一次并带上用户问题；`local_kb` 两种情况都在。
  - `rg "get_latest_knowledge" interpace-backend/app` 的结果是「定义保留 + 唯一调用点已加条件」。
  - **收益量化**：实测一次 `get_latest_knowledge("Python 后端 面试")` 耗时 **20.21 秒**，且返回长度为 **0**（没拿到任何有用内容）。也就是说此前**每条消息都要多等约 20 秒**，换来一个随即被丢弃的空结果。这次改动直接把这段延迟去掉了。
- **依赖**：T1.0。

---

## 4. 阶段 2：笔记模块持久化与「一键存入」

流程图里学习、刷题、面试、复盘四条链路都以「存入笔记模块」收口，但后端完全没有笔记存储：没有 `notes` 表，也没有笔记路由。

**动手前先看清现状**：现在这个笔记本不只是「不持久化」，而是**基本不可用**。

- 正文是从该会话的**聊天消息**推导出来的（`mapMessagesToNoteContent`），但笔记本会话（`session_model=2`）永远不会产生消息——没人会在笔记本里对话。所以每条笔记打开都是「当前会话暂无聊天记录，可直接开始记录笔记」。
- 编辑器里的标题与正文只写内存 ref：`updateNoteTitle` / `updateNoteContent` **都没有接口调用**，刷新即丢。而侧边栏的改名是调了接口的——同一个东西两个入口，一个持久化一个不持久化。

**已定的数据模型**：笔记自己当主实体，**不再复用 `sessions`**。新增独立的 `notes` 表，直接以笔记为列表单位；`session_model=2` 这套「笔记本会话」不再使用（枚举值暂时保留，不影响其他模块）。

### T2.1 确定笔记的数据模型

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。决策结论写回本文档，再开始 T2.2。
- **需要定的点**：笔记是否复用 `session_model=2` 的会话作为分组？一条笔记的正文存在哪？
- **结论（选项 C）**：新增独立 `notes` 表，**笔记直接作为列表单位，不关联 `sessions`**。原先建议的「`session_id` 可空 + 会话当分组」被否掉，理由如下。
  - **前端改动更小**：编辑器的前提是「选中一个 → 编辑它」。用 C 选中的就是一条笔记，编辑器逻辑一行不用改；用原方案反而要先补出「分组下的笔记列表」这层界面。
  - **语义不再拧巴**：一个「笔记本分组」根本不是会话，为它保留 `session_model=2` 这个枚举值，还得忍受「这个会话永远没有消息」——现在那段从消息推导正文的逻辑，就是这个拧巴的直接后果。
  - **「一键存入」更直接**：点一下列表里就多一条，用户立刻看得见；不用先想「存到哪个分组」。
  - **代价**：`NotebookRoom` 的会话管理要重写（新建 / 改名 / 删除改成调 notes 接口），`session_model=2` 变成历史遗留。
  - **分组能力没丢**：真需要按主题归类时，给 `notes` 加一个 `group` 字段即可，比现在就搭一层分组轻。

### T2.2 后端新增 notes 表

- **状态**：已完成（2026-09-29）
- **做法**：在 `app/db/models.py` 新增 `Note` 模型。
- **字段建议**：`id`、`user_id`、`title`、`content`（MEDIUMTEXT，存富文本 HTML）、`source_type`（0 手写 / 1 来自对话 / 2 来自复盘）、`source_message_id`（可空，记录这条笔记是从哪条消息来的）、`created_at`、`updated_at`。
- **注意**：按 T2.1 的结论，**不带 `session_id`**。列表按 `updated_at` 倒序更符合笔记的使用习惯（最近改过的排前面）。
- **涉及文件**：`interpace-backend/app/db/models.py`
- **实际改动**：`app/db/models.py` 新增 `Note`；`source_message_id` **故意不加外键**——笔记正文是复制过来的，源消息被删（比如整个会话被删）不该影响用户自己的笔记，所以只留一个可能失效的出处 ID，并在注释里写明是软引用。列表索引 `idx_notes_user_updated (user_id, updated_at)`。
- **验收结果**：`Base.metadata.create_all` 后 `notes` 表存在，字段与索引与设计一致（字段：id / user_id / title / content(MEDIUMTEXT) / source_type / source_message_id / created_at / updated_at；索引：`idx_notes_user_updated`）。此步不含接口，`pytest` **29 passed**。
- **依赖**：T2.1。

### T2.3 后端笔记 CRUD 接口

- **状态**：已完成（2026-09-29）
- **做法**：新增 `app/schemas/note_schemas.py`、`app/services/note_service.py`、`app/routes/note_routes.py`，并在 `main.py` 注册路由。
- **接口设计**：
  - `GET /notes`：分页列表，返回 `{items, total}`，参数 `limit` / `offset`。
  - `POST /notes`：创建，返回 201。
  - `GET /notes/{note_id}`：详情。
  - `PUT /notes/{note_id}`：更新标题与正文。
  - `DELETE /notes/{note_id}`：删除，返回 204。
- **要求**：每个接口都要做归属校验（复用 `get_current_user`），别人的笔记一律 404。
- **接口变更**：是。
- **实际改动**：新增 `app/schemas/note_schemas.py`（`NoteItem` 列表项**不含正文**，`NoteDetail` 才带）、`app/services/note_service.py`、`app/routes/note_routes.py`；`app/schemas/__init__.py` 与 `app/routes/__init__.py` 补导出；`main.py` 挂到 `/notes`。
- **两处实现取舍**：
  - **时间字段沿用 Unix 秒**，没有按 `AGENTS.md` 写的用 ISO 8601 字符串——现有接口（sessions / chat_messages）全是 Unix 秒，只在 notes 上另起一套会让前端处理两种格式。这条约定其实全项目都没落实，已在 schema 文件里注明。
  - **越权一律 404**，不区分「没有这条」和「不是你的」，避免用状态码探测他人数据是否存在。
- **顺带清理**：`async_client` 与「注册+登录取鉴权头」在两个测试文件里各有一份，正好要写第三份，就按「公共方法统一抽离」提到了 `tests/conftest.py`，`test_smoke.py` 改为使用夹具。
- **验收结果**：新增 `tests/test_notes_api.py`，`pytest` **33 passed**（新增 4 个用例，每个路由的正常路径 + 错误路径都覆盖到）。
  - 生命周期：创建 201 → 列表（`total=1` 且列表项不含 `content`）→ 详情 → 只传标题更新时正文不变 → 删除 204 → 再取 404。
  - 隔离：A 的笔记对 B 在读/改/删上均为 404，B 的列表里也看不到；A 自己一切正常。
  - 错误路径：未登录 401；标题为空、`limit=0`、`note_id=0` 均 422。
- **踩到并修掉的一个坑**：加完这 4 个用例后，全套注册次数从 4 次涨到 8 次，**超过了注册接口「每分钟 5 次」的限流**，导致 `test_smoke.py` 里三个用例报 429。修法是给 `app/core/rate_limit.py` 加一个 `reset_rate_limit_windows()`（明确标注主要给测试用），并在 `conftest.py` 里加 autouse 夹具每个用例前清空窗口。连续跑两次都是 33 passed，确认稳定。**这类失败很隐蔽——单独跑某个文件永远是绿的，只有全套跑才炸。**
- **依赖**：T2.2。

### T2.4 前端补齐笔记接口封装与类型

- **状态**：已完成（2026-09-29）
- **做法**：新增 `src/api/note.ts` 与 `src/types/note.ts`，与 T2.3 的 Pydantic 模型对齐。
- **实际改动**：`src/types/note.ts`（`NoteItem` / `NoteDetail` / `NoteListResponse` / `NoteCreatePayload` / `NoteUpdatePayload` / `NoteSourceType`）、`src/api/note.ts`（`getNotes` / `createNote` / `getNoteDetail` / `updateNote` / `deleteNote`，复用 `http.ts` 的 axios 实例，自动带 token 并享受 401 自动刷新）。
- **验收结果**：`pnpm run build` 通过。
- **依赖**：T2.3。

### T2.5 前端 NotebookRoom 接入真实接口

- **状态**：已完成（2026-09-29，含浏览器实机验证）
- **做法**：去掉 `NotebookRoom.vue` 里的 `notes` 内存态，改为**左侧笔记列表 + 右侧编辑器**：列表数据来自 `GET /notes`，新建 / 改名 / 删除都走笔记接口（不再调会话接口），选中项直接喂给现有的 `NotebookEditor`（编辑器的「选中一个 → 编辑它」前提不用改）。自动保存策略见 D5。
- **要一并删掉的东西**：`loadSessionNoteFromMessages`、`mapMessagesToNoteContent`、`renderSegments` 这几个「从会话消息推导笔记正文」的函数——按 T2.1 的结论它们整段作废，不要留着。
- **实际改动**：
  - 新增 `src/composables/useNoteAutoSave.ts`：自动保存逻辑（防抖 + 串行化 + 按笔记分组攒改动 + 可立即冲刷），前端规则要求「可复用逻辑抽离组合式函数」，而且它独立出来 NotebookRoom 才不至于过长。
  - 重写 `src/views/NotebookRoom.vue`（284 → 261 行）：列表/详情/增删改全部改走笔记接口，删掉三个「从会话消息推导正文」的函数与内存态 `notes`。
  - `src/components/notebook/NotebookEditor.vue` 增加可选的 `statusText`，在标题右侧显示「待保存… / 保存中… / 已保存 / 保存失败…」。
- **实现细节（对应 D5 的四条）**：
  - 停止输入约 1 秒提交；
  - `openNote`（切换笔记）、`createNewNote`、`onBeforeUnmount`、`visibilitychange` 四处都先 `flush()`，兜住「防抖没到点就切走 / 关页面」；
  - 保存请求串行化：同一时刻只有一个 PUT 在飞，其余排队，避免并发乱序把新内容覆盖成旧的；
  - 待提交内容**按笔记 ID 分组**——切换笔记时 A 的改动不会被写进 B（这是串行队列最容易被忽略的坑）；
  - 保存返回**不覆盖 `activeNote`**：用户可能已在继续输入，覆盖会把新输入顶掉；只回写左侧列表的标题。
- **验收结果（构建与静态核对）**：`pnpm run build` 通过；`NotebookRoom.vue` 已不再引用任何会话接口与 `SESSION_MODEL`；`loadSessionNoteFromMessages` / `mapMessagesToNoteContent` / `renderSegments` 全库无残留。
- **验收结果（接口链路，已实测通过 2026-09-29）**：通过 **vite 代理（5173）**——也就是浏览器实际走的那条路——完整跑了一遍：注册 201 → 登录 200 → 建笔记 201 → 列表 200（`total=1`，且列表项**不含正文**）→ 更新 200 → 删除 204 → 再查 `total=0`。确认前端代码、代理 rewrite、后端路由三者的衔接没有问题。
- **踩到的坑（已修）**：第一次在页面上打开笔记本时全部 404，日志显示 `GET /notes` 与 `POST /notes` 都是 404。原因是**后端进程是 14:00 启动的，而 `/notes` 路由是之后才加的**——uvicorn 没开 `--reload`，加载的还是旧代码。这已经是同一个坑第三次出现（前两次分别在 T1.2 和 T1.8 之前的联调），所以这次直接把后端改成 `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` 启动，后续后端改动会自动热加载。
- **验收结果（UI 行为，已实测通过 2026-09-29）**：「刷新后内容还在」与「改完立刻切换笔记也不丢」两条都由你在浏览器里验证通过。
- **后续补充的文案修正**：左侧栏原来写死「新建会话 / 历史会话」，而这轮之后笔记本里装的是笔记不是会话，措辞不对。改法是给 `SideBar` 加可选的 `createLabel` / `sectionTitle`，默认值保持「新建会话 / 历史会话」（学习室、面试间不受影响），笔记本传「新建笔记 / 历史笔记」。
- **仍未解决的限制**：`visibilitychange` 能覆盖切标签页与最小化，但**关标签页时的异步 fetch 不保证发得出去**（要彻底可靠得用 `navigator.sendBeacon`，且后端要额外适配，当前未做）——这条记在这里，不当作已解决。
- **依赖**：T2.4。

### T2.6 后端新增「一键存入笔记」接口

- **状态**：已完成（2026-09-29）
- **做法**：新增 `POST /notes/import`，入参 `message_id`、可选 `title`；服务层校验这条消息属于当前用户，把它的问答内容转成富文本初稿写入 `notes`，并用 `source_type=1`、`source_message_id` 记录出处。
- **幂等策略（原 D6，我改了文档的建议）**：原建议是「同一条消息只对应一条笔记，重复点击**走更新**」。落地时改成了**「已存在就直接返回，不覆盖」**——AI 回答本身不会再变，重复存入带不来新信息；而「走更新」会把用户后来编辑的内容整段抹掉。这是数据安全上的取舍，不是实现偷懒。
- **注意**：按 T2.1 的结论笔记不关联会话，所以**不需要 `session_id`**——消息自身带着会话归属，校验「消息属于当前用户」就够了。
- **涉及文件**：`interpace-backend/app/routes/note_routes.py`、`app/services/note_service.py`、`app/schemas/note_schemas.py`
- **接口变更**：是。
- **实际改动**：`app/schemas/note_schemas.py` 新增 `NoteImportRequest` / `NoteImportResponse`；`note_service.py` 新增 `import_from_message` 与一组 Markdown 轻量转换函数（`markdown_lite_to_html` 等）；`note_routes.py` 新增 `POST /notes/import`。
- **两处实现取舍**：
  - **Markdown 做「轻量」转换**：AI 回答原文是 Markdown，直接塞进富文本会满屏 `##` 和 `**`。所以转义后把标题、加粗、行内代码、段落与换行转成对应标签。**不是完整的 Markdown 渲染器**，真要完整渲染得引入 Markdown 库（后端目前没有），属于后续的事。先整体转义再套标签，避免回答里的尖括号被当成 HTML 注入。
  - **路由必须声明在 `/{note_id}` 之前**，否则 `import` 会被当成 `note_id` 去解析整数而报 422。代码里留了注释。
- **验收结果**：`pytest` **35 passed**（新增 2 个用例）。
  - 正常路径：存入后 `created=true`、`source_type=1`、`source_message_id` 等于来源消息、标题取自问题文本，正文里 `## 一句话回答` 变成了 `<h2>`、`**...**` 变成了 `<strong>`，且**不含残留的 `**`**。
  - 幂等：用户改过正文之后再存一次，`created=false`、返回的是同一条，且**用户改过的内容没有被覆盖**。
  - 错误路径：存入他人的消息、存入不存在的消息，均为 404。
- **依赖**：T2.3。

### T2.7 前端「存入笔记」入口

- **状态**：已完成（2026-09-29，含浏览器实机验证）
- **做法**：在 AI 回答气泡上增加「存入笔记」按钮，点击后调 T2.6 的接口并给出成功提示。
- **涉及文件**：`src/components/chat/MessageBubble.vue`、`src/components/chat/ChatWindow.vue`、`src/views/StudyRoom.vue`、`src/views/InterviewRoom.vue`、`src/api/note.ts`
- **实际改动**：`types/note.ts` 与 `api/note.ts` 补 `importNoteFromMessage`；`MessageBubble.vue` 在助手回答下新增「存入笔记」按钮，`MessageList` / `ChatWindow` 逐层透传 `save-to-note`；两个房间实现 `handleSaveToNote`。
- **顺带补的一处数据**：`UiMessage` 增加 `messageId`（后端主键）。原来气泡上只有 `${记录id}-resp` 这种字符串 ID，拿不到真实消息 ID。`useSessionStreamSender` 的占位写入器新增 `setMessageId`，在收到 SSE `start` 事件时回填——否则**刚回答完的消息要刷新页面才能存笔记**。
- **去重**：房间层用一个 `importingNoteMessageId` 保证同一时刻只处理一条，避免连点并发。后端没有 `(user_id, source_message_id)` 唯一约束（表已建好，`create_all` 不会给已有表加约束），所以这道闸门目前放在前端。
- **验收结果**：`pnpm run build` 通过（`vue-tsc` 覆盖了新增的 prop/emit 透传链）。**浏览器实机验证已通过 2026-09-29**：在面试间的回答上点「存入笔记」后，笔记本左侧出现对应笔记，标题取自问题文本、正文含「问题 / 回答」两段，且 AI 回答里的 `## 一句话回答`、`## 原理` **渲染成了真正的标题**而不是原样的 `##`——Markdown 轻量转换按预期生效。
- **已知取舍**：按钮没有「存入中」的禁用态（那需要把在途状态透传过 MessageList / ChatWindow 三层）。本地接口很快，加上房间层已有防连点，暂时够用；要加也不难。
- **依赖**：T2.6。

---

## 5. 阶段 3：通用附件上传与文件解析

学习室的刷题评测可以「上传简历」，面试间的简历优化与模拟面试也都需要简历，但现状是 `handleAttach` 只弹一句「暂未接入」提示；后端 `StreamChatRequest` 也不接受附件，落库时 `request_segments` 写死为空数组。

**技术选型（已定）：简历解析走 MinerU 本地部署，不用 pypdf 那套轻量方案。**

MinerU 4.0 自带 V1 HTTP 服务（`mineru-kit api-server`），调用链是「创建上传 → 传字节 → 完成 → 提交解析任务 → 轮询 → 下载产物」。这带来一个关键好处：**后端不需要新增任何 Python 依赖**——用已有的 `httpx` 调 HTTP 即可，MinerU 装成独立工具环境，后端 venv 保持干净。

选它的理由：pypdf 只能取文字层，**扫描件直接返回空**，而简历经常是扫描件或复杂排版；MinerU 能处理复杂版式、表格，并且自带 OCR。代价是重（模型约 2GB、需要常驻服务）。

### T3.0 部署 MinerU 本地服务（阶段前置）

- **状态**：已搁置（2026-09-29）：生产环境撑不住，见下方「与生产部署冲突」
- **目标**：本机跑通一个 MinerU 解析服务，能用 curl 解析一份 PDF 拿到 Markdown。
- **做法**：
  - 用 `uv tool install "mineru>=4.0,<5"` 装成**独立工具环境**，不装进后端 venv（避免把 torch 那一坨塞进后端依赖图）；
  - 起服务：`mineru-kit api-server --host 127.0.0.1 --port 8181 --tier standard`（8000 被后端占用，另选端口）；
  - 用官方 V1 流程验证：`POST /v1/uploads` → `PUT upload_url` → `POST /v1/uploads/{id}/complete` → `POST /v1/parse/jobs` → 轮询 `GET /v1/parse/jobs/{job_id}` → `GET /v1/files/{file_id}/content`。
- **机器适配（已确认）**：本机 M1 Pro / 32GB / arm64，官方推荐表里 macOS + Apple Silicon 对应 `standard` 档（PyTorch + llama.cpp），**基础包已自带 `torch` extra，macOS 不需要装 `[full]`**；standard 档模型约 2GB、最低 8GB 内存，均满足。
- **验收**：服务健康检查通过；一份真实 PDF 简历能解析出可读的 Markdown；记录一次解析的实际耗时（官方没给数字，需要实测）。
- **成本（如实记录）**：首次装包下载依赖；**首次解析会下载约 2GB 模型**；需要常驻一个本地服务进程。
- **⚠️ 与生产部署冲突（2026-09-29 核实）**：生产目标是一台**腾讯轻量云 2核2G** 服务器，**MinerU 放不下**——
  - 官方档位要求：`basic`（ONNX）模型约 0.8GB、**最低 2GB 内存**；`standard`（ONNX + llama.cpp）模型约 2GB、**最低 8GB 内存**；官方还明确建议「本地高吞吐部署按 **16GB** 规划」。而 2GB 那台机器还要同时跑 MySQL、Redis、后端与前端。
  - `flash` 档的原生解析路径（`.docx`、有文字层的 PDF）确实**不需要推理模型**，但那一路的产出质量与轻量解析库相当，却要多背一个 MinerU 服务；真正需要模型的是扫描件 OCR，而那个更吃内存。
  - **容器化也绕不过去**：MinerU 4.0 的官方 Docker 镜像是 NVIDIA 专用（`--gpus all` + CUDA），文档原文「Docker deployment for non-NVIDIA devices is pending an update」，非 NVIDIA 只能自己写 CPU 版镜像。
  - **结论**：本机（M1 Pro / 32GB）跑 MinerU 没问题，用于开发与验收；**生产那台 2核2G 跑不了**。生产怎么解析需要重新决策，见对话中的三个选项。

### T3.1 后端 StreamChatRequest 扩展支持附件

- **状态**：已完成（2026-09-29）
- **做法**：请求体新增 `segments`（默认空列表，元素复用已有的 `MessageSegment`）；`stream_chat_service` 落库时写入 `request_segments`，不再写死 `[]`。
- **实际改动**：`chat_schemas.py` 的 `StreamChatRequest` 新增 `segments`；顺手把 `MessageSegment.type` 从裸 `str` 改成 `Literal["file","image","audio"]`——写入侧就能挡住非法类型，读取侧 `ChatService` 本来就按同一组白名单过滤。`stream_chat_service.stream_chat` 新增 `segments` 参数并 `model_dump()` 后落库；`session_routes.py` 透传 `payload.segments`。
- **接口变更**：是。
- **验收结果**：`pytest` **36 passed**。新增用例走**真实 HTTP 接口**（不是直接调 service），覆盖：非法附件类型 `{"type":"hack"}` 返回 422；带合法 `file` 段发消息后，`GET /sessions/{id}/messages` 返回的 `request_segments` 与提交内容完全一致。
- **没做的事（记一笔）**：没有校验 `resource_id` 是否属于当前用户。也就是 A 可以把 B 的资源 ID 写进自己的消息里。实际影响有限——读取侧只返回原样字段，而会话删除时的资源回收本来就带 `user_id` 过滤，不会误删他人资源。等 T3.3 前端接入时会自然只传自己的 ID，先不做额外校验。
- **顺带发现**：`POST /sessions` 返回的是 **200 而不是 201**，与 `AGENTS.md` 的「创建 201」约定不符（`/notes`、`/users` 都是 201，只有 sessions 是 200）。写测试时踩到了，已按实际行为断言并留了注释。是否统一属于后续清理。

### T3.2 后端文档解析服务（轻量方案 + 扫描件识别）

- **状态**：已完成（2026-09-29）
- **做法**：新增 `app/services/document_parse_service.py`，按后缀分发：`.txt` / `.md` 直读；`.docx` 用 `python-docx` 取段落与表格；`.pdf` 用 `pypdf` 取文字层。解析结果写入当前消息的 `file_extracted_text`，作为上下文注入模型。
- **扫描件必须先识别、再决定，不能静默返回空**：`pypdf` 取出的文字量低于阈值（且页面里存在图片对象）时判定为「疑似扫描件」，此时**不硬解析**，而是返回一个明确的状态给前端。
- **统一的解析结果结构**：`{ ok, char_count, suspected_scanned, message }`——三种情况都要能区分：解析成功 / 疑似扫描件 / 解析失败（格式不支持、文件损坏、超时）。
- **反馈时机**：解析放在**上传时**做一次（文件字节就在手里，`pypdf`/`docx` 对简历都是几十毫秒级），结果随上传响应返回，用户**上传完立刻**就知道行不行，而不是发完消息才发现没读到。发送消息时后端按 `resource_id` 再解析一次写入 `file_extracted_text`——文本类文件重复解析的代价可以忽略，好处是不用改 `resources` 表结构（`create_all` 不会给已有表加列）。如果以后发现重复解析开销大，再改成把结果缓存到表上（那时需要迁移）。
- **扫描件的处理（已选路径 B，2026-09-29）**：**不需要跑 OCR 模型**——已实测确认 `deepseek-flash` 支持图片输入且能准确读取图中文字（用一张写着 `PURPLE-ELEPHANT-4271` 的测试图验证，模型完整读对）。所以 OCR 交给已经在用的多模态模型，比 `RapidOCR` / `PaddleOCR` 那套（几十到几百 MB 模型、还要实测内存峰值）省得多。
  - **实现方式**：加 `pymupdf`（实测 23.5 MB、**无任何运行期依赖**），服务端把扫描版 PDF 的页面渲染成图片，交给多模态模型——**用户全程无感**，不用换格式也不用截图。
  - 渲染出的图片怎么送进模型，见 T3.6。
- **渲染时机**：页面渲染放在**发送消息时**、按 `resource_id` 从 MinIO 取原文件现渲染，不落库、不留中间产物（避免给 2C2G 机器再添一份存储和清理负担）。上传时只做一次轻量的文字层检测，用于给用户即时反馈。
- **成本提醒**：图片输入会显著增加 token 消耗（一页扫描件约几千 token），建议给扫描件加页数上限（例如前 5 页）。
- **实际改动**：
  - 新增 `app/services/document_parse_service.py`：按后缀分发的解析 + 扫描件识别 + `render_pdf_pages()`（扫描件渲染成 PNG，供 T3.6 用）。解析入口整体包了兜底，**任何异常都转成失败结果、不向上抛**——解析失败不该影响上传本身。
  - `upload_schemas.py` 新增 `UploadParseInfo`，`UploadResponse` 增加 `parse` 字段（非文档类型为 `null`）；`upload_service_minio.py` 在 `save_file` 里顺手解析一次并把结果作为第三个返回值传出；`upload_routes.py` 透传。
  - 依赖按 D7 装上：`pypdf` 6.19.0 / `python-docx` 1.2.0 / `pymupdf` 1.28.2，`uv.lock` 只增加 49 行（没有连带升级别的包）。
- **一处范围调整**：原做法里写的「解析结果写入 `file_extracted_text` 并注入模型」**挪到了 T3.6**。原因是查下来 `file_extracted_text` 目前**根本没有任何地方读取**——写进去模型也看不到；把「文本怎么进模型」和「图片怎么进模型」放在一起做更顺，否则 T3.2 会出现「写了个没人读的字段」这种半成品。
- **验收结果**：`pytest` **45 passed**（本任务新增 9 个用例）。
  - 纯解析：`.txt` / `.md` 直读；`.docx` **连表格内容一起取**（简历常用表格排版，不取会整段丢经历）；有文字层的 PDF 正常解析且**不被误判**为扫描件；文字少但无图片的 PDF 判为短文档（也测了这一分支）；扫描件被识别并给出明确说明；不支持的类型报「暂不支持」而不是静默返回空。
  - 渲染：`render_pdf_pages` 产出真实 PNG（校验了 PNG 魔数）；页数上限生效（3 页文档传 `max_pages=2` 得 2 张、传 10 得 3 张）。
  - 上传集成：走真实 HTTP 接口——上传 `.docx` 返回 `parse.ok=true` 且字数大于 0；上传扫描件 PDF 返回 `suspected_scanned=true`；上传图片返回 `parse=null`。
  - 测试用的 PDF 是现场生成的：文字版直接 `insert_text`；**扫描件先把文字页渲染成位图、再把位图插进新 PDF**，得到「有图无文字层」的文件，正好对应扫描件的特征。
- **依赖**：T3.1。

### T3.3 前端附件上传接入

- **状态**：已完成（2026-09-29，浏览器实机验证待补）
- **做法**：`handleAttach` 从「弹提示」改成真实流程——选文件 → 调 `POST /upload/file` → 拿到 `resource_id` / `file_path` 组装成 `MessageSegment` → 随消息发送并渲染。
- **涉及文件**：`src/api/upload.ts`、`src/components/chat/ChatInput.vue`、`src/components/chat/ChatWindow.vue`、`src/views/StudyRoom.vue`、`src/views/InterviewRoom.vue`、`src/composables/useSessionStreamSender.ts`
- **实际改动**：
  - `api/upload.ts`：抽出通用的 `uploadFile(file, options)` 并补上 `parse` 类型，`uploadAvatar` 改为复用它（原来两处各写一遍 FormData 拼装）。
  - `ChatInput.vue`：附件按钮从「弹提示」改成真实流程——隐藏的 `<input type=file>` → 选中即上传（拿到 `resource_id`）→ 待发附件以 chip 形式显示在输入框上方，可单独移除。**上传时立即反馈解析结果**（T3.2 的 `parse.message`），解析失败会 `ElMessage.warning` 提示，不让用户发完消息才发现没读到。
  - **发送条件放宽**：原来必须有文字才能发，现在「有文字**或**有待发附件」即可——只传简历不提问也是合法用法。
  - 链路打通：`send` 事件带上 `segments`，经 `ChatWindow` → 房间 → `useSessionStreamSender` → `api/streamChat` 请求体。`createPending` 也接收 `segments`，用户气泡能立刻显示附件。
  - **顺手清掉**：`attach` 事件与两个房间里的 `handleAttach` 占位提示（原来只是 `ElMessage.info('暂未接入')`）。
- **验收结果**：`pnpm run build` 通过（`vue-tsc` 覆盖了新增的 props/emits 透传链）；静态核对了六段链路（选文件 → 上传组装 segment → ChatWindow → 房间 → composable → 请求体），并确认旧的 `attach` 占位已无残留。
- **未验证**：**浏览器实机验证没做**——文件选择框、附件 chip 的显示、上传中状态、以及「只带附件不写字」能否发送，都需要真人点一遍。
- **依赖**：T3.1。

### T3.4 前端附件展示校验

- **状态**：已完成（2026-09-29，浏览器实机验证待补）
- **做法**：确认 `MsgFile.vue` 对 `file` / `image` / `audio` 三类都有可用展示——图片能预览、音频能播放、文件能下载。当前这三条都未验证过。
- **验收**：三类附件都能正常展示与交互。
- **先解决了根因（资源怎么对外提供）**：`MsgFile.vue` 原来直接把 `segment.url` 塞进 `<img src>` / `<audio src>` / `<a href>`，而那是 `minio://bucket/object_key`，浏览器根本加载不了——三类展示**其实全是坏的**。
  - 新增 `GET /resources/{resource_id}/content`（`app/routes/resource_routes.py` + `app/services/resource_service.py`）：按 `resource_id + user_id` 做归属校验，从 MinIO 取字节原样返回；越权、不存在、对象已被清理都返回 404。
  - **关键约束**：资源接口走 `Authorization: Bearer`，而 `<img>` / `<audio>` 带不了自定义请求头。所以前端不是把接口地址塞给 `src`，而是**用 axios 取成 Blob → `URL.createObjectURL` 转临时地址**（`src/api/resource.ts`）。
- **`MsgFile.vue` 重写**：
  - 图片：挂载时主动取并内联显示；
  - 音频：点了才取，取到后渲染播放器并自动播放（由用户点击触发，不受自动播放策略限制）；
  - 文件：点了才取，取到后触发下载；
  - 音频与文件按需加载，**避免一进会话就为所有历史附件发一堆请求**；
  - `onBeforeUnmount` 释放 object URL，避免切换消息后内存泄漏；
  - 旧数据没有 `resource_id` 时只提示、不发请求。
- **验收结果**：`pytest` **49 passed**（新增 1 个：本人可读且字节与上传一致、他人 404、不存在 404、未登录 401）；`pnpm run build` 通过。
- **未验证**：**浏览器实机**——三类附件的实际展示与交互（图片预览、音频播放、文件下载）需要真人点一遍。
- **顺带说明**：**T0.4 剩下的「头像显示」现在有解了**——同一套机制（资源内容接口 + Blob 转 object URL）即可，只差把 `users.avatar` 那个路径反查成资源。本任务没有顺手改，留作独立一步。
- **依赖**：T3.3。

### T3.5 会话删除的资源回收补测试

- **状态**：已完成（2026-09-29）
- **现状**：`ChatService.delete_session` 已经会回收当前会话涉及的 MinIO 对象，但没有任何测试覆盖，属于纯靠人眼保证的逻辑。
- **做法**：新增 `pytest` 用例，验证带附件会话删除后 `resources` 记录与 MinIO 对象都被清理。
- **涉及文件**：`interpace-backend/tests/`
- **验收**：用例能覆盖「有附件」和「无附件」两条路径。
- **实际改动**：新增 `tests/test_session_resource_cleanup.py`。顺带把两个测试文件共用的 API 助手（上传、建会话、替换模型）抽到 `tests/api_helpers.py`——`test_attachment_to_model.py` 里那份本来只有它自己用，这次要被第二个文件复用了。
- **验收结果**：`pytest` **51 passed**（本任务新增 2 个）。
  - **有附件**：上传文件 → 带附件发消息 → 删除会话，`deleted_resources=1`、`deleted_messages=1`；删除前资源接口可读且 MinIO 对象存在，**删除后接口 404 且 MinIO 对象确实没了**。
  - **无附件**：删除会话照常成功，`deleted_resources=0`，不报错。
- **一处刻意的做法**：MinIO 对象是否存在用 `stat_object` **直接查**，而不是看资源接口返回什么——记录被删之后接口本来就会 404，光看接口区分不出「记录删了但对象还在」这种泄漏。
- **依赖**：T3.3。

### T3.6 把附件内容接入模型调用（文本 + 图片）

- **状态**：已完成（2026-09-29）
- **现状**：`build_stream_graph` 只把 `request_text` 与历史文本送进模型。附件方面有**两个洞**：
  - `image` 类型的附件段只是被存进 `request_segments`，**从来没有进入模型调用**；
  - `chat_messages.file_extracted_text` 这个字段**没有任何地方读取**——T3.2 解析出来的文档文本写进去也没用，模型同样看不到。
- **做法**：发送消息时按附件段的 `resource_id` 取出原文件并处理，然后把结果拼进人类消息：
  - 文档（`.docx` / 带文字层的 `.pdf` / `.txt` / `.md`）→ 解析成文本，拼进人类消息（并顺手写入 `file_extracted_text` 留档）；
  - 扫描件 PDF → `render_pdf_pages()` 渲染成图片，作为多模态内容块；
  - 图片附件 → 直接作为多模态内容块。
- **需要先补的能力**：`MinioStorageService` 目前只有上传与删除，**没有取对象的方法**，得先加一个按 `storage_path` 读字节的入口。
- **已确认的前提**：`deepseek-flash` 支持图片输入，且能准确读取图中文字（2026-09-29 实测，见 T3.2 的说明）。
- **注意**：图片走 base64 还是 URL 需要定——项目现在没有资源对外提供接口（T3.4 也卡在这），所以**短期只能 base64 内联**。另外历史消息里的附件不要重复注入，否则 token 会爆。
- **实际改动**：
  - `MinioStorageService.get_object_bytes()`：按 `minio://` 路径读出对象字节与 content-type（之前只有上传与删除）。**注意释放连接**，否则会耗尽 urllib3 连接池。
  - 新增 `app/services/attachment_content_service.py`：把附件段解析成「文本 + 图片」。按 `resource_id` 做**归属校验**（避免引用他人的文件），再从 MinIO 取字节并分流——图片直传、文档解析成文本、扫描件渲染成图片、音频明确提示不支持。单个附件出问题只记一条说明，不打断整轮对话。
  - `prompt_layer.build_stream_graph`：新增 `attachment_text` / `attachment_images` 参数，拼出**多模态人类消息**（附件正文 + 用户输入 + `image_url` 内容块，图片以 base64 data URL 内联）。
  - `stream_chat_service`：建行前解析附件，结果写进 `file_extracted_text`（这个字段终于有人读也有人写了）。
- **一处结构改动**：编排层的本轮输入从 `user_input`（字符串）改成 `user_messages`（消息列表）。因为带图片时人类消息是多模态内容块，**没法塞进 f-string 模板**，所以改用 `MessagesPlaceholder`。无附件时也是单元素的内容块数组，统一走一条路径。相应地更新了 `test_stream_graph` 里对输入键的断言。
- **验收结果**：`pytest` **48 passed**（本任务新增 3 个）。测试用一个「会记录收到的消息」的假模型替换真模型，走真实 HTTP 接口发消息，断言的是**模型收到了什么**，而不是「解析函数返回了什么」：
  - 图片附件 → 人类消息是内容块数组，含 1 个 `image_url`，data URL 与上传的字节逐字节一致；
  - Word 附件 → 简历正文（含表格内容）出现在发给模型的文本里，且 `chat_messages.file_extracted_text` 也留了档；
  - 扫描件 PDF → 渲染成 1 张 PNG 内容块，且文本里带有「扫描件」说明（否则模型只看到一张没有来由的图）。
- **真实端到端（2026-09-29）**：走运行中的后端——注册 → 上传一张写着 `PURPLE-ELEPHANT-4271` 的图片 → 建会话 → 带附件发消息 → **模型答出 `PURPLE-ELEPHANT-4271`**。完整链路（上传 → MinIO 取字节 → 多模态内容块 → 模型读图）确认打通。
- **依赖**：T3.1、T3.2。

---

## 6. 阶段 4：学习模块 · 知识精讲

对应流程图：`学习模块` → 有选择模式 → 知识精讲 → AI 输出结构化知识卡片 + 一对一语音播客讲解。本阶段先做文本部分，语音播客依赖阶段 7 的 TTS 能力，放到 T4.4。

### T4.1 确定知识精讲的输出协议

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。
- **需要定的点**：让模型输出 JSON 还是固定小节的 Markdown？流式场景下 JSON 解析困难、容易出现半截 JSON。
- **建议方案**：先用固定小节的 Markdown（概念 / 原理 / 示例 / 常见追问），前端按现有 Markdown 渲染直接出效果，不新增卡片组件。等确认内容形态稳定了，再考虑升级成结构化卡片。
- **结论**：采纳建议方案——**固定小节的 Markdown，不做 JSON 卡片**。
  - 流式场景下 JSON 很容易出现半截、无法解析，而 Markdown 可以边生成边渲染，体验上完胜。
  - 实际落地的小节比建议的四个更贴合面试场景，一共六个：**一句话回答 / 原理 / 示例 / 面试怎么答 / 常见追问 / 本节要点**。其中「面试怎么答」是产品特有的价值点——它逼模型把知识转成可直接说出口的答题提纲。
  - 这个协议在 T1.3 seed 模板时就已落地并实测生效，本任务只补记决策。

### T4.2 编写并 seed 知识精讲提示词模板

- **状态**：已完成（2026-09-29，由 T1.3 一并完成）
- **做法**：按 T1.3 的 seed 机制补充 `study` 场景模板，模板里用上 `target_job` / `target_skills` / `weak_topics` 等用户画像变量。
- **验收**：学习室选「知识精讲」提问，回答结构符合 T4.1 的约定，且能体现用户画像信息。
- **说明**：T1.3 的 `SEED_TEMPLATES` 里本来就包含 `study` 公共模板与 `difficulty_learner` 私有模板，所以这一任务无需再做。查询数据库确认：两条记录都在（`active=1`），`build_personalized_prompt(db, 0, "difficulty_learner", "study")` 返回非 `None`，且正文里的固定小节正是 T4.1 约定的六个。
- **一处如实说明**：「体现用户画像信息」这一半**现在验不了**——画像变量确实被注入了模板，但 `user_profiles` 表还没有任何对外接口，注入进去的永远是「未指定」。等阶段 9（T9.3 / T9.4）把画像打通后才能真验。模板侧的工作已完成。
- **依赖**：T1.3、T4.1。

### T4.3 知识精讲端到端联调与验收

- **状态**：已完成（2026-09-29，由 T1.7 的浏览器验证覆盖）
- **做法**：用一条真实问题走通「选模式 → 提问 → 流式回答 → 落库 → 刷新回显」。
- **验收**：刷新页面后消息与模式标签都在；`pnpm run build` 与 `pytest` 通过。
- **证据（2026-09-29）**：T1.7 做模式标签的浏览器验证时，走的就是这条链路——在面试间选「知识精讲」、问「什么是索引覆盖？」，回答的小节序列是**一句话回答 / 原理 / 示例 / 面试怎么答 / 常见追问 / 本节要点**，与 seed 的模板逐节对应；刷新页面后消息与模式标签都能从接口重新渲染出来。也就是说「选模式 → 提问 → 流式回答 → 落库 → 刷新回显」五步都已实测通过。
- **补充验证**：本任务执行时又查了一次数据库，确认两条 `study` 模板仍在且 `active=1`，`build_personalized_prompt` 返回非 `None`。
- **依赖**：T4.2。

### T4.4 知识精讲接入语音播客讲解

- **状态**：待办
- **做法**：复用阶段 7 的 TTS 能力，把知识精讲正文转成可播放语音，对齐流程图里「一对一的语音播客讲解」。
- **验收**：知识精讲结果旁有播放按钮，点击能播放对应讲解音频。
- **依赖**：T7.6。

---

## 7. 阶段 5：学习模块 · 刷题评测

对应流程图：用户输入岗位 / 技术栈需求（或上传简历）→ AI 二次确认题型、难度、题量 → 用户确认后生成题库 → 用户答题并提交 → AI 评分、抽取薄弱点并解答 → 可调用知识精讲、可存入笔记。

这是流程图里最长的一条链路，也是唯一需要「结构化题库 + 用户作答 + 评分」的链路，风险集中在 T5.4。

**技术选型约束**：「确认参数 → 生成题库 → 用户作答 → 评分」是典型的状态流转，用 LangGraph 编排，不手写轮次循环；模型、提示词、记忆用 LangChain。

### T5.1 确定多轮确认的实现方式

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。
- **选项**：(a) 纯提示词多轮，靠对话历史维持上下文；(b) 用 LangGraph 显式编排状态（确认参数 → 生成题库 → 待作答 → 已评分）。
- **建议方案**：先用 (a) 跑通，改动最小；如果模型稳定性不够（比如它没等用户确认就出题），再升级到 (b)。注意 (b) 不是另写一套循环，而是用 LangGraph 的状态图表达，符合根 `AGENTS.md` 的智能体开发约定。
- **结论（原 D9）**：采纳选项 (a) 纯提示词多轮，并靠下面两条让它足够稳：
  - **出题的触发用「内容判据」，不用状态机**：后端每轮都试着把模型输出解析成约定的题库结构，**解析成功就算出题完成**并落库。不需要显式记录「现在处于哪个状态」。
  - **岗位 / 难度 / 题量随输出一起给**：让模型在题库 JSON 里带上这三个参数，后端照存到 `quiz_papers`。参数存在输出里，而不是存在某个节点状态里。
- **升级到 (b) 的条件（写进验收，不含糊）**：如果 T5.4 的稳定性验证发现模型**频繁不守「先确认后出题」**（用户还没确认就自己出题），说明纯提示词管不住这个流程，那时改用 LangGraph 状态图表达——不是另写一套循环。


### T5.2 确定题库的数据模型

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。
- **结论（原 D10）**：拆两张表。
  - **`quiz_papers`**：`id`、`user_id`、`session_id`、`message_id`（入口消息，唯一）、`target_job`、`difficulty`、`question_count`、`status`（0 待作答 / 1 已提交 / 2 已评分）、`created_at`、`updated_at`。
  - **`quiz_questions`**：`id`、`paper_id`、`order_index`、`question`、`reference_answer`（可空，防模型漏给）、`user_answer`（可空）、`score`（可空，0-100 整数）、`analysis`（可空）、`created_at`。
  - 拆开的好处是「一次出题」和「一道题」的字段不混在一起，后续统计（如「这个用户在 SQL 上的平均得分」）好做。
- **两条一起定的约束**：
  - **一份卷子只支持一次作答**：用户答案、得分、解析直接挂在题目行上。以后要做「重做一遍再对比」得再加 `quiz_submissions` 表——v1 不提前加。
  - **前端怎么找到某条消息对应的卷子**：`chat_messages` 表已经存在，**加不了新列**（`create_all` 不会给已有表加列，要迁移，而 Alembic 现在是空壳——见 T10.7）。所以改用**新增一个 `status` 取值标记「题库入口」消息**（现有列，零迁移），前端再通过「按会话列出卷子」的接口拿到 `message_id → paper_id` 映射来渲染卡片。这和面试卡片的做法不同（面试有专门的 `interview_id` 列），但不需要动表结构。

### T5.3 后端新增题库相关表

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/db/models.py`
- **验收**：表能建出来；此步无接口，`pytest` 仍应全绿。
- **实际改动**：
  - `app/db/models.py` 新增 `QuizPaper` 与 `QuizQuestion`，字段按 T5.2 的结论。`reference_answer` 特意允许为空——模型偶尔漏给时不该整批写入失败，缺了在评测环节单独提示。
  - **顺手修了一处必然会踩的坑**：卷子的 `message_id` 指向 `chat_messages`、`session_id` 指向 `sessions`，而 `ChatService.delete_session` 原来只删面试记录与消息。**不先删卷子就会撞外键、整个删除请求失败**（用户删不掉带题库的会话）。已把「先删题目 → 再删卷子 → 最后删消息/会话」的顺序补进删除流程；`DeleteSessionResponse` 相应新增 `deleted_quizzes`，前端类型同步。
- **验收结果**：`pytest` **52 passed**；`pnpm run build` 通过。
  - 建表后核对结构：`quiz_papers` 字段与索引（含 `idx_quiz_papers_session_message`）齐全，`quiz_questions` 字段与 `idx_quiz_questions_paper` 齐全。
  - 新增用例专门验**外键删除顺序**：造一份卷子 + 一道题 → 删除会话 → 返回 `deleted_quizzes=1`，且卷子与题目都查不到了。
- **依赖**：T5.2。

### T5.4 约定题库的结构化输出格式并验证模型稳定性

- **状态**：已完成（2026-09-29）
- **优先级**：高风险，先验证再做后面几步
- **涉及文件**：`interpace-backend/app/services/quiz_service.py`（新增）、`interpace-backend/app/services/prompt_template_seed_service.py`、`interpace-backend/tests/test_quiz_service.py`（新增）
- **做法**：在提示词里约定严格的 JSON 结构，写一个最小脚本，用真实模型跑 8 次两轮对话，统计解析成功率。流式时先把文本透传给前端展示，`done` 事件到达后再解析并落库。
- **实际改动**：
  - 新增 `quiz_service.py`：**契约与解析放在一起**——`QUIZ_JSON_CONTRACT` 同时被提示词模板和解析器引用（模板里用 `_escape_braces()` 双写花括号），两边结构不可能写岔。
  - `parse_quiz_payload()` **不抛异常**：解析不出来就返回 `None`，由上层理解为「这轮不是出题」。容错点都来自实测常见情况：` ```json ` 代码块包裹、前后夹解释文字、题目缺 `reference_answer`、题干为空的条目丢弃、`question_count` 一律以实际列表长度为准（不采信模型自报数字）。
  - 刷题模板 `QUIZ_GENERATE_TEMPLATE` 走两阶段：**先复述参数请用户确认 → 用户确认后才吐 JSON**，并和公共模板一起 seed 进 `prompt_templates`（`[公共:quiz] v1`、`[quiz_generate_workflow:quiz] v1`）。
  - **踩到的坑（已解决，已回归覆盖）**：模板正文会被 `ChatPromptTemplate` 当模板解析，JSON 示例里的裸花括号会被当成模板变量、调用时抛 `KeyError`，必须双写成 `{{` / `}}` 再 `.replace()` 填入。新增 `test_quiz_template_renders_into_chat_prompt_template` 守住这条。
- **验收结果**：**8/8 通过**。
  - **确认门可靠**：8 次里「用户还没确认就出题」= **0 次**；首轮模型都在复述参数请确认。
  - **确认后解析成功**：**8/8**；题量分布 `{5: 8}`（与要求一致）；缺参考答案的题目 **0 道**。
  - `pytest` **70 passed**（新增 18 个纯函数用例，覆盖代码块包裹、夹带解释、非法 JSON、空题量、全空题干、非字典条目、题量自报与实际不符、难度越界取值、字段去空白等）。
- **一次误报（记录以免误导）**：早先一轮 0/8，原因是**测试脚本没给全参数**（没给难度和题量），模型正确地回「还差两项没定」并拒绝出题——是脚本错、不是模型错。给全参数后即 8/8。
- **结论**：**不需要升级到 T5.1 的选项 (b)（LangGraph 状态图）**，纯提示词多轮 + 内容判据足够稳。若后续实测在其它参数组合上出现「未确认就出题」，再按 T5.1 写的条件升级。
- **注意**：如果解析成功率不达标，需要回头调整 T5.1 的方案，不要硬做 T5.5。

### T5.5 后端「生成题库」能力

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/quiz_service.py`、`interpace-backend/app/services/stream_chat_service.py`、`interpace-backend/app/db/models.py`（状态注释）、`interpace-frontend/src/api/streamChat.ts`（`done` 事件类型）、`interpace-backend/tests/test_quiz_paper_persistence.py`（新增）
- **做法**：走 T1.2 的模式路由，在流式结束后解析 JSON 并落 `quiz_papers` / `quiz_questions`。
- **实际改动**：
  - `stream_chat_service` 在 `finally` 里、**消息正文提交之后**调用 `_persist_quiz_if_any()`：只有 `scene == "quiz"` 才尝试解析，解析成功才落库（T5.1 的「内容判据」，不引入状态机）。
  - **跳过条件**：用户中途停止（`stopped`）或本轮报错时一律不解析——半截输出不该落成卷子。
  - `quiz_service.save_quiz_paper()` **只 flush 不 commit**，事务边界留给调用方，失败可整体回滚，不会留下「有卷子没题目」的半截数据；并且**以 `message_id` 幂等**（重放/重试不会产生第二份卷子）。
  - 落库成功把入口消息 `status` 置为 **3（题库入口）**，前端靠它认出「这条消息该渲染答题卡片」。为不改表结构，`chat_messages` 只是新增一个既有列的状态取值（T5.2 的约定）。
  - **接口变更（一项，向后兼容）**：`stream-chat` 的 `done` 事件新增可选字段 `quiz_paper_id`（没出题时为 `null`），前端 `StreamEvent` 类型已同步。
- **验收结果**：`pytest` **73 passed**（新增 3 个用例）；`pnpm run build` 通过。
  - 用例直接查库（`quiz_papers` / `quiz_questions`）而非看接口：刷题模式 + 题库 JSON → 卷子字段与 2 道题目正确、`order_index` 为 1/2、`score` 为空、消息 `status=3`；
  - 刷题模式 + 还在确认参数 → 不落库、`status` 保持 0；
  - 其它模式 + 题库 JSON → 不落库（只有 quiz 场景才解析）。
- **未验证**：真实模型（非桩）走完整 HTTP 链路的落库，等 T5.6 前端能拉取卷子后合并到端到端验证里做。
- **依赖**：T5.3、T5.4。

### T5.6 后端「获取题库」接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/routes/quiz_routes.py`（新增）、`interpace-backend/app/schemas/quiz_schemas.py`（新增）、`interpace-backend/app/services/quiz_service.py`、`interpace-backend/app/routes/__init__.py`、`interpace-backend/app/main.py`、`interpace-backend/tests/test_quiz_api.py`（新增）、`interpace-frontend/src/api/quiz.ts`（新增）、`interpace-frontend/src/types/quiz.ts`（新增）
- **接口变更**：是，新增两个只读接口（按 AGENTS 已同步后端路由+Pydantic、前端 `src/api/`+类型）。
- **实际改动**：
  - `GET /quiz-papers/{paper_id}`：卷子详情 + 题目列表。**题目不含 `reference_answer`**——为把这件事做到结构上不可能出错，单独定义了 `QuizQuestionItem` 模型，而不是直接序列化 ORM 行（谁都不能"顺手"把它加进响应）。
  - `GET /quiz-papers?session_id=`：按会话列出卷子。这是 T5.2 提到的「按会话列出卷子」接口，用来给前端一张 `message_id → paper_id` 映射表——刷新页面后靠它把答题卡片挂回历史消息上（`status=3` 只说明「这条是题库入口」，不含 paper id）。
  - 分层对齐笔记路由：路由只做接入与参数校验，查询与归属校验都在 `quiz_service`；越权一律 404，口径与笔记一致（不区分「不存在」与「不是你的」）。
- **验收结果**：`pytest` **77 passed**（新增 4 个用例）；`pnpm run build` 通过。
  - 用例断言响应的题目里**没有 `reference_answer` 字段**、`order_index` 为 1/2、`status=0`；
  - 列表接口返回 `message_id` 且**不含题目**；
  - 他人卷子：详情 404、列表 `total=0`；不存在的卷子 404。
- **未验证**：前端调用这两个接口（T5.9 做答题 UI 时才会真正用上）。
- **依赖**：T5.5。

### T5.7 后端「提交答案」接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/quiz_evaluation_service.py`（新增）、`interpace-backend/app/services/quiz_service.py`、`interpace-backend/app/services/prompt_template_seed_service.py`、`interpace-backend/app/services/prompt_template_service.py`（注册内部 agent）、`interpace-backend/app/schemas/quiz_schemas.py`、`interpace-backend/app/routes/quiz_routes.py`、`interpace-backend/tests/test_quiz_submission.py`（新增）、`interpace-frontend/src/api/quiz.ts`、`interpace-frontend/src/types/quiz.ts`
- **接口变更**：是。新增 `POST /quiz-papers/{paper_id}/submissions`（按 AGENTS 已同步后端路由+Pydantic、前端 `src/api/`+类型）。
- **实际改动**：
  - 新增评分提示词模板 `QUIZ_EVALUATE_TEMPLATE`（agent `quiz_evaluator` / scene `quiz`），并把 `quiz_evaluator` 注册进 `AGENT_CONFIG`（内部 agent，不登记为可选模式）。输出契约 `QUIZ_EVALUATION_JSON_CONTRACT` 同样**契约与解析器共用一份**。
  - **评分是同步单次调用，不走流式**：用户点提交等一个结果即可，不需要「边算边看」。所以这里用 LangChain 的普通 `invoke`，没有为此再建一张 LangGraph 图（与 T5.1 的结论一致——值得上图的是有状态流转的链路）。
  - **两次提交，保住用户答案**：先写用户作答并 `commit`（卷子置 `status=1 已提交`），再调模型评分，成功才推到 `status=2 已评分`。评分失败（模型输出解析不出来）返回 **502**，但答案已经落库，可原样重试（重试时 `answers` 传空数组即可，用库里存的作答重评）。
  - `parse_quiz_evaluation()` 容错口径与 `parse_quiz_payload()` 一致（剥代码块、取首尾花括号、不抛异常），另外：得分**收敛到 0-100 并四舍五入**、薄弱点**去重且保持顺序**、题号非正整数的条目丢弃、只有空白的解析归一成 `null`。
  - 一份卷子**只评分一次**：已评分的再提交返回 **409**。
- **验收结果**：`pytest` **88 passed**（新增 4 个接口用例 + 6 个解析器用例）；`pnpm run build` 通过。
  - 正常提交：总分/薄弱点/逐题得分与原样落库，卷子 `status=2`，**响应里依然不出现 `reference_answer`**；
  - 重复提交 409；他人卷子 404；
  - **评分失败路径**：返回 502，卷子停在 `status=1`、用户答案已落库、`score` 仍为空。
  - seed 已执行：`[quiz_evaluator:quiz] 写入 v1`，缓存已刷新。
- **未验证**：真实模型（非桩）的评分质量与稳定性——等 T5.9 前端答题 UI 做出来，用真实模型走一遍完整链路再验。
- **依赖**：T5.6。

### T5.8 后端把薄弱点写回用户画像

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/user_profile_service.py`、`interpace-backend/app/services/quiz_evaluation_service.py`、`interpace-backend/tests/test_user_profile_weak_topics.py`（新增）、`interpace-backend/tests/test_quiz_submission.py`
- **做法**：提交答案后，把薄弱点去重合并进 `user_profiles.weak_topics`（复用 `UserProfileService`）。
- **实际改动**：
  - 新增 `UserProfileService.merge_weak_topics()`：**去重合并**（已有顺序不变、新的追加在后、重复的跳过），超过 `MAX_WEAK_TOPICS=50` 时丢弃最早的、保留最近的；没有画像记录时顺手建一条。
  - 方法带 `commit=False` 参数，供评分流程**与评分写回放进同一个事务**——避免出现「卷子已评分但画像没更新，重试又被 409 挡住」的不可恢复状态。
  - 薄弱点为空时不动画像，免得给每个提交过的用户都建一条空记录。
  - **闭环生效点**：`build_personalized_prompt` 每次请求实时读画像，所以合并进 `weak_topics` 之后，后续学习室 / 刷题的提示词里就会带上这些薄弱点（「越用越好用」的第一条闭环）。
- **验收结果**：`pytest` **92 passed**（新增 4 个数据层用例，并给评分用例加了画像断言）。
  - 数据层：缺记录自动建、重复提交不堆积、顺序稳定、超上限按最近保留、空白知识点忽略；
  - 接口层：提交卷子后 `user_profiles.weak_topics` 等于模型给出的 `["GIL", "索引失效"]`。
- **备注（后续收敛点）**：这是本任务的最简实现（直接落 `weak_topics`）。阶段 9 的统一记忆抽取（T9.5/T9.6）就绪后，应把这里的写入改为调用统一入口，避免两套抽取逻辑长期并存。
- **依赖**：T5.7。

### T5.9 前端答题与结果 UI

- **状态**：已完成（2026-09-29）
- **做法**：题目列表 + 作答区 + 提交按钮；结果区展示得分、薄弱点、逐题解析；提供「针对薄弱点讲一讲」（跳知识精讲）与「存入笔记」两个入口。
- **涉及文件**：新增 `src/components/quiz/QuizCard.vue`、`src/components/quiz/QuizQuestionBlock.vue`、`src/types/quiz.ts`、`src/api/quiz.ts`；改动 `src/components/chat/MessageBubble.vue`、`src/components/chat/MessageList.vue`、`src/components/chat/ChatWindow.vue`、`src/views/StudyRoom.vue`、`src/constants/chat-modes.ts`
- **实际改动**：
  - 拆成两个子组件：`QuizCard`（取卷子 / 提交 / 结果 / 跨模块入口）与 `QuizQuestionBlock`（单题的作答态与结果态）。`StudyRoom.vue` 只多了「题库映射」这一小块状态，没有继续往页面里堆 UI。
  - **答题卡片挂载判据**：`message_id → paper_id` 映射（来自 `GET /quiz-papers?session_id=`）。历史回显和刚出题完（流式结束）走的是同一份映射，不额外存状态。所以**没有**用 `status=3` 判定，`status` 只在后端留作语义标记。
  - 会话切换时自动刷新映射（`watch(activeSessionId)`），发完消息也刷一次；刷新只更新映射、不碰消息列表，所以不会引起消息区跳动。
  - **出题消息的正文不再直接显示**：它是约定的 JSON，显示原始 JSON 对用户没有意义，直接由答题卡片呈现（同时隐藏该消息上通用的「存入笔记」，避免把 JSON 存进笔记）。
  - **「存入笔记」存的是人读得懂的内容**：不存入口消息正文，而是复用已有的 `POST /notes`，把「得分 + 薄弱点 + 逐题解析」拼成富文本笔记（题干/解析来自模型输出，拼 HTML 前做了转义）。
  - **「针对薄弱点讲一讲」**：卡片发事件 → 学习室把模式切到知识精讲（`select_model=1`）并把这几个知识点作为一轮提问发出去，复用原有流式链路，没有新接口。
  - 模式常量收敛成 `DEFAULT_CHAT_MODE` / `KNOWLEDGE_MODE` / `QUIZ_MODE`，不再散落魔法数字。
- **验收结果**：`pnpm run build`（含 `vue-tsc`）**通过**；**浏览器实测通过**（2026-09-29，用户实测）。
  - 实测覆盖：出题 → 答题 → 提交 → 看到评分 → 「针对薄弱点讲一讲」→ 「存入笔记」完整链路。
- **已知限制（记录在案，不在本任务解决）**：
  1. **刷新页面后不显示薄弱点**：`weak_topics` 只写进了用户画像，没有落 `quiz_papers`（T5.2 约定 v1 不加列），所以刷新后只显示逐题得分与解析。要补的话，等 T10.7 的 Alembic 落地后给卷子加一个评分结果字段。
  2. **刷新后总分显示为「逐题平均分」**：同理，模型给的整体 `total_score` 只存在于提交响应里。刚提交完显示模型总分，刷新回来显示平均分（卡片上用同一个「得分」位置，数值口径不同，需要时再统一）。
- **依赖**：T5.7、T4.3、T2.7。T4.3/T2.7 已完成，依赖满足。
- **拆分说明**：原计划的「T5.10 结果页与跨模块联动」已并入本任务一起做完，不再单开编号。

---

## 8. 阶段 6：面试模块 · 简历优化

对应流程图：面试模块 → 选中模式 → 简历优化 → 用户上传简历或输入简历资料 → AI 深度分析 → 评判优缺点 → 重新生成优化后的简历（可下载 Word）→ 直接进入模拟面试。

### T6.1 简历优化提示词模板 seed

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/prompt_template_seed_service.py`
- **做法**：补 `resume` 场景的公共模板与 `resume_parser` / `resume` 私有模板。
- **实际改动**：
  - 新增 `INTERVIEW_COMMON_TEMPLATE`（面试间公共背景）。**注意**：公共模板是按 `scene` 存的，而面试侧三个场景（简历优化 / 模拟面试 / 面试复盘）要共用同一份背景，所以每个 scene 各 seed 一次同一个常量——现阶段只做 `resume`，阶段 7 / 8 直接复用这个常量，不再复制正文。
  - 新增 `RESUME_OPTIMIZE_TEMPLATE`（`resume_parser` / `resume`），把 T6.3 的小节结构一次写进去（见下条）。
  - 面试间公共模板比学习室多两条硬约束：**站在招聘方视角**（说清「招聘方会怎么理解」），以及**只依据用户提供的材料、不编造经历/学历/公司/数字**；缺信息时用占位符标出。
  - 已执行 seed：`[公共:resume] 写入 v1`、`[resume_parser:resume] 写入 v1`，缓存已刷新。
- **验收结果**：模板能被 `get_full_prompt` 查到；`pytest tests/test_prompt_template_seed.py` 4 passed（含「模板里不能有裸露花括号」，`{{待补充：项目成果数据}}` 是合法转义）；结构稳定性见 T6.3。
- **未验证**：浏览器里选「简历优化」提问的实际观感（等你验）。
- **依赖**：T1.3。

### T6.2 简历解析结果结构化并写入用户画像

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/profile_extraction_service.py`（新增）、`interpace-backend/app/services/profile_proposal_service.py`（新增）、`interpace-backend/app/routes/profile_proposal_routes.py`（新增）、`interpace-backend/app/schemas/profile_proposal_schemas.py`（新增）、`interpace-backend/app/services/stream_chat_service.py`、`interpace-backend/app/services/chat_service.py`、`interpace-backend/app/services/prompt_template_seed_service.py`、`interpace-backend/app/db/models.py`、`interpace-frontend/src/components/profile/ProfileProposalCard.vue`（新增）、`interpace-frontend/src/api/profile.ts`（新增）、`interpace-frontend/src/types/profile.ts`（新增）、`interpace-backend/tests/test_profile_proposal.py`（新增）
- **结论（原 D11，已确认）**：**解析结果必须先给用户确认，确认后才写 `user_profiles`。** 画像每轮都会注入提示词，解析错一次会污染之后所有回答；相比省一次点击，这个代价太大。
- **做法**：从简历文本中抽取 `target_job` / `years_experience` / `target_level` / `target_skills` / `weak_topics`，先落「待确认」，用户确认后再写 `user_profiles`。
- **实际改动**：
  - **抽取用独立的第二次模型调用**，不让主回答吐 JSON：简历优化的正文是给人看的六节结构（T6.3），把机器用的 JSON 混进去会毁掉排版。抽取走新 seed 的 `resume_extractor` / `resume` 模板，契约 `PROFILE_JSON_CONTRACT` 仍是**提示词与解析器共用一份**。
  - **触发条件**：只有 `scene=resume`、且本轮输入（提问 + 附件正文）**累计 ≥120 字**才抽。纯提问（「简历怎么写」）不含简历内容，不该白花一次调用。
  - **新增 `profile_proposals` 表**（`payload` 存 JSON、`message_id` 唯一）：待确认状态要跨刷新保留，不能只放前端内存。
  - **新增三个接口**：`GET /profile-proposals?session_id=`（刷新后把卡片挂回历史消息）、`POST /{id}/confirm`、`POST /{id}/dismiss`。
  - **确认的写入语义**：标量字段只覆盖显式给出的值（清空 = 这个字段不动，不是删除）；技能 / 薄弱点**与已有画像合并去重**，不会因为确认一次把之前积累的冲掉。已处理的记录再确认返回 **409**；越权一律 **404**。
  - **顺手补了一个必然踩的坑**：`profile_proposals.message_id` 指向 `chat_messages`、`session_id` 指向 `sessions`，不先删就会撞外键导致会话删不掉——`ChatService.delete_session` 已补上删除顺序（与 T5.3 处理题库时同一个坑）。
  - 前端新增画像确认卡片：字段可编辑，「确认写入画像 / 忽略」；确认或忽略后就地更新，不整页重拉。
- **验收结果**：`pytest` **105 passed**（新增 7 个用例，含越权、重复确认、忽略不写画像、短输入不抽取）；`pnpm run build` 通过；运行中的后端已加载三个新接口（openapi 可查）。
  - **真实模型 3/3 可解析**：给定一份含「求职意向：Python 后端开发 / 2021.07-2025.06 / 正在学习 Docker」的简历，抽出的岗位、年限（4 年）、技能、薄弱点（Docker）三次一致正确。
  - 观察到一处小偏差：简历没写级别时，模型有 2/3 次仍推断出「中级」（提示词要求「判断不了填 null」）。因为**确认环节可以改**，暂不处理；等阶段 9 统一记忆抽取时一起收紧。
- **未验证**：浏览器里上传简历 → 看到确认卡片 → 改字段 → 确认写入的完整观感（等你验）。
- **依赖**：T6.1、T3.2。
- **备注（后续收敛点）**：这是长期记忆（阶段 9）的一个写入来源。阶段 9 的 T9.5 记忆抽取服务就绪后，应把这里的抽取改为调用统一入口，避免两套抽取逻辑长期并存。

### T6.3 简历优缺点评判输出

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/prompt_template_seed_service.py`
- **做法**：约定输出小节（亮点 / 不足 / 改进建议），走现有流式渲染。
- **实际改动**：定了六个固定小节，标题原样保留，**把「分析」和「优化后的简历」在结构上彻底分开**：
  1. `## 简历诊断`（整体判断 + 最关键问题）
  2. `## 亮点`（每条说明为什么好）
  3. `## 不足`（按严重程度排序，每条写「哪里不对」+「招聘方会怎么理解」）
  4. `## 改进建议`（尽量给「改前 → 改后」对照）
  5. `## 优化后的简历`（完整可用版本，按「个人信息/技能/工作或实习经历/项目经历/教育经历」组织，**不得新增未提供的经历或数字**，缺的关键信息用 `{{待补充：…}}` 标出）
  6. `## 下一步`（继续优化方向，或提示可以进入模拟面试）
- **验收结果**：**真实模型跑 3 次，六节齐全 3/3**（各次输出长度 3852 / 4631 / 4991 字），且三次都实际用到了 `待补充` 占位——说明「不编造数字」这条约束在生效，不是只写在提示词里好看。
  - 走现有流式渲染，没有新增前端改动（Markdown 小节标题本来就会被渲染）。
- **未验证**：浏览器里的实际排版观感（等你验）。
- **依赖**：T6.1。

### T6.4 优化后简历的 Word 导出接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/resume_export_service.py`（新增）、`interpace-backend/app/routes/resume_routes.py`（新增）、`interpace-backend/app/schemas/resume_schemas.py`（新增）、`interpace-backend/app/services/upload_service_minio.py`、`interpace-backend/tests/test_resume_export.py`（新增）、`interpace-frontend/src/api/resume.ts`（新增）、`interpace-frontend/src/types/resume.ts`（新增）
- **结论（原 D12，已确认）**：**先落资源再返回 `resource_id` + 下载地址**，复用现有资源治理与过期回收。返回文件流要另写一套下载与清理，不划算。
- **做法**：新增导出接口，把优化后的简历文本生成 `.docx` 并返回下载方式。依赖取舍见 D7（复用已装的 `python-docx`，不新增依赖）。
- **接口变更**：是。
- **实际改动**：
  - 新增 `POST /resumes/export`，请求只要 `message_id`，返回 `resource_id` / `file_name` / `content_type` / `download_path` / `reused`；下载仍走既有的 `GET /resources/{id}/content`，鉴权口径完全一致。
  - **只导出「优化后的简历」这一节**：正文是六节结构，把「不足」「改进建议」一起塞进 Word 没意义。**踩到的坑**：一开始按「遇到标题就结束」切小节，结果简历正文自带的 `# 张伟`、`## 技能` 被判成小节结束，导出的内容直接退化成全文——改成只认 T6.3 约定的兄弟小节标题（诊断 / 亮点 / 不足 / 改进建议 / 下一步），并写了回归用例。
  - Markdown → Word 只处理标题、无序 / 有序列表与 `**加粗**`（加粗转成真正的 run，不留 `**` 字符）；这是优化后简历实际会用到的结构，不做完整 Markdown 渲染器。
  - 落资源复用了上传服务新增的 `save_generated_file()`：同样按 `(user_id, file_hash)` 去重、同样按存储场景算过期时间，所以**导出的 Word 会被既有的过期清理一起回收**，不用另立一套治理。
- **验收结果**：`pytest` **105 passed**（新增 6 个用例）；运行中的后端已加载 `/resumes/export`。
  - 生成的 `.docx` 校验了三层：① 是合法 OOXML（zip 内含 `[Content_Types].xml` 与 `word/document.xml`）；② 能被 `python-docx` 重新打开；③ 正文与源文本一致、`**` 不残留、列表走了 `List Bullet` / `List Number` 样式。
  - 端到端：导出 → 用返回的 `download_path` 下载 → 拿到真实 Word 字节，且「不足」那节确实没被导出。
  - 越权 404、消息不存在 404、正文为空 409。
- **未验证**：Word 在 Microsoft Word / WPS 里的实际排版观感（本机没有 LibreOffice，没法渲染成图片看）。样例文件已生成在 `/private/tmp/sample-resume.docx`，可以直接打开看一眼。
- **依赖**：T6.3。

### T6.5 前端下载入口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-frontend/src/components/resume/ResumeDownloadButton.vue`（新增）、`interpace-frontend/src/components/chat/MessageBubble.vue`、`interpace-frontend/src/constants/chat-modes.ts`
- **做法**：在优化后的简历消息旁提供「下载 Word」按钮。
- **实际改动**：
  - 新增 `ResumeDownloadButton`：先调导出接口，再用 axios 取 Blob 触发下载。**两步走的原因**：资源接口要 `Authorization` 头，`<a href>` 带不上——与附件下载同一条路（T3.4 踩过同一个坑）。
  - 显示条件：助手消息、已落库、不在生成中、模式为简历优化（`select_model=3`）、正文非空。模式数字收敛成 `RESUME_MODE` 常量，不再散落魔法数字（顺带把 4 / 5 也命名了）。
- **验收结果**：`pnpm run build`（含 `vue-tsc`）通过。
- **未验证**：浏览器里点「下载 Word」的实际下载（可以和 T6.2 的确认卡片一起测）。
- **依赖**：T6.4。

### T6.6 简历优化完成后跳转模拟面试

- **状态**：待办
- **做法**：在优化结果上提供「直接开始模拟面试」入口，带上当前简历上下文切到模拟面试模式。
- **验收**：点击后进入模拟面试且简历信息被带入。
- **依赖**：T6.5、T7.4。

---

## 9. 阶段 7：面试模块 · 模拟面试（含语音）

对应流程图：用户上传简历或在提示词中体现简历信息 → AI 提取简历信息 → 调用语音识别和语音合成模型进行一对一语音面试 → 面试完成后调用面试复盘。

`interviews` 表已经建好（含 `qa_object` / `status` / `message_id` / `interview_duration`），但全项目**没有一处写入**，只有读。本阶段要先把这个洞补上。

**技术选型约束**：多轮面试问答与「结束触发复盘」是状态流转，用 LangGraph 编排（节点负责提问、记录问答、收尾），LangChain 负责模型、提示词与记忆。

**面试官形象：三步走（先轻后重）**

数字人本质是 TTS 之上的渲染层，所以整条路线挂在 T7.6 的语音能力上，不单独提前做。**每一步验证过再走下一步**：

1. **不做数字人**（T7.6 / T7.7）：先把纯语音面试做出来——有声音、一个静态面试官头像、一条音频波形就够了。目标是验证用户是不是真的需要「看见人说话」。
2. **确有需要，再加动效**（T7.9）：一张静态头像 + 音频驱动的轻微动效（呼吸、眨眼、口型 3 档开合）。成本极低、临场感提升明显，**这一步性价比最高**。
3. **验证过价值，再考虑重方案**（T7.10，条件任务）：Live2D / Rive / 云 SDK。四条路线的取舍与成本见该任务。

两处「留口子」是这条路线成立的前提，已写进 T7.6 / T7.7：TTS 响应预留 `viseme_timeline` 字段、`src/components/avatar/` 目录与可订阅的播放状态。现在做几乎零成本，漏了就要返工。

### T7.1 语音方案选型

- **状态**：已完成（2026-09-29）
- **优先级**：最高风险项，必须最先做
- **选项**：(a) 浏览器原生 `Web Speech API`——零成本、无需后端，但中文识别质量参差、Safari 支持差；(b) 云端 ASR + TTS——效果好、可控，但要选厂商、要付费、要新增依赖与密钥配置。
- **结论（2026-09-29）**：采纳 **(b) 云端方案**，**ASR 与 TTS 都用火山引擎**（TTS：双向流式语音合成 WebSocket；ASR：实时语音识别 WebSocket），且**第一版就做 WebSocket 流式**，不做「整句返回」的简化版。
  - ASR 文档：`docs/DoubaoVoice/bidirectional-streaming-automatic-speech-recognition-websocket`，接入点 `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`。
  - 同厂商的理由：一套鉴权、一套文档、协议家族相同（下面说的二进制帧格式两边通用），两边的坑可以共用一套排查经验。
- **从官方文档核实到的事实**（2026-09-29 实读，不是二手转述）：
  - 接入点 `wss://openspeech.bytedance.com/api/v3/tts/bidirection`；鉴权用请求头 `X-Api-Key`，模型版本用 `X-Api-Resource-Id`（`seed-tts-2.0` 合成大模型 / `seed-icl-2.0` 声音复刻）。
  - 响应事件齐全：`ConnectionStarted` / `SessionStarted` / `TTSSentenceStart` / `TTSResponse`（音频分片）/ `TTSSentenceEnd` / `TTSSubtitle`（字幕）/ `SessionFinished` / `ConnectionFinished`，另有 `SessionCanceled` / `SessionFailed` 等异常事件。
  - `audio_params.format` 支持 `mp3 / pcm / ogg_opus / wav`，**文档明确建议流式场景用 `pcm`，不建议 `wav`**。
- **对「口型同步」的关键结论（这是 D13 里点名要评估的那一项）**：
  - **该服务不提供 viseme / 唇形 / 口型字段**（文档全文搜 `viseme`、`唇形`、`口型` 均为 0 命中）。
  - **但它提供比 viseme 更底层的两类时间戳**：请求参数 `enable_subtitle`（开启字幕服务，**返回字级别时间戳**，仅中英文）与响应里的 `words`（字级别时间戳）、`phonemes`（**音素相关时间戳**）。
  - **结论：T7.9 的口型数据来源要改。** 原计划是「优先 viseme，厂商给不了就退回前端 Web Audio 分析音量」；现在应该改成**优先用音素时间戳在本地做 phoneme→口型的映射**（就是一张映射表 + 时间线对齐，几十行代码），Web Audio 音量分析只当最后兜底。这比原方案精度高一档，而且不用引第三方口型引擎。
- **对 T7.6 / T7.7 的拆分影响**：合成侧确定用「后端代理 + WebSocket 连火山」，**API Key 不能下发到浏览器**；ASR 与「音频怎么回前端」见 D13，定了就能动 T7.6。
- **ASR 侧核实到的事实（同样实读官方文档 + 官方 Python 参考实现）**：
  - 请求体三段：`user` / `audio`（`format`、`codec=raw|opus`、`rate` 默认 16000、`bits` 默认 16、`channel` 默认 1）/ `request`（`model_name=bigmodel` 必填，`show_utterances`、`enable_punc`、`enable_itn`、`enable_ddc` 等开关）。
  - **VAD 内置**：`end_window_size`（默认 800ms，推荐 800~1000）静音判停即触发分句，`force_to_speech_time`（推荐 1000）可规避开头静音导致的过早判停。这对「面试官等候选人说完再回答」是关键能力——**不需要我们自己写静音检测**。
  - 鉴权：握手头 `X-Api-Key` + `X-Api-Resource-Id`（2.0 小时版 `volc.seedasr.sauc.duration` / 并发版 `volc.seedasr.sauc.concurrent`）+ `X-Api-Request-Id`（随机 UUID）。
- **两侧共用的二进制帧协议（最容易踩坑的地方，官方文档自己把它列为排查第 1 项）**：
  - 每帧 = 4 字节帧头 + 可选扩展字段 + 4 字节 payload 长度 + payload。帧头：byte0 `(version<<4)|header_size`、byte1 `(msg_type<<4)|flags`、byte2 `(serialization<<4)|compression`、byte3 保留。
  - **`payload_size` 必须填压缩后的字节数**（填原始长度会导致服务端读帧错位）；ASR 侧 JSON 与音频块都要 gzip，TTS 侧官方参考实现默认不压缩。
  - **ASR 末包规则（`session unexpectedly finished` 的头号原因）**：最后一个音频包的 flags 必须是 `NEG_WITH_SEQUENCE` 且 `seq` 取**负值**；末包判定要基于「分段总数」而不是「这次读到的长度不足」，否则音频长度正好是分包整数倍时会漏标记；所有退出路径都要 best-effort 补发负序号末包。
  - 服务端 8 秒收不到下一个包就结束会话，所以**收发必须是两个并发任务**，发送方绝不能阻塞等回包。

### T7.2 面试会话状态机设计

- **状态**：已完成（2026-09-29）
- **目标**：先设计，不写代码。
- **需要定的点**：面试何时创建、一问一答怎么追加、用户中途退出或停止（与 T1.8 交叉）时怎么收尾、`status=2`（异常）何时使用。
- **结论（状态迁移说明）**：
  1. **创建**：用户在面试间选「模拟面试」（`select_model=4`）发出消息时，若当前会话**没有进行中的面试**，就新建一条 `interviews`（`status=0`、`qa_object=[]`），并把这条消息标成入口（消息 `status=1` + `interview_id`）。若会话里已有进行中的面试，这条消息算**同一场面试的后续轮次**，不新建。
  2. **一问一答的语义**：**提问来自面试官（助手），回答来自候选人（用户）**。助手每回复一次，就往 `qa_object` 追加一条 `{id, question, answer: "", created_at}`；用户的下一条消息回填到**最后一条 `answer` 为空**的条目上。这与流程图里的语音面试一致，也是复盘（阶段 8）要读的数据。
  3. **用户连续发两条消息**（中间没有面试官提问）时，第二条无处可挂——**直接忽略并记日志**，不新建「空提问」的条目污染数据。
  4. **结束**：用户点「结束面试」（T7.8 提供入口）→ `status=1` 并冻结 `interview_duration`。v1 只做手动结束，轮次上限留作可选。
  5. **中途停止生成（与 T1.8 对齐）**：用户点停止 → 该条消息 `status=2`（既有语义），但**面试记录不置异常**，已生成的问答照常保留。理由：停止只是不想听这一段，不代表这场面试坏了；把「停止」等同于「异常」会让用户不敢用停止按钮。
  6. **`status=2`（异常）**：留给「服务端写入过程中真的失败」这类情况，v1 实际上用不到，但取值先占住，避免以后加值引起歧义。
  7. **时长**：每次有问答写入时把 `interview_duration` 更新为「当前时间 − 创建时间」，结束时冻结。
- **对 T7.4 / T7.5 的拆分影响**：两者都在**流式收尾**里做（与 T5.5 题库落库同一个位置和套路），不需要新接口——入口消息、详情接口（`GET /interviews/{id}`）与前端卡片**都已经存在**，只是从来没被写入过。
- **与语音的关系（重要）**：T7.4 / T7.5 **只处理文本**。语音层（T7.6 / T7.7）的职责是把「用户说的话」变成 `request_text`、把「面试官的话」变成音频播放，**不碰数据层**。所以先把数据层做完，语音接上来时不用返工。

### T7.3 面试主考提示词模板 seed

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/prompt_template_seed_service.py`
- **做法**：补 `interview` 场景下 `interview_host` 的模板，包含提问风格、追问策略、结束条件。
- **实际改动**：
  - 新增 `INTERVIEW_HOST_TEMPLATE`（`interview_host` / `interview`），并把 `INTERVIEW_COMMON_TEMPLATE` 也 seed 到 `interview` 场景（公共模板按 scene 存，与 `resume` 共用同一份正文）。
  - 提问策略写死的几条：**一次只问一个问题**、先一句话反馈再问下一题、难度递进（基础 → 项目深挖 → 开放设计）、同一知识点最多追两次、跑题要拉回。
  - **因为输出会给 TTS 念出来**，模板里专门加了一节表达约束：口语化、不要 Markdown 标题/编号/表格/代码块、单次回复 2~4 句。这条以前不会有人想到，是 T7.1 定了语音方案之后才成为硬约束。
  - 另加两条安全/体验约束：不替候选人回答、不问与岗位无关的隐私信息（年龄、婚育、家庭、政治倾向）。
  - 已执行 seed：`[公共:interview] 写入 v1`、`[interview_host:interview] 写入 v1`，缓存已刷新。
- **验收结果**：模板能被 `get_full_prompt("interview_host", "interview")` 查到；`pytest tests/test_prompt_template_seed.py` 4 passed。
  - **真实模型 3 场 × 3 轮，合规 9/9**（检查项：无 Markdown 标题、无代码块、问题数 ≤2、单次回复 ≤400 字）。实际表现符合预期：开场会说明面试流程，每次只问一个问题，候选人答完先给一句反馈再问下一题，答不上来给提示后换题，跑题时用一句话拉回来。
  - 测试脚本里用的是**固定回答**，和模型动态提出的问题并不总是对得上（比如模型问 FastAPI 处理流程、脚本答的是 GIL）。这反而暴露了一个好现象：模型没有顺着答错的内容跑偏，而是明确指出「我问的不是这个」并换问法或给提示——这正是模板里「跑题要拉回」那条在生效。
- **未验证**：浏览器里的实际观感（等你验）。
- **依赖**：T1.3。

### T7.4 后端创建面试记录与入口消息

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_service.py`（新增）、`interpace-backend/app/services/stream_chat_service.py`、`interpace-backend/tests/test_interview_records.py`（新增）
- **做法**：从「模拟面试」模式发起时创建 `interviews` 行，并把入口消息的 `status=1`、`interview_id` 写上——这样前端已有的「查看面试记录详情」卡片才能真正被点开。
- **实际改动**：
  - 新增 `InterviewService`：`get_running_interview()` / `create_interview()`，按 T7.2 的约定——**会话里没有进行中的面试才新建**，否则算同一场面试的后续轮次。
  - `stream_chat_service` 在流式收尾里调用 `_persist_interview_round_if_any()`（与 T5.5 题库落库同一个位置和套路），`done` 事件新增 `interview_id` 字段。
  - 前端 `useSessionStreamSender` 新增可选的 `setResult` 回调，把 `done` 事件里的结构化产物（题库 / 画像 / 面试记录）交给各房间；面试间用它**让面试卡片当场出现**，不必等刷新（之前只有刷新后才会亮）。
  - `interviews` 表**自建库以来第一次被写入**。`delete_session` 本来就删面试记录，所以会话删除链路无需改动。
  - **首条消息就被停止/报错时不建记录**：否则会留下一条没有内容的空面试，用户点开卡片只看到空白。
- **验收结果**：`pytest` **111 passed**（新增 6 个用例）；服务已加载（路由无变化，详情接口本来就在）。
  - 用例覆盖：首条消息建记录 + 入口消息 `status=1` + `interview_id` 正确 + 详情接口能取回；同一会话第二轮不新建记录。
  - **顺手修了一个测试暴露的问题**：`test_stream_chat_routing` 的清理函数原来只删消息与会话，现在「模拟面试」会真的写 `interviews`，外键会把清理挡住——已按「先删面试记录再删消息」的顺序修好（生产侧 `delete_session` 本来就是这么做的）。
- **未验证**：前端「查看面试记录详情」卡片在浏览器里的实际点击效果（等你验）。
- **依赖**：T7.2、T7.3。

### T7.5 后端一问一答落库

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_service.py`、`interpace-backend/tests/test_interview_records.py`
- **做法**：每轮问答追加进 `qa_object`，同步更新 `updated_at` 与 `interview_duration`。
- **实际改动**：
  - `record_round()` 的固定顺序：**先回填上一题的答案 → 再追加这一轮的新问题**。一次请求里同时完成两件事，所以「一问一答」是 AI 提问 + 用户回答（与 T7.2 的语义一致）。
  - 用户连续发两条消息（中间没有面试官提问）时，第二条**无处可挂 → 忽略并记 warning**，不新建「空提问」条目污染数据。
  - 时长口径：每次写入把 `interview_duration` 更新为「当前时间 − 创建时间」。
  - **踩到一个 SQLAlchemy JSON 列的坑（已修，值得记）**：回填答案时如果「在原来的 dict 上原地改、再把同一个列表赋回去」，SQLAlchemy 比较新旧值发现相等 → **不会产生 UPDATE**，答案看起来写进去了、其实没落库。解法是把每条 `dict()` 成新对象再整体赋回。测试先失败了一次才暴露出来。
- **验收结果**：`pytest` **111 passed**（新增 6 个用例）。
  - 多轮：两轮后 `qa_object` 长度为 2，第一条有答案、第二条待答，`interview_duration` 有更新。
  - **中途停止的两条路径都有确定性测试（直接测服务层，避开流式时序抖动）**：首条就被停止 → 不建记录；后续轮次被停止 → 答案保留、半截回答不变成面试题、面试状态仍是「进行中」（停止不等于异常）。
- **未验证**：真实模型多轮问答的落库（等你验或我下一步补真实模型验证）。
- **依赖**：T7.4。

### T7.6 后端语音识别与语音合成接口

- **状态**：已完成（2026-09-29）。**ASR 与 TTS 都已通过真机验证，并跑通「文字 → 语音 → 语音 → 文字」完整往返。**
- **做法（2026-09-29 按「第一版就做 WS 流式」重写）**：新增**后端 WebSocket 端点**（而不是两个 POST 接口），后端作为火山引擎的代理：
  - `WS /sessions/{session_id}/speech/stream`：前端把麦克风音频分片推上来，后端转发给火山 ASR；识别出完整一句话后跑面试 Agent，再把面试官的话转成 TTS 音频分片推回前端。
  - **为什么必须后端代理**：`X-Api-Key` 不能下发到浏览器；而且这里要串起「ASR → Agent → TTS」三段，放前端等于把编排逻辑散到浏览器里。
  - 拆成三个可独立测试的模块：`app/services/volc_speech/protocol.py`（帧编解码）、`asr_client.py`、`tts_client.py`；路由层只做连接管理与转发。
  - 依赖：`websockets`（**已随 `uvicorn[standard]` 装在环境里，实测 16.1.1，不新增安装体积**；会补进 `pyproject.toml` 显式声明，避免将来传递依赖变化时被动）。
- **留口子（给 T7.9）**：合成接口的响应结构里**预留 `viseme_timeline` 字段（先返回 `null`）**——它承载「第几毫秒发哪个口型」的序列。现在不实现不填，但字段先占位，这样将来接入口型同步是**新增数据**而不是破坏性改接口。选型时也按 D13 的要求确认厂商能否提供这个数据。
- **留口子修订（2026-09-29）**：`viseme_timeline` 将来由「TTS 返回的 `phonemes` 时间戳 → 本地音素→口型映射」填充；T7.6 这一版**先把 `phonemes`/`words` 原样透传下去（或至少记录下来）**，别把它们丢掉，否则 T7.9 要重新调一次 TTS 才能拿到。
- **接口变更**：是。
- **验收**：① 帧编解码有纯函数级回归测试（往返一致、末包负序号、payload 长度取压缩后值）；② 用**本地假火山服务**跑通「推音频 → 出识别结果 → 出 TTS 音频分片」；③ 真实火山服务需要凭证，届时另做一次端到端验证。
- **依赖**：T7.1。
- **实际改动（2026-09-29）**：
  - 涉及文件：`app/services/volc_speech/protocol.py`（帧编解码）、`asr_client.py`（实时语音识别）、`tts_client.py`（双向流式合成）、`app/services/speech_turn_service.py`（一轮回合）、`app/services/speech_stream_service.py`（WS 编排）、`app/routes/speech_routes.py`（WS 路由）、`app/core/settings.py`（新增 6 个语音配置项）、`pyproject.toml` + `uv.lock`（显式声明 `websockets`）、`tests/test_volc_protocol.py`、`tests/test_volc_speech_clients.py`、`tests/test_speech_stream.py`。
  - `protocol.py`：ASR / TTS 共用的帧编解码（两边的帧格式属于同一协议家族，合成一份避免两套实现漂移）。
  - `asr_client.py`：建连 → 首帧（序号 1）→ 音频包（序号自增）→ 末包（**负序号 + NEG_WITH_SEQUENCE**）；`stream_audio()` 用**收发两个并发任务**（官方硬性要求：发送方不能阻塞等回包）；`finish()` 幂等补末包，覆盖所有退出路径。
  - `tts_client.py`：`StartConnection → StartSession → TaskRequest → FinishSession → FinishConnection` 全流程；`enable_subtitle=True` 拿字级别时间戳，并把 `phonemes`（音素时间戳）解析出来交给上层——**这是 T7.9 口型同步的输入，不能丢**。
  - **WS 端点与编排**：`WS /sessions/{session_id}/speech/stream?session_model=1&token=...`，**token 走查询参数**（浏览器建 WebSocket 带不了自定义请求头），鉴权与归属校验**在 accept 之前**完成，不给未授权连接开门。
  - `speech_turn_service`：一轮 = 落用户消息 → 调面试 Agent（**复用文字链路同一套提示词与编排图**，只是改成非流式 invoke，因为要拿完整文本才能送 TTS）→ 回写 → 追加面试记录。**语音面试与文字面试在库里是同一种数据**，阶段 8 的复盘不用区分来源。
  - `speech_stream_service`：`ASR → Agent → TTS` 串接，按**「一句话一趟 ASR 会话」**组织——火山要求音频流持续有包、8 秒断会话，而面试天然一问一答，按句开会话既避开超时又不用自己写静音检测（服务端 VAD 会分句）。
  - 同步的 DB + 大模型逻辑统一用 `asyncio.to_thread` 丢到线程里，不阻塞事件循环；WS 生命周期比一次请求长，所以每次都自己开一个 DB Session。
  - 前端消息协议：控制消息走文本帧 JSON（`start_utterance` / `end_utterance` / `text`），音频上下行走二进制帧；下行事件有 `asr_partial` / `asr_final` / `reply` / `tts_start` / `tts_subtitle` / `tts_end` / `error`。`text` 消息可跳过 ASR 直接喂文字，用于联调与降级。
- **验收结果**：`pytest` **125 passed**（本轮新增 14 个用例）。
  - 假服务端**自己按官方协议拼字节**（不复用被测代码），所以验的是真东西：首帧带 `X-Api-Key` / `X-Api-Resource-Id` / `X-Api-Request-Id`、音频序号实测为 `[2, 3, -4]`（末包负序号）、TTS 事件顺序实测为 `[1, 100, 200, 102, 2]`、音频分片与音素时间戳都能取回。
  - **过程中修掉两个真 bug（都属于官方排查清单点名的类型）**：① 音频包帧头声明了 gzip，实际发的却是原始 PCM，服务端解压必然失败——改成在构建器内部压缩；② 错误帧漏写 `error_code` 字段，导致解码错位。两个都补了回归用例。
  - **WS 端点测试**（换成假 ASR / TTS + 桩模型）走的是**真实 WebSocket**：推音频 → 收到 `asr_partial`/`asr_final` → 收到 `reply` → 收到两段音频与带音素时间戳的 `tts_subtitle` → `tts_end`；音频确实转发给了 ASR；**库里的消息与面试记录与文字链路完全一致**；无效 token 在 accept 前被拒。
  - 写测试时又踩了一次「声明 gzip 却没压缩」的坑（这次在假服务端里），顺手修了——说明这类错误确实容易发生，两个方向都值得留测试。
- **真机验证结果（2026-09-29，凭证已就位）**：
  - **ASR 通过**：官方 16k 示例音频（14.4 秒 / 72 个 200ms 包）识别正确，`utterances` 带 `start_time` / `end_time` / `definite`——**「服务端 VAD 能按句判停」这条设计前提成立**，不需要自己写静音检测。
  - **TTS 通过**：音色 `zh_male_liufei_uranus_bigtts` + 资源包 `seed-tts-2.0`，17 字合成出约 3.0 秒 PCM（144 KB）。
  - **完整往返通过**：把 TTS 合成出来的音频重采样到 16k 喂回 ASR，识别结果与原文**一字不差**（「你好，我是今天的面试官，我们开始吧。」）。这条打通的就是 T7.6 要交付的能力。
  - **真机一共揪出 5 个问题，全部属于「假服务永远测不出来」的那一类**：
    1. **`speaker` 必须放在 StartSession 的 `req_params` 里**；放到 TaskRequest 会报
       `resource ID is mismatched with speaker related resource`。这个报错**非常误导**——
       看起来像「资源包买错了」，实际是参数放错了层级，为此多花了好几轮探测。
    2. **必须主动发 `FinishSession`**：这是「文本流式输入」接口，不发明文结束标记，服务端会一直
       等后续文本——音频照流，但**永远不补句子结束与会话结束事件**，客户端只能干等超时。
    3. **`_receive` 原先没有超时**：一次失败的合成会让连接挂到调用方被强杀（实测卡了 180 秒）。
       已加超时，并补了「服务端沉默时 close() 也必须返回」的回归用例。
    4. **ASR 判「一句话说完了」要看 `utterances[-1].definite`**，不能只看「有没有 utterances」：
       快速推流时中间结果同样带 utterances，只看有无会把 3 句话判成 **9 次**最终结果，一轮面试被切碎。
    5. `result.text` 是**会话累计文本**（会把上一句带上），必须优先取 `utterances[-1].text`；
       解析时间戳时还踩了 `0.0 or x` 的 falsy 坑（起始时间就是 0，被「或」吞掉）。
  - **一个没解决的问题（已记录，影响 T7.9）**：即使 `enable_subtitle=True`，返回的 `words` 与
    `phonemes` 都是**空数组**——当前音色/账号下**拿不到字级与音素级时间戳**。开关放会话级、任务级、
    两边都放都试过，多句文本也试过，都是空。所以 **T7.9 的口型同步只能走「前端音量分析兜底」**
    （原计划的次选方案）。代码仍会把 `words`/`phonemes` 原样往下传，换成支持字幕的音色时可直接启用。
- **未验证**：浏览器里的端到端语音面试（要等 T7.7 前端做完）。
- **依赖说明**：`websockets` 本来就随 `uvicorn[standard]` 装在环境里（16.1.1），**本轮没有新增任何安装体积**；已在 `pyproject.toml` 显式声明并更新 `uv.lock`，避免将来传递依赖变化把我们带崩。

### T7.7 前端语音面试 UI

- **状态**：已完成（2026-09-29）。前端构建通过；**输入区布局与语音入口经用户在浏览器确认**（按 `docs/img.png` 调整后确认可用）。
- **做法**：录音按钮 + 播放 AI 语音 + 识别结果回填输入框；面试官区域渲染**静态头像 + 音频波形**——这就是三步走里的第 1 步，本阶段**不做任何形变动画**。
- **做法补充（2026-09-29，定了 WS 流式之后）**：
  - 前端不再走「录完整段再上传」，而是**边录边推**：用 `AudioWorklet` 拿原始 PCM（重采样到 **16kHz / 16bit / 单声道**，与 ASR 声明的 `audio` 参数一致），按 ~200ms 一包通过 WebSocket 推给后端。
  - 播放侧不再用 `<audio src>`：TTS 回来的是 PCM 分片，用 **Web Audio 的 `AudioBufferSourceNode` 排队播放**（分片有先后，不能各播各的）。播放状态（是否在播、已播到第几毫秒）要能被头像层订阅，这是 T7.9 口型同步的输入。
  - 「面试官说完再开始录」这条时序由后端控制：后端在 TTS 结束后推一个「可以说下一句」的事件，前端据此切换录音状态，避免和后端的 VAD 抢判停。
- **实际改动（2026-09-29）**：
  - 新增 `src/api/speechStream.ts`：WebSocket 客户端（token 走查询参数、二进制帧收音频、文本帧收事件），含 `http(s) → ws(s)` 的地址换算。
  - 新增 `src/utils/pcm.ts`：重采样到 16k（窗口平均做抗混叠，不是直接抽点）、Float32↔Int16 转换（越界样本截断而非回绕）、RMS 音量。
  - 新增 `src/composables/useVoiceInterview.ts`：状态机 `idle → recording → waiting → speaking → idle`。麦克风用 `AudioWorklet`（内联源码 + Blob URL 加载，不为它单独配置构建产物路径）按 200ms 分包上推；下行 PCM 分片用 Web Audio 排队无缝播放；播放状态（`isPlaying` / `currentMs` / `durationMs` / `levels`）集中暴露给头像层订阅——**这就是给 T7.9 留的口子**。
  - 新增 `src/components/avatar/InterviewerAvatar.vue`（**静态头像**，刻意不做形变动画）+ `src/components/speech/VoiceWaveform.vue`（音量柱）+ `src/components/speech/VoiceInterviewPanel.vue`（面板：开关、录音按钮、识别结果回填、**文字兜底输入**）。
  - `InterviewRoom.vue` + `ChatInput.vue`：**语音入口放进输入框底部那条控制带**，与「文件选择」「发送」同处一排（文件在左、发送在右，这两个的位置一个像素没动），语音按钮紧挨文件按钮右侧。点它会自动把模式切到「模拟面试」，切走模式或离开页面自动断开（不留后台连接与麦克风）。
    - **按效果图重构（`docs/img.png`）**：输入区与功能条合并成**一个圆角输入容器**——输入框在上、功能条在下；功能条左侧是「＋附件」与「语音面试」胶囊，右侧是「模式选择」与「发送」。附件按钮由回形针改为「＋」。模式选择器也从输入框上方搬进了这条功能条，并收窄尺寸以免挤走发送按钮。
    - **语音按钮的显示条件**：只有**模拟面试**模式才显示（用户明确要求）。因此也去掉了「点击自动切模式」的逻辑——按钮本来就只在该模式下存在。
    - **真机反馈改动**：最初写成「只有处于模拟面试模式才显示入口」，结果用户在默认的「快速回答」模式下根本看不到按钮——**入口不该依赖用户先猜对模式**；随后按用户要求把它从聊天区上方搬到了输入框底部。
    - **同时修了一个自己引入的样式问题**：右侧容器被加了内边距、又漏了 `min-height: 0`，导致面试间右侧布局错位；现在容器不加内边距，聊天区与学习室保持一致的排版。
    - **布局规则（用户明确要求，两个房间都适用）**：**输入框固定在底部不随页面滚动，可滚动的只有右侧消息列表**。落地方式是四处收口：房间与右侧列 `overflow: hidden`、`ChatWindow` 补 `min-height: 0`（否则消息列表的自动最小高度会把滚动条顶到整页）、`ChatInput` 加 `flex-shrink: 0`（窗口变矮时不压扁输入框）、语音面板 `flex-shrink: 0` + `max-height: 46vh`（内部滚动，不挤走输入框）。学习室是同构结构，一并补上。
  - `vite.config.ts`：代理加 `ws: true`。**不加的话开发环境 WebSocket 握手会被直接拒掉**，前端只会看到「连接失败」，且报错很不直观。
- **验收结果**：
  - `pnpm run build`（含 `vue-tsc`）**通过**。
  - **整条链路端到端验证通过**（用脚本模拟前端连我们自己的后端 WebSocket，走真实火山 ASR / 真实 DeepSeek / 真实 TTS）：
    推 3.0 秒音频 → ASR 识别正确 → 面试官给出开场白与第一题（口语化、无 Markdown、一次一问）→ 回传 **747KB ≈ 15.6 秒**音频 → 面试记录落库 1 条问答 → 会话清理正常。生产的音频存在 `/private/tmp/voice_e2e_reply.wav`。
- **说明**：整条链路的后端部分已用脚本端到端验证；界面布局已由用户确认。若实际录音或播放在某个浏览器上异常，按 T7.9 的口型数据来源一并排查（都依赖同一份播放状态）。
- **给运维留一条**：生产用 Nginx 托管前端时，`/api` 的 **WebSocket 升级头（`Upgrade`/`Connection`）也要配**，否则语音面试在线上会静默失败——已记进 T11.3。
- **留口子（给 T7.9）**：面试官区域按「可以塞进一个头像层」的结构来组织——`src/components/avatar/` 目录先建好，本阶段只渲染一个静态头像占位；播放语音的状态（是否在播、播放到第几毫秒）要能被头像层订阅，不要在录音按钮组件里写死。
- **涉及文件**：新增 `src/components/speech/*`、`src/components/avatar/*`；`src/views/InterviewRoom.vue`（已 409 行，必须拆子组件）
- **验收**：能完整完成一轮纯语音问答。
- **依赖**：T7.6。

### T7.8 面试结束触发复盘

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_service.py`、`app/routes/interview_routes.py`、`app/schemas/interview_evaluation_schemas.py`、`tests/test_interview_evaluation.py`、`interpace-frontend/src/api/chat.ts`、`src/types/chat.ts`、`src/components/chat/ChatInput.vue`、`src/components/chat/ChatWindow.vue`、`src/components/evaluation/EvaluationPanel.vue`、`src/views/InterviewRoom.vue`
- **做法**：面试结束（用户点结束或达到设定轮次）时调用阶段 8 的复盘能力，并把面试状态置为已结束。
- **实际改动**：
  - 新增 `POST /interviews/{id}/finish`：状态置为已结束并**冻结时长**。**幂等**——重复点不报错、不改数据，只返回 `already_finished=True`（用户手滑点两下是常事，第二次报 409 只会让人以为出错了）。
  - **「结束」与「生成复盘」拆成两个请求**：`finish` 瞬时返回，复盘由前端紧接着调既有接口生成。好处是结束不会卡十秒、生成复盘可以有独立等待状态、失败了能单独重试；也直接复用了已经测过的复盘接口。
  - 前端「结束面试」按钮放在**输入框底部工具条**（挨着「语音面试」，与已确认的布局一致，不新增独立按钮栏），只在「模拟面试」模式且本会话已有面试记录时出现。
  - 交互链路：点「结束面试」→ 提示里带**时长与问答轮数** → 自动切到「面试复盘」模式 → 自动生成并展示复盘。
- **验收结果**：`pytest` **146 passed**（新增 2 个用例：结束幂等且时长冻结、别人的面试不能结束）；`pnpm run build` 通过；运行中的后端已加载 `/interviews/{id}/finish`。
- **未验证**：浏览器里的实际点击链路（结束 → 自动切模式 → 看到复盘）。
- **依赖**：T8.2。因此本任务与阶段 8 的实施顺序可以交叉，不必严格串行。

### T7.9 面试官形象的轻量动效（数字人第 2 步）

- **状态**：待办
- **前提**：这是「面试官形象」三步走的第 2 步。第 1 步是纯语音面试，已经在 T7.6 / T7.7 里；第 3 步见 T7.10。
- **目标**：用极低成本拿到「对面坐着一个面试官」的临场感，先验证用户到底需不需要「看见人说话」，再决定要不要投入重方案。
- **做法**：静态面试官头像 + 音频驱动的轻微动效——呼吸起伏、随机眨眼、口型按档开合（3 档足够）。口型数据优先用 T7.6 预留的 `viseme_timeline`；厂商给不了就退回前端 Web Audio 分析音量兜底。
- **做法修订（2026-09-29，读完火山引擎文档后）**：口型时间线的**数据来源改为「TTS 返回的音素时间戳 → 本地映射成口型档位」**，而不是等厂商给 viseme（火山引擎不提供 viseme）。映射表 + 时间线对齐是本地几十行代码的事，精度明显高于音量分析；前端 Web Audio 音量分析只保留为「时间戳缺失时」的兜底。T7.6 里的字段名仍叫 `viseme_timeline`（它承载的已经是映射后的口型时间线）。
- **做法再次修订（2026-09-29，真机验证之后）**：**时间戳这条路走不通了**——真机实测 `enable_subtitle=True` 时 `words`/`phonemes` 返回的都是空数组（当前音色/账号拿不到），换开关层级与多句文本都无效。所以 **T7.9 这一版就按「前端 Web Audio 音量分析 → 3 档口型开合」实现**（原计划的兜底方案），不要再等音素时间戳。将来若换到支持字幕的音色，`words` 已经在链路里原样透传，届时把映射接上即可，不用返工。
- **涉及文件**：`src/components/avatar/*`
- **不做**：不引入 Live2D / Rive / 云 SDK，不做表情与动作库。这一版只验证价值。
- **验收**：播放面试官语音时口型与声音基本同步、不眼晕；用户能明显感到「在和人对话」而不是「在听录音」。**口型对不上宁可不做**——音画不同步的负体验比没有动画更强。
- **依赖**：T7.7（以及 T7.6 预留的 viseme 口子）。

### T7.10 数字人重方案（条件任务，验证通过再做）

- **状态**：待办（**条件触发**：只有 T7.9 的用户反馈证明「形象确实有价值」，才启动本任务）
- **背景**：可选路线与取舍如下。

  | 路线 | 渲染位置 | 美术成本 | 运行费用 | 适合场景 |
  | --- | --- | --- | --- | --- |
  | 云厂商数字人 SDK | 云端 WebRTC 推流 | 低（平台生成） | **按时长计费，属持续成本** | 要写实形象、想最快上线 |
  | Live2D + PixiJS | 浏览器 WebGL | **高**（模型绑定是全流程最贵的一环） | 免费 | 二次元形象、长期迭代 |
  | Rive / Spine | 浏览器 Canvas/WebGL | 中 | 免费 | 扁平卡通 IP、移动端 |
  | 序列帧 / Canvas | 浏览器 Canvas | 低 | 免费 | 极简头像 |

- **成本要点**：一场模拟面试 20~40 分钟，云方案按分钟计费是**持续成本**，必须和预计用户量一起算；Live2D 的美术绑定则是**一次性大投入**。具体厂商与报价需自行核实，这类产品价格与 SDK 能力变动很快，不要照抄旧数据。
- **无论选哪条都躲不开的三件事**：
  - 口型同步的数据来源——TTS 返回 viseme 时间戳（推荐）或前端 WASM 分析（精度差一档）；
  - **打断逻辑**——用户开口说话要立刻停 TTS、停动画，可直接复用 T1.8 建立的停止机制；
  - 资源体积与 CDN——Live2D 模型动辄数 MB，必须分片 + CDN，否则拖慢面试页首屏。
- **不要做**：不要因为「有数字人」就顺手把它塞进学习室的知识精讲。那是语音播客场景，用户很可能不看屏幕，投在这里回报最低。
- **为什么排在最后**：面试产品的核心价值是问题质量与复盘准确度，形象是最容易过度投入、回报最不确定的部分。
- **依赖**：T7.9 的验证结论。

---

## 10. 阶段 8：面试模块 · 面试复盘

对应流程图：面试复盘 → 用户上传真实的语音音频让 AI 复盘分析 → 生成复盘结果并给出改进建议；以及模拟面试结束后的自动复盘 → 针对难点问题输出结构化知识卡片 + 语音播客讲解。

**技术选型约束**：复盘涉及「取面试记录 → 评分 → 抽薄弱点 → 给建议」多节点流转，用 LangGraph 编排，LangChain 承载模型与提示词；与 T7.8 的自动复盘共用同一张图，不要写两份。

### T8.1 面试评测提示词模板 seed

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/prompt_template_seed_service.py`、`interpace-backend/app/services/interview_evaluation_service.py`（新增，契约与解析器）
- **做法**：补 `evaluation` 场景下 `interview_evaluator` 的模板。
- **实际改动**：
  - 新增 `INTERVIEW_EVALUATION_TEMPLATE`（`interview_evaluator` / `evaluation`），并把 `INTERVIEW_COMMON_TEMPLATE` seed 到 `evaluation` 场景（面试侧三个场景共用一份公共背景）。
  - 输出契约 `EVALUATION_JSON_CONTRACT`（`summary` / `weak_topics` / `suggestions`）仍由**提示词与解析器共用一份**，解析器不抛异常。
  - 模板里写死了几条质量约束，这是评测能不能用的关键：总结必须**先给结论再给依据**、不要客套话；薄弱点必须是**知识点级名词短语**（明确禁止「表达能力」这类没法训练的结论）；建议必须**可执行**（禁止「多看书」）；候选人说不会或留空时要点名。
  - 已执行 seed：`[公共:evaluation] 写入 v1`、`[interview_evaluator:evaluation] 写入 v1`。
- **验收结果**：**真实模型 3/3 解析成功**，内容质量符合预期：
  - 能准确定位「MySQL 索引失效答不出来」是硬伤（并指出「简历自报会 MySQL 却答不出，比不会更糟」这种面试官视角的判断）；
  - 薄弱点都是知识点级（`MySQL 索引失效场景`、`GIL 释放时机与 CPython 并发模型`、`短码生成与分布式 ID`），没有出现泛泛的软技能结论；
  - 建议全部带具体动作（建 100 万行表逐条 `EXPLAIN`、写三组 benchmark、按 STAR 整理真实案例），且有一条明确写了「没有数字就标出待补充，**不要编造**」——说明公共模板里的「不编造」约束在生效。
- **未验证**：前端展示（属于 T8.5）。
- **依赖**：T1.3。

### T8.2 后端生成复盘结果接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_evaluation_service.py`（新增）、`interpace-backend/app/routes/interview_routes.py`、`interpace-backend/app/schemas/interview_evaluation_schemas.py`（新增）、`interpace-backend/app/db/models.py`、`interpace-backend/app/services/chat_service.py`、`interpace-backend/tests/test_interview_evaluation.py`（新增）
- **做法**：入参 `interview_id`，输出「表现总结 + 薄弱点 + 改进建议」，落库供回显。
- **接口变更**：是。
- **实际改动**：
  - 新增表 `interview_evaluations`（**一场面试一行**，`interview_id` 唯一）。**为什么单独建表而不是给 `interviews` 加列**：`create_all` 不会给已有表加列，加列等于要动表结构，而 Alembic 还是空壳（T10.7）；单独建表零风险，且「复盘结果」与「面试过程」本就是两件事。
  - 新增 `POST /interviews/{id}/evaluations`（生成，重复调用**按最新问答记录覆盖**）与 `GET /interviews/{id}/evaluations`（读取，没生成过返回 404）。
    - **纠偏（真机反馈）**：`GET` 改成**返回 200 + `evaluation=null`**，不再用 404 表达「还没生成」。原因：那是**正常状态**而不是错误；更糟的是项目里的全局响应拦截器**对每个 404 都弹「资源不存在」**，用户一打开复盘面板就会莫名看到一个红色报错（`api/interviews/57/evaluations 404`，实际那条面试只是还没生成复盘）。现在 404 只留给「面试记录不存在 / 不是你的」。
  - 行里额外记 `qa_count`（生成时的问答条数）：回显时能看出「复盘之后又答了几轮」，为「要不要重新生成」提供依据。
  - **顺手补了外键删除顺序**：`interview_evaluations.interview_id` 指向 `interviews`，会话删除时若不先删复盘就会撞外键删不掉会话——`delete_session` 已补上（这已经是这个项目里第三次踩同类坑了，见 T5.3 / T6.2）。
  - 编排用**同步单次调用**（不是 LangGraph）：输入是一份已经落库的问答记录，取记录 → 评分 → 抽薄弱点 → 给建议由一次结构化输出完成；等真需要拆节点时再上图，不为一张纯函数的图付复杂度。
- **验收结果**：`pytest` **139 passed**（新增 8 个用例）；服务已加载（路由挂在既有的 `/interviews` 前缀下）。
  - 用例覆盖：生成后落库且结构完整；重复生成**覆盖而非新增**（库里仍只有一行，`qa_count` 随之更新）；没生成过读取返回 404；别人的面试记录生成与读取**都是 404**；没有问答记录时 409；解析器容错（代码块包裹、前后夹文字、去重、全空返回 None）。
- **依赖**：T8.1、T7.5。

### T8.3 上传真实语音音频复盘

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_evaluation_service.py`、`app/services/volc_speech/asr_client.py`、`app/routes/interview_routes.py`、`app/schemas/interview_evaluation_schemas.py`、`app/core/settings.py`、`app/db/models.py`、`tests/test_interview_evaluation.py`
- **做法**：复用阶段 3 的上传能力与 T7.6 的 ASR，把音频转成文本后走 T8.2 的复盘逻辑。
- **结论（用户选择方案 A）**：**录音挂在一场已有面试记录上**。录音本身没有「面试记录」这个实体，挂上去才能复用同一张复盘表与回显逻辑，不新增表、不新增一套回显。录音复盘会**覆盖**这场面试原有的复盘（同一行），来源字段随之切换。
- **实际改动**：
  - 新增 `POST /interviews/{id}/evaluations/from-audio`（入参 `resource_id`），响应额外回传**转写文本**——识别错的地方用户一眼能看出来，否则「AI 的结论为什么是这样」无从判断。
  - **走独立的「整段识别」端点**（`bigmodel_nostream`，配置项 `VOLC_ASR_FILE_URL`）。这是本任务最关键的技术判断：流式端点**要求按实时节拍喂音频**（官方文档明确要求，否则 VAD 分句会乱——实测全速推 14 秒音频时，3 句话被切成 9 段或并成 1 段），一段 20 分钟的录音就要 20 分钟才转写完。整段识别让服务端尽快跑完，**实测 14.4 秒音频约 2.4 秒出结果，快一个数量级**。
  - **不做本地音频解码**：火山 ASR 的 `audio.format` 原生支持 `wav/mp3/m4a/aac/ogg/pcm` 等，我们用文件后缀推断格式后把原始字节交给服务端解，省掉一个音频解码依赖；不支持的后缀返回 400，而不是硬当音频解。
  - 复盘表加了两列：`source`（0=问答文本 / 1=上传录音）与 `resource_id`（来源为录音时记下，便于回放与追查）。建表时该表刚创建且 **0 行**，所以直接删除重建（已在终端说明，无数据损失）。
  - 整段识别端点的返回结构有个坑：**会回大量空帧**（服务端在轮询），**只有 `is_last_package=True` 那一帧带完整文本**，必须读到最后一帧才算完。
- **验收结果**：`pytest` **144 passed**（新增 5 个用例：录音复盘落库与来源字段、录音覆盖问答复盘仍只有一行、不支持格式 400、别人的录音 404、格式后缀推断）。
  - **真机端到端通过**：用 TTS 现合成一段 17.9 秒的「候选人回答」当面试录音 → 上传 → 火山 ASR 转写（**准确**，连「Python 后端4年了」这种口语都转对）→ DeepSeek 复盘。它精准抓到「MySQL 索引优化这块我不太熟」是本场最大失分点，并指出「自述 4 年、展示出的深度更接近 1–2 年」，建议全部可执行。来源 `source=1`、`resource_id` 正确、分句数 4。
- **已知小问题（可接受）**：上传的录音没有挂在任何消息的附件段上，所以**删除会话时不会一起回收**，要等过期清理按 30 天回收（存储场景为长过期）。要立刻回收得给资源单独加删除入口，属于 T10 收尾的事。
- **依赖**：T3.3、T7.6、T8.2。

### T8.4 复盘薄弱点写入用户画像

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/interview_evaluation_service.py`
- **做法**：复盘产生的薄弱点去重合并进 `user_profiles.weak_topics`，逻辑与 T5.8 复用同一套服务方法。
- **实际改动**：直接调用 T5.8 已经抽出来的 `UserProfileService.merge_weak_topics()`（去重、保持顺序、上限 50、没有画像时自动建），**没有另写一套合并逻辑**——这正是 T5.8 备注里要求的「先做 T5.8、这里直接复用」。写入与复盘的落库**在同一事务**里提交。
- **验收结果**：`pytest` 覆盖——复盘后 `user_profiles.weak_topics` 等于模型给出的两个知识点。
- **依赖**：T8.2。
- **备注**：同 T5.8，阶段 9 的 T9.5 记忆抽取服务就绪后应把这里收敛到统一入口。

### T8.5 复盘结果「存入笔记」与「跳知识精讲」

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-frontend/src/components/evaluation/EvaluationPanel.vue`（新增）、`src/api/chat.ts`、`src/types/chat.ts`、`src/views/InterviewRoom.vue`
- **做法**：复用 T2.7 的存入笔记入口；针对复盘出的难点提供跳转知识精讲的入口，对齐流程图里「针对难点问题输出结构化知识卡片 + 语音播客讲解」。
- **实际改动**：
  - 新增 `EvaluationPanel`：在「面试复盘」模式下显示，**两种输入都能出复盘**——「生成复盘」（读问答记录，快）与「上传录音复盘」（T8.3，慢但能复盘外部录音）。
  - 结果区给出总结 / 薄弱点 chips / 改进建议；录音复盘额外有**可折叠的转写文本**（用户能核对「AI 听到的是什么」）。
  - 两个出口都接上：**「针对薄弱点讲一讲」**把薄弱点拼成一轮提问、切到知识精讲模式（复用既有流式链路）；**「存入笔记」**把总结 + 薄弱点 + 建议拼成富文本笔记（模型输出先转义再拼 HTML，避免尖括号被当标签）。
  - 两处工程细节：① 音频复盘的 HTTP 调用**单独放宽超时到 180 秒**（默认 10 秒必挂，转写本来就要等）；② 读取复盘时**只把 404 当「还没生成」**，其它错误如实报错——否则后端出问题时会伪装成「你还没生成复盘」，把人带偏。
- **依赖**：T8.2、T2.7、T4.3。
- **验收结果**：`pnpm run build`（含 `vue-tsc`）通过；后端 `pytest` 144 passed（复盘接口本身已由 T8.2 / T8.3 的用例覆盖，本任务是纯前端接入）。
- **验收结果补充**：**用户已在浏览器实测通过**（生成复盘、存入笔记等路径）。
- **一次真机纠偏**：最初 `GET /interviews/{id}/evaluations` 在「还没生成」时返回 404，导致**每次打开面板都弹一个红色「资源不存在」（全局拦截器对 404 统一提示）**。已改成 200 + `evaluation=null`——「还没创建」不是错误，详见 T8.2 的备注。
- **已知限制**：面板取的「最近一场面试」是从**已加载的消息页**里找的。会话很长、面试入口消息落在未加载的历史页时，面板会显示「还没有面试记录」；等 T10 收尾阶段再加「按会话列出面试记录」的接口来根治。

---

## 11. 阶段 9：长期记忆（越用越好用）

**目标**：让每个用户拥有独立、可累积、可复用的长期记忆，用得越久越准。三层记忆都以 `user_id` 作为唯一隔离键。

**三层划分（对齐 Hermes Agent）**

参考 Hermes Agent（Nous Research）的三层记忆架构：`hermes-agent.ai/blog/hermes-agent-memory-system`、`hermes-agent.nousresearch.com/docs/user-guide/features/memory/`。

**注意 Hermes 不是按「时间长短」分层，而是按记忆的用途分层**，这一点和常见做法不同：

| 层 | Hermes 原义 | 本项目对应 | 现状 |
| --- | --- | --- | --- |
| L1 持久事实记忆 | MEMORY.md（环境与约定）+ USER.md（用户画像），有硬字符上限，会话开始时以冻结快照注入 | 用户画像：目标岗位、目标级别、经验年限、技能掌握度、薄弱点 | 有表无接口，字段太粗，实际一直注入「未指定」 |
| L2 程序性记忆 | Skills：可复用的工作流、命令与验证步骤，按需加载，不占 L1 的字符预算 | 用户的答题方法与反复出现的表达问题（例如「回答行为题总是漏掉量化结果」） | 完全没有 |
| L3 会话检索 | 历史会话存 SQLite + FTS5 全文检索，返回真实消息，不做 LLM 摘要 | 按 `user_id` 检索历史对话、复盘结果与笔记 | 完全没有 |

Hermes 明确认为**会话内不需要记忆机制**——重要的东西都还在活跃上下文里，记忆的价值体现在会话边界上。所以本项目不把「单会话上下文」算作一层记忆，长会话的上下文压缩单独列为 T9.16。

**从 Hermes 借鉴的六条设计原则**

1. **记忆是声明式事实，不是任务日志**。「用户偏好先讲结论」「目标岗位是 Python 后端」是好记忆；「今天修了 X」「明天要做第三步」是坏记忆，一周内就过期，不该进记忆。
2. **容量必须封顶**。Hermes 的 MEMORY.md 限 2,200 字符、USER.md 限 1,375 字符，**超限写入直接报错而不是静默丢弃**，逼 agent 在同一轮内做整合。我们的画像字段是结构化的，对应做法是给技能与薄弱点的条目数设上限。
3. **写入要经过用户**。Hermes 提供 `write_approval`：开启后所有记忆写入先暂存，用户用 `/memory pending` 查看、`approve` 或 `reject`，并且会记录被覆盖前的原文。这正好落在 D19「记忆可见可删」上。
4. **记忆按 profile 隔离**。Hermes 用 profile 目录隔离记忆，本项目用 `user_id`，本质是同一件事。
5. **学习发生在会话结束后，且是异步的**。Hermes 在每轮结束后跑一个后台 review（可以用更便宜的模型），而不是在做题过程中同步写入。所以本项目也不该在对答链路上同步抽取画像。
6. **验收看行为，不看复述**。Hermes 的原话是：agent 不应该只是「背诵」自己记得什么，而应该因为这条记忆**选择了正确的默认动作**。这条直接作为 T9.7 的验收标准。

**执行顺序建议**：L1（T9.2~T9.9）→ L2（T9.10~T9.12）→ L3（T9.13~T9.15）→ 收尾（T9.16~T9.17）。L1 不引入任何新依赖、投入产出比最高，先做；L3 的方案选型见 T9.13。

**隔离要求（三层通用）**

- 所有记忆的读写都必须以 `user_id` 为过滤条件，检索类接口不允许只靠相似度返回结果。
- 记忆的读取、写入、删除接口都要过 `get_current_user`，越权一律 404。
- 删除用户、删除会话时记忆的级联策略要明确，并写进测试。

**画像来源策略（已定）**

画像字段分两类，来源和可信度完全不同，不能用同一个入口收集：

| 字段 | 类型 | 最佳来源 |
| --- | --- | --- |
| 目标岗位 | 意图 | 用户在刷题 / 模拟面试时选的岗位（简历通常没有求职意向，且写的是「过去」） |
| 目标级别 | 意图 | 同上 |
| 经验年限 | 声明 | 简历解析 |
| 技术栈清单 | 声明 | 简历解析（会什么）与岗位选择（要什么）取交集 |
| 技能掌握度 | 能力 | 刷题得分 + 面试回答质量 |
| 薄弱点 | 能力 | 刷题错题 + 面试复盘 + 真实录音复盘 |

落地优先级：

1. **简历解析**（T6.2）作为冷启动入口。上传简历是面试产品的必经动作——用户为了简历优化或模拟面试而上传，系统顺手把画像填了，用户感知不到额外成本。
2. **刷题 / 面试时的岗位与难度选择**（阶段 5、7）——用户当下的意图比简历更准，且不增加额外交互，正好补上简历缺「目标岗位」这个缺口。
3. **刷题评分与面试复盘**（T5.8、T8.4）作为持续修正——这是唯一能得出掌握度与薄弱点的来源，但属于慢热型，产品得先跑起来才有数据。
4. **「我的画像」页面**（T9.4）只作纠错与兜底入口，不作为主要来源。指望用户主动填，绝大多数人不会填。

合并规则按字段类型分别处理：

- **能力类字段**（技能掌握度、薄弱点）：行为证据 > 用户自评 / 简历声明 > 模型推断。简历写「精通 Python」而刷题 5 题错 3 题时，以后者为准。
- **意图类字段**（目标岗位、目标级别）：以用户当下的声明为准，行为数据不覆盖；如果与简历里的经历明显矛盾，只做提示，不自动改写。
- **时间衰减**：行为证据带时间戳，旧数据权重衰减，避免「越用越准」变成「越用越旧」。

**抽取时机（对齐 Hermes）**：不在对答链路上同步抽取，而是在**会话结束后异步跑**一次 review。触发点先限定在低频事件上——一次刷题评分完成、一场面试复盘完成、一次简历解析完成——不做每轮全量抽取。Hermes 靠更便宜的辅助模型兜住每轮成本，本项目现阶段按低频事件触发更稳妥。

噪声不靠「不抽」来控制，而是靠三道闸门：写入审批（T9.9）、完全重复的条目直接不写入、字段容量上限（T9.8）。「想了解一下 GIL」这类临时兴趣会在审批环节被挡掉。

### T9.1 确认三层记忆的边界与数据模型

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。
- **需要定的点**：画像用固定列还是 JSON schema 扩展；L2 技能层与现有的 `prompt_templates` 表（系统侧的提示词模板）如何区分——前者是「用户的方法」，后者是「系统的提示词」，不要混成一张表。
- **已定**：三层的含义已按 Hermes 对齐（见上方对照表）；用户画像的来源优先级已在「画像来源策略」中定稿，不在本任务重复讨论。
- **结论（原 D18，已确认）**：
  1. **新增明细表 `user_memories`**，一行 = 一个能力条目，带**掌握程度、来源、置信度、证据次数、最后证据时间**。JSON 数组表达不了这四个维度，而这四样正是「越用越准」与时间衰减的前提。
  2. **掌握程度用 0–100 整数**，**对外只映射成四档**（熟练 / 熟悉 / 了解 / 待加强）。理由：等级制的区分度太低（同一级里「刚会」和「快熟了」对出题难度意义完全不同）；百分比看着精确、其实也是拍脑袋。用户看到「73 分」只会纠结为什么不是 80，看到「熟悉」才知道下一步该干嘛。
  3. **`target_skills` / `weak_topics` 两个 JSON 列保留，但降级为派生缓存**（由明细表重建）。它们仍被现有提示词注入与 `merge_weak_topics` 读取，一次性改掉所有读者风险大；等 T9.7 重写注入时再收敛。
  4. **意图类字段留在 `user_profiles`**（`target_job` / `target_level` / `years_experience`）——「用户想要什么」和「用户会什么」来源与可信度完全不同，混在一张表里迟早要拆。
  5. **L2 复用同一张 `user_memories` 表**（`category=2`），不新建表：L1 与 L2 的差别是**语义**（事实 vs 方法）而不是**结构**，共用还能让注入逻辑统一。系统侧的 `prompt_templates` 是另一件事，绝不混。
- **依赖**：无。

### T9.2 扩展用户画像的数据模型

- **状态**：已完成（2026-09-29）
- **现状**：`user_profiles` 只有 `target_skills` / `weak_topics` 两个 JSON 数组，只能表达「会不会」，表达不了「多熟、依据是什么、什么时候得出的」。
- **做法**：扩展画像模型。能力类字段（技能掌握度、薄弱点）必须带掌握程度、来源、置信度、更新时间；意图类字段（目标岗位、目标级别）与能力类字段分开存放，不要混在同一组 JSON 里。字段方案见 D18。
- **涉及文件**：`interpace-backend/app/db/models.py`、`app/services/user_memory_service.py`（新增）、`app/services/user_profile_service.py`、`app/services/user_service.py`、`tests/test_user_memory.py`（新增）、`tests/test_user_deletion.py`（新增）
- **验收**：表能建出来；既有字段的读取不受影响。
- **实际改动**：
  - 新增表 `user_memories`：`category`（0技能/1薄弱点/2答题方法）、`name`、`mastery`(0-100)、`source`(0推断/1自述/2简历/3行为证据)、`confidence`、`evidence_count`、`last_evidence_at`、`pending_approval`（给 T9.9 的写入审批预留），`(user_id, category, name)` 唯一。**它同时承载 L1 与 L2**，差异只在 `category`。
  - 新增 `UserMemoryService`：**合并规则就是本阶段的「画像来源策略」的代码化**——来源权重 `行为证据(3) > 自述/简历(2) > 模型推断(1)`；弱来源**不覆盖**强来源的掌握程度、只增加证据计数；同权重用证据数加权平均（避免一次偶发观测带偏结论）；证据计数与时间每次刷新，供 T9.8 的容量整合与时间衰减使用。
  - 掌握程度映射成四档的 `mastery_label()` 也在这里，**分数只在内部流转**。
  - **把老写入路径桥接到新表**：`UserProfileService.merge_weak_topics()` 现在会同时 upsert 一条 `user_memories`（来源=行为证据）。这样新表从第一天就有真实数据，而不是空跑到 T9.6 才统一入口；JSON 列继续作为派生缓存供既有注入使用。
- **顺手修了一个既有缺陷（真机验证过）**：`UserService.delete_user` 原来只 `db.delete(user)`，而 `users` 被 **10 张表以 `NO ACTION` 外键引用、没有任何级联**——**只要用户建过一次会话，删用户就必然 `IntegrityError 1451`**。这不是本次引入的（题库、画像待确认、复盘三处都踩过同类坑），但我这次又往 `users` 上挂了一张表，就一并修了：按依赖从叶子到根逐表清理，最后删用户行，事务提交后再 best-effort 回收对象存储。
- **验收结果**：`pytest` **155 passed**（本任务新增 8 个用例）。
  - 合并规则：行为证据 40 分能覆盖简历声明的 90 分；反向的简历 95 分**不能**覆盖行为证据，只把证据计数从 2 加到 3；同来源重复观测取加权平均（40 与 70 → 55）。
  - 老路径桥接：`merge_weak_topics` 后 JSON 缓存与 `user_memories` 两边都能查到同样的两个薄弱点，来源都是行为证据。
  - **删用户覆盖所有依赖表**：造一个「有会话+消息+面试+复盘+题库+题目+笔记+画像+记忆+资源」的用户，删除后 10 张表全清干净、不留孤儿；不存在的用户仍返回 404。
- **依赖**：T9.1。

### T9.3 用户画像的读写接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/routes/user_profile_routes.py`（新增）、`app/schemas/user_profile_schemas.py`（新增）、`app/routes/__init__.py`、`app/main.py`、`tests/test_user_memory.py`
- **做法**：新增 `app/routes/user_profile_routes.py`、`app/schemas/user_profile_schemas.py`，提供 `GET /profile`（读取当前用户画像）、`PUT /profile`（更新基础字段）、技能与薄弱点的增删改接口。全部走 `get_current_user`，天然按当前用户隔离。
- **接口变更**：是。
- **实际改动**：前缀 `/profile`，五个接口：
  - `GET /profile`：意图字段 + 能力记忆明细 + 两个兼容用的扁平列表（`target_skills` / `weak_topics`）。**没有画像记录时返回空结构而不是 404**——「还没填」是正常状态，不该是错误（这条是 T8.2 踩过的坑，见那里的备注）。
  - `PUT /profile`：只更新显式传入的意图字段。
  - `POST /profile/memories`（201）、`PUT /profile/memories/{id}`、`DELETE /profile/memories/{id}`（204）、`GET /profile/memories?category=`。
  - 响应里带 `mastery_label` / `source_label` / `category_label` 三个中文标签：**掌握程度对外只给四档，来源要能说清「这条是谁说的」**（用户自述 / 简历 / 答题表现 / 模型推断）——这是「记忆可解释」的最小实现。
  - 用户手动改过的条目，来源改记为「你的自述」并**自动置为已生效**（不会被 T9.9 的待确认机制再打回去）。
- **验收结果**：`pytest` **155 passed**。
  - 用例覆盖：空画像读取 → 改意图字段 → 新增条目（201，标签正确）→ 改掌握程度（标签随之变化）→ 按类别过滤 → 删除（204）→ 删除后列表为空。
  - 越权：别人的条目改与删都是 404，且侵入者自己的画像列表里看不到别人的条目。
- **依赖**：T9.2。

### T9.4 前端「我的画像」页面

- **状态**：已完成（2026-09-29）
- **涉及文件**：`src/views/ProfileView.vue`（新增）、`src/api/userProfile.ts`（新增）、`src/types/userProfile.ts`（新增）、`src/constants/nav-tabs.ts`、`src/router/index.ts`
- **做法**：新增页面展示当前用户的目标岗位、经验、技能掌握度与薄弱点，支持手动增删改。它同时是「记忆可解释」的入口——用户能看到系统记住了自己什么，也能删掉记错的内容。
- **涉及文件**：新增 `src/views/ProfileView.vue`、`src/api/userProfile.ts`、`src/types/userProfile.ts`；`src/components/layout/AppHeader.vue`（加入口）
- **实际改动**：
  - 顶部导航新增第四个 tab「我的画像」（`tabs` 常量 + 路由 `/profile`），页面沿用 AppHeader 的既有布局。
  - 两段式界面，与后端的数据分段一一对应：**求职意向**（目标岗位 / 经验 / 级别，可改可保存）与**能力与薄弱点**（按 技能 / 薄弱点 / 答题方法 三组展示）。
  - 每条记忆显示：条目名、掌握程度（下拉四档）、**来源**（你的自述 / 简历 / 答题与面试表现 / 模型推断）、被观察次数、删除按钮。**「来源」这一列是这张页面的核心价值**——用户能判断这条是系统推断的还是自己说过的。
  - 掌握程度按「档」编辑并映射成分数（待加强 20 / 了解 45 / 熟悉 70 / 熟练 90），**展示永远只给档、不给分数**——分数是内部结构，用户看到「73 分」只会纠结为什么不是 80。
  - 修改掌握程度时就地替换那一行，不整页重载（避免滚动跳动）；已带 `pending_approval` 的条目显示「待确认」标签，为 T9.9 的写入审批先留出展示位。
- **验收结果**：`pnpm run build`（含 `vue-tsc`）通过；运行中的后端已加载 `/profile` 与 `/profile/memories` 两组接口，dev server 已提供新页面。
- **未验证**：浏览器里的实际观感与操作（改意向、改掌握程度、删条目）。等你实测。
- **备注**：目前表单里的掌握程度是「选档 → 存分数」，将来若要支持更细的调整，可以在这张页面上加滑杆，不影响数据结构。
- **依赖**：T9.3。
- **见**：待确认 D19。

### T9.5 记忆抽取服务

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/memory_extract_service.py`（新增）、`app/services/prompt_template_seed_service.py`、`app/services/prompt_template_service.py`、`tests/test_memory_extract.py`（新增）、`tests/api_helpers.py`
- **做法**：新增服务，输入「一次评分结果 / 一次复盘结果 / 一次简历解析结果 / 一段明确的自述句」，输出结构化的画像更新（新增或修订哪些技能、哪些薄弱点）。抽取的编排用 LangGraph、模型与提示词用 LangChain（遵守根 `AGENTS.md`）。
- **来源优先级**：按本阶段的「画像来源策略」执行——评分与复盘属行为证据，权重最高；简历属声明，次之；模型推断最低。**不要对每轮对话都抽取**，只处理明确的自述句并做限流。
- **待确认**：抽取结果是否要先让用户确认见 D20；具体的权重系数与衰减参数见 D21。
- **涉及文件**：新增 `app/services/memory_extract_service.py`、`app/agent/scenes/memory.py`
- **实际改动**：
  - **编排用 LangGraph**（根 `AGENTS.md` 的约定）：`抽取 → 校验 → 落库` 三个节点串成状态图。现在看着像线性流程，但 T9.8 的「超出容量上限时先整合再重试」要在这里接一条条件边——先用图把这层结构立住，比之后把三个函数缠在一起改造容易。
  - **输入统一成 `MemoryEvidence`**（kind + summary + source）：评分结果、复盘结果、简历、自述各自在调用方归一化成一段证据文本，抽取服务不认识任何业务表的字段。为此提供了 `build_quiz_evidence()` / `build_interview_evidence()` 两个构造器。
  - **输出走共用契约** `MEMORY_JSON_CONTRACT`（提示词与解析器同一份），解析器**不抛异常**：空输入直接返回、解析失败返回空列表、未知类别/空名字/重复条目丢弃、分值越界收敛到 0-100。
  - **写入策略（D20 的落地）**：**行为证据直接生效**（用户自己考出来的结果，且用户已经用「提交答案 / 生成复盘」表达了意愿）；**模型推断先落待确认**（`pending_approval=1`，批准前不影响对话）。把「谁说的」和「要不要确认」绑定，比一刀切全要审批更合理——否则「越用越好用」的闭环会被一串弹窗卡死。
  - 新增模板 `memory_extractor` / `memory`（**故意没有公共模板**：抽取时注入画像会让模型倾向于复述已有画像，而不是根据证据独立判断）。
  - **踩到并验证了花括号那个坑**：模板里写空列表示例 `{"items": []}` 时忘了双写，`test_seed_templates_only_have_escaped_braces` 立刻失败——这条测试（T1.3 留的）确实在干活。修正后又发现一个**更隐蔽的问题**：seed 是幂等的，库里那条 v1 仍是带 bug 的旧正文，而它一旦被 `ChatPromptTemplate` 解析就会抛 `KeyError`。已原位修正 v1 并刷新缓存，并用 `ChatPromptTemplate.format()` 实测渲染成功。
- **验收结果**：`pytest` **162 passed**（本任务新增 7 个用例：代码块与类别映射、脏数据丢弃与去重、分值越界收敛、垃圾输出、行为证据直接生效、模型推断落待确认、空证据不调模型）。
  - **真实模型 3/3 抽取成功**：给定「一次刷题评测结果」的证据，稳定抽出 `MySQL 索引优化`（掌握度 10-15，因为候选人明说不会）与 `GIL 与并发模型`（35-50，因为答得浅），置信度 75-90（证据里明确写了答案对错）。
  - 观察到一处模型波动：有一次把「答对但很浅」的 GIL 归成 `skill` 而不是 `weak_topic`。语义上确实两可，暂不处理；同一名字跨类别会存成两行，这一点记在备注里。
- **备注**：同一知识点可能同时以 `skill` 与 `weak_topic` 出现（例如「GIL」既算会一点又算薄弱），目前按两行存。是否要跨类别归并，等 T9.8 做容量整合时一并决定。
- **依赖**：T9.2。

### T9.6 把记忆写入接入既有场景

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/user_memory_service.py`、`app/services/user_profile_service.py`、`app/services/quiz_evaluation_service.py`、`app/services/interview_evaluation_service.py`、`app/services/profile_proposal_service.py`、`scripts/backfill_user_memories.py`（新增）、`tests/test_profile_proposal.py`
- **做法**：把 T5.8（刷题评分写薄弱点）、T8.4（复盘写薄弱点）、T6.2（简历解析写画像）改为统一调用 T9.5 的抽取服务，避免三处各写一套写入逻辑；合并时按「画像来源策略」的规则处理权重与冲突。
- **实际改动**：
  - `UserMemoryService.ingest()` 成为**唯一写入入口**：一批已知条目入库 + 按来源权重合并 + 重建派生缓存 + 来源标记 + 待确认策略。`merge_weak_topics` 退化成它的薄封装（保留原签名，调用方不用自己构造条目）。
  - 三个场景全部改走这个入口：刷题评分（`SOURCE_BEHAVIOR`）、面试复盘（`SOURCE_BEHAVIOR`，抽成 `_write_weak_topics` 供问答与录音两条路径共用）、简历确认（`SOURCE_SELF_REPORT`——简历是声明，但这里是**用户确认过**的值，用户点头之后这条就是他自己认可的）。
  - **一处刻意偏离任务原文（要说明）**：任务原文说三处都调用 T9.5 的模型抽取，但实际只在**非结构化输入**（简历正文、用户自述）上调用它。刷题评分与复盘产出的 `weak_topics` **已经是知识点级别的结构化条目**，再让模型抽一遍只会多花一次调用、还可能把已经归纳好的结论拆散。三个场景共用的仍然是同一套「写入 + 合并 + 缓存重建」逻辑，只是不重复调用模型。
  - **派生缓存的排序刻意保持原语义**（技能按掌握度从高到低、薄弱点按加入顺序），避免升级后悄悄改变注入给模型的内容顺序。
- **踩到一个真实的数据迁移问题（已处理）**：缓存改成「从明细表重建」后是**覆盖**语义，而 T9.2 之前的数据只躺在 JSON 列里——**升级后第一次写入就会把旧数据抹掉**。实测开发库有 75 行画像属于这种情况（共 173 条）。
  - 新增一次性回填脚本 `scripts/backfill_user_memories.py`（幂等、支持 `--dry-run`）：把 JSON 里缺的条目补进明细表；技能标「用户自述」、薄弱点标「行为证据」（历史上薄弱点都来自刷题与复盘）。
  - 已执行：扫描 123 行 → 回填 75 行 / 173 条；复查「只在 JSON 里」的条目数 **0**。
  - 顺带修正了 `test_profile_proposal` 的造数方式：它原来直接往 JSON 列塞数据，而 JSON 现在是派生缓存，改成写明细表。
- **验收结果**：`pytest` **162 passed**。
  - 三个场景写入都带来源标记、都经过同一套合并规则（行为证据覆盖声明这条规则由 T9.2 的用例保证）。
  - 意图类字段（岗位 / 级别 / 年限）仍由 `user_profiles` 直接承载，行为数据不写它们——符合「意图以用户当下声明为准」。
- **依赖**：T9.5、T5.8、T6.2、T8.4。

### T9.7 画像注入强化与效果验证

- **状态**：已完成（2026-09-29）
- **现状**：`build_personalized_prompt` 是把整份画像无差别塞进提示词，不做裁剪。
- **做法**：按场景裁剪注入内容（面试场景重岗位与经验、刷题场景重技能与薄弱点），并验证注入后回答确实更贴合用户。
- **涉及文件**：`app/services/user_profile_service.py`、`app/agent/prompt_layer.py`、`tests/test_profile_injection.py`（新增）
- **实际改动**：
  - 新增 `SCENE_INJECTION_RULES`：每个场景一份 `(技能上限, 薄弱点上限, 关注点)`。理由很实在——画像会长（技能 30 条、薄弱点 50 条），**无差别全塞进去会把真正重要的信息稀释掉**，还让提示词无谓变长。面试场景重岗位与经验（技能 5 / 薄弱点 8），刷题场景重技能与薄弱点（10 / 10），学习室 8 / 8，复盘 5 / 10，快速回答 8 / 5；**未传场景（内部步骤如记忆抽取）退到最小集合 5 / 5**，避免污染内部判断。
  - **注入内容带上掌握程度**：「薄弱点：MySQL 索引优化(待加强)」比光给一个名字的信息多得多。技能由强到弱排、薄弱点由弱到强排，再按上限裁剪——**顺序决定谁被留下**，所以排序规则写在这里而不是随手 `[:n]`。
  - `get_profile_dict` 改为**优先从 `user_memories` 读取**（T9.2 起它才是真源），明细表为空时回退到 JSON 派生列，兼容还没跑回填的环境。
  - 每个场景追加一句「本场景的关注点」。**为什么用追加而不是改模板**：模板一旦 seed 进库就有版本，改一次要走 `--force` 出一版新的、把十几条模板全部升版；而这句只是注入层的关注点说明，追加在末尾零成本、零版本噪音。
- **验收结果**：`pytest` **169 passed**（本任务新增 7 个用例）。
  - **裁剪实测**（同一份 30 技能 / 50 薄弱点的长画像）：study 8/8、quiz 10/10、interview 5/8、evaluation 5/10、chat 8/5、无场景 5/5——按场景确实不同。
  - **同一问题在不同画像下的回答差异（真实模型）**：问「讲讲 MySQL 索引」——
    - **初级/应届画像**：从「索引是什么」讲起，用「查书目录」比喻，解释什么是全表扫描，再对比二叉树 / 哈希 / B+ 树；开头一整段里没有任何进阶术语。
    - **高级/6 年画像**：开口就是「聚簇索引叶子存整行、二级索引存主键**需要回表**；设计核心是区分度 + 最左前缀 + 尽量覆盖，`EXPLAIN` 的 `Extra` 是判断索引用得对不对的第一手依据」，随后给出聚簇 vs 二级索引的对比表。
    - 这是「越用越准」最直观的验收点：**同一个问题，回答的切入点、术语层级与组织结构都随画像变化**。
  - **诚实说明**：我最初想用一个自动化指标（数「进阶概念命中数」）量化差异，结果是 5 vs 6——**指标区分度不足**（两个回答都会提到 B+ 树、全表扫描）。真正的差异在切入点与组织结构上，靠人眼判断；该指标只留作参考，不作为验收依据。
- **依赖**：T9.6。

### T9.8 记忆容量上限与整合策略

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/user_memory_service.py`、`app/services/memory_extract_service.py`、`app/services/prompt_template_seed_service.py`、`app/services/prompt_template_service.py`、`tests/test_memory_extract.py`
- **现状**：`user_profiles.target_skills` / `weak_topics` 是无上限的 JSON 数组，用得越久堆得越多，最后会变成没人看的垃圾桶。
- **做法**：按 Hermes 的容量封顶思路，给能力类字段设条目数上限（例如技能 30 条、薄弱点 20 条）。**达到上限时新增写入直接报错，而不是静默淘汰旧条目**，由抽取服务在同一轮内先做整合（合并相近条目、淘汰过期条目）再重试；完全重复的条目不写入。
- **实际改动**：
  - 新增 `CATEGORY_LIMITS`：技能 30、薄弱点 20、答题方法 20。**超限时新增写入抛 `MemoryCapacityExceeded`（领域异常，不是 HTTP 错误）**，由上层决定怎么处理。Hermes 的原话是「超限写入直接报错而不是静默丢弃，逼 agent 在同一轮内做整合」——静默淘汰最坏的结果是用户不知道系统把自己说过的东西丢了。
  - **计数只对「新增」生效**：命中已有条目属于合并，不增加条数，永远不该被容量挡住（这条单独写了用例）。
  - 抽取图新增两个节点与一条条件边：`capacity`（判断「新增」会不会超限，同一批次的增量一起算）→ 超限则走 `consolidate`（模型合并相近条目、淘汰过时条目，给出最终列表与淘汰名单）→ `persist`。**这正是 T9.5 当初用状态图而不是串行函数的理由**：加这条分支只是加一条边，写成串行会把抽取与落库缠在一起。
  - 整合只跑一次（`consolidated` 标记）：模型来回整合会越整越多。
  - **整合解析失败时返回空 drops**——绝不能把「模型没输出 JSON」当成「删光旧条目」，那会清空用户的记忆。
- **验收结果**：`pytest` **173 passed**（本任务新增 4 个用例）。
  - 容量报错：把方法类填满 20 条后新增 → 抛 `MemoryCapacityExceeded`，且**报错后老数据一条没少**（这是「绝不静默丢数据」的直接证据）；同一类别下命中已有条目则照常合并通过。
  - 整合重试：填满 20 条 + 新抽到 1 条 → 模型被调用**两次**（抽取 + 整合），整合淘汰一条旧条目、保留新条目，最终条数仍等于上限；被淘汰的条目确实从库里删除了。
  - 解析容错：`drop` 里类别非法或缺名字的条目被丢弃；整合输出整段解析不出来时 `drops` 为空。
- **依赖**：T9.2、T9.5。

### T9.9 记忆写入审批与治理

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/db/models.py`、`app/services/user_memory_service.py`、`app/services/user_service.py`、`app/routes/user_profile_routes.py`、`app/schemas/user_profile_schemas.py`、`tests/test_user_memory.py`、`tests/api_helpers.py`、`interpace-frontend/src/views/ProfileView.vue`、`src/api/userProfile.ts`、`src/types/userProfile.ts`
- **做法**：对齐 Hermes 的 `write_approval`。记忆写入先落「待确认」状态，用户在「我的画像」页逐条批准或拒绝，自动抽取的条目打标记以便区分；替换或删除已有条目时要记录被覆盖的原文，便于回溯。
- **接口变更**：是（新增待确认列表、批准、拒绝三个操作）。
- **实际改动**：
  - 新增三个接口：`GET /profile/memories/pending`、`POST /profile/memories/{id}/approve`、`POST /profile/memories/{id}/reject`，以及 `GET /profile/memory-logs`（变更日志）。
  - **批准前不影响对话**由架构本身保证：待确认条目不进派生缓存（`rebuild_profile_cache` 只取 `pending_approval=0`），而提示词注入读的正是那份缓存。批准时显式重建一次缓存，这条记忆才开始生效。
  - **拒绝 = 删除**，不保留「已拒绝」状态。用户明确说不要的东西，留着只会在列表里反复出现，还占着容量。
  - 新增 `user_memory_logs` 表记录变更：新增 / 合并更新 / 已批准 / 已拒绝 / 你修改了 / 已删除，**before/after 都存快照**。这张表的 `memory_id` **故意不加外键**——被删掉的记忆恰恰最需要留痕。这是「记录被覆盖的原文，便于回溯」的落点。
  - 合并日志只在**内容真的变了**时才写（`before != after`），避免每次重复观测都堆一条噪声。
  - 前端「我的画像」页新增「待你确认」区块（批准 / 拒绝）与「变更记录」列表；待确认区块用暖色区分，并明确写出「在你确认之前不会影响回答」。
  - `UserService.delete_user` 的清理顺序补上 `user_memory_logs`。
- **验收结果**：`pytest` **175 passed**（本任务新增 2 个用例，并给删用户用例加了日志表的断言）。
  - **批准路径**：自动抽取（来源=模型推断）→ 待确认列表能查到、`/profile` 的技能列表为空（**证明批准前不影响对话**）→ 批准后技能列表出现该条目 → 日志里有「已批准」且 `before_json` 非空。
  - **拒绝路径**：拒绝返回 204 → 待确认列表与记忆列表都查不到 → 日志里留下「已拒绝」与原文（`before_json` 含条目名）。
- **顺手收拾的一个重复踩坑**：本轮又因为「新增了一张引用 `users` 的表」导致多处测试清理撞外键。这次把「删用户相关数据」抽成共享 helper `purge_user()`（顺序：记忆日志 → 记忆 → 画像 → 用户），测试里不再各写一遍。这个坑在 T5.3 / T6.2 / T8.2 / T9.2 已经各踩过一次，**根因是「加表时只改生产代码、忘了改测试清理与级联」**，有了共享 helper 之后至少测试侧不会再漏。
- **依赖**：T9.3、T9.4、T9.5。
- **见**：待确认 D19、D20。

### T9.10 L2 程序性技能：确认产品语义

- **状态**：已完成（2026-09-29）
- **目标**：先决策，不写代码。这是照搬 Hermes 时最容易出错的地方。
- **需要定的点**：Hermes 的 L2 是「agent 自己怎么干活的工作流」；本产品的用户是求职者而不是 agent，套用前必须明确 L2 到底记什么。备选：用户的答题方法（如「习惯用 STAR 结构答题」）、反复出现的表达问题（如「讲项目漏掉量化结果」）、某个岗位的固定面试流程。
- **结论（原 D22，已确认）**：L2 记**两类**，判据用 Hermes 的原话——**可复用的做法进 L2，陈述性事实进 L1**：
  1. **答题方法**：如「习惯用 STAR 结构组织行为题回答」「讲技术方案时先给结论再讲取舍」；
  2. **反复出现的表达问题**：如「回答项目题稳定漏掉量化结果」「讲方案只给结论、不给权衡」。

  **明确不记**：① 单次的知识点对错（那是 L1 的薄弱点）；② 某个岗位的固定面试流程（那是系统提示词的职责，不该按用户记）。

  **注入时机对齐 Hermes 的按需加载**：只在 **模拟面试（点评候选人怎么答）** 与 **面试复盘** 里注入；**知识精讲里不注入**——那是讲知识点的地方，塞「你上次答题漏了量化结果」纯属噪音，还白占提示词预算。

  **验收口径**：① 同类表达问题在多次复盘后被**合并成一条稳定条目**（T9.11）；② 注入方法条目后，点评能指出用户**具体**的方法问题，而不是泛泛说「表达要更好」（T9.12）。
- **依赖**：T9.1。

### T9.11 L2 程序性技能：抽取与沉淀

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/memory_extract_service.py`、`tests/test_memory_extract.py`
- **做法**：复用 T9.5 的抽取服务，但从「用户答成什么样」里提炼可复用的**方法**，而不是事实。分层判据用 Hermes 的原话——**陈述性事实进 L1，可复用的做法进 L2**。例如「回答行为题时稳定漏掉结果和量化数据」属于 L2；「上次答错了一道 Redis 持久化题」属于 L1 的薄弱点。
- **验收**：同类表达问题在多次复盘后被合并成一条稳定的方法论条目，而不是每次复盘都新增一条。
- **实际改动**：
  - `category=method` 的支持在 T9.5 就已经有了（提示词、解析、入库都能处理），本任务补的是**让它真正沉淀下来**的机制。
  - **把「已有的方法条目」放进抽取提示词**，并明确要求：这次观察到的是同一个问题时**直接复用已有说法，不要换新名字**。
    - 为什么必须这么做：L2 的价值在于「反复出现的问题沉淀成一条稳定的方法论」。如果每次复盘都用新说法记一条（「答项目题漏掉量化结果」/「讲项目没给数字」），条目只会越堆越多却永远不收敛，L2 就退化成第二个垃圾桶。
    - 为什么放在提示词里而不是事后再做一次「语义去重」调用：**省一次模型调用，而且更准**——模型在抽取的同一轮就知道该复用哪个名字，不用等写完再回头合并。
  - **一处刻意的取舍**：这条要求写在**每轮都会带上的调用上下文**里，而不是写进 seed 模板——模板一旦入库就有版本，改一次要走 `--force` 把十几条模板全部升版；而这个要求是抽取逻辑的一部分，跟着代码走更合适，也不产生版本噪音。
- **依赖**：T9.10、T9.5。
- **验收结果**：`pytest` **196 passed**（本任务新增 2 个用例：已有方法条目确实进了模型输入、同名条目累积证据数而不是新增）。
  - **真机验证通过**：同一个问题、两种完全不同的措辞（「全程没有给出任何数字」vs「仍然没有说清具体数据」）分两次抽取——两次都写入 **`项目成果量化表达`**，最终**方法条目数 = 1、证据次数 = 2**。这就是「沉淀成一条稳定条目」的直接证据。

### T9.12 L2 程序性技能：注入到回答指导

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/services/user_profile_service.py`、`app/agent/prompt_layer.py`、`tests/test_profile_injection.py`
- **做法**：对齐 Hermes 的按需加载——技能条目只在相关场景注入（例如只在模拟面试的回答点评里注入答题方法，不在知识精讲里注入），不占 L1 的字符预算。
- **涉及文件**：`app/agent/prompt_layer.py`
- **验收**：同一场模拟面试，注入了技能条目的点评能指出用户的具体方法问题，而不是泛泛而谈。
- **实际改动**：
  - `InjectionRule` 新增 `include_methods`，**只给 `interview`（模拟面试）与 `evaluation`（面试复盘）打开**；`study` / `quiz` / `chat` / 内部步骤一律关闭。这就是 Hermes 的「按需加载」——技能条目不占无关场景的提示词预算。
  - 方法条目单独走 `get_profile_dict` 的 `answer_methods` 字段，注入时追加在提示词末尾，并明确要求模型「点评时结合这些**具体指出**，不要泛泛地说表达要更好」。
  - 两个场景的「关注点」文案也相应补充：面试场景要求点评时**具体指出他这次有没有再犯**；复盘场景要求在总结里**点出这些反复出现的问题**。
  - 同样用「追加」而不是模板占位符，理由与 T9.7 一致（避免为一句场景策略把十几条模板全部升版）。
- **验收结果**：`pytest` **196 passed**（本任务新增 1 个用例，断言只有 interview / evaluation 两个场景会注入方法条目）。
- **依赖**：T9.11、T9.7。

### T9.13 L3 检索方案选型

- **状态**：已完成（2026-09-29，决策已定；实现见 T9.14）
- **目标**：先决策，不写代码。这是本阶段唯一可能引入新依赖的地方。
- **关键事实**：Hermes 的 L3 用的是 **SQLite + FTS5 全文检索**，并没有上向量库。它返回真实消息、不做 LLM 摘要、不截断，检索约 20ms 且不产生模型成本。这说明「按关键词找回历史对话」这个需求，全文检索就够了。
- **备选**：复用现有 MySQL 的 FULLTEXT 索引（**零新增依赖**）；或引入向量库做语义检索。Hermes 的 `session_search` 有三种调用形态（discovery / scroll / browse），可以借鉴。
- **建议**：先做 MySQL FULLTEXT，把「检索历史对话」跑通并实测效果；只有命中率确实不够时再追加向量检索。这样能把一个大依赖推迟到真正需要的时候，也避免过早优化。
- **结论（原 D17，已确认）**：**先上 MySQL FULLTEXT，不引入向量库**。理由：① Hermes 用的就是全文检索（SQLite FTS5，约 20ms、零模型成本），说明「找回历史对话」这个需求不需要语义检索；② 向量库要多一个运行组件 + embedding 调用成本，对 2核2G 的部署目标是实打实的负担；③ 真不够时再追加，届时索引与接口都不用重做。
- **依赖**：无（可与 L1 并行推进）。

### T9.14 L3 会话索引与检索接口

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/db/models.py`、`app/services/memory_search_service.py`（新增）、`app/routes/search_routes.py`（新增）、`app/schemas/search_schemas.py`（新增）、`app/services/note_service.py`、`app/services/stream_chat_service.py`、`app/services/interview_evaluation_service.py`、`app/services/chat_service.py`、`app/services/user_service.py`、`scripts/backfill_search_index.py`（新增）、`tests/test_memory_search.py`（新增）、`tests/api_helpers.py`
- **做法**：把历史对话、复盘结果、笔记按 T9.13 的选型建立可检索索引。索引记录必须带 `user_id`，检索接口强制以当前用户为范围。**检索结果返回原文，不做 LLM 摘要、不截断**——这是 Hermes 的明确做法，能让检索结果保持可信。
- **接口变更**：是。
- **实际改动**：
  - 新增 `search_documents` 表，把**三种来源统一成一种可检索结构**（对话消息 / 笔记 / 面试复盘）。为什么不给 `chat_messages`、`notes` 直接加 FULLTEXT：加索引同样是 DDL，而单独建表零风险，还能让检索逻辑只写一套。
  - **必须用 ngram 分词器**：InnoDB 默认的全文分词按空格与标点切词，对中文等于不工作（整句被当成一个词，搜「索引」永远搜不到）。表结构里用了 `WITH PARSER ngram`，已用 `SHOW CREATE TABLE` 确认索引建成。
  - **检索强制按 `user_id` 过滤**（三层记忆共同的隔离要求），没有「只按相似度返回」的路径；单字查询（ngram 按 2 字切词，单字到不了全文索引）退回 LIKE，仍然按用户过滤，并转义了用户输入的 `%` / `_`。
  - **写入时建索引**：消息（流式收尾处，被停止/出错的也建——那也是真实经历）、笔记（新增与修改）、复盘（问答与录音两条路径）。删除侧同步清理：删笔记、删会话、删用户都会清掉对应索引，因为索引对来源**不设外键**，不显式清理就会留下「删掉的对话还能被搜到」的脏数据。
  - 新增 `GET /search?q=&limit=&source_types=`，返回**原文**（含来源标签、相关度、来源 ID 便于前端跳转）。
  - 新增 `scripts/backfill_search_index.py`：索引是写入时建的，所以**升级前的历史内容不在索引里**（用户搜「上次那道题」正好搜不到最该搜到的东西）。已执行：对话消息 49 条、笔记 4 条、复盘 1 条。
- **验收结果**：`pytest` **182 passed**（本任务新增 7 个用例）。
  - 中文检索实测：搜「索引」命中历史对话、搜「布隆」命中笔记、搜「缓存击穿」命中笔记且相关度更高（0.27 vs 0.09）——**证明 ngram 生效**，不是「建了索引却搜不到」。
  - 隔离：换一个 `user_id` 搜同样的词，命中数 **0**；接口层同样验证（A 用户的笔记 B 用户搜不到）。
  - 失效清理：删掉笔记后再搜，命中数归零。
- **记录一个已知特性（不是 bug）**：InnoDB 全文索引对**刚写入的行**有短暂可见性延迟（FTS 索引缓存按批刷盘），表现为「刚发完消息立刻搜可能搜不到」。对真实使用没影响，但**测试里要容忍**——`test_memory_search` 用短重试规避，断言本身没有放宽。第一次跑全量时确实出现过一次单点失败，第二次起稳定通过；这个特性记在服务模块注释里，避免以后有人把它当 bug 查半天。
- **依赖**：T9.13。

### T9.15 L3 检索接入对话链路

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/agent/memory.py`、`app/agent/prompt_layer.py`、`tests/test_memory_recall.py`（新增）
- **做法**：当用户提到「之前聊过」「上次那道题」这类跨会话指代时，先检索该用户的历史再回答，而不是让用户重讲一遍。**检索必须带 `user_id` 过滤。**
- **实际改动**：
  - `app/agent/memory.py` 重新分工成三条链路并写进模块注释，避免以后混用：① `build_chat_history_from_rows`（**会话内**最近 N 条）；② `build_memory_context`（**跨会话**找回用户自己的历史，来自 L3 索引，**强制按 user_id 过滤**）；③ `get_latest_knowledge`（**外部**最新信息，DuckDuckGo）。
  - **`get_latest_knowledge` 选择共存而不是收敛**：它找的是「外面有什么新东西」，与「你说过什么」不冲突。两者也都不是每轮都跑——外网检索只在提示词真的引用了 `{search_result}` 时才跑（T1.9 定的），用户历史检索只在话里有回溯指代时才跑。
  - **触发条件用关键词而不是每轮检索**：`RECALL_KEYWORDS`（之前/上次/刚才/历史/聊过/那道题/我们讨论……）命中才查。大半提问与历史无关，白跑一次全文检索只是徒增延迟；宁可漏一点，也不让每条消息都背上检索成本。
  - 命中后把历史拼成一段文字**注入本轮用户消息**，并明确告诉模型「与当前问题无关就忽略，不要生搬硬套」——否则它会硬把历史塞进回答，比检索不到更糟。
  - **注入限长 500 字/条、最多 3 条**，与接口刻意不同：`GET /search` 返回完整原文（检索结果要可信），注入提示词必须限长（否则一段长对话就能把提示词顶爆）。截断处会写明「已截断，完整内容可查看」。
  - 检索失败只记日志、降级成「没有历史」继续回答，不让记忆检索把正常回答带崩。
- **验收结果**：`pytest` **187 passed**（本任务新增 5 个用例）。
  - 隔离：给 A、B 两个真实用户各塞一条含相同关键词的记录，A 的检索上下文里**一个字的 B 内容都没有**（这是三层记忆的硬要求）。
  - 触发条件：`should_recall` 的正反例；接口层验证「普通提问不注入历史块」。
  - 真的进了提示词：用记录型假模型断言「检索到的历史出现在模型收到的消息里」，而不是查出来丢掉。
  - **真机端到端通过**：第一轮让助手记住暗号「紫象-4271」→ 第二轮只给指代（「我上次让你记住的那个暗号是什么？我们之前说过的」）→ 模型准确答出**「紫象-4271」+ 布隆过滤器**。这就是本任务要的效果：**用户不必重讲一遍**。
- **备注**：检索的可见性依赖 T9.14 的索引写入；历史数据需要跑 `scripts/backfill_search_index.py`（已跑过）。
- **依赖**：T9.14。

### T9.16 长会话上下文压缩

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/app/db/models.py`、`app/services/session_summary_service.py`（新增）、`app/agent/prompt_layer.py`、`app/services/chat_service.py`、`tests/test_session_summary.py`（新增）、`tests/api_helpers.py`
- **说明**：这一项**不属于记忆层**，对应的是 Hermes 的上下文压缩（`/compress`），不是三层记忆中的任何一层。放在这里是因为它与 T9.15 的检索能力互补——Hermes 的取舍是「会话内靠压缩、会话间靠记忆」，两者要一起看。
- **现状**：`prompt_layer.build_stream_chain_context` 固定取最近 10 条原始消息，超过 10 条的更早内容完全丢失。
- **做法**：会话超过阈值后，把更早的消息压缩成摘要并持久化，注入时用「摘要 + 最近 N 条原文」的组合。
- **实际改动**：
  - 新增 `session_summaries` 表（一个会话一份摘要）+ `SessionSummaryService`：**渐进式压缩**，不是每次全量重压。保留最近 10 条**原文**（细节不能丢），更早的攒够 10 条压一次，把「上一版摘要 + 这批新消息」一起压成新版；`covered_message_id` 记录压到哪条，据此算增量——所以长会话里大约每 10 条消息才花一次模型调用。
  - **首次越界就先压一次**：会话刚到 15 条时虽然没攒够一批，但早期内容此刻已经在丢，所以先压。
  - 注入方式：摘要用现成的 `SystemMessage` 塞在历史之前，**不走模板字符串**——摘要里出现花括号会被 `ChatPromptTemplate` 当变量解析（这个坑本轮真踩到了，见下）。
  - 摘要限长 2000 字注入；摘要生成失败只记日志、降级成「没有摘要」继续回答。
  - **同时修了一个刚引入的真 bug**：`DELETE /sessions` 会被 `session_summaries` 的外键挡住——生产侧的 `delete_session` 又漏了新表。这已经是这一类问题的**第六次**（题库 / 画像待确认 / 复盘 / 记忆 / 检索索引 / 会话摘要），所以这轮把 `purge_user` 也补齐了会话与摘要。
- **验收结果**：`pytest` **192 passed**（本任务新增 5 个用例）。
  - 节流：15 条时才压一次；紧接着再调**不重复压**（没有新批次）；再加 10 条消息才压第二次，`covered_count` 只增加新压的那批。
  - 降级：摘要模型抛异常时返回空串，不打断正常回答。
  - 注入：用记录型假模型断言摘要真的出现在模型收到的消息里。
  - **真机端到端通过**：写 50 轮历史（第 3 轮埋「紫象-4271」），提问**故意不带任何回溯指代词**（不说「之前」「上次」，所以无法靠 T9.15 的检索兜底）——模型答出 **紫象-4271**；生成的摘要覆盖 41 轮，并准确提炼出「此为本段对话中唯一确定的方案性信息」。
- **依赖**：T9.1。

### T9.17 记忆隔离与清理的验证

- **状态**：已完成（2026-09-29）
- **涉及文件**：`interpace-backend/tests/test_memory_isolation.py`（新增）
- **做法**：补一组测试，覆盖：A 用户读不到 B 用户的记忆、检索结果不会跨用户、删除用户与删除会话时记忆的级联行为符合预期。
- **实际改动**：新增 `test_memory_isolation.py`，把三层记忆共用的隔离要求**集中验一遍**（前面各阶段是零散覆盖的）：
  1. **跨用户 ID 查询**（任务点名要求的那类用例）：拿别人的记忆条目 ID 去 **改 / 删 / 批准 / 拒绝**，四个操作全部 404；同时断言别人的条目不会出现在自己的列表里。
  2. **检索与画像隔离**：B 搜 A 笔记里的关键词返回 0 条；B 的画像列表是空的（没被 A 的数据污染）。
  3. **删会话的级联**：该会话的检索索引与上下文摘要都被清掉——两者一个不清理就是脏数据（删掉的对话还能搜到），一个会被外键直接挡住删除（实现时真踩到过）。
  4. **删用户的级联**：用**泛化断言**遍历 `Base.metadata` 里所有带 `user_id` 的表，任何一张有残留就失败——加了新表却忘了改删除逻辑时，这条会自动抓到。
- **验收结果**：`pytest` **196 passed**（本任务新增 4 个用例）。
- **依赖**：T9.15。

---

## 12. 阶段 10：收尾

### T10.1 统一接口版本前缀 `/api/v1`

- **状态**：已完成（2026-09-30）
- **涉及文件**：`app/main.py`、`tests/conftest.py`、`tests/test_smoke.py`、`tests/test_speech_stream.py`、`interpace-frontend/.env.development`、`.env.example`、`.env.production`、`vite.config.ts`、`src/api/speechStream.ts`、根 `AGENTS.md`、`interpace-backend/prompt.md`
- **现状**：根 `AGENTS.md` 要求接口统一带 `/api/v1/`，实际后端不带前缀、靠 Vite 代理 `rewrite` 把 `/api` 剥掉；`.env.example` 写的是 `/api/v1`，与实际不符。
- **实际改动**：
  1. **后端**：新增 `API_V1_PREFIX = "/api/v1"`，把所有业务 router 挂进一个 `api_v1_router` 再 `app.include_router`。挂成一层而不是给 14 个 router 逐个写前缀，是为了以后加 v2 时只多挂一个 router。
  2. **刻意不带前缀的三类**：探活 `/health/*`、文档 `/docs`、根路径 `/` 与静态目录 `/uploads`。探活是给容器/负载均衡调用的，不该跟着 API 版本走。
  3. **测试**：前缀放进 `conftest.py` 的 `base_url`（`http://test-server/api/v1/`）。httpx 会把 base_url 的路径与请求路径拼接，所以**用例里那 230 处路径一个字都不用改，测的仍是真实路径**。只有 3 处例外要单独处理：`/health`、`/docs` 用绝对地址绕开 base_url（`test_smoke.py`），以及 `test_speech_stream.py`——那个文件用 starlette 的 `TestClient`，它的路径合并只对 HTTP 生效、**WebSocket 不合并**，所以显式拼了前缀常量。
  4. **前端**：三个 env 文件的 `VITE_API_BASE_URL` 统一改成 `/api/v1`；`vite.config.ts` 删掉 `rewrite`（代理转发前不再剥前缀）；`speechStream.ts` 的注释同步。
  5. **文档**：根 `AGENTS.md` 的「现状提醒」换成「已落实 + 新增接口别再自己拼前缀」；`interpace-backend/prompt.md` 顶部加了一条说明——该文档里写的路径是相对业务前缀的写法。
- **验收结果**：
  - `pytest` **219 passed**（新增 `test_business_path_requires_api_v1_prefix`：裸 `/users` 必须 404、`/api/v1/users` 未登录必须是 401，这条是「前缀真的加上了」的直接证据）。
  - `pnpm run build` 通过。
  - **真机联通**（后端 8000 与 Vite 5173 都在跑）：`8000/api/v1/users` → 401、`8000/users` → 404、`8000/health/ready` → 200；经 Vite 代理 `5173/api/v1/users` → 401、`5173/api/v1/prompt/config/agents` → 200。代理不再改写路径后前后端地址是对齐的。
- **注意**：这是破坏性变更（所有接口地址变了），已在同一个任务里改完前后端与文档；如果本地还有旧的前端进程或用了 `.env.local` 覆写，重启后才会生效。
- **依赖**：T0.3。

### T10.2 补充接口文档

- **状态**：已完成（2026-09-30）
- **涉及文件**：`docs/接口/README.md`（新增）、`docs/接口/会话与对话.md`（新增）、`docs/接口/笔记.md`（新增）
- **现状**：`docs/` 下只有两个流程图和一个 TODO，没有任何接口文档。`AGENTS.md` 要求"改接口要同步文档"，之前这条无法执行。
- **做法**：先立三份文档，按"总览 + 模块"的层级组织，避免一个文件越长越大：
  1. **`docs/接口/README.md`**：通用约定（版本前缀、鉴权、统一错误结构、状态码、时间与分页口径、SSE/WS 概述）+ **53 个接口的全量索引表**（含是否鉴权）。索引表不是手抄的，是从 `app.openapi()` 导出核对的，文档里附了导出命令，方便新增接口后重新核对。
  2. **`docs/接口/会话与对话.md`**：会话 CRUD、消息分页、SSE 流式对话的**完整事件序列**（`start`/`delta`/`error`/`done`）、停止接口的幂等语义、语音 WebSocket 的双向消息协议与音频参数。`session_model` 这个"除了创建都要再传一次"的反直觉约定单独写了小节说明原因。
  3. **`docs/接口/笔记.md`**：笔记 CRUD 与"按消息导入"接口，并解释了**笔记为什么没有 `session_id`**（来源是软引用、笔记生命周期比会话长）。
- **写文档时纠正的三处偏差**（都是"凭印象写会写错"的地方，逐条对着代码核对后改的）：
  - `DELETE /notes/{id}` 返回的是 **204 No Content**，不是带 message 的 JSON；
  - 停止接口的文案是 **"已请求停止生成"**、重复调用变成"该消息此前已请求停止"；
  - 笔记列表用的是 `limit`/`offset` + `total`，而会话列表用的是 `page`/`page_size` + `has_more`——**两套分页口径并存**，是本项目的一个既有不一致，文档里明确写出来了。
- **顺带记录的风险**：`/api/v1/prompt/*` 三个接口无鉴权（见 T10.8），索引表里把"鉴权=否"标了出来。
- **验收结果**：对照 `app.openapi()` 导出的 41 条 HTTP 路径 + 1 条 WebSocket 路径逐条核对，索引表**无遗漏、无多余**；四组必写模块（会话、消息、流式对话、笔记）的路径、方法、请求体、响应体、错误码与约定均已覆盖。
- **第二批（同一天补完）**：把其余模块一并写完，不留半成品——
  - `docs/接口/面试与复盘.md`：面试详情 / 结束面试（幂等）/ 生成复盘 / 读取复盘 / 按录音复盘，含五条细分错误码；
  - `docs/接口/学习与素材.md`：题库（**一份卷子只评分一次，重复提交 409**）、简历导出（只导"优化后的简历"那一节、按哈希去重）、检索（FULLTEXT + ngram、"刚写入可能搜不到"的可见性延迟）、资源与上传（`resource_type`/`storage_scene`/`upload_purpose` 取值表）；
  - `docs/接口/画像与记忆.md`：三层记忆里的 L1 明细（`category`/`source`/`mastery`/`pending_approval` 语义与合并规则）、记忆 CRUD 与批准 / 拒绝、画像提案"先确认再写入"、用户与鉴权（注册 / 登录 / 刷新）、提示词管理。
- **本轮又纠正的两处**：
  - `GET /profile-proposals` 返回的是该会话的**全部**提案（含已确认 / 已忽略），不是只返回待确认——前端要靠 `message_id → id` 映射把卡片挂回历史消息，所以必须全量返回；文档里写明由前端按 `status` 过滤；
  - `GET /profile` 的 `memories` **包含待确认条目**，只有批准过的才参与注入。
- **依赖**：T10.1（已完成，前缀定型后再写文档，免得路径改名重写一遍）。

### T10.3 后端补充 `.env.example`

- **状态**：已完成（2026-09-30）
- **涉及文件**：`interpace-backend/.env.example`（新增）
- **现状**：后端只有 `.env`，没有 `.env.example`，新人无法知道需要哪些变量。前端已有模板。
- **做法**：按 `app/core/settings.py` 的必填校验项整理模板，密钥位留空占位。
- **实际改动**：模板分两段写——**必填项**（缺失或不合格时应用启动就失败：`MYSQL_URL`、`JWT_SECRET`、MinIO 四元组）与**选填项**（有默认值：JWT 有效期、大模型、Redis、语音服务）。每个键都写了用途与坑：
  - `JWT_SECRET` 标了「至少 32 字节」和生成命令；
  - `VOLC_TTS_SPEAKER` 标了「必须与 TTS 模型版本配套，否则报 `resource ID is mismatched...`」（这是实测踩过的坑）；
  - 语音的两个接入点也列了出来（本地联调时可以指向假服务）。
- **验收结果**：用脚本比对确认**模板覆盖了 `settings.py` 读取的全部键**（差集为空）；再把模板解析成环境变量实际加载一次 —— 配置能正常构建，必填项与默认值都符合预期。
- **一处过程记录**：第一次验证时我用 `APP_ENV=examplecheck` 想加载临时文件，但 `_normalize_app_env` 只接受 development/production（其它值一律归到 development），实际加载的是 `.env.development`，**等于没验**。改成「把模板值直接注入环境变量」后才真正验证到模板本身。

### T10.4 前端产物分包

- **状态**：已完成（2026-09-30）
- **涉及文件**：`interpace-frontend/src/router/index.ts`、`interpace-frontend/vite.config.ts`
- **现状**：改造前是**一个 2112 kB（gzip 714 kB）的 `index.js`** + 一个 405 kB 的 CSS。原因是两件事叠在一起：路由用静态 `import`（所有页面进同一包），且 `main.ts` 全量注册 `element-plus`。
- **做法**：两处改动，都不加依赖、不改组件写法。
  1. **路由级懒加载**：`src/router/index.ts` 里五个页面组件改成 `() => import(...)`。笔记页才用得到的 wangEditor、代码高亮用的 prismjs 因此自动离开首屏。
  2. **大依赖单独分块**：`vite.config.ts` 加 `build.rolldownOptions.output.advancedChunks.groups`，按 `node_modules` 路径把 `element-plus` / `@wangeditor` / `markdown-it+prismjs` / `vue 全家桶` 拆成四个 vendor chunk。它们内容稳定，发版后 hash 不变，用户能一直吃浏览器缓存。
- **验收结果**：`pnpm run build` 通过。入口包 **2112 kB → 56.74 kB**（gzip 714 kB → **21.56 kB**），拆出 `vendor-element-plus` 989 kB、`vendor-wangeditor` 800 kB（**仅笔记页加载**）、`vendor-markdown` 146 kB、`vendor-vue` 31 kB，页面级 chunk 每个 5~29 kB。
  - 逐项核对：`dist/assets/NotebookRoom-*.js` 只有 5.4 kB，wangEditor 那 800 kB 被 `NotebookRoom` 动态触达，**不再进首屏**。
- **遗留（未达标的一条，已单列 D27）**：**构建告警没有消失**——`vendor-element-plus` 989 kB（gzip 316 kB）与 `vendor-wangeditor` 800 kB 仍超 500 kB 阈值。前者是因为 `main.ts` 里 `app.use(ElementPlus)` 全量注册，**首屏仍要下载它**；改成按需引入是标准解法，但要加构建期依赖（`unplugin-vue-components`），按 AGENTS 规定需先确认，见第 15 节 D27。`vendor-wangeditor` 只在笔记页加载，体积大但不在关键路径上，可以接受。
- **依赖**：各页面功能基本定型。

#### 后续修复：分包导致 prismjs 在生产环境报错（2026-09-30）

**现象**（用户在部署好的站点上看到）：

```
ReferenceError: Prism is not defined
    at vendor-markdown-*.js
```

**根因**：`prismjs/components/prism-*.js` 这些语言包是给 `<script>` 直接引入设计的，
它们引用的是**全局变量** `Prism`，而不是 `import` 进来的模块。Prism 核心本来会挂全局，但它写的是：

```js
typeof global !== 'undefined' && (global.Prism = Prism)
```

浏览器里没有 `global`（那是 Node 的东西），**这句永远不执行**。原来所有代码在一个 chunk 里时
碰巧没事；T10.4 拆分块后，语言包在全局还没挂上时求值就炸了。
**开发模式看不到这个错**（Vite 的 CJS 互操作会补上 `global`），**只有生产构建才暴露**。

**修法**（两步，缺一不可）：

1. 新增 `src/utils/prism-setup.ts` 显式把 Prism 挂到 `globalThis`，并在 `markdownUtil.ts` 里
   **放在所有语言包之前 import**（ESM 依赖按书写顺序求值）；
2. `vite.config.ts` 里把 `prismjs` **从手动分块规则中移除**——core / setup / 语言包必须待在
   同一个 chunk 里，跨 chunk 的加载顺序不受控，这个保证就没了。

**验证**：构建后确认挂全局的语句与语言包落在**同一个 chunk**且赋值在前；
再用 CDP 在被 Nginx 托管的**部署产物**上打开聊天页，读到的页面状态是
`{"prismGlobal":"object","hasGrammar":true,"highlight":"<span class=\"token keywo…"}`，
**控制台零错误**。

> 教训：这类"引擎语义 + 打包行为"的坑，`pnpm run build` 成功、开发模式正常都发现不了，
> 必须在**真实构建产物**上跑一遍。T11.8 的冒烟脚本目前覆盖不到页面级 JS 错误，
> 后面可以考虑加一条"打开关键页面、断言控制台无 error"的检查。

### T10.5 后端测试覆盖补齐

- **状态**：已完成（2026-09-30）
- **涉及文件**：`interpace-backend/tests/test_prompt_api.py`（新增）、`tests/test_user_api_errors.py`（新增）、`tests/test_auth_api.py`（新增）、`app/routes/prompt_routes.py`
- **现状**：`tests/` 下已有 30 个测试文件、202 个用例，但**覆盖是「按任务」长出来的，不是「按路由」**。用 `app.openapi()` 逐个核对后，缺口是：
  - `/prompt/*` 三个接口**完全没有用例**（模板版本列表、回滚、智能体配置）；
  - `/auth/refresh` 没有用例（注册/登录的成功链路被 conftest 间接覆盖了，错误路径没有）；
  - `/users` 只验了「列表接口匿名 401」和成功链路。
- **做法**：本轮只补缺口，不重写已有用例。新增三个文件按模块对齐，每个用例走一个正常路径 + 一组错误路径。
- **实际改动（含两处真实缺陷修复）**：写用例时先撞上两个真问题，都属于「错误路径压根不可达」这一类，所以连测试带修复一起做了：
  1. **提示词接口的实际路径是 `/prompt/prompt/...`**（前缀写了两遍）。`prompt_routes.py` 的 `APIRouter(prefix="/prompt")` 与 `main.py` 的 `include_router(..., prefix="/prompt")` 叠加。判定依据是 `interpace-backend/prompt.md` 里登记的路径本来就是单前缀，且**前端没有任何地方调用这三个接口**——修正为单前缀不会破坏调用方。修法按项目惯例（其余 13 个 router 都不自带前缀）删掉 router 上的前缀。
  2. **回滚接口的 404 被自己的兜底吞成 400**：`raise HTTPException(404)` 写在 `try` 里，而下面 `except Exception` 会连 `HTTPException` 一起抓，最终返回 `400 + detail="回滚模板失败: 404: 模板不存在"`。加了一条 `except HTTPException: raise` 放行。
- **验收结果**：`pytest` **218 passed**（本轮新增 16 个用例；`InsecureKeyLengthWarning` 仍为 0）。逐路由核对后，**41 个 HTTP 路径全部有对应用例**，`/auth/refresh`、`/prompt/*`、`/users` 错误路径的缺口已填。
- **顺带记录（未改行为）**：`/prompt/config/agents` 会把**全部智能体名与场景**公开返回，且这三个接口**没有任何鉴权**（router 没挂 `get_current_user`）。当前前端不调用它们，属于内部管理接口，但一旦上公网就是「提示词清单可被匿名读取」。已单列为 T10.8 待决策。
- **依赖**：阶段 1~8 接口定型。

### T10.8 提示词管理接口的鉴权与暴露面

- **状态**：待办
- **现状**：`/prompt/templates/{agent}/{scene}` 返回模板**正文全文**，`/prompt/config/agents` 返回全部智能体清单，三个接口均无鉴权、无限流，公网可直接访问。前端目前不调用它们。
- **做法（择一）**：① 直接给 router 挂 `get_current_user`（最小改动，但仍对全部登录用户开放）；② 挂管理员校验（需要先有"管理员"这个概念）；③ 生产环境不挂载该 router（`APP_ENV=production` 时跳过 `include_router`）。
- **倾向**：先做 ①，等有管理后台再说 ②；③ 适合"确定永远不对外"的场景。
- **依赖**：T10.5（已完成，缺陷来源）。

### T10.6 JWT 密钥长度不足

- **状态**：已完成（2026-09-30）
- **涉及文件**：`interpace-backend/app/core/settings.py`、`interpace-backend/.env`、`.env.development`、`tests/test_settings_validation.py`（新增）
- **现状**：T0.1 跑测试时出现 `InsecureKeyLengthWarning: The HMAC key is 20 bytes long, which is below the minimum recommended length of 32 bytes for SHA256`（RFC 7518 §3.2）。当前 `.env` 里的 `JWT_SECRET` 只有 20 字节，签名强度不足。
- **做法**：换成长度足够的随机密钥，并在 `app/core/settings.py` 的 `from_env` 里加最小长度校验，让配置错误在启动时就暴露，而不是等到运行期才告警。
- **注意**：换密钥会让已签发的 token 全部失效，需要在低峰期操作并提前通知；`.env` 不进仓库，别忘了同步更新部署环境的配置。
- **实际改动**：
  - `Settings.from_env` 新增最小长度校验（`MIN_JWT_SECRET_BYTES = 32`）。**放在启动期校验是刻意的**：PyJWT 只打一条 `InsecureKeyLengthWarning` 就继续跑，这种「警告级」问题极容易被忽略——那个 20 字节的密钥就是这么一路留到 T0.1 跑测试才暴露的。报错里同时给出生成命令，省得别人再去搜怎么写。
  - 生成了 64 字节的随机密钥并写入 `.env` / `.env.development`。
- **验收结果**：`pytest` **202 passed**，且 **`InsecureKeyLengthWarning` 出现次数从 196 次降到 0**（这是最直接的证据）。
  - 新增 3 个用例：过短的密钥启动即失败且报错里含生成命令、达标长度通过、完全没配时报的仍是「必填」而不被长度校验抢信息。
- **注意（已在文档与本任务留痕）**：换密钥会让**所有已签发的 token 立即失效**（用户需重新登录）。本次是开发环境、影响可忽略；**上线换密钥时要在低峰期操作并提前通知用户**，`.env` 不进仓库，别忘了同步更新部署环境的配置。

### T10.7 对齐 Alembic 基线与真实 schema

- **状态**：已完成（2026-09-30）
- **结论（原 D24，已确认）**：**补一版基线迁移、正式启用 Alembic**。现在这种「配了但没跑过任何 DDL」的中间态风险最大。
- **涉及文件**：`interpace-backend/alembic/versions/598c8ac58d95_baseline_schema.py`（新增）、`app/main.py`、`docs/开发/数据库变更流程.md`（新增）
- **现状**：`alembic/` 配置齐全（`env.py` 已接 `Base.metadata`），但唯一迁移 `8d4d0586ab85_init_user_table.py` 的 `upgrade()` 是空的 `pass`。真实 schema 全部来自 `app/main.py` lifespan 里的 `Base.metadata.create_all(engine)`——`user_profiles`、`sessions`、`chat_messages`、`resources`、`interviews`、`prompt_templates` 六张表都没有对应迁移。等于 schema 变更没有任何版本管理。
- **风险**：一旦上生产，加列 / 改类型 / 加索引没有可回滚的路径；多人协作时也无法确认各环境 schema 是否一致。这是 T1.3 选脚本而非 Alembic 做数据 seed 的原因之一。
- **做法**：先按 D24 定 Alembic 的定位，再决定是补一版基线迁移对齐现状，还是正式弃用并移除相关配置。不要留成现在这种「配了但没用」的中间态。
- **实际改动**：
  - **基线迁移怎么来的**：不手写，而是**对着一个空的临时库跑 `alembic revision --autogenerate`**——这样产出的就是「`create_all` 会建出来的全部表」的显式 DDL（16 张表）。`mysql_prefix='FULLTEXT'` / `mysql_with_parser='ngram'` 也被正确带上了（这条最容易在 autogenerate 里丢掉）。
  - 删掉了原来那条空的 `8d4d0586ab85_init_user_table.py`，把基线设成根（`down_revision = None`），并在文件头写清楚它的定位与「已有库不要执行、要 stamp」。
  - **`main.py` 的 lifespan 改造**：开发环境仍跑 `create_all`（图方便：跑测试、新拉代码即可用），**生产环境跳过**。让 `create_all` 在生产跑只会掩盖「迁移没执行」——表面能用、实际 schema 是旧的。
  - 新增 `docs/开发/数据库变更流程.md`：日常流程（改模型 → autogenerate → **人工检查** → upgrade）、autogenerate 的三个已知盲区、已有库如何首次接入（`alembic stamp`）、回滚、以及一条「校验迁移与模型是否一致」的自检方法。
  - 开发库已 `alembic stamp --purge head` 标记到基线（原来的版本行记着已删除的旧 revision，不 purge 会报 `Can't locate revision`）。
- **验收结果**：`pytest` **202 passed**；`alembic current` 显示 `598c8ac58d95 (head)`。
  - **schema 一致性实测**：在空库上 `alembic upgrade head`，再与 `create_all` 产出的库逐维度比对 —— **17 张表、51 个索引、24 个外键，列 / 索引 / 外键三个维度零差异**。
  - **比对方法本身也踩了一下**：直接比 `SHOW CREATE TABLE` 会报 6 张表不一致，但差异全是**自动生成的外键约束名编号顺序**（`xxx_ibfk_1/2/3` 指向不同列）；改用 `information_schema` 按「列 / 索引 / 外键指向」比对才是有效判据。另外验证库的**排序规则必须与目标库一致**，否则列上的 collation 会全都不一致。
  - **顺带发现一个真实证据**：开发库里 `chat_messages.status` 的列注释还停留在旧版，而新库注释是新的——因为 `create_all` **永远不会修改已存在的表**。这正是「schema 变更没有版本管理」的活证据，已写进文档。
- **依赖**：无，但建议在正式部署前完成。

---

## 13. 阶段 11：Docker 化与部署上线（腾讯轻量云 2核2G）

**为什么单独立一个阶段**：目标环境是腾讯轻量云 **2 vCPU / 2GB 内存**，这是个硬约束，
有几处会影响实现方式（镜像在哪构建、MinIO 要不要留、uvicorn 开几个 worker）。
这一阶段与阶段 6~10 没有代码依赖，**可以随时提前做**；建议放在阶段 8 之后、正式上线前。

**2核2G 的三条硬约束（写在最前面，后面每个任务都受它约束）**：

1. **不在服务器上构建前端**：`vite build` 峰值内存通常在 1GB 以上，2G 机器上和 MySQL 抢内存极易 OOM。镜像必须在本机（或 CI）构建好推仓库，服务器只 `pull` + `up`。
2. **默认只跑 1 个 uvicorn worker**：后端进程加载了 `pymupdf` 等原生库，单进程常驻内存已不小；2 核开多 worker 只会互相抢内存，收益是负的。
3. **内存要留余量**：MySQL + Redis + 后端 + 反向代理的常驻内存要留出至少 300MB 空闲，否则一次大文件解析就可能被 OOM Killer 干掉。具体数字在 T11.5 里对账。

### T11.1 部署形态与上线环境确认（决策）

- **状态**：待办（决策任务，先拍板再动代码）
- **做法**：确认三件事，并写回 T11.2~T11.9：① 镜像在哪构建（本机构建后推镜像仓库 / CI 构建）；② 域名与备案情况（腾讯云大陆机房用 80/443 必须先备案，没备案只能走 IP + 非标准端口，或换香港/境外机房）；③ HTTPS 证书来源（腾讯云免费证书手动续期 vs Let's Encrypt 自动续期）。
- **验收**：三件事都有明确结论，且和 T11.4 的编排、T11.6 的配置一致。
- **依赖**：无。

### T11.2 后端 Dockerfile

- **状态**：进行中（2026-09-30，Dockerfile 已写并构建通过；**用户要求暂停部署阶段**，尚未做容器内冒烟）
- **涉及文件**：`interpace-backend/Dockerfile`（新增）、`interpace-backend/.dockerignore`（新增）
- **实际改动**：
  - 两阶段构建：builder 用 `uv==0.12.9`（与开发机同版本，避免 lock 解析漂移）+ `uv sync --frozen --no-dev`；runtime 只 `COPY --from=builder /app`。
  - 先拷 `pyproject.toml`/`uv.lock` 再拷源码，让改代码不使依赖层缓存失效。
  - 非 root（uid 10001）运行；装 `tzdata`（否则日志与业务时间退化成 UTC）。
  - **`uploads/` 必须预建**：`main.py` 的 `StaticFiles(directory="uploads")` 默认 `check_dir=True`，目录不存在会**直接启动失败**；`logs/` 同理（loguru 文件 sink 的属主必须是 appuser）。
  - `HEALTHCHECK` 打 `/health/live`（不带 `/api/v1` 前缀，见 T10.1）。
  - `CMD` 里 **worker 数写死为 1**，不给环境变量留口子，避免有人"顺手调大"违反阶段 11 的硬约束 2。
  - `.dockerignore` 挡掉 `.env`、`.venv`、`logs/`、`uploads/`、`tests/`。
- **验证结果**：`docker build -t interpace-backend:dev .` **构建成功**（镜像 sha256 `ad3d7a5b…`）。**容器启动与容器内冒烟未做**（用户暂停了部署阶段）。
- **依赖**：T11.1。

### T11.3 前端 Dockerfile 与静态托管

- **状态**：进行中（2026-09-30，Dockerfile 与 Nginx 配置已写，**构建未验证**；用户要求暂停部署阶段）
- **涉及文件**：`interpace-frontend/Dockerfile`（新增）、`interpace-frontend/.dockerignore`（新增）、`interpace-frontend/deploy/nginx.conf`（新增）
- **实际改动**：
  - 构建阶段 `node:22-slim` + `corepack` + `pnpm install --frozen-lockfile` → `pnpm run build`（走 `.env.production`，`VITE_API_BASE_URL=/api/v1`）；运行阶段只带 `dist/` + 配置，用 `nginx:1.27-alpine`。
  - `deploy/nginx.conf`：静态托管 + `/api` 反代到 `http://backend:8000`（服务名与 T11.4 的 compose 对齐），并覆盖了三个**必须单独配置的路径**：
    1. **SSE**（`/api/v1/sessions/{id}/stream-chat`）关 `proxy_buffering`——否则前端拿不到增量，打字机效果失效；
    2. **WebSocket**（`.../speech/stream`）转发 `Upgrade`/`Connection` 且 `proxy_http_version 1.1`——否则语音面试线上静默失败；
    3. `client_max_body_size 100m`，否则上传录音/PDF 直接 413。
  - `index.html` 明确 `no-cache`，带 hash 的 `/assets/` 强缓存一年。
- **注意（T7.7 补充）**：Nginx 的 `/api` 反代必须配 **WebSocket 升级头**（`proxy_http_version 1.1` + `Upgrade` / `Connection`），否则语音面试在线上会静默失败（本地开发靠 Vite 代理的 `ws: true`，线上没有它）。
- **验证结果**：**未验证**（没跑 `docker build`）。恢复部署阶段后要做的第一件事就是把它构建出来，并用浏览器走一遍登录 + 流式对话 + 一次语音面试。
- **依赖**：T11.1。

**补充（2026-09-30）：Nginx 必须能在运行时重新解析上游**

部署后实测发现一个会在**发版时中断服务**的问题：nginx 只在**启动时**解析一次上游主机名并把 IP 缓存住。
发版如果只重建了后端（很常见——只改了后端镜像），后端容器可能拿到新 IP，
而 nginx 还往旧 IP 转发，表现是**持续 502，直到手动重启 nginx**。

修法（`deploy/nginx.conf`）：加 `resolver 127.0.0.11 valid=10s ipv6=off;`，
并把所有 `proxy_pass` 改成**变量形式** `proxy_pass http://$upstream_backend:8000;`
（配合 `set $upstream_backend backend;`）。用变量时 nginx 才会在运行时重新解析。

**决定性验证**：删掉后端容器 → 起一个占位容器**抢走旧 IP**（172.27.0.5）→ 重建后端
（拿到新 IP 172.27.0.7）→ **不重启 nginx**，连续请求全部 200。
没有这个配置，nginx 会一直打在那个占位容器上。

代价：解析缓存过期那一刻的请求可能拿到一次 502（可接受的权衡——比"永久 502 直到重启"好得多）。

另外把 frontend 的 `depends_on` 从 `service_started` 升级为 **`service_healthy`**：
否则后端还在跑迁移时 nginx 就开始接请求，用户会看到一片 502。

### T11.4 docker-compose 编排

- **状态**：已完成（2026-09-30）
- **做法**：一个 compose 文件编排后端 / MySQL / Redis / （按 D25 决定是否含 MinIO）/ Nginx；显式声明数据卷、容器网络、`restart: unless-stopped`，并给日志加 `max-size` 上限（否则磁盘会被日志吃满）。
- **安全硬要求（T12.4 验证时确认）**：**后端 8000 端口只能 `expose`，不能 `ports` 映射到宿主机**。
  否则攻击者可以绕过 Nginx 直连后端，IP 配额与限流的所有前提都不成立（详见 T12.4 的补充说明）。
  同理 MySQL / Redis / MinIO 也只在容器网络内可达。
- **验收**：`docker compose up -d` 后所有容器健康；`down` 再 `up` 数据不丢。
- **依赖**：T11.2、T11.3。

**涉及文件**：`docker-compose.yml`（新增）、`.env.example`（新增，compose 用它）、
`interpace-backend/docker-entrypoint.sh`（新增）、两个 Dockerfile、`.gitignore`、`docs/部署/docker部署.md`（新增）

**实际改动与踩到的坑**：

1. **容器启动前必须跑迁移**。生产环境 `main.py` 不跑 `create_all`（T10.7 的决定），
   表结构的唯一来源是 Alembic，所以新增 `docker-entrypoint.sh`：先 `alembic upgrade head`，
   再用 `exec` 启动 uvicorn（exec 才能让 uvicorn 成为 PID 1、正确接收 SIGTERM）。
   `set -e` 是刻意的：迁移失败就让容器退出，**不要**带着旧 schema 硬启动——
   那会变成"服务活着但功能时好时坏"，比直接挂掉更难查。
2. **变量文件必须叫 `.env`**。compose 只自动读当前目录的 `.env`，别的名字每次都要加
   `--env-file`（很容易忘）。所以模板是仓库根目录的 `.env.example`，用 `cp .env.example .env`。
3. **顺手补了一个安全隐患**：`.gitignore` 原来只逐个列了 `.env` / `.env.development` / `.env.production`，
   新出现的 `.env.demo`、`.env.test`、`.env.docker` **都不在忽略名单里**——
   部署时创建它们会被 `git add .` 直接提交上去。已改成 `.env.*` + 只放行 `!.env.example`。
4. **前端镜像不能依赖 `.env.production`**：那个文件被 gitignore 排除了，全新克隆/CI 里没有它，
   构建出的产物会在**用户浏览器里**报"缺少 VITE_API_BASE_URL"（很难定位）。
   改成用构建参数 `ARG VITE_API_BASE_URL=/api/v1` 并给默认值。
5. **pnpm 版本要锁**：corepack 默认装最新版，而 **pnpm 10+ 遇到被忽略的构建脚本会直接报错退出**
   （`ERR_PNPM_IGNORED_BUILDS`），本机用 9.x 正常、容器里失败。已锁 `pnpm@9.1.0`。
6. **MinIO 镜像两个源都不好用**（实测）：Docker Hub 的 `minio/minio` 报 `repository does not exist`，
   `quay.io/minio/minio` 报 `unauthorized`（匿名拉取被拒）。compose 用 quay 源，
   服务器上要么 `docker login quay.io`，要么走离线传输（`docker save` → `scp` → `docker load`）——
   后者反正对 MySQL / Redis 也是必需的（大陆机房拉 Docker Hub 很慢）。
   **这不改变 D25 的结论**（仍先留着 MinIO），只是因为"离线传输本来就要做"，多了一步镜像获取。
7. **redis 的 `--save` 要两个参数**：写成 `--save=` 会被当成"`save` + 空值"，
   再把后一个 `--appendonly=no` 吃掉，直接 `Bad directive` 起不来。必须写成独立的
   `--save` + 空串。
8. 只给 frontend 发布端口（`WEB_PORT`，默认 80），其余服务都不写 `ports`（见上面的安全硬要求）。
   全部服务配 `json-file` 日志上限（10m × 3），不然 2G 机器会被日志吃满磁盘。

**验证结果（本机真跑了一遍，不是只看语法）**：

- `docker compose up -d --build` 后**五个容器全部 healthy**。
- **迁移真的执行了**：后端日志显示 `Running upgrade -> 598c8ac58d95, baseline schema` 与
  `-> 71257d0297db, add usage_records`；库里有 **18 张表**，`alembic_version` = `71257d0297db`。
- **整条链路经 Nginx 打通**：首页 200、`/api/v1/config/runtime` 200、
  注册 201 → 登录拿到 token → 建会话 → **SSE 流式对话增量到达**（证明 Nginx 那段
  `proxy_buffering off` 生效，不是攒完一次性吐）。
- **数据持久化**：`docker compose down` 后再 `up -d`，原 token 仍可用、历史消息仍在。
- **内存实测**：frontend 9M / redis 17M / minio 87M / mysql 155M / backend 245M，
  **合计约 513 MiB**，2G 机器上还剩约 1.2G。

**顺手修的小问题**：`index.html` 的静态 `<title>` 还是脚手架默认的 `interpace-frontend`
（首屏渲染前与分享抓取时看到的就是它），已改成正式标题并补了 `description`。

**未验证的部分**：语音面试的 WebSocket 经 Nginx 的真实链路（需要一个能发音频的客户端），
Nginx 的升级头配置是按官方写法配的，但**没有真机跑过**。

### T11.5 2核2G 资源预算与参数调优

- **状态**：进行中（2026-09-30：已完成内存实测与参数下调，剩余"上线前再测一次"）
- **做法**：按约束 2、3 对账：MySQL 的 `innodb_buffer_pool_size` 等参数下调；Redis 设 `maxmemory`；后端固定单 worker；视需要加一块 swap 兜底（只防猝死，不能当常态）；上线前用 `docker stats` 记录一份真实内存占用。
- **验收**：给出各容器常驻内存的实测数字，且合计留出 ≥300MB 空闲。
- **依赖**：T11.4。

**已做**（2026-09-30）：MySQL 显式 `--innodb-buffer-pool-size=256M`、`--max-connections=50`、
关掉 `performance_schema`；Redis `--maxmemory 96mb` + `allkeys-lru` 且关持久化（只是模板缓存，
丢了能从 MySQL 重建）；后端 worker 写死 1。

**实测内存**（空闲状态）：frontend 9M / redis 17M / minio 87M / mysql 155M / backend 245M，
**合计约 513 MiB**。2G 机器上余量约 1.2G，远超 ≥300MB 的要求。

**还没做**：服务器上的实测（本机是 32G，测出来的只是"绝对占用"，
真正的风险是服务器上 swap 与 OOM 行为）；是否需要加 swap 兜底，等真机部署后再定。

### T11.6 生产环境变量与密钥

- **状态**：已完成（2026-09-30）
- **做法**：补齐生产 `.env`（数据库/Redis/MinIO 连接、模型 Key、JWT 密钥、CORS 白名单）；`DEBUG`/`APP_ENV` 切生产；JWT 密钥换成足够长的随机值（与 T10.6 合并处理）；确认 `.env` 不进镜像、不进仓库。
- **验收**：容器里读到的配置全部是生产值；仓库里搜不到任何真实密钥。
- **依赖**：T11.4、T10.3、T10.6。

**实际改动与验证**：

1. **密钥不进仓库**：`.gitignore` 原来只逐个列了 `.env` / `.env.development` / `.env.production`，
   新出现的 `.env.demo` / `.env.test` / `.env.docker` **都不在忽略名单**——部署时创建它们会被
   `git add .` 提交上去。已改成 `.env.*` + `!.env.example`。
   用 `git grep` 搜真实 Key 值：**未命中**。
2. **密钥不进镜像**（实测，不是只看 `.dockerignore`）：镜像里 `find / -name '.env*'` 为空；
   镜像文件系统里 `grep` 真实 Key 为空；`docker history` 的构建层里也搜不到（有些密钥会残留在层里）。
3. **CORS 白名单改成可配**：原来写死在 `main.py` 里三个本机地址。现在读 `CORS_ORIGINS`
   （逗号分隔），不配时退回本机开发地址、**不会**变成"允许所有来源"。
   生产是同源部署（Nginx 同时托管前端与反代 `/api`），浏览器根本不发跨域请求，所以留空即可。
4. `APP_ENV=production`、`RUN_MIGRATIONS=true`、`TRUST_PROXY_HEADERS=true` 都写进 compose 与
   `.env.example`，并逐项注明了用途与坑。

**验收结果**：容器里读到的是生产值（`APP_ENV=production`、`MINIO_*` 为随机密码）；
仓库与镜像三处扫描均无密钥；`pytest` 新增 2 个 CORS 用例。

### T11.7 数据持久化与备份

- **状态**：已完成（2026-09-30）
- **涉及文件**：`deploy/backup.sh`（新增）、`deploy/restore.sh`（新增）
- **做法**：MySQL 与对象存储挂持久卷；`mysqldump` 定时备份并轮转；写一次**恢复演练**步骤。
- **备份脚本的两处讲究**：
  - 用 `MYSQL_PWD` 而不是 `-p<密码>`：后者会把密码暴露在进程列表里，还会让 mysqldump
    每次打一句 "Using a password on the command line interface can be insecure"。
  - 做完**完整性校验**（gzip 可解压 + 内容里有 `CREATE TABLE`）。只检查"文件非空"是不够的——
    导出中途失败同样会留下一个非空的坏文件。
- **实测的完整演练**：备份 → 恢复到临时库 `interpace_restore_drill` →
  表数量 18 与 `alembic_version` 均与生产库一致，`users` / `sessions` / `chat_messages` /
  `usage_records` 四张表的行数逐表比对完全相同 → 删除临时库。
  **恢复是破坏性的**，所以脚本支持传目标库参数，演练时往临时库灌。
- **另一个已验证的点**：`docker compose down`（保留数据卷）后 `up -d`，原登录 token 仍可用、
  历史消息仍在。数据卷为 `mysql-data` / `minio-data` / `backend-logs`；`down -v` 才会删数据。
- **还没做**：服务器上的 crontab 尚未配置（命令已写进部署文档），
  以及"定时任务真的按天跑起来"只有到服务器上才能确认。

### T11.8 上线冒烟检查清单

- **状态**：已完成（2026-09-30）
- **涉及文件**：`interpace-backend/scripts/smoke_test.py`（新增）、`deploy/smoke-test.sh`（新增）
- **做法**：做成**可执行脚本**而不是纸面清单——纸面清单每次靠人照着敲 curl，步骤一多必漏。
  脚本能重复跑、失败非零退出，可以当部署门禁。
- **两个关键设计**：
  - **跑在容器里**（`docker compose exec backend python /app/scripts/smoke_test.py`）：
    服务器上不一定有 python3，而后端镜像里本来就有 httpx，零额外依赖。
  - **默认打 `http://frontend/api/v1`**（compose 服务名），让链路**真的经过 Nginx**；
    直接打 127.0.0.1:8000 会绕过反代，把 SSE 缓冲这类问题全漏掉。
- **不对模型产物做断言**：出题能不能生成卷子、简历能不能导出，取决于模型这一轮吐什么。
  拿它当断言，模型心情不好就会把冒烟判成失败，久而久之没人信这个测试。
  所以只断言链路（接口可达、SSE 有 start/delta/done、数据落了库），产物只打印摘要。
- **覆盖**：探活 → 运行时配置 → 注册登录 → 建会话 → 上传附件**并读回**（验证对象存储）→
  流式对话 → 停止接口幂等 → 消息已落库 → 会话/题库/画像/记忆/笔记/检索接口 → 清理数据。
- **验收结果**：在容器里跑通，**全部通过**。而且**第一次跑就抓到一个真实部署缺陷**：
  compose 里 MinIO 的 `MINIO_ROOT_USER/PASSWORD` 没映射成后端读的 `MINIO_ACCESS_KEY/SECRET_KEY`，
  后端退回默认的 `minioadmin`，附件上传直接 500。本地开发不会暴露这个问题——
  这就是"冒烟脚本必须真跑"的价值。

#### 上线后由用户发现的问题：零会话时输入框禁用且无提示（2026-09-30，已修）

**现象**：部署好后进面试间 / 学习室，输入框点不进去、打不了字，看起来像组件坏了。

**定位过程**（用 CDP 在部署产物上复现，不靠猜）：

```
没有会话时   → {"disabled": true,  "placeholder": "输入你的回答..."}
建一个会话后 → {"disabled": false}
```

根因是房间页的条件 `:disabled="sending || !activeSessionId"`——**消息必须挂在某个会话下**，
所以没有会话时输入框就是禁用的，入口是左侧栏的「新建会话」按钮。
功能上没错，但**每个新访客都会撞上这个困惑**：熟悉代码的人能查出来，陌生人只会认为产品坏了。

**改法（选了"引导"而不是"自动建会话"）**：

- `ChatWindow` 新增 `noSession` 属性与空状态：没有会话时在消息区显示
  「还没有会话 / 消息需要挂在某个会话下，先建一个」+ 一个**「新建会话」按钮**，
  点击后调起既有的新建流程（复用侧边栏那条路径，不另写一套）；
- `ChatInput` 新增 `placeholder` 属性，由 `ChatWindow` 按是否有会话切换文案
  （没有会话时说"先新建会话，再开始提问"，而不是继续写"输入你的回答…"）；
- 两个房间各传一行 `:no-session="!loadingSessions && !activeSessionId"`
  ——带 `!loadingSessions` 是为了避免"会话还在加载"时先闪一下空状态。

**为什么没选"自动建会话"**：那样会**静默创建数据**（用户没点新建，会话列表里却多出一条），
而演示环境有"单账号会话数上限"，静默创建可能让他莫名其妙撞上限。
一次点击换来"我知道自己在干什么"更划算。

**验证**：在部署产物上用零会话账号进两个房间，实测
`{"emptyShown":true,"title":"还没有会话","hasButton":true,"placeholder":"先新建会话，再开始提问","inputDisabled":true}`，
点按钮能正常弹出「新建会话」输入框，控制台无错误；并截图确认视觉与既有界面一致。

### T11.9 部署文档与回滚步骤

- **状态**：已完成（2026-09-30）
- **涉及文件**：`docs/部署/docker部署.md`（新增）
- **做法**：构建、推送、首次部署、更新、回滚、常见故障各一节；回滚要能在不改代码的前提下
  退回上一个镜像版本。
- **实际验证（回滚是真跑的，不是写的步骤）**：
  1. `IMAGE_TAG=v2026-09-30 docker compose build backend` → `up -d` → 确认容器跑在新镜像上；
  2. 把 `IMAGE_TAG` 改回 `local` → `up -d` → **容器确实跑回了旧镜像**；
  3. 在回滚后的实例上再跑一次冒烟：**全部通过**（说明加表/加字段这类迁移对旧代码是兼容的）。
- **写进文档的关键前提**：回滚要求旧镜像还在服务器上，所以发版时**别急着 `docker image prune`**；
  另外"迁移只向前"，删字段/改类型这类变更要当成不可回滚对待，发布前先备份。

**补充（2026-09-30）："服务器上部署（推荐流程）"整条链路也实测过**

按文档一字不差地走了一遍——用另一个目录 + 另一个 compose 项目名**模拟一台干净的服务器**，
只放 `docker-compose.yml` + `.env` + 离线镜像包（**没有源码目录**）：

| 步骤 | 实测 |
| --- | --- |
| `docker save ... \| gzip` | 5 个镜像 → **562 MB**（未压缩约 1.9 GB），M1 Pro 约 66 秒 |
| `docker load` | 18 秒恢复全部 5 个镜像 |
| 只有 compose + `.env` 的目录里 `up -d`（不带 `--build`） | ✅ 成功，**不会因为缺 build 上下文报错** |
| 全新库启动 | 后端入口自动跑迁移（baseline → usage_records） |
| 五个容器 + 冒烟检查 | 全部 healthy，冒烟**全部通过** |
| 内存（生产模式） | 合计约 **434 MiB** |

两个从实测里得到的注意点，已写进部署文档：

1. **镜像标签要和服务器 `.env` 的 `IMAGE_TAG` 对上**——`save`/`load` 保留的是 tag，
   对不上时 compose 会去找一个不存在的镜像然后尝试构建，而服务器上根本没有源码目录。
2. **传输时间是主要成本**：562MB 在大陆机房常见上行带宽下要几分钟到十几分钟，
   后续发版可以只 `save` 变化的那个镜像。

测试用的是临时目录与临时项目名（`-p interpace-srv`），跑完已 `down -v` 清理干净，
没有动到本机 8080 那套环境与数据。

**⚠️ 2026-09-30 更正：上面那次"验证通过"有致命盲区**

用户把镜像传到云服务器后报错：

```
! redis  The requested image's platform (linux/arm64/v8) does not match the detected host platform (linux/amd64/v3)
dependency failed to start: container interpace-redis-1 is unhealthy
```

**原因**：我在 Apple Silicon（arm64）上构建，`docker save` 传过去的是 **arm64** 镜像，
而服务器是 amd64。更糟的是——我那次"模拟服务器"的验证也放在同一台 arm64 Mac 上，
所以 arm64 镜像在 arm64 上跑得好好的，**架构问题完全没暴露**。
**验证环境和目标环境不一致时，验证等于没做**，这是这次最该记住的一条。

补做的实测（M1 Pro）：

| 想产出 amd64 镜像 | 结果 |
| --- | --- |
| 前端镜像（node + vite） | ✅ 可以交叉构建，实测 `amd64/linux`，约 90 秒 |
| **后端镜像（`uv sync`）** | ❌ **不行**：`uv` 是 Rust 二进制，QEMU 下段错误（`uncaught target signal 11`） |
| python / node / nginx 的 amd64 变体 | ✅ 都能跑（所以问题只在 `uv`） |
| `mysql:8.0` / `redis:7-alpine` 的 amd64 变体 | ✅ 能拉 |
| `quay.io/minio/minio` 的 amd64 变体 | ❌ 匿名拉取被拒（要 quay 登录） |

**结论与改法**：arm64 Mac 上无法完整产出 amd64 部署镜像 → 部署文档的**推荐流程改成"在服务器上构建"**
（服务器是 amd64，原生构建没有这个问题），并补了 2核2G 上的注意事项
（加 swap、npm 走国内镜像、先构建再启动）。
原来的"离线传输"降级为**备选**，并明确要求构建机必须是 amd64。
文档里还加了传输前的自检命令：
`docker image inspect <镜像> --format '{{.Architecture}}'`。

**留下的教训（写进文档了）**：跨架构的验证必须在目标架构上做；
做不到时，至少要用 `docker image inspect` 自检产物架构——一条命令的成本，
比到服务器上才发现便宜得多。

**流程第三次修正（2026-09-30）：源码走 git，在服务器上 clone 后构建**

用户实际采用的流程是"本机 push → 服务器 `git clone` → `docker compose build`"，
比他手动 rsync 更省事，所以把它定为推荐做法并重写了文档：

1. **首次部署**：本机 `git push` → 服务器 `git clone <仓库> /opt/interpace` →
   `cp .env.example .env` 并填值 → 准备三个第三方镜像（服务器上往往已有，直接用；
   没有就 pull，注意架构）→ `docker compose build && up -d`。
2. **更新**：`git pull` → `build` → `up -d` → 冒烟。
3. **回滚**：`git checkout <上一个提交>` → `build` → `up -d` → 冒烟；
   比"换镜像标签"直观得多。

**文档里特别强调了两点**（都是会让人卡住的地方）：

- **`.env` 永远不会从 git 来**（它被 gitignore 排除，这是对的——里面是密钥）。
  新机器必须 `cp .env.example .env` 再填，忘掉的表现是 `MYSQL_ROOT_PASSWORD is missing a value`。
- **部署相关的新文件要确认已提交**。Dockerfile 这类文件第一次是"未跟踪"状态，
  只 `git commit` 已有改动的话不会带上它们，服务器 clone 下来就会报
  `open Dockerfile: no such file or directory`（用户实际撞到的就是这条）。
  文档里给了一条自检：`git ls-files | grep -E "Dockerfile|docker-compose|..."`。

**流程第四次修正（2026-09-30）：CI 构建 + 镜像仓库**

用户在服务器上实测 `docker compose build` **太慢**（2核2G：拉基础镜像 + 下几百 MB 依赖 +
vite 吃满 CPU）。给出的解法按"见效快慢"排序：

1. **前端镜像在本机交叉构建后传过去**（实测可行）：node 在 QEMU 下正常，
   前端镜像 64 秒构建完、amd64、`docker save | gzip` 后只有 **20MB**，
   传过去 `docker load` 即可。服务器上就只剩后端的 `uv sync`。
2. **CI 构建 + 镜像仓库（推荐长期方案）**：新增 `.github/workflows/build-images.yml`，
   runner 本来就是 amd64，构建完推到镜像仓库（阿里云 ACR / 腾讯云 TCR，Docker Hub 在国内慢），
   服务器只 `docker compose pull`。compose 里为此加了 `IMAGE_PREFIX` 支持：
   `image: ${IMAGE_PREFIX:-}interpace-backend:${IMAGE_TAG:-local}`（实测插值正常）。

**注意**：工作流只做了结构校验（YAML 能解析、步骤齐全），**没有真正跑过 GitHub Actions**——
本机跑不了。第一次用要留意 Actions 日志，可能需要调的就是仓库地址与凭据。

### 服务器部署的当前状态（2026-09-30，用户要求先搁置）

已经打通的：服务器（amd64，2核2G）上 `git clone` + `docker compose build` + `up -d` 能跑起来，
后端容器启动时自动执行了迁移，**本机 `curl 127.0.0.1:8080` 返回 200**。

还没做完的三件事（都不是代码问题）：

1. **外网访问不通**：腾讯云轻量应用服务器的「防火墙」默认只放行 22/80/443/3389，
   ~~需要在控制台手动放行 TCP 8080~~ **已解决**：用户接了 NPM，域名
   `https://interai.sql668.com` 可以访问了。
2. **MinIO 镜像仍是 arm64**：那是早先打包传过去的，在 amd64 上跑不起来 →
   **附件上传会 500**（其他功能不受影响，所以不容易发现）。换法见部署文档的 MinIO 一节。
3. **域名与 HTTPS 还没接**：服务器上已有 Nginx Proxy Manager（容器名 `npm-app-1`，占着 80/81/443），
   ~~接入方式见部署文档~~ **已解决**：已接上 NPM，域名 `interai.sql668.com` 可用。

**接上 NPM 后发现并修复的一个真问题（2026-09-30）**：
客户端 IP 被 NPM 的地址覆盖了 —— 我们的 nginx 用 `proxy_set_header X-Real-IP $remote_addr`，
而 `$remote_addr` 此时是 NPM 容器的地址，于是**所有访客共用一个配额桶**，
第一个人的用量算到所有人头上（用户遇到的 429 有一部分就是这么来的）。

修法：`deploy/nginx.conf` 加 realip 模块配置，从 `X-Forwarded-For` 还原真实客户端地址。
**实测验证过**：带 `X-Forwarded-For: 203.0.113.99` 发一轮对话，后端 `usage_records.client_ip`
记的就是 `203.0.113.99`（修复前记的是 `172.27.0.5` 这类容器网段地址）。

> 安全说明（**实测确认**）：`set_real_ip_from` 是**按对端地址**校验的——只有来自信任网段的
> 请求，其 X-Forwarded-For 才会被采信。把信任表改成只含 `10.0.0.0/8` 后，从宿主机
> （对端 192.168.65.1）和另一个容器（对端 172.27.0.5）各发一次带伪造 XFF 的请求，
> `$remote_addr` 两次都是真实对端 ✅ —— **从公网直连的请求伪造不了 IP**。
> 配合 NPM 时仍建议把端口绑回环（不是必须，是"少一个对外端口少一类风险"）。
>
> 过程记录：这条结论我一开始写反了，中间几次实测结果互相矛盾，最后发现是
> **我的 sed 改错了网段**（还留下三条重复的 `set_real_ip_from`）。教训：验证
> 安全类行为前，先用 `nginx -T` 确认"生效配置"到底是什么，别信自己的改动意图。

**用户遇到的 429 说明**：服务器用的是 `APP_ENV=demo`（那份 `.env` 是从本机拷过去的），
演示配额生效，其中「每个 IP 每天最多 1 次面试复盘」限制了第二次复盘。
调大数值改 `config/demo_limits.json` 即可（改完热生效；容器重建会被镜像里的原文件覆盖）。

#### 顺手修掉的体验问题：429 弹的是 axios 英文原文（2026-09-30）

**现象**：页面弹窗写着 `Request failed with status code 429`，用户看不出为什么被拦。

**根因**：`http.ts` 的响应拦截器里**根本没有 429 分支**（只处理了 400/403/404/409/422/500），
而各组件又是自己 `ElMessage.error(error.message)` —— axios 的默认文案就这么露出来了。

**修法**（新增 `src/utils/errorMessage.ts`，两个函数）：

1. `resolveErrorMessage(error, fallback)`：按「后端 `message` → 非 axios 默认文案的
   `error.message` → `fallback`」的顺序取一句话。后端本来就返回精心写过的中文
   （429 是"演示环境的体验额度已用完…"、409 是"用户名已被占用"），比"按状态码套模板"准确得多。
   顺带把 `Request failed with status code xxx` 和 `Network Error` 这两种无信息量的英文过滤掉。
2. `notifyError(error, fallback)`：拦截器已经弹过就跳过（拦截器会打 `__notified` 标记），
   **避免同一次失败弹两个框**。

**改动的文件**：`api/http.ts`（加 429 分支、优先后端文案、按状态码兜底、打标记）、
`utils/errorMessage.ts`（新增），以及 8 处自己弹提示的组件/composable
（EvaluationPanel ×2、ProfileProposalCard ×2、QuizCard、ResumeDownloadButton、ChatInput、
useNoteAutoSave、useSessionStreamSender、LoginCard）。

**顺带**：429 用 `ElMessage.warning` 而不是 `error` —— 它的语义是"暂时不能用了"，
不是"坏了"，视觉上不该一样刺眼。

**验证**：**真机跑过**。先把登录接口的限流打满（10 次/分钟），再用浏览器真的提交一次登录，
读到的弹窗是 `[warning] 请求过于频繁，请稍后再试`——**一条、中文、warning 样式**；
修复前这里会是 `[error] Request failed with status code 429`。

> 说明：验证走的是"限流触发的 429"这条路径（最容易构造）。配额触发的 429
> （用户实际遇到的那种）走的是同一段代码，会显示后端那句"演示环境的体验额度已用完…"，
> 但没有单独构造场景跑一遍。

> 本机开发环境（`localhost:8080`）**不受这些影响**，五个容器都健康、冒烟全过。
> 上面三条只是"对外可用"的最后一段路。

### 本地开发体验：一键启停脚本 + 环境验证文档（2026-09-30）

用户提出两个诉求，都已交付并**实测**：

1. **一键启停**：新增根目录 `dev.sh`（`start` / `stop` / `restart` / `status` / `logs`），
   后台运行 + PID 文件 + 日志落在 `.dev-run/`（已 gitignore）。**只管应用、不管中间件**
   ——MySQL 是系统服务、Redis/MinIO 是常驻容器且可能被别的项目共用，脚本只检查不启停。
2. **环境验证方法**：写进 `docs/开发/本地开发环境.md`，核心是"另起一个端口 + 独立的
   `.env.{APP_ENV}`"，用 `/api/v1/config/runtime` 一眼看配置有没有生效。

写这两个东西时踩到/修掉的问题（都记在文档里了）：

- **`$var` 后面紧跟中文标点会被当成变量名**：`"（PID $pid）"` 触发
  `pid）: unbound variable`。同一个坑我这是**第二次**踩（第一次在 `deploy/backup.sh`）。
  已把三个脚本里所有"变量 + 中文标点"的写法统一改成 `${var}`。
- **kill 父进程停不干净**：`uvicorn --reload` / `vite` 都会 fork 子进程，只 kill 父进程
  会让子进程被 reparent 到 init、继续占着端口（脚本报"已停止"但端口没释放）。
  修法是**先 `pgrep -P` 记下子进程再杀父进程**；另外保留"按端口兜底收掉"作为最后防线。

**实测**：`start` → 两个服务就绪（后端 health 200、前端 200）；`stop` → 两个端口都释放、
无残留；再 `start` 恢复正常。环境验证也真跑了：8001 起 `APP_ENV=demo` 时
`/config/runtime` 返回 `quota_enforced: true` + 完整 limits，而 8000 的 development 是
`false` + `limits: null`。

---

## 14. 阶段 12：多环境配置与演示环境限制

**为什么单独立一个阶段**：项目要部署到云服务器给别人尝鲜，需要**开发 / 演示 / 测试 / 正式**
四套环境各用各的配置；其中演示环境对外开放，**必须防止被人无限刷、把模型的额度烧光**。

### 这个阶段最容易做错的一件事

**"限制接口调用次数"不等于"限制 token 消耗"**，本项目的差距尤其大。实测过的调用放大：

- 每轮流式对话，`prompt_layer` 组装提示词时会调 `SessionSummaryService.ensure_summary`
  （最近 10 条之外的旧消息攒够 10 条就压缩一次，**偶发**多一次模型调用）；
- 简历场景每轮再多一次画像抽取（`_persist_profile_proposal_if_any`）；
- 出题、评分、面试复盘、记忆抽取与合并、会话摘要，各自都是**独立**的模型调用；
- 语音面试一轮 = 面试官回复（LLM）+ TTS（按字符计费）+ ASR（按时长计费），
  火山那条链路的计费口径与 token 完全不同。

结论：**计量必须卡在模型调用那一层**。全项目唯一的模型出口是
`app/agent/llm.py` 的 `get_chat_model`（7 个调用点全部经过它），
在所有路由入口上做限流都挡不住"一次请求触发 3~5 次调用"。

### T12.1 多环境配置体系

- **状态**：已完成（2026-09-30，配置体系部分；`.env.demo` / `.env.test` 的实际内容待部署时填）
- **现状**：`_normalize_app_env` 只认 `development` / `production`（其它值一律归到 development），
  后端只有 `.env`、`.env.development`、`.env.example`；前端只有 `.env.development` / `.env.production`。
- **做法**：把环境枚举扩成 `development | demo | test | production`，四套配置各一个文件；
  环境相关行为全部读 `settings.app_env`，**不在代码里散落 `if env == ...` 的字面量**。
- **注意**：现在的"其它值一律归到 development"是**静默降级**——部署时把 `APP_ENV` 写错
  （比如 `APP_ENV=demoo`）会安静地跑成开发环境，正是演示环境最怕的那种错。
  要改成"不认识的值启动即失败"。
- **验收**：四套环境各自启动成功，`/health/live` 能反映当前环境名；写错环境名启动失败并给出可选值。
- **依赖**：无。

**实际改动**：`VALID_APP_ENVS = (development, demo, test, production)`，支持 `dev` / `prod` /
`staging` 简写；**不认识的值抛 RuntimeError 并列出可选值**（原来是静默归到 development）。
`.env.example` 补了 `APP_ENV` 的取值说明，并修正了一处描述错误——模板里写的是
「基础 `.env` → `.env.<APP_ENV>` → 环境变量」，但代码**从来不读基础 `.env`**，
实际只有 `.env.<APP_ENV>` 与操作系统环境变量两级。

**验证结果**：`pytest` 覆盖四种取值 + 三种简写 + 拼错即失败（报错里必须带可选值）。

### T12.2 演示环境准入控制

- **状态**：待办（依赖决策 D28）
- **做法**：按 D28 选定的方式限制"谁能进演示环境"：邀请码 / 演示账号池 / 开放注册 + 人机校验。
  注册开关由环境配置决定（演示环境可以关掉开放注册，正式环境按 D28）。
- **验收**：演示环境按选定方式能进、不能滥用；正式环境行为不受影响。
- **依赖**：T12.1、D28。

### T12.3 统一用量计量

- **状态**：已完成（2026-09-30，**只覆盖大模型链路**；火山 ASR / TTS 的计量尚未做，见下方遗留）
- **做法**：
  1. 新增 `usage_records` 明细表：一次模型/语音调用一行（用户、环境、场景、provider、模型、
     `prompt_tokens` / `completion_tokens`、语音字符数或音频秒数、时间）。
  2. 在 `get_chat_model` 返回的模型上挂 LangChain callback，从 `usage_metadata` 取真实 token 数，
     **不自己估算**（估算在中文场景误差很大）。
  3. 语音链路的 ASR / TTS 在各自的 client 里单独记账（口径不同，不能混算）。
  4. 聚合表 `usage_daily_counters`（用户 + 日期 + 场景）：配额判断走聚合表，
     避免每次都在明细表上做范围扫描。
- **验收**：跑一轮对话 / 一次出题 / 一次语音，`usage_records` 里的条数与 token 数
  与 provider 控制台的账单量级对得上。
- **依赖**：T12.1。

**实际改动**：

- 新表 `usage_records`（迁移 `71257d0297db`）+ 三条索引。**`user_id` 不建外键**，
  是刻意的：删用户不该被账本挡住，而且**删账号不能顺手洗掉 IP 的累计额度**——
  否则删号重建就能把配额刷回来。`test_user_deletion.py` 的"泛化断言"里把它列为例外并写明原因。
- 计量挂在 `app/agent/llm.py:get_chat_model`（全项目**唯一**的模型出口，7 个调用点全走它），
  用 LangChain callback 在 `on_llm_end` 抓 `usage_metadata`。
- 场景标识走请求上下文（`app/core/request_context.py` 的 contextvar），**没有给函数加参数**：
  给七八个函数加两个与业务无关的参数，迟早会漏传，而漏传的表现是"配额静默失效、无任何报错"。
  身份信息在 `main.py` 的中间件里设置（同步依赖里改 contextvar 传不到外层，这点在代码里注明了）。

**真机验证（关键的三条实测结论）**：

1. **流式也能拿到真实用量**，但它**不在最后一帧、而在中间某一帧**——按"读最后一块 chunk"
   的写法会拿到 `None`，然后整个配额系统静默失效。这是本次最容易写错的地方，已用回调实现规避。
2. `stream_usage=True` 要显式打开；顺带确认 DeepSeek 的流式与非流式都能返回 usage。
3. **推理过程计费且可能占大头**：探测中一次输出 137 token 有 133 是 reasoning。
   所以记账与配额都按 `total_tokens`（含推理）算，只算正文会严重低估成本。
   演示环境一次真实短对话实测：`prompt=435 / completion=34 / total=469`。

**遗留**：火山 ASR / TTS 的用量（按时长 / 字符）还没记账。它们与 token 不是一个口径，
需要各自 client 单独埋点。已留在任务里，等语音链路的演示额度真正要生效时再做。
当前的效果是：**演示环境关语音就只能靠 `disable_voice_interview` 开关，不能按分钟细致限制**。

### T12.4 三层配额与全局熔断

- **状态**：已完成（2026-09-30，数值已按 D31 落在配置文件里，可随时改）
- **做法**：三层一起卡，缺一层都挡不住：
  1. **按用户**：每日对话轮数 / 出题次数 / 复盘次数 / 语音分钟数；
  2. **按 IP**：防止一个人注册多个账号绕过按用户配额（复用并改造现有内存限流依赖，
     或挪到 Redis，见下方注意）；
  3. **全局日预算熔断**：当日模型调用次数或 token 总量超过阈值后，**所有人一律拒绝**——
     按用户限流挡不住"很多人各用一点"的长尾，这一层才是真正护住钱包的。
- **注意**：现有 `app/core/rate_limit.py` 是**进程内内存**实现，重启即清零、多进程不共享。
  演示环境如果只有一个后端实例、不追求精确，可以先沿用并说明；
  要跨重启保留就必须落到 Redis（依赖已在，不需要新增库）。
- **验收**：三类配额都能触发 429；熔断触发后日志有明确记录；配额在次日自动恢复。
- **依赖**：T12.3。

**实际改动**：

- 配额全部写在 **`config/demo_limits.json`**，配套说明见 `config/README.md`。
  读取器 `app/core/quota_config.py` **按 mtime 热重载（最多 5 秒）**，改完保存即生效，不用重启。
  用 **JSON + 标准库**而不是 YAML：`PyYAML` 只是别人的传递依赖，为它写配置等于依赖一个
  我们没声明的包。JSON 写不了注释，所以每个键旁边放一个下划线开头的兄弟键当注释。
- **改坏了不会挂**：解析失败时保留上一份有效配置并打 ERROR 日志（只在错误内容变化时打，
  避免每 5 秒刷屏）。这是刻意的取舍——演示环境的价值是"一直能访问"，一个少写的逗号
  不该让整站 500。
- **只对指定环境生效**：`enabled` 之外还有 `environments`（默认 `["demo"]`）。
  这是实现过程中发现并修掉的一个真问题：最初只写了无条件的 `enabled=true`，
  结果**本地开发也被自己的配额卡住、后台抽取被静默关掉**。
- 三层检查顺序：全局熔断 → 单 IP 累计 token → 单 IP 当日次数（对话 / 出题 / 复盘）。
  顺序固定，用户看到的拒绝理由才稳定。
- **顺带修掉一个真实的绕过漏洞**：原来的限流取 `X-Forwarded-For` 的**第一个**值，
  而 Nginx 用的是 `$proxy_add_x_forwarded_for`（保留客户端值、在末尾追加真实 IP），
  所以第一个值可以被客户端随便伪造——每个请求换个假 IP，限流就完全失效。
  新增 `app/core/client_ip.py`：优先 `X-Real-IP`（Nginx 覆盖写入、伪造不了），
  其次 XFF 的**最后一段**，并且只在 `TRUST_PROXY_HEADERS=true` 时才认这些头。
  HTTP 与 WebSocket 共用同一套口径（两边不一致会让同一用户被算成两个 IP）。

**验证结果**：`pytest` 新增 18 个用例全绿，**完整套件 237 passed**。
真机验证（demo 环境跑真实请求）：一轮对话正确落账并归属到 `X-Real-IP`；
把账本推到超额后，`POST /sessions/{id}/stream-chat` 返回 **HTTP 429** +
`{"code":429,"message":"演示环境的体验额度已用完…","detail":{"reason":"ip_token_quota"...}}`。
（顺带确认：配额检查发生在建模型之前、也在 SSE 响应开始之前，所以用户拿到的是干净的 429，
而不是流到一半冒出来的错误提示。）

**一个需要你注意的配置相互作用**：真机验证时先触发的不是"每 IP 300 万"，而是
**全局日预算 50 万**——因为两个额度管的是不同的事：

| 额度 | 管什么 | 何时触发 |
| --- | --- | --- |
| 每 IP 累计 300 万（你指定的） | **长期**防同一个人反复来刷 | 跨天累积，单日很难到 |
| 全局每日 50 万 | **单日**总支出兜底 | 通常先触发 |

所以当前配置下，实际先卡住的是全局日预算。如果你希望"单个 IP 的 300 万"成为真正先触发的硬限制，
把 `global.daily_token_budget` 提到 300 万即可（改文件即时生效，不用重启）。
反之想更省，把它调到 20 万。这个数字本质上是"你每天愿意为演示环境花多少钱"，建议你定一个。

**容器侧也验证过**（这一步很关键）：后端 Dockerfile 原来**没有把 `config/` 复制进镜像**，
容器里读不到配额文件就会退回"不限制"——演示防护会在无人察觉的情况下失效。
已补 `COPY config ./config`，并实测：容器内路径为 `/app/config/demo_limits.json`，
`APP_ENV=demo` 时 `is_enforced=True`、降本开关生效。想在服务器上热改配额而不重建镜像，
用 compose 把宿主机目录挂到 `/app/config` 覆盖即可。

#### 补充：单场模拟面试 3 分钟上限

**需求**：演示环境里一场模拟面试最多 3 分钟（`interview.max_minutes`，改配置即时生效）。

**口径**：时长从**面试记录创建**算起，**语音与文字共用同一个时钟**——用户语音聊了 2 分钟
再切到文字，也只剩 1 分钟。这样"一场面试 3 分钟"才是一个确定的概念，
而不是按连接或按模式各算一份。

**两端的执行方式不同，这一点是刻意的**：

| 形态 | 到点后的行为 | 为什么 |
| --- | --- | --- |
| 语音面试 | 服务端**主动结束**：结束面试记录 → 下发 `interview_timeout` 事件 → 关闭连接 | 语音是长连接，用户不挂断就会一直烧 ASR/TTS。文字那套"下一轮不回答"在语音里等于没限制 |
| 文字面试 | 下一轮**不再回答**：给固定提示、结束面试记录、**不调用模型** | 正在生成的回答不打断（半截答案体验差），但新问题直接拒绝 |

**实现落点**：`app/services/usage_quota_service.py` 提供 `interview_remaining_seconds()`
（返回 `None` = 不限、`<= 0` = 已超时，负数保留具体超时秒数便于排查）；
语音在 `speech_stream_service.run()` 用 `asyncio.wait_for` 给 `receive()` 加截止时间；
文字在 `stream_chat_service.stream_chat()` 建提示词与模型**之前**检查并早退。

**前端**（`speechStream.ts` / `useVoiceInterview.ts` / `InterviewRoom.vue`）：新增
`interview_timeout` 事件，收到后停止录音、把状态切回可用、提示用户，并刷新消息列表让
「结束面试 / 查看复盘」的入口亮起来。用一个独立的 `timeoutMessage` 而不是复用
`errorMessage`——这是**正常结束**，不是错误。

**验证结果**：

- `pytest` 新增 7 个用例（时长计算 4 个 + 文字链路 3 个 + 语音链路 1 个，合计 8 个断言场景）；
  **完整套件 244 passed**。
- **真机验证**（演示环境跑真实请求）：第 1 轮真实调用模型（983 token，面试记录 status=0）；
  把创建时间前推 5 分钟后发第 2 轮 → 返回"本场模拟面试已达演示环境的 3 分钟上限…"，
  **账本仍是 1 次调用（没有新增，token 没有被消耗）**，且面试记录变为 status=1（已结束）。
- 反向用例也在测：没到点（1 分钟）必须照常回答、第一轮必须放行（否则演示环境会出现
  "连第一句都问不出去"）。

#### 补充：IP 不可伪造这件事是怎么落实的

配额按 IP 算，所以"IP 能不能被伪造"决定配额有没有意义。要点是**区分两个层次**：

- `$remote_addr` / `request.client.host` 来自 **TCP 连接的对端地址**，建立连接后伪造不了；
- `X-Forwarded-For` / `X-Real-IP` 只是**普通 HTTP 头**，客户端想写什么就写什么。

因此真正的可信边界是"**谁直接连到了我们**"，转发头只有在"请求确实来自我们自己的代理"
这个前提下才有意义——这就是 `TRUST_PROXY_HEADERS` 控制的开关（默认 `false`）。

**Nginx 侧改成了覆盖而不是追加**：原来用 `$proxy_add_x_forwarded_for`（保留客户端传的值、
在末尾追加真实 IP），等于把一个可伪造的字符串原样带给了后端。现在三处转发
（SSE / WebSocket / 通用 `/api/`）都改成 `proxy_set_header X-Forwarded-For $remote_addr;`。

**真机验证**（临时起了一套 Nginx + 回显服务，用完即删）：客户端带上伪造的
`X-Forwarded-For: 1.2.3.4` 与 `X-Real-IP: 9.9.9.9` 请求，后端实际收到的两个头都是
`192.168.65.1`（TCP 对端真实地址）——**伪造值被完全丢弃**。Nginx 配置语法也用
`nginx -t` 校验通过。

**两条还没做、但必须做的**（记在这里防止遗忘）：

1. **后端端口不能对公网开放**。上面的防护有个前提：请求只能经由我们的 Nginx 到达后端。
   如果 8000 端口直接映射到公网，攻击者绕过 Nginx 直连后端，`$remote_addr` 就是他自己的地址，
   但他同时也能直接污染任何"信任代理头"的判断——所以 T11.4 写 compose 时，
   后端只能 `expose`（仅容器网络内可见），**不要 `ports: 8000:8000`**。
2. **前面加 CDN 时要在 Nginx 还原真实 IP**。挂了腾讯云 CDN / 高防之后 `$remote_addr`
   会变成 CDN 节点地址，必须用 `ngx_http_realip_module`（`set_real_ip_from` 只列 CDN 回源网段
   + `real_ip_header` + `real_ip_recursive on`）。**`set_real_ip_from 0.0.0.0/0` 等于没做防护**。

**为什么初始值要压这么小**（这组数字是刻意收紧的，先紧后松）：

1. **被骂太紧可以立刻调大，被刷爆的额度要不回来。** 演示环境的目的是"让人看到能力"，
   不是"让人用够"，10 轮对话足够体会出题、面试、画像三件事各一次。
2. **单轮成本随会话变长而上涨。** 注入的历史消息、会话摘要、画像与记忆条目都跟着轮数增长，
   第 20 轮的一次提问可能比第 1 轮贵好几倍。所以"**单会话 ≤ 5 轮**"这条比单纯降每日轮数更有效——
   它压的是**单价**，不只是次数。
3. **配额要按"最坏情况"设计。** 真实流量的长尾一定超过预估，全局熔断值（150 次/50 万 token）
   是按"每个访客都用满、且同时来 15 个人"估的。上线后拿 T12.3 的实测数据回调，
   而不是一开始就按理想值放开。

### T12.5 演示环境降本开关

- **状态**：部分完成（2026-09-30；开关已接上，`disable_file_upload` 与"演示环境提示词"尚未接）
- **做法**：把"省钱"做成环境配置，而不是改代码：
  - 模型可换更便宜的一档、`DEEPSEEK_MAX_TOKENS` 调小；
  - 注入的上下文条数、记忆条目数降档；
  - 高成本功能按开关关闭（如"用录音生成复盘"这一步要整段识别，成本明显更高）；
  - 演示环境在系统提示词里注入一句"当前是演示环境"的说明，避免用户误以为是成品。
- **验收**：同一轮对话在演示环境的 token 消耗明显低于正式环境（用 T12.3 的明细对比）。
- **依赖**：T12.3、T12.1。

**比降配额更有效的三条开关**（按性价比排序，都做成环境变量）：

1. **关掉"用户看不见的模型调用"**。记忆抽取与合并、会话摘要压缩、画像抽取这些
   都在后台额外烧 token，但对"尝鲜体验"几乎没有贡献。演示环境直接关掉，
   单轮成本立刻降下来，用户感受不到差别。
2. **语音面试设成小额体验额度或默认关闭**。它是**双计费**（ASR 按时长 + TTS 按字符），
   一轮下来比纯文字对话贵一个量级。如果语音是主要卖点，就给 1~3 分钟的体验额度；
   如果不是，演示环境直接不给。
3. **限制上传与解析**。上传 PDF / 图片会把解析出的全文塞进上下文，
   一次就能顶几十轮对话。演示环境限制体积、页数或直接关掉上传，
   是性价比最高的一道闸。

另外聊天页面上写明"演示环境：每日重置、有调用次数上限"，让用户对"怎么突然不能用了"有预期。

**本次已接上的开关**：

- `disable_background_extraction`：已接到**三处**——会话摘要压缩（`prompt_layer` 组装提示词时）、
  记忆抽取（`MemoryExtractService.extract`）、简历画像抽取（`extract_profile`）。
  这三处都是"用户看不见的额外模型调用"，关掉后演示环境一轮对话只花一次调用的钱。
- `max_tokens`：已接到模型工厂，演示环境把单次输出上限压到配置值（当前 1024）。

**已接（2026-09-30 补充）**：`disable_voice_interview`——**演示环境不显示「语音面试」按钮**。
这一项做成两处都判、读同一份配置：

- 新增 `GET /api/v1/config/runtime`（不鉴权）返回 `features.voice_interview`，
  前端 `useRuntimeConfig` 拉一次缓存起来，`InterviewRoom` 据此决定按钮显不显示；
- 后端 `speech_routes` 在 `accept()` 之前也判一次，关掉时直接关闭连接（1008）。

**为什么必须两边都判**：只藏按钮挡不住绕过界面直接连 WebSocket 的请求，而语音是
ASR（按时长）+ TTS（按字符）双计费，是所有链路里最贵的一条。反过来，如果只判后端不判前端，
用户会看到按钮、点了却连不上，这种"功能坏了"的观感比不显示更糟。

**只藏按钮不改环境变量的另一个理由**：开关的唯一事实来源是 `config/demo_limits.json`，
改完即时生效；如果做成前端构建期环境变量，改一次要重新构建、重新发版，两边还可能不一致。

**已接（同一天补）**：`disable_file_upload`——同样是两边都判：
前端 `ChatInput` 隐藏「+ 附件」按钮，后端 `POST /upload/file` 返回 403。
这条也一并暴露到 `/config/runtime` 的 `features.file_upload`
（之前**故意不暴露**，因为那时后端没判，暴露了就是"字段有值但功能没生效"的误导）。

**顺带**：`/config/runtime` 新增 `limits` 字段（当前生效的配额数值，未启用时为 `null`），
供首页展示——数字由后端下发，避免页面里写死一份会过期的配额。

**尚未接**："在系统提示词里注入演示环境说明"（等 T12.7 的前端标识一起做更合适）。

### T12.6 演示数据定期重置

- **状态**：待办（依赖决策 D29）
- **做法**：定时把演示环境清回起始状态（保留 `prompt_templates` 等基础数据），
  并给用户一个明确预期（页面上写明"演示数据每日重置"）。
- **注意**：**演示环境必须用独立数据库**。除了"重置不能误删正式数据"，
  还有一条更实际的：演示用户可能上传真实简历，混库意味着别人能看到。
- **验收**：重置脚本可重复执行；执行后演示环境可正常注册登录、正式库数据未受影响。
- **依赖**：T12.1。

### T12.7 前端环境标识

- **状态**：待办
- **做法**：前端把环境名一起注入（`VITE_APP_ENV`），演示 / 测试环境在页面顶部显示醒目横幅
  （如"演示环境 · 数据每日重置"），避免与正式站混淆。
- **验收**：四套环境的构建产物各自显示正确标识；正式环境不显示横幅。
- **依赖**：T12.1。

### T12.8 用量查看

- **状态**：待办
- **做法**：加一个只对自己人开放的口径（管理接口或脚本），能按天查看：
  总调用数、总 token、Top 消耗用户、被熔断拦下的次数。
- **验收**：上线后能一眼看出"今天谁在刷"。
- **依赖**：T12.3。

### T12.9 多环境与配额文档

- **状态**：待办
- **做法**：新增 `docs/部署/多环境配置.md`：四套环境的差异表、各自的启动方式、
  配额参数怎么调、演示环境出问题的排查路径（先看熔断日志再看单用户配额）。
- **验收**：照文档能独立起一套演示环境。
- **依赖**：T12.1~T12.7。

### T12.10 首页（介绍页）

- **状态**：已完成（2026-09-30）
- **需求**：加一个首页，介绍项目、架构、亮点（三层记忆 + 自主进化）、功能说明，以及演示环境的限制。
- **涉及文件**：`interpace-frontend/src/views/HomeView.vue`（新增）、`src/router/index.ts`、
  `app/schemas/runtime_config_schemas.py`、`app/services/usage_quota_service.py`（补 `limits` 字段）
- **路由改动**：`/` 原来是 `redirect: '/interview-room'`，现在指向首页；
  守卫的白名单从 `if (path === '/login')` 改成 `PUBLIC_PATHS` 集合（首页 + 登录页免登录）。
  顺手补了 `scrollBehavior`——**原来缺它，页内锚点点击不会滚动**（Vue Router 会接管带 hash 的跳转）。
- **设计取舍**（按 `frontend-design` 指引做的，不是套模板）：
  - **配色沿用产品既有色**：主蓝 `#4385f1`、品牌暖橙 `#f59a1b`、纸白 `#fbf8f3` 都取自登录页与房间页，
    深墨 `#16232f` 只用于 hero 与记忆区块。首页不该是另一套视觉。
  - **标题用宋体**（`Songti SC`）：这个产品的产物是简历、复盘、评价这类"书面文件"，宋体自带那种正式感，
    且系统自带、不引入字体依赖；正文仍是全站黑体。
  - **数字与标记用等宽**：L1/L2/L3、配额数字用等宽字体，一眼与文案区分。
  - **签名元素是"记忆三层"剖面图**：一条贯穿的竖线 + 三层标签（L1/L2/L3），
    每层写清「记住什么 / 存在哪 / 什么时候用」。这是产品最核心的差异点。
  - **编号只用在真有顺序的地方**：功能区/架构区不编号（没有先后关系），
    自主进化的五步与 L1/L2/L3 才用编号——避免"01/02/03"这种纯装饰的模板感。
  - **动效只做一处**：hero 的对话卡片逐行出现，呼应产品里的流式回答；
    `prefers-reduced-motion: reduce` 下全部静态。
- **演示限制不写死**：读 `/config/runtime` 的 `limits` 与 `features`——
  配额改了页面跟着变；语音/附件被关掉时，限制区会自动多出对应的说明条目。
- **验证结果**：
  - `pnpm run build` 通过。
  - **用无头 Chrome 逐屏截图自查**（1440 宽）：hero、痛点、房间、记忆三层、自主进化、
    架构表、演示限制、页脚均渲染正常；把配置临时对开发环境生效后复查了"有数字"时的排版，
    确认 4 张配额卡（300 万 / 10 轮 / 2 次 / 3 / 10）与两条动态说明都正确，随后已还原配置。
  - `pytest` 覆盖 `/config/runtime` 的新增字段与"关掉上传后 403"。
- **注意**：全局样式里 `html, body` 有 `min-width: 1200px`（整个应用是桌面优先），
  首页本身是流式布局、窄屏不塌，但**没有做真正的移动端适配**——那是全站层面的改动，不在本任务范围。
- **依赖**：T12.4（`/config/runtime`）。

#### 补充：首页与工作台之间的导航闭环

第一版做完后暴露两个问题，都已修掉：

1. **登录后落在工作台，看不到首页**。`LoginCard` 原来固定跳 `/interview-room`，
   现在落点规则是：**带 `?redirect=` 就回原目标页，没有就进首页**——
   被守卫拦下来的用户（比如直接点 `/notebook`）想去的地方要还原，
   而正常登录的人先看到"这是什么、演示环境有什么限制"，再由首页把人送进工作台。
   两条登录路径（注册后自动登录、直接登录）共用 `resolvePostLoginPath()`，落点只在一处定义。

   **安全处理**：`redirect` 能被随便构造（它直接来自地址栏），所以只接受**站内路径**
   （必须以单个 `/` 开头），挡掉 `//evil.com` 这类协议相对地址——
   不挡的话就是个开放重定向，能被人拿去钓鱼。
2. **首页是单向入口，进了工作台就回不去**。现在两处退路：
   - 工作台顶部**品牌标题可点回首页**（"logo 点回首页"的通用约定，带 hover 与键盘焦点样式）；
   - **登录页左上角「← 返回首页」**。

**验证方式值得记一笔**：本机的浏览器自动化桥接不可用，所以用 **Chrome 的调试协议（CDP）**
真的跑登录表单——填账号密码、点「登录」，再读页面状态。第一次用假 token 注入时
被 401 打回登录页（说明"无效 token 会被登出"这条逻辑是对的），换成真账号才验到位。
最终三种落点规则全部实测通过：

```
[OK] 无 redirect        : 登录后落地 /          （期望 /）
[OK] 带站内 redirect    : 登录后落地 /notebook  （期望 /notebook）
[OK] 站外 redirect      : 登录后落地 /          （期望 /，挡掉开放重定向）
```

登录态下首页的主按钮会切换成「回到工作台」（实测 `cta: "回到工作台"`）。

> 踩坑记录：填表时用 `.login-card input` 会把**头像的 file input** 一起选中，
> 而它的 `value` 不允许被脚本赋值（抛 `InvalidStateError`）。要按
> `.el-input__inner` 精确选择。

---

## 15. 待确认的产品/技术决策

这些问题需要先拍板，任务才能往下走。确认后把结论写回对应任务，并从这里删掉。编号保持稳定、不重排，所以表里出现空缺（如已确认的 D1、D2、D4、D5、D6、D8、D9、D10、D11、D12、D13、D15、D16、D17、D18、D19、D20、D22、D24）表示该项已落进对应任务。

| 编号 | 决策点 | 关联任务 | 建议方案 |
| --- | --- | --- | --- |
| D3 | 模式标签在消息气泡上的视觉形式（文字标签 / 图标 / 不同气泡色） | T1.7 | 先用轻量文字标签，放在时间戳旁边。**T1.7 已按此实现**，另外自作主张加了一条：默认模式（`select_model=0`）不显示标签。想调整直接改 `MessageBubble.vue` |
| D7 | 文档解析与 Word 导出的依赖取舍 | T3.2、T6.4 | **已定**：解析用 `pypdf`（386 KB，纯 Python）+ `python-docx`（247 KB，依赖 `lxml` 已随其他装好）+ `pymupdf`（23.5 MB，零运行期依赖，用于把扫描版 PDF 渲染成图片交给多模态模型），合计净增约 24 MB。**导出 Word（T6.4）复用同一个 `python-docx`，不再额外增加依赖。** 语音相关见 D13 |
| D14 | 停止流式的子决策（停止协议、部分内容保留策略、消息状态取值、面试场景收尾） | T1.8 | **已按 T1.8 的默认决策落地**：双保险协议、保留部分内容、新增 `status=2`、面试场景等阶段 7 再对齐。若要改成「整条丢弃」或复用其他状态值，直接说 |
| D21 | 画像合并的具体参数：各类来源的权重系数、时间衰减半衰期、低于多少置信度不写入 | T9.5、T9.6 | 先定一组可配置的默认值（行为证据权重高于声明、声明高于推断），上线后按实际效果调；不要把这些数值散落硬编码在代码里 |
| D23 | 记忆注入的快照策略：Hermes 在会话开始时注入一次冻结快照（保护 prompt 前缀缓存），本项目现在是每轮重新读取 `user_profiles` | T9.7 | 倾向保持每轮实时读取。本产品的画像更新发生在评分 / 复盘之后，用户期望立刻生效；且会话通常较短，缓存收益不如「即时生效」重要。需实测确认 |
| D25 | 2核2G 上对象存储怎么放：继续用 MinIO（多一个容器、约 100~200MB 常驻内存），还是把存储换成服务器本地磁盘（要改 `MinioStorageService` 这层抽象，代码改动更大） | T11.4、T11.5 | 倾向**先继续用 MinIO**：内存能接受，且不用改代码；实测内存吃紧再考虑换本地磁盘。换的成本不在部署，在要重做存储抽象与历史数据迁移 |
| D26 | 大陆机房的域名与备案：腾讯云大陆机房走 80/443 必须完成 ICP 备案，否则只能用 IP + 非标准端口访问 | T11.1、T11.8 | 倾向**优先走备案 + 域名 + HTTPS**（对外可用性最好）；如果短期不想等备案，就先用 IP + 非标准端口跑通内部验证，把备案当并行事项推进 |
| D27 | `element-plus` 是否改成按需引入：现在 `main.ts` 全量注册，首屏必须下载 989 kB（gzip 316 kB）的 vendor chunk，也是构建告警剩下的两个来源之一 | T10.4 | 标准解法是加**构建期** devDependency `unplugin-vue-components`（自带 resolver，按模板里实际用到的标签自动引入组件与样式；只在构建时生效，不进产物、不影响运行期体积），首屏预计降到 400 kB 上下。按 AGENTS「不擅自引入依赖」的要求先确认。备选：不加依赖，接受现状（该 chunk 会被浏览器强缓存） |
| D28 | 演示环境的准入方式：① 邀请码（发给特定的人）；② 演示账号池（一组固定账号，页面直接给出，大家共用）；③ 开放注册 + 人机校验 | T12.2 | **倾向 ② 演示账号池 + ③ 的轻量版**：给 3~5 个固定演示账号，页面上直接展示，用完即走。理由是尝鲜阶段要让对方"零摩擦"，而邀请码会劝退一半人；风险是账号被共享滥用，靠 D31 的按 IP 配额兜住。**不建议此时做开放注册**——那意味着要处理垃圾账号、找回密码、发信验证一整条链路 |
| D29 | 演示环境的数据是否每日重置 | T12.6 | **倾向重置**（每天凌晨清一次，保留基础数据）。演示数据积多了既占磁盘，也会让画像 / 记忆越用越"脏"，影响新用户的第一印象；代价是演示用户上次的对话会消失，需要在页面上写明 |
| D30 | 演示环境是否使用**单独的一套 API Key**（DeepSeek + 火山各一个） | T12.3、T12.5 | **强烈建议单独开**。这是唯一能"物理兜底"的手段：代码里的配额逻辑写错、被人绕过、或者熔断失效时，损失被限制在演示 Key 的充值上限里，正式 Key 不受影响。成本是多管两个 Key，收益是"最坏情况可预期" |
| D31 | 演示环境的具体配额数值：每用户每日对话轮数 / 出题次数 / 复盘次数 / 语音分钟数，以及全局日预算上限 | T12.4 | **第一版刻意收紧**（被人嫌弃太紧，比被人刷爆好调）：**每 IP 每日 10 轮对话、2 次出题、1 次复盘、3 分钟语音**；**全局每日 150 次模型调用或 50 万 token 熔断**；**单会话 ≤ 5 轮**、**单用户会话 ≤ 3**、**笔记 ≤ 10**。理由与调法见 T12.4 末尾的"为什么这么小" |

---

## 附录 A：支持手动停止流式回答（原始方案）

- **状态**：待办
- **记录时间**：2026-09-17
- **任务编号**：T1.8
- **涉及模块**：`interpace-frontend`（对话输入区、流式请求层）、`interpace-backend`（会话路由、流式对话服务）
- **变更类型**：接口变更（新增停止接口）+ 前端交互变更

### A.1 背景与现状

`ChatInput` 回车（或点发送）后请求一经发出就无法中断：

- 前端 `src/api/streamChat.ts` 用 `fetch` 直接读取响应体流，没有 `AbortController`。
- `src/composables/useSessionStreamSender.ts` 里的 `stopActiveStream()` 只是自增 `epoch` 丢弃后续回调，网络请求仍在后台把整个流读完，后端 LLM 也在继续生成、继续计费。
- 流式期间 `:disabled="sending"` 会把输入框锁死，界面上没有任何「停止」入口。
- 后端 `app/services/stream_chat_service.py` 的 SSE 生成器一旦开始，就只能等模型输出结束。

### A.2 目标行为（验收标准）

1. 回答生成中，输入区把「发送」按钮切换为「停止」按钮（文案用中文）。
2. 点击停止后：
   - 前端立刻停止接收与渲染后续内容，界面解除发送中的禁用状态，可以继续提问；
   - 后端**立即停止后续逻辑**，不再继续消费模型输出、不再做面试转写等后置处理，并释放底层模型连接；
   - 已生成的部分内容按既定策略保留或丢弃（见 A.4），落库后消息状态能区分「正常完成」和「用户停止」。
3. 停止是幂等的：重复点击、或流已自然结束时点击，都不报错、不产生脏数据。

### A.3 方案要点

#### 后端

1. 新增停止接口，路由放在 `app/routes/session_routes.py`，路径沿用现有流式接口的写法：
   `POST /sessions/{session_id}/stream-chat/stop`（携带要停止的消息标识，如 `message_id` 或 `request_id`）。
   路由只做参数校验与鉴权，业务逻辑放 `app/services/`，请求/响应体用 Pydantic 模型。
2. 新增一个进程内的「停止登记表」（`message_id` / `request_id` → 取消标志），由流式服务在循环中轮询：命中标志即跳出循环，不再调用模型、不再执行后续逻辑。
3. `StreamChatService.stream_chat` 的生成器需要改造：
   - 循环里检查取消标志（当前是 `for chunk in chain_with_memory.stream(...)`，直接遍历不可中断，需要包一层判断并在退出时 `close()` 模型流，否则底层 HTTP 连接不会立刻释放）；
   - 落库逻辑（`finally` 中的 `row.response_text` 回写）要保证在「用户停止」路径上也一定执行，并写入停止状态；
   - 前端断开连接不能作为唯一手段：生成器是同步函数，Starlette 在线程池里迭代它，客户端断连时的取消不一定能及时打断，也可能跳过 `finally` 导致已生成内容不落库。
4. 停止接口要做归属校验（复用 `get_current_user` 与会话归属校验），避免越权停止他人会话。

#### 前端

1. `src/api/streamChat.ts`：`fetch` 接入 `AbortController`，把 `signal` 暴露出去；停止时先调用停止接口、再 `abort()`，保证即使停止接口失败也能停止本地渲染。
2. `src/api/` 新增停止接口的请求函数与类型定义（与后端 Pydantic 模型对齐）。
3. `src/composables/useSessionStreamSender.ts`：`stopActiveStream()` 改为真正的中断（abort + 调停止接口 + 取消打字机动画 + 收尾占位消息的 pending 状态），并导出供页面绑定。
4. `src/components/chat/ChatInput.vue`：`sending` 为真时把发送按钮渲染为停止按钮，新增 `stop` 事件；`ChatWindow` 透传；`InterviewRoom` / `StudyRoom` 接到事件后调用 `stopActiveStream()`。

### A.4 待确认的设计决策

1. **停止协议**：只依赖前端断连，还是「显式停止接口 + 断连」双保险？（建议双保险，原因见 A.3 后端第 3 点）
2. **部分内容**：停止后已生成的内容保留在气泡里，还是整条丢弃？
3. **消息状态**：`chat_messages.status` 目前 0=常规聊天、1=面试转写入口。停止如何标记？新增一个值（如 2=用户已停止）会影响前端展示逻辑，需要确认；若新增值，还要考虑它与 `status=1` 的面试转写入口如何共存（停止时未完成的面试记录怎么收尾）。
4. **面试场景**：面试进行到一半停止，已生成的部分是否需要生成不完整的面试记录卡片，还是直接丢弃。
5. **接口版本前缀**：根 `AGENTS.md` 要求接口统一带 `/api/v1/`，但现状是后端路由不带、前端 `VITE_API_BASE_URL=/api` 由 Vite 代理转发。新增接口先沿用现状，版本前缀统一由 T10.1 处理。

### A.5 验证要点

- 前端：`cd interpace-frontend && pnpm run build`。
- 后端：`cd interpace-backend && pytest`，新增停止接口的正常路径 + 越权/资源不存在路径用例。
- 联调：生成中点停止后，确认后端日志不再有后续模型输出、数据库里的响应文本与状态符合预期、前端可以立刻继续提问。
