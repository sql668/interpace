# 待办事项

## 1. 支持手动停止流式回答（前端 + 后端）

- 状态：待办
- 记录时间：2026-09-17
- 涉及模块：`interpace-frontend`（对话输入区、流式请求层）、`interpace-backend`（会话路由、流式对话服务）
- 变更类型：接口变更（新增停止接口）+ 前端交互变更

### 背景与现状

`ChatInput` 回车（或点发送）后请求一经发出就无法中断：

- 前端 `src/api/streamChat.ts` 用 `fetch` 直接读取响应体流，没有 `AbortController`。
- `src/composables/useSessionStreamSender.ts` 里的 `stopActiveStream()` 只是自增 `epoch` 丢弃后续回调，网络请求仍在后台把整个流读完，后端 LLM 也在继续生成、继续计费。
- 流式期间 `:disabled="sending"` 会把输入框锁死，界面上没有任何"停止"入口。
- 后端 `app/services/stream_chat_service.py` 的 SSE 生成器一旦开始，就只能等模型输出结束。

### 目标行为（验收标准）

1. 回答生成中，输入区把"发送"按钮切换为"停止"按钮（文案用中文）。
2. 点击停止后：
   - 前端立刻停止接收与渲染后续内容，界面解除发送中的禁用状态，可以继续提问；
   - 后端**立即停止后续逻辑**，不再继续消费模型输出、不再做面试转写等后置处理，并释放底层模型连接；
   - 已生成的部分内容按既定策略保留或丢弃（见下方待确认项），落库后消息状态能区分"正常完成"和"用户停止"。
3. 停止是幂等的：重复点击、或流已自然结束时点击，都不报错、不产生脏数据。

### 方案要点（初稿，实施前再确认）

#### 后端

1. 新增停止接口，路由放在 `app/routes/session_routes.py`，路径沿用现有流式接口的写法：
   `POST /sessions/{session_id}/stream-chat/stop`（携带要停止的消息标识，如 `message_id` 或 `request_id`）。
   路由只做参数校验与鉴权，业务逻辑放 `app/services/`，请求/响应体用 Pydantic 模型。
2. 新增一个进程内的"停止登记表"（`message_id` / `request_id` → 取消标志），由流式服务在循环中轮询：
   命中标志即跳出循环，不再调用模型、不再执行后续逻辑。
3. `StreamChatService.stream_chat` 的生成器需要改造：
   - 循环里检查取消标志（当前是 `for chunk in chain_with_memory.stream(...)`，直接遍历不可中断，需要包一层判断并在退出时 `close()` 模型流，否则底层 HTTP 连接不会立刻释放）；
   - 落库逻辑（`finally` 中的 `row.response_text` 回写）要保证在"用户停止"路径上也一定执行，并写入停止状态；
   - 前端断开连接不能作为唯一手段：生成器是同步函数，Starlette 在线程池里迭代它，客户端断连时的取消不一定能及时打断，也可能跳过 `finally` 导致已生成内容不落库。
4. 停止接口要做归属校验（复用 `get_current_user` 与会话归属校验），避免越权停止他人会话。

#### 前端

1. `src/api/streamChat.ts`：`fetch` 接入 `AbortController`，把 `signal` 暴露出去；停止时先调用停止接口、再 `abort()`，保证即使停止接口失败也能停止本地渲染。
2. `src/api/` 新增停止接口的请求函数与类型定义（与后端 Pydantic 模型对齐）。
3. `src/composables/useSessionStreamSender.ts`：`stopActiveStream()` 改为真正的中断（abort + 调停止接口 + 取消打字机动画 + 收尾占位消息的 pending 状态），并导出供页面绑定。
4. `src/components/chat/ChatInput.vue`：`sending` 为真时把发送按钮渲染为停止按钮，新增 `stop` 事件；`ChatWindow` 透传；`InterviewRoom` / `StudyRoom` 接到事件后调用 `stopActiveStream()`。

### 待确认的设计决策

1. **停止协议**：只依赖前端断连，还是"显式停止接口 + 断连"双保险？（建议双保险，原因见后端第 3 点）
2. **部分内容**：停止后已生成的内容保留在气泡里，还是整条丢弃？
3. **消息状态**：`chat_messages.status` 目前 0=常规聊天、1=面试转写入口。停止如何标记？新增一个值（如 2=用户已停止）会影响前端展示逻辑，需要确认；若新增值，还要考虑它与 `status=1` 的面试转写入口如何共存（停止时未完成的面试记录怎么收尾）。
4. **面试场景**：面试进行到一半停止，已生成的部分是否需要生成不完整的面试记录卡片，还是直接丢弃。
5. **接口版本前缀**：根 `AGENTS.md` 要求接口统一带 `/api/v1/`，但现状是后端路由不带、前端 `VITE_API_BASE_URL=/api` 由 Vite 代理转发。新增接口先沿用现状，版本前缀统一另开任务处理。

### 验证要点

- 前端：`cd interpace-frontend && npm run build`。
- 后端：`cd interpace-backend && pytest`，新增停止接口的正常路径 + 越权/资源不存在路径用例。
- 联调：生成中点停止后，确认后端日志不再有后续模型输出、数据库里的响应文本与状态符合预期、前端可以立刻继续提问。
