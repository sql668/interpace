# 面途 InterPace · 前端

Vue 3 + TypeScript + Vite + Pinia + Element Plus。
项目总览与本地启动见根目录 [README](../README.md)。

## 命令

```bash
pnpm install        # 安装依赖
pnpm run dev        # 开发服务器，默认 5173
pnpm run build      # 生产构建（含 vue-tsc 类型检查）
pnpm run preview    # 用构建产物起预览服务
```

> 根目录的 `./dev.sh start` 也能一键起前端（连同后端），并管好进程与日志。

## 目录结构

```
src/
  api/         接口封装（axios 实例、流式对话、语音 WebSocket）
  components/  chat / notebook / quiz / resume / profile / evaluation / speech …
  composables/ useSessionStreamSender、useVoiceInterview、useNoteAutoSave…
  constants/   模式与导航常量（select_model 与后端 scene_registry 对齐）
  router/      路由（页面级懒加载）
  stores/      Pinia
  types/       与后端 schema 对齐的类型
  utils/       markdown 渲染、错误文案、PCM 处理等
  views/       首页、登录、学习室、面试间、笔记本、我的画像
deploy/nginx.conf   容器里的 Nginx 配置（生产用）
```

## 环境变量（构建期注入）

`VITE_*` 是**打包时**写入产物的，改了要重新构建或重启 dev server：

| 变量 | 说明 |
| --- | --- |
| `VITE_API_BASE_URL` | 接口基地址。开发是 `/api/v1`，由 Vite 代理转发到后端 |
| `VITE_APP_TITLE` | 站点标题 |
| `VITE_API_PROXY_TARGET` | 仅开发用，代理目标（默认 `http://127.0.0.1:8000`） |

注意 **`pnpm run dev` 永远读 `.env.development`**；想看"生产构建的样子"用
`pnpm run build && pnpm run preview`。

## 两个踩过坑的地方（改代码时留个心）

1. **代码高亮依赖全局 `Prism`**：`src/utils/prism-setup.ts` 负责把它挂到 `globalThis`，
   **必须排在 `markdownUtil.ts` 里所有 `prismjs/components/*` 之前 import**。
   顺序调换、或把它拆到别的 chunk，会在**生产构建**里报 `Prism is not defined`
   （开发模式看不见这个错）。
2. **错误提示统一走 `src/utils/errorMessage.ts`**：`notifyError()` 优先用后端的 `message`
   （比"按状态码套模板"准确），并跳过拦截器已经提示过的，避免一次失败弹两个框。
   不要再用 `ElMessage.error(error.message)`——那会把 axios 的英文原文
   （`Request failed with status code 429`）暴露给用户。
