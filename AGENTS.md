# InterPace（面途）协作规则

AI 模拟面试 + 自动复盘项目。前端 Vue 3 + Vite + TypeScript，后端 Python + FastAPI，接口风格 REST。


## 架构通用规范

1. 项目必须按功能模块拆分，禁止编写超大单体文件
2. 通用工具、公共方法统一抽离封装，全局复用
3. 业务逻辑和页面/接口入口分离，不把所有逻辑写在入口处
4. 目录结构清晰，同类文件统一归类存放


## AI / 智能体开发

1. 涉及智能体开发（多步骤推理、工具调用、流程编排、状态流转）一律优先使用 LangGraph 编排、LangChain 承载模型与提示词，禁止手写编排循环，也禁止另造一套 Agent 框架。
2. 分工：编排用 LangGraph（`StateGraph` 定义节点与状态流转）；模型接入、提示词模板、工具、记忆用 LangChain 对应的包。
3. 编排代码统一放 `interpace-backend/app/agent/`，按场景拆分模块，不写进路由层或 service 入口。
4. 流式输出沿用现有 SSE 事件约定，编排层只负责产出增量文本，路由层不感知编排细节。
5. 依赖已声明 `langchain`、`langchain-community`、`langchain-openai`、`langgraph`，优先复用；要引入其他智能体相关依赖时按「改动纪律」先确认。


## 沟通与产出

- 默认用中文回答、写注释和提交信息；变量名、函数名、接口字段一律英文。
- 动手前先说明打算改哪些文件；跨模块或涉及接口的改动，先给方案再改代码。
- 需求不清楚就问，不要自行扩大改动范围或替用户做产品决定。

## 目录职责

- `interpace-frontend/`：前端。详细规则见 `interpace-frontend/AGENTS.md`。
- `interpace-backend/`：后端。详细规则见 `interpace-backend/AGENTS.md`。
- `docs/`：设计文档与流程图，只放文档，不放代码。

## 改动纪律

- 只做与当前任务相关的改动，不顺手重构、不删除无关代码、不格式化无关文件。
- 不提交 `node_modules/`、构建产物、`.env`、任何密钥或 Token。
- 不擅自引入新的第三方依赖：先说明用途、替代方案和体积影响，得到确认再加。

## 验证

- 前端改动后至少跑通 `cd interpace-frontend && npm run build`。
- 后端改动后至少跑通 `cd interpace-backend && pytest`。
- 验证没跑或没跑通要如实说明，不要含糊带过。

## 接口变更

- 改接口就同时改三处：后端路由与 Pydantic 模型、前端 `src/api/` 与类型定义、相关文档。
- 接口路径统一带版本前缀 `/api/v1/`。
- **现状（T10.1 已落实）**：后端在 `app/main.py` 用 `API_V1_PREFIX` 统一挂前缀，前端 `VITE_API_BASE_URL=/api/v1`，Vite 代理只转发、不再做 `rewrite`。**新增接口直接写在业务前缀之下即可，不要再自己拼 `/api/v1`**。
- 例外：探活（`/health/*`）、接口文档（`/docs`）、根路径（`/`）与静态目录 `/uploads` 刻意不带版本前缀——它们不是业务接口，不该随 API 版本变动。
