import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

/** 项目根目录（interpace-frontend/），用于解析别名和环境变量目录 */
const projectRoot = fileURLToPath(new URL('.', import.meta.url))

/** 后端服务默认地址，与 uvicorn 默认端口保持一致 */
const DEFAULT_API_PROXY_TARGET = 'http://127.0.0.1:8000'

/**
 * 生产构建的分包策略（T10.4）。
 *
 * 背景：改造前是「一个 2.1MB 的 index.js」——路由静态导入 + element-plus 全量注册，
 * 把笔记页才用得到的 wangEditor、代码高亮用的 prismjs 也塞进了首屏。
 *
 * 这里只做两件事：
 * 1. 路由组件已经改成动态 import（见 src/router/index.ts），天然按页拆包；
 * 2. 把跨页面复用、且体积大的依赖单独拆成 vendor chunk——它们内容稳定，
 *    发版时 hash 不变，用户能一直命中浏览器缓存。
 *
 * 注意：`element-plus` 仍是全量注册（main.ts 里 app.use(ElementPlus)）。
 * 想再降一截要改成按需引入，那需要引入 unplugin-vue-components 之类的构建期依赖，
 * 属于「加依赖」的改动，单独评估，不在这里顺手做。
 */
const VENDOR_CHUNK_RULES: Array<{ name: string; test: RegExp }> = [
  { name: 'vendor-element-plus', test: /node_modules[\\/]element-plus[\\/]/ },
  { name: 'vendor-wangeditor', test: /node_modules[\\/]@wangeditor[\\/]/ },
  // prismjs **刻意不单独分块**：它的语言包依赖全局 Prism，而全局是在
  // `src/utils/prism-setup.ts` 里挂的。如果 core / setup / 语言包被拆到不同 chunk，
  // 加载顺序就不受控，语言包可能在全局还没挂上时求值 → 生产环境
  // "ReferenceError: Prism is not defined"（真机上踩过）。
  // 让它们留在同一个 chunk 里，ESM 的依赖求值顺序才有保证。
  { name: 'vendor-markdown', test: /node_modules[\\/]markdown-it[\\/]/ },
  { name: 'vendor-vue', test: /node_modules[\\/](vue|vue-router|pinia|@vue)[\\/]/ },
]

/** 开发/预览服务器统一代理配置：/api 开头的请求转发到后端 */
const createProxy = (target: string) => ({
  '/api': {
    target,
    changeOrigin: true,
    // 语音面试走 WebSocket（T7.6 的 /sessions/{id}/speech/stream）。
    // 不打开 ws 的话，开发环境下握手会被代理直接拒掉，前端只会看到「连接失败」。
    ws: true,
    // T10.1 之后前端基地址是 /api/v1、后端也挂在 /api/v1，两边一致，
    // 代理只负责转发，**不再需要 rewrite**（之前的 rewrite 会把 /api 剥掉）。
  },
})

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 第三个参数传空字符串，才能读到没有 VITE_ 前缀的变量（如代理地址）
  const env = loadEnv(mode, projectRoot, '')
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || DEFAULT_API_PROXY_TARGET

  return {
    plugins: [vue()],
    envDir: projectRoot,
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      proxy: createProxy(apiProxyTarget),
    },
    preview: {
      proxy: createProxy(apiProxyTarget),
    },
    build: {
      rolldownOptions: {
        output: {
          // 同名的 chunk 会被合并，未命中的依赖仍按动态 import 自动拆包。
          advancedChunks: {
            groups: VENDOR_CHUNK_RULES.map((rule) => ({
              name: rule.name,
              test: rule.test,
            })),
          },
        },
      },
    },
  }
})
