/**
 * 运行环境变量统一出口。
 * 变量定义在 .env / .env.[mode] 中，必须以 VITE_ 前缀才会注入到前端代码。
 * 业务代码统一从这里读取，不直接访问 import.meta.env。
 */

/** 默认站点标题 */
const DEFAULT_APP_TITLE = '面途 InterPace AI'

/** 接口基础地址缺失时的提示信息 */
const MISSING_API_BASE_URL_MESSAGE =
  '缺少环境变量 VITE_API_BASE_URL，请参考 .env.example 在 .env.[mode] 中配置'

export interface AppEnv {
  /** 接口基础地址，末尾不带斜杠，例如 /api/v1 */
  apiBaseUrl: string
  /** 站点标题 */
  appTitle: string
  /** 是否为开发环境 */
  isDev: boolean
}

/** 去掉末尾斜杠，避免拼接接口路径时出现双斜杠 */
function normalizeBaseUrl(rawValue: string): string {
  return rawValue.trim().replace(/\/+$/, '')
}

function readApiBaseUrl(): string {
  const rawValue = import.meta.env.VITE_API_BASE_URL

  if (!rawValue || !rawValue.trim()) {
    throw new Error(MISSING_API_BASE_URL_MESSAGE)
  }

  return normalizeBaseUrl(rawValue)
}

function readAppTitle(): string {
  return import.meta.env.VITE_APP_TITLE?.trim() || DEFAULT_APP_TITLE
}

export const env: AppEnv = {
  apiBaseUrl: readApiBaseUrl(),
  appTitle: readAppTitle(),
  isDev: import.meta.env.DEV,
}
