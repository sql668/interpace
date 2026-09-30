import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { env } from '@/config/env'
import { markNotified, resolveErrorMessage } from '@/utils/errorMessage'
import router from '../router'
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './token'

// 统一从 env 出口读取，缺失时会直接抛错，不再静默拿到 undefined
const baseURL = env.apiBaseUrl

// 业务接口实例：统一挂载鉴权头
const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 刷新专用实例：避免拦截器递归
const refreshClient = axios.create({
  baseURL,
  timeout: 10000
})

let isRefreshing = false
let pendingQueue: Array<(token?: string) => void> = []

function enqueuePending(cb: (token?: string) => void) {
  pendingQueue.push(cb)
}

function flushPending(token?: string) {
  pendingQueue.forEach((cb) => cb(token))
  pendingQueue = []
}

// 请求拦截：注入 access_token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const status = error.response?.status

    // 非 401 或已重试过，直接抛出
    if (status && status !== 401) {
      // 优先用**后端返回的 message**：它比"按状态码套模板"具体得多，
      // 例如 429 的"演示环境的体验额度已用完…"、409 的"用户名已被占用"。
      // 拿不到后端文案时才退回通用提示。
      const statusFallback: Record<number, string> = {
        400: '请求参数错误',
        403: '没有访问权限',
        404: '资源不存在',
        409: '资源冲突',
        422: '请求参数校验失败',
        429: '请求过于频繁，请稍后再试',
        500: '系统异常，请稍后再试'
      }
      const text = resolveErrorMessage(error, statusFallback[status] ?? '请求失败，请稍后再试')
      // 429 是有"明确原因"的一类（配额用完 / 限流），用 warning 而不是 error，
      // 视觉上更贴近"不是坏了，是暂时不能用了"。
      if (status === 429) {
        ElMessage.warning(text)
      } else {
        ElMessage.error(text)
      }
      // 标记一下，避免组件里再弹一次（同一次失败弹两个框很烦）
      markNotified(error)
      return Promise.reject(error)
    }

    if (status !== 401 || original?._retry) {
      return Promise.reject(error)
    }

    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      // 没有 refresh_token，清理本地并抛出
      clearTokens()
      router.replace('/login')
      return Promise.reject(error)
    }

    if (isRefreshing) {
      // 正在刷新：将请求挂起，等刷新完成后重试
      return new Promise((resolve, reject) => {
        enqueuePending((token) => {
          if (!token) {
            reject(error)
            return
          }
          original.headers.Authorization = `Bearer ${token}`
          resolve(api(original))
        })
      })
    }

    original._retry = true
    isRefreshing = true

    try {
      // 根据接口文档：刷新请求体字段名为 "refresh token"
      const refreshResp = await refreshClient.post('/auth/refresh', {
        'refresh token': refreshToken
      })
      const data = refreshResp.data as { access_token: string; refresh_token: string; expires_in?: number }
      if (!data?.access_token || !data?.refresh_token) {
        throw new Error('Invalid refresh response')
      }
      // 保存新 token，并重放挂起请求
      setTokens(data)
      flushPending(data.access_token)
      original.headers.Authorization = `Bearer ${data.access_token}`
      return api(original)
    } catch (refreshError) {
      // 刷新失败：清理本地并拒绝所有挂起请求
      clearTokens()
      flushPending(undefined)
      router.replace('/login')
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

export default api
