<script setup lang="ts">
import { Paperclip, Promotion } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
  attach: []
}>()

const text = ref('')
const canSend = computed(() => text.value.trim().length > 0 && !props.disabled)

const onSend = () => {
  if (!canSend.value) {
    return
  }
  emit('send', text.value.trim())
  text.value = ''
}

const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    onSend()
  }
}
</script>

<template>
  <section class="chat-input">
    <el-input
      v-model="text"
      class="chat-input__field"
      type="textarea"
      resize="none"
      :rows="3"
      :disabled="disabled"
      placeholder="输入你的回答..."
      @keydown="onKeydown"
    />
    <div class="chat-input__actions">
      <el-button class="icon-btn" :disabled="disabled" @click="emit('attach')">
        <el-icon><Paperclip /></el-icon>
      </el-button>
      <el-button class="send-btn" :disabled="!canSend" @click="onSend">
        <el-icon><Promotion /></el-icon>
      </el-button>
    </div>
  </section>
</template>

<style scoped lang="scss">
.chat-input {
  position: relative;
  background: #f4f5f7;
  border-top: 1px solid #d9dce1;
  padding: 12px 0;
  display: flex;
  justify-content: center;
}

.chat-input__field {
  width: min(1040px, calc(100vw - 560px));
  min-width: 560px;
}

:deep(.el-textarea__inner) {
  min-height: 92px !important;
  border-radius: 12px;
  background: #f7f8fb;
  border: 1px solid #d3d9e2;
  padding-right: 100px;
  font-size: 16px;
  line-height: 1.6;
}

.chat-input__actions {
  position: absolute;
  width: min(1040px, calc(100vw - 560px));
  min-width: 560px;
  pointer-events: none;
  height: 92px;
}

.icon-btn,
.send-btn {
  position: absolute;
  bottom: 14px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  pointer-events: all;
}

.icon-btn {
  left: 12px;
  background: #e9ebf0;
  color: #596272;
}

.send-btn {
  right: 12px;
  background: #f6c700;
  color: #ffffff;

  &.is-disabled {
    background: #d1d5dc;
    color: #9ea6b3;
  }
}

@media (max-width: 1100px) {
  .chat-input__field,
  .chat-input__actions {
    width: calc(100vw - 130px);
    min-width: 0;
  }
}
</style>
