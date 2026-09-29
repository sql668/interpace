import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

/** 项目根目录（interpace-frontend/），用于解析别名和环境变量目录 */
const projectRoot = fileURLToPath(new URL('.', import.meta.url))

/** 后端服务默认地址，与 uvicorn 默认端口保持一致 */
const DEFAULT_API_PROXY_TARGET = 'http://127.0.0.1:8000'

/** 开发/预览服务器统一代理配置：/api 开头的请求转发到后端 */
const createProxy = (target: string) => ({
  '/api': {
    target,
    changeOrigin: true,
    // 前端统一以 /api 作为基地址（VITE_API_BASE_URL），
    // 但后端路由本身不带 /api 前缀，转发前需要把这段前缀去掉。
    rewrite: (path: string) => path.replace(/^\/api/, ''),
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
  }
})
