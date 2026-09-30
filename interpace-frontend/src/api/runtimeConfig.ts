import api from './http'
import type { RuntimeConfig } from '@/types/runtimeConfig'

/**
 * 拉取当前环境的能力开关（T12.4）。
 *
 * 接口不带鉴权，所以登录页也能调用；返回的都是环境名与布尔开关，没有敏感信息。
 */
export async function getRuntimeConfig() {
  const { data } = await api.get<RuntimeConfig>('/config/runtime')
  return data
}
