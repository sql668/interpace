<script setup lang="ts">
import { Download, Headset, Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { fetchResourceBlob } from '@/api/resource'
import type { MessageSegment } from '@/types/chat'

const props = defineProps<{
  segment: MessageSegment
}>()

const objectUrl = ref('')
const loading = ref(false)
const failed = ref(false)
const audioRef = ref<HTMLAudioElement | null>(null)

const displayName = computed(() => props.segment.name || '未命名附件')
const hasResource = computed(() => typeof props.segment.resource_id === 'number')

/** 释放临时地址，避免切换消息或卸载后内存泄漏 */
const releaseUrl = () => {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = ''
  }
}

/** 按需拉取资源内容；成功返回临时地址，失败返回空串 */
const load = async (): Promise<string> => {
  const resourceId = props.segment.resource_id
  if (typeof resourceId !== 'number' || loading.value) {
    return objectUrl.value
  }
  if (objectUrl.value) {
    return objectUrl.value
  }

  loading.value = true
  failed.value = false
  try {
    objectUrl.value = URL.createObjectURL(await fetchResourceBlob(resourceId))
    return objectUrl.value
  } catch {
    failed.value = true
    return ''
  } finally {
    loading.value = false
  }
}

// 图片要立刻显示，所以挂载与切换时主动取；音频与文件按需取，
// 免得一进会话就为所有历史附件发一堆请求。
watch(
  () => [props.segment.resource_id, props.segment.type] as const,
  async () => {
    releaseUrl()
    failed.value = false
    if (props.segment.type === 'image' && hasResource.value) {
      await load()
    }
  },
  { immediate: true }
)

onBeforeUnmount(releaseUrl)

const handleAudioPlay = async () => {
  const url = await load()
  if (!url) {
    return
  }
  await nextTick()
  // 播放由用户点击触发，不会被浏览器的自动播放策略拦下
  audioRef.value?.play().catch(() => undefined)
}

const handleDownload = async () => {
  const url = await load()
  if (!url) {
    ElMessage.error('附件下载失败')
    return
  }
  const link = document.createElement('a')
  link.href = url
  link.download = displayName.value
  link.click()
}
</script>

<template>
  <div class="msg-file">
    <!-- 历史数据里可能没有 resource_id（旧消息），这时只能提示，不要去请求 -->
    <p v-if="!hasResource" class="hint">该附件缺少资源标识，无法显示</p>

    <template v-else>
      <!-- 图片：直接内联显示 -->
      <template v-if="segment.type === 'image'">
        <img
          v-if="objectUrl"
          class="image"
          :src="objectUrl"
          :alt="displayName"
          @error="failed = true" />
        <p v-else-if="loading" class="hint hint--muted">
          <el-icon><Picture /></el-icon>
          图片加载中…
        </p>
        <p v-else class="hint">图片加载失败</p>
      </template>

      <!-- 音频：点了再取，取到后自动播放 -->
      <template v-else-if="segment.type === 'audio'">
        <audio v-if="objectUrl" ref="audioRef" class="audio" :src="objectUrl" controls></audio>
        <el-button v-else class="play-btn" :loading="loading" @click="handleAudioPlay">
          <el-icon><Headset /></el-icon>
          播放 {{ displayName }}
        </el-button>
      </template>

      <!-- 文件：点了再取，取到后触发下载 -->
      <template v-else>
        <el-button class="download-btn" :loading="loading" @click="handleDownload">
          <el-icon><Download /></el-icon>
          {{ displayName }}
        </el-button>
      </template>

      <p v-if="failed" class="hint">附件读取失败，可能已被清理</p>
    </template>
  </div>
</template>

<style scoped lang="scss">
.msg-file {
  margin-top: 8px;
}

.image {
  width: min(560px, 100%);
  max-height: 420px;
  object-fit: contain;
  border-radius: 10px;
  border: 1px solid #dfe5ef;
  display: block;
  background: #f5f8fd;
}

.audio {
  width: min(360px, 100%);
}

.play-btn,
.download-btn {
  height: 34px;
}

.hint {
  margin: 6px 0 0;
  color: #bf5b48;
  font-size: 12px;
}

.hint--muted {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #7b8290;
}
</style>
