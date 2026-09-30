<script setup lang="ts">
/**
 * 语音面试面板（T7.7）：面试官形象 + 波形 + 录音按钮 + 识别结果 + 文字兜底。
 *
 * 只负责展示与交互，语音链路的逻辑都在 `useVoiceInterview` 里。
 */
import { computed, ref, watch } from 'vue'
import { Microphone, VideoPlay } from '@element-plus/icons-vue'
import InterviewerAvatar from '@/components/avatar/InterviewerAvatar.vue'
import VoiceWaveform from '@/components/speech/VoiceWaveform.vue'
import type { VoiceStatus } from '@/composables/useVoiceInterview'

const props = defineProps<{
  status: VoiceStatus
  connected: boolean
  asrPartial: string
  asrFinal: string
  replyText: string
  micLevels: number[]
  playback: {
    isPlaying: boolean
    currentMs: number
    durationMs: number
    levels: number[]
  }
}>()

const emit = defineEmits<{
  start: []
  stop: []
  sendText: [text: string]
}>()

/** 文字兜底输入：浏览器不支持麦克风、或环境太吵时的退路 */
const fallbackText = ref('')

const statusText = computed(() => {
  switch (props.status) {
    case 'connecting':
      return '正在连接语音通道…'
    case 'recording':
      return '正在听你说；说完停一下会自动结束，也可以点按钮手动结束'
    case 'waiting':
      return '面试官正在思考…'
    case 'speaking':
      return '面试官正在说'
    case 'error':
      return '语音通道异常，可先用下面的文字输入'
    default:
      return props.connected ? '点下面的按钮开始回答' : '点击「开启语音面试」建立连接'
  }
})

const canStart = computed(() => props.connected && props.status === 'idle')

const handleFallbackSend = () => {
  const text = fallbackText.value.trim()
  if (!text) {
    return
  }
  emit('sendText', text)
  fallbackText.value = ''
}

// 识别出完整一句后把文字留在输入框里，方便用户核对（也可以直接改）
watch(
  () => props.asrFinal,
  (value) => {
    if (value) {
      fallbackText.value = value
    }
  }
)
</script>

<template>
  <section class="voice-panel">
    <InterviewerAvatar
      :speaking="playback.isPlaying"
      :current-ms="playback.currentMs"
      :duration-ms="playback.durationMs"
      :levels="playback.levels" />

    <p class="voice-panel__status">{{ statusText }}</p>

    <!-- 录音时的音浪：让用户确认麦克风真的在收音 -->
    <VoiceWaveform
      v-if="status === 'recording'"
      class="voice-panel__mic-wave"
      :levels="micLevels"
      active />

    <div class="voice-panel__actions">
      <button
        type="button"
        class="record-button"
        :class="{ 'record-button--active': status === 'recording' }"
        :disabled="!canStart && status !== 'recording'"
        @click="status === 'recording' ? emit('stop') : emit('start')">
        <el-icon><Microphone /></el-icon>
        {{ status === 'recording' ? '说完了' : '开始说话' }}
      </button>
    </div>

    <div v-if="asrPartial || asrFinal" class="voice-panel__line">
      <span class="voice-panel__label">你说的</span>
      <span class="voice-panel__text">{{ asrFinal || asrPartial }}</span>
    </div>

    <div v-if="replyText" class="voice-panel__line">
      <span class="voice-panel__label">面试官</span>
      <span class="voice-panel__text">{{ replyText }}</span>
    </div>

    <!-- 文字兜底：语音不可用时也能继续面试 -->
    <div class="voice-panel__fallback">
      <input
        v-model="fallbackText"
        type="text"
        placeholder="也可以用文字回答"
        :disabled="status === 'waiting' || status === 'speaking'"
        @keyup.enter="handleFallbackSend" />
      <button
        type="button"
        :disabled="!connected || status === 'waiting' || status === 'speaking'"
        @click="handleFallbackSend">
        <el-icon><VideoPlay /></el-icon>
        发送
      </button>
    </div>
  </section>
</template>

<style scoped lang="scss">
.voice-panel {
  border: 1px solid #dfe6f1;
  border-radius: 12px;
  background: #fbfcff;
  padding: 16px;
  /* 与外层保持同样的左右留白，避免贴边；上留白和入口按钮拉开距离 */
  margin: 10px 16px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  /* 面板高度固定不可压缩；窗口太矮时它自己内部滚动，
     绝不把下面的输入框挤出屏幕（否则就会出现「输入框跟着页面滚」）。 */
  flex-shrink: 0;
  max-height: 46vh;
  overflow-y: auto;
}

.voice-panel__status {
  margin: 0;
  font-size: 13px;
  color: #7b8290;
}

.voice-panel__mic-wave {
  width: 240px;
}

.record-button {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #cfd8e6;
  border-radius: 999px;
  background: #fff;
  color: #2f4660;
  font-size: 15px;
  padding: 10px 22px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.record-button--active {
  border-color: #e06262;
  background: #fdeaea;
  color: #c33;
}

.voice-panel__line {
  width: 100%;
  display: flex;
  gap: 8px;
  font-size: 14px;
  line-height: 1.6;
}

.voice-panel__label {
  flex-shrink: 0;
  color: #9ea6b4;
}

.voice-panel__text {
  color: #2f3642;
  word-break: break-word;
}

.voice-panel__fallback {
  width: 100%;
  display: flex;
  gap: 8px;

  input {
    flex: 1;
    border: 1px solid #cfd8e6;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;

    &:focus {
      outline: none;
      border-color: #4385f1;
    }
  }

  button {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid #4385f1;
    border-radius: 8px;
    background: #4385f1;
    color: #fff;
    padding: 8px 14px;
    cursor: pointer;

    &:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
  }
}
</style>
