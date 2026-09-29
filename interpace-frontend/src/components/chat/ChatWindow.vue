<script setup lang="ts">
import ChatInput from './ChatInput.vue'
import MessageList from './MessageList.vue'
import type { UiMessage } from '@/types/chat'

defineProps<{
  messages: UiMessage[]
  hasMore?: boolean
  loadingMore?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
  attach: []
  loadMore: []
  openInterview: [interviewId: number]
}>()
</script>

<template>
  <main class="chat-window">
    <MessageList
      :messages="messages"
      :has-more="hasMore"
      :loading-more="loadingMore"
      @load-more="emit('loadMore')"
      @open-interview="emit('openInterview', $event)"
    />
    <ChatInput :disabled="disabled" @send="emit('send', $event)" @attach="emit('attach')" />
  </main>
</template>

<style scoped lang="scss">
.chat-window {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
</style>
