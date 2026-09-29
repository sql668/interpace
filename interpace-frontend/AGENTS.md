# 前端规则（interpace-frontend）

Vue 3 + TypeScript + Vite。当前依赖只有 `vue`，路由、状态管理、请求库尚未接入。

## 组件写法

- 一律用 `<script setup lang="ts">` 单文件组件，禁止 Options API。
- 禁止 `any`；`props`、`emits` 必须显式声明类型。
- 组件文件用 `PascalCase.vue`，其他文件用 `kebab-case.ts`。
- 变量方法使用小驼峰命名
- 单文件超过约 300 行就要考虑拆分子组件。
- 接口请求统一封装，不在页面内直接写网络请求代码
- 页面和通用组件拆分，可复用逻辑抽离组合式函数
- 严格按目录分层：页面、组件、接口、工具分开存放

## 目录约定

- `src/api/`：接口调用封装。
- `src/types/`：与后端接口对应的类型定义。
- `src/views/`：页面级组件；`src/components/`：可复用组件。
- `src/composables/`：可复用的组合式逻辑，命名 `useXxx.ts`。
- `src/stores/`：全局状态（接入 Pinia 后使用）。
- `src/config/`：全局配置（环境变量等），统一出口为 `src/config/env.ts`。

## 接口调用

- 组件里禁止直接 `fetch` 或直接调用请求库，统一走 `src/api/` 导出的函数。
- 后端返回的错误在一个地方统一处理，组件只处理业务分支，不重复写 try/catch 兜底。
- 接口地址统一走 `env.apiBaseUrl`（`src/config/env.ts`），路径自带 `/api/v1` 前缀，开发环境由 Vite 代理转发。

## 别名与环境变量

- 导入 `src/` 下的模块一律用 `@/` 别名，不写多层 `../../` 相对路径。
- 环境变量写在 `.env.development` / `.env.production`，本地覆盖写 `.env.local`，模板见 `.env.example`；新增变量要同步 `src/types/env.d.ts` 和 `.env.example`。

## 样式

- 组件样式写 `<style scoped>`；全局样式只放 `src/style.css`。
- 不写内联 `style`，动态计算的值除外。
- UI 文案用中文。

## 验证

- 提交前跑 `npm run build`，它包含 `vue-tsc` 类型检查，报错必须清零。
- ESLint / Prettier 尚未配置；接入后在此补上 lint 命令。

## 包管理器
使用 pnpm 管理依赖，禁止使用 npm 或 yarn。
