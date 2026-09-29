/// <reference types="vite/client" />

/** 项目用到的环境变量，新增变量时同步更新这里和 .env.example */
interface ImportMetaEnv {
  /** 站点标题 */
  readonly VITE_APP_TITLE?: string
  /** 接口基础地址，如 /api/v1 */
  readonly VITE_API_BASE_URL?: string
  /** 开发服务器代理的后端地址，仅 vite.config.ts 使用 */
  readonly VITE_API_PROXY_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
