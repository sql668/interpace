<script setup lang="ts">
/**
 * 音频波形：把音量序列渲染成一排竖条。
 *
 * 纯展示组件：数据从外面传进来（录音时传麦克风音量，播放时传 TTS 音量），
 * 自己不做任何音频处理——这样它既能当「音浪指示」也能被头像层复用。
 */
import { computed } from 'vue'

const props = defineProps<{
  /** 音量序列（0~1），越靠后越新 */
  levels: number[]
  /** 是否处于活跃状态（录音或播放） */
  active?: boolean
  /** 播放进度与总时长，用于显示时间（T7.9 口型同步也会用这份进度） */
  currentMs?: number
  durationMs?: number
}>()

/** 固定的柱数：把传入的序列补齐/截断到同样长度，避免柱子数量来回跳 */
const BAR_COUNT = 48

const bars = computed(() => {
  const padded = [...props.levels.slice(-BAR_COUNT)]
  while (padded.length < BAR_COUNT) {
    padded.unshift(0)
  }
  return padded
})

const seconds = computed(() => ((props.currentMs ?? 0) / 1000).toFixed(1))
const totalSeconds = computed(() => ((props.durationMs ?? 0) / 1000).toFixed(1))
</script>

<template>
  <div class="waveform" :class="{ 'waveform--active': active }">
    <div class="waveform__bars">
      <span
        v-for="(level, index) in bars"
        :key="index"
        class="waveform__bar"
        :style="{ height: `${Math.max(6, Math.round(level * 100))}%` }" />
    </div>
    <p v-if="durationMs" class="waveform__time">{{ seconds }}s / {{ totalSeconds }}s</p>
  </div>
</template>

<style scoped lang="scss">
.waveform {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.waveform__bars {
  width: 100%;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.waveform__bar {
  flex: 1;
  min-width: 2px;
  border-radius: 2px;
  background: #c7d3e6;
  transition: height 0.08s linear, background-color 0.2s ease;
}

.waveform--active .waveform__bar {
  background: #4385f1;
}

.waveform__time {
  margin: 0;
  font-size: 12px;
  color: #9ea6b4;
}
</style>
