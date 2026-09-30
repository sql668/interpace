<script setup lang="ts">
import type { ChatMode } from '@/constants/chat-modes'

const props = defineProps<{
  /** 可选的模式列表，由各房间按自己的会话类型提供 */
  modes: ChatMode[]
  /** 当前选中的 select_model */
  modelValue: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const handleSelect = (value: number) => {
  // 生成中不允许切换模式，避免一次回答对应两个模式。
  if (props.disabled || value === props.modelValue) {
    return
  }
  emit('update:modelValue', value)
}
</script>

<template>
  <div class="mode-selector">
    <button
      v-for="mode in modes"
      :key="mode.value"
      type="button"
      class="mode-chip"
      :class="{ 'mode-chip--active': mode.value === modelValue }"
      :disabled="disabled"
      @click="handleSelect(mode.value)">
      {{ mode.label }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.mode-selector {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.mode-chip {
  border: 1px solid #d3d9e2;
  border-radius: 999px;
  background: #f7f8fb;
  color: #4d5563;
  font-size: 14px;
  line-height: 1;
  padding: 8px 16px;
  cursor: pointer;
  transition:
    background-color 0.15s,
    border-color 0.15s,
    color 0.15s;

  &:hover:not(:disabled) {
    border-color: #f6c700;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}

.mode-chip--active {
  background: #fff6d6;
  border-color: #f6c700;
  color: #7a5b00;
  font-weight: 600;
}
</style>
