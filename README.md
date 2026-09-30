# 面途 InterPace

AI 模拟面试 + 自动复盘。像面试官一样追问，像教练一样复盘，**并且记得住你**——
你的项目、薄弱点、反复犯的表达问题会沉淀成画像，让下一次回答比上一次更贴着你。

## 它做什么

| 模块 | 内容 |
| --- | --- |
| **学习室** | 知识精讲（把知识点讲透，可追问）、刷题评测（按岗位出卷 → 卡片作答 → 自动评分 → 薄弱点写回画像） |
| **面试间** | 简历优化（解析 + 改写 + 导出 Word）、模拟面试（一问一答或**语音对话**）、面试复盘（总结 + 薄弱点 + 改进建议） |
| **笔记本** | 把任何一轮对话一键存成笔记；进入全文检索索引，之后能"翻回去" |
| **我的画像** | 看清系统记住了你什么，可以改、可以删、可以拒绝 |

## 亮点：三层记忆（越用越准）

借鉴 Hermes 的分层思路，**每个人的记忆完全隔离**：

| 层 | 记住什么 | 存在哪 | 什么时候用 |
| --- | --- | --- | --- |
| **L1 明细** | 技能 / 薄弱点 / 答题方法，带掌握度、来源与证据次数 | `user_memories` | 每次回答前挑相关的注入 |
| **L2 方法** | 反复出现的表达问题沉淀成的"答题套路"，同类问题复用同一条 | `user_memories(category=method)` | 只在面试与复盘场景注入 |
| **L3 检索** | 历史对话 / 笔记 / 复盘的原文 | `search_documents`（MySQL 全文索引 + ngram） | 只在你说的话里出现回溯指代时才查 |

写入不是"模型说了算"：

- **来源权重**：行为证据 > 自述与简历 > 模型推断，弱来源不能覆盖强来源；
- **先确认再写入**：模型推断出的画像落成"待确认"，你点了确认才生效；
- **容量上限**：每类满了自动合并相近条目，而不是无限堆积；
- **可解释**：每次改动留变更日志，你在「我的画像」里能看、能改、能删；
- **按用户隔离**：别人的画像不会进入你的提示词。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Element Plus（路由级懒加载） |
| 后端 | FastAPI + SQLAlchemy + Alembic（路由 / 校验 / 业务 / 数据四层） |
| 智能体 | **LangGraph + LangChain**（对话图、记忆抽取状态图） |
| 存储 | MySQL 8（含中文全文检索）、Redis（模板缓存）、MinIO（对象存储） |
| 语音 | 火山引擎 ASR + TTS，双向流式 WebSocket（Key 只留在后端） |
| 部署 | Docker Compose + Nginx，目标机器 2核2G |

## 目录结构

```
interpace-backend/    后端（FastAPI，见其 README）
interpace-frontend/   前端（Vue 3，见其 README）
docs/                 文档（设计、接口、开发、部署）
docker-compose.yml    生产编排（+ docker-compose.npm.yml 用于接入 Nginx Proxy Manager）
dev.sh                本地开发一键启停
```

## 快速开始（本地开发）

**前置**：Python 3.10+ 与 `uv`、Node 22 与 `pnpm`、MySQL 8；
Redis 与 MinIO 建议用 Docker 容器常驻（详见本地开发环境文档）。

```bash
git clone <仓库地址> && cd InterPace

# 装依赖
cd interpace-backend  && uv sync
cd ../interpace-frontend && pnpm install

# 后端配置（.env 系列不进仓库，需要手动建一份）
cd ../interpace-backend && cp .env.example .env.development && vim .env.development
cd ..

# 一键启停：后端 8000 + 前端 5173，后台运行，日志在 .dev-run/
./dev.sh start
./dev.sh status      # 看状态与当前环境
./dev.sh logs        # 跟日志
./dev.sh stop
```

浏览器打开 **http://localhost:5173**（接口文档在 http://127.0.0.1:8000/docs）。

细节、常见问题、**如何指定与验证不同环境**：见 [本地开发环境](docs/开发/本地开发环境.md)。

## 测试与构建

需要 MySQL 在运行（后端测试会连真实数据库）：

```bash
cd interpace-backend  && uv run pytest          # 后端测试
cd interpace-frontend && pnpm run build         # 前端构建（含类型检查）
```

改数据库模型要配迁移，流程见 [数据库变更流程](docs/开发/数据库变更流程.md)。

## 部署

目标环境是腾讯轻量云 2核2G：

```bash
cp .env.example .env && vim .env      # 填数据库/对象存储密码、JWT 密钥、模型 Key
docker compose build
docker compose up -d
docker compose ps                     # 全部 healthy 才算成功
```

完整流程（含 Nginx Proxy Manager 接入、更新与回滚、备份恢复、上线冒烟、常见故障）见
[Docker 部署](docs/部署/docker部署.md)。

> ⚠️ 两个最容易踩的坑，**动手前先看文档**：
> **构建机与服务端 CPU 架构必须一致**（Apple Silicon 上构建不出 amd64 镜像）；
> **`docker load` 会覆盖同名标签**（离线传镜像时不要把第三方镜像也打包进去）。

## 环境与配置

运行环境由 **`APP_ENV`** 决定，四套配置各一个文件（`.env.{APP_ENV}`）：

| 环境 | 用途 | 配额 |
| --- | --- | --- |
| `development` | 本机开发，自动建表 | 不生效 |
| `demo` | 对外演示 | **生效**（按 IP 限 token / 轮数 / 单场面试时长…） |
| `test` | 测试 | 不生效 |
| `production` | 正式 | 不生效，且不自动建表（靠 Alembic 迁移） |

演示环境的限制写在 `interpace-backend/config/demo_limits.json`，**改完最多 5 秒热生效**、
不用重启；当前生效值可以直接问接口：`GET /api/v1/config/runtime`。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [本地开发环境](docs/开发/本地开发环境.md) | 启动/停止、指定环境、两套环境的区别、常见问题 |
| [数据库变更流程](docs/开发/数据库变更流程.md) | 改模型 → 生成迁移 → 校验 |
| [Docker 部署](docs/部署/docker部署.md) | 构建、编排、NPM 接入、更新回滚、备份恢复、冒烟 |
| [接口文档](docs/接口/README.md) | 通用约定 + 全部接口索引（分模块详细说明） |
| [流程图](docs/流程图/) | 学习模块、面试模块的设计图 |
| [火山引擎语音](docs/火山引擎_语音识别_文档.md) | ASR / TTS 接入细节（本项目用到的部分） |
| [TODO / 路线图](docs/TODO.md) | 任务、决策、已完成与遗留（**最全的单一事实来源**） |

## 当前进度

阶段 0~10 已完成（模式路由、笔记、附件、知识精讲、刷题评测、简历优化、模拟面试与语音、
面试复盘、长期记忆、收尾）；部署（阶段 11）已跑通并支持接入 Nginx Proxy Manager；
多环境与演示配额（阶段 12）已完成主要部分。

待办、遗留与待拍板的决策都记在 [docs/TODO.md](docs/TODO.md)。
