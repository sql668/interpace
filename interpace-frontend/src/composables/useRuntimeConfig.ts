/**
 * 运行时能力开关的读取与缓存（T12.4）。
 *
 * 做成模块级单例的原因：这个配置在一次页面生命周期里不会变，但可能被多个页面
 * （面试间、以后的学习室、登录页的横幅）同时需要。每个组件各拉一次接口既浪费，
 * 也会让"同一时刻不同组件看到不同开关"成为可能。
 *
 * 拉取失败时**默认按"功能可用"处理**：演示环境关掉语音只是省钱，不是安全边界
 * （后端在 WebSocket 路由上也判了同一份配置）；反过来，如果因为一次网络抖动就把
 * 正式环境的功能藏起来，那才是真问题。
 */

import { readonly, ref } from 'vue'
import { getRuntimeConfig } from '@/api/runtimeConfig'
import type { RuntimeConfig } from '@/types/runtimeConfig'

const runtimeConfig = ref<RuntimeConfig | null>(null)
const loading = ref(false)
let loaded = false
let inflight: Promise<void> | null = null

/** 与后端接口的默认值保持一致：不确定时按"开放"处理。 */
const FALLBACK_FEATURES = { voice_interview: true, file_upload: true }

async function load(force = false): Promise<void> {
  if (loaded && !force) return
  if (inflight) return inflight

  loading.value = true
  inflight = (async () => {
    try {
      runtimeConfig.value = await getRuntimeConfig()
      loaded = true
    } catch (error) {
      // 不弹提示：这是后台能力探测，失败不该打断用户正在做的事。
      console.warn('[运行时配置] 拉取失败，暂时按功能可用处理', error)
      runtimeConfig.value = {
        app_env: 'unknown',
        quota_enforced: false,
        features: FALLBACK_FEATURES,
        interview_max_minutes: 0,
        notice: { banner_text: '' },
        limits: null
      }
      loaded = true
    } finally {
      loading.value = false
      inflight = null
    }
  })()
  return inflight
}

export function useRuntimeConfig() {
  return {
    /** 当前配置快照；未加载完成时为 null */
    runtimeConfig: readonly(runtimeConfig),
    loading: readonly(loading),
    /** 幂等加载；多个组件同时调用只会发一次请求 */
    ensureRuntimeConfig: load
  }
}
