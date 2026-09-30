/**
 * 统一把错误转成"能给用户看的一句话"。
 *
 * 为什么需要它：后端返回的错误体里本来就有精心写好的中文 `message`
 * （例如 429 的"演示环境的体验额度已用完…"、409 的"用户名已被占用"），
 * 但很多组件直接用 `error.message` —— 那是 **axios 的默认文案**
 * （`Request failed with status code 429`），用户看了只会一头雾水。
 *
 * 另外：`http.ts` 的响应拦截器也会弹一次提示。如果不做去重，
 * 同一次失败会弹两个框。所以拦截器提示过之后会在错误对象上打一个标记，
 * 这里看到标记就跳过。
 */

import { ElMessage } from 'element-plus'

/** 带标记的错误对象：拦截器已经弹过提示了 */
type NotifiedError = { __notified?: boolean }

/** 后端统一错误体的形状（见 app/core/response_models.py） */
type BackendErrorBody = { message?: string; detail?: unknown }

/**
 * 从错误对象里取出最适合展示的一句话，取不到就用 `fallback`。
 *
 * 优先级：后端 `message` → 非 axios 默认文案的 `error.message` → `fallback`。
 */
export function resolveErrorMessage(error: unknown, fallback: string): string {
  const body = (error as { response?: { data?: BackendErrorBody } })?.response?.data
  if (body && typeof body.message === 'string' && body.message.trim()) {
    return body.message
  }

  if (error instanceof Error && error.message) {
    // 过滤掉 axios 自己的英文兜底文案，它对用户没有信息量
    if (!/^Request failed with status code \d+$/.test(error.message) && !/^Network Error$/i.test(error.message)) {
      return error.message
    }
  }

  return fallback
}

/**
 * 弹一次错误提示。
 *
 * 如果 `http.ts` 的拦截器已经为这次失败弹过，就什么都不做（避免双弹窗）。
 */
export function notifyError(error: unknown, fallback: string): void {
  if ((error as NotifiedError)?.__notified) {
    return
  }
  ElMessage.error(resolveErrorMessage(error, fallback))
}

/** 标记这条错误已经提示过（拦截器调用）。 */
export function markNotified(error: unknown): void {
  if (error && typeof error === 'object') {
    ;(error as NotifiedError).__notified = true
  }
}
