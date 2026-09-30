<script setup lang="ts">
/**
 * 面试官形象（T7.7：三步走里的第 1 步——**静态头像**）。
 *
 * 这一版刻意不做任何形变动画。它的作用是先把「可以塞进一个头像层」的结构立起来，
 * 让 T7.9 的口型动效只需要替换这里的渲染，而不用动上层。
 *
 * 播放状态通过 props 传入（是否在播、播到第几毫秒、当前音量），
 * 这样头像层与语音逻辑解耦：T7.9 要用这些数据驱动口型，不需要去按钮组件里翻。
 */
import { computed } from 'vue'
import VoiceWaveform from '@/components/speech/VoiceWaveform.vue'

const props = defineProps<{
  /** 是否正在播放面试官的语音 */
  speaking: boolean
  /** 播放进度（毫秒）与总时长（毫秒），T7.9 口型同步会用 */
  currentMs: number
  durationMs: number
  /** 播放音量序列（0~1） */
  levels: number[]
}>()

/** 说话时给头像加一圈光晕，给用户「他在说话」的直观反馈 */
const ringClass = computed(() => (props.speaking ? 'avatar__ring avatar__ring--active' : 'avatar__ring'))
</script>

<template>
  <div class="avatar">
    <div :class="ringClass">
      <!-- 静态头像占位：用内联 SVG 画一个中性的人像，不引入图片资源与依赖 -->
      <svg class="avatar__svg" viewBox="0 0 96 96" role="img" aria-label="面试官">
        <defs>
          <linearGradient id="avatarBg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#e8eefc" />
            <stop offset="100%" stop-color="#cfdcf6" />
          </linearGradient>
        </defs>
        <circle cx="48" cy="48" r="46" fill="url(#avatarBg)" />
        <circle cx="48" cy="38" r="15" fill="#8ba3c7" />
        <path d="M18 84c4-16 16-24 30-24s26 8 30 24z" fill="#8ba3c7" />
      </svg>
    </div>
    <p class="avatar__hint">{{ speaking ? '面试官正在说…' : '面试官' }}</p>
    <VoiceWaveform
      class="avatar__wave"
      :levels="levels"
      :active="speaking"
      :current-ms="currentMs"
      :duration-ms="durationMs" />
  </div>
</template>

<style scoped lang="scss">
.avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.avatar__ring {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  padding: 3px;
  background: transparent;
  transition: box-shadow 0.25s ease, background 0.25s ease;
}

.avatar__ring--active {
  background: rgba(67, 133, 241, 0.12);
  box-shadow: 0 0 0 6px rgba(67, 133, 241, 0.16);
}

.avatar__svg {
  width: 100%;
  height: 100%;
  display: block;
}

.avatar__hint {
  margin: 0;
  font-size: 13px;
  color: #7b8290;
}

.avatar__wave {
  width: 220px;
}
</style>
