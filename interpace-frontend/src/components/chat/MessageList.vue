<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MessageBubble from './MessageBubble.vue'
import type { UiMessage } from '@/types/chat'

const props = defineProps<{
  messages: UiMessage[]
  hasMore?: boolean
  loadingMore?: boolean
}>()

const emit = defineEmits<{
  loadMore: []
  openInterview: [interviewId: number]
}>()

const listRef = ref<HTMLElement | null>(null)
// 顶部加载更多时记录滚动位置，等数据插入后做高度补偿，避免列表“跳动”。
const pendingTopCompensation = ref<{ scrollTop: number; scrollHeight: number } | null>(null)
const requestedDuringLoading = ref(false)
// 是否跟随最新消息：用户主动上滑查看历史后置为 false，流式输出不再把列表拽回底部。
const stickToBottom = ref(true)

// 距离底部多少像素以内算“仍在底部”，留一点容差避免像素误差导致跟随失效。
const NEAR_BOTTOM_OFFSET = 80

// 最后一条消息的文本长度：流式输出只改文本、不改数量，需要单独监听它才能跟随滚动。
const lastMessageLength = computed(() => {
  const last = props.messages[props.messages.length - 1]
  return last ? last.text.length : 0
})

const scrollToBottom = () => {
  if (!listRef.value) {
    return
  }
  listRef.value.scrollTop = listRef.value.scrollHeight
}

const isNearBottom = (el: HTMLElement) =>
  el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_OFFSET

const onScroll = () => {
  if (!listRef.value) {
    return
  }
  // 记录用户的浏览位置，决定后续流式增量是否继续跟随
  stickToBottom.value = isNearBottom(listRef.value)
  if (!props.hasMore || props.loadingMore) {
    return
  }
  // 距离顶部 100px 触发上拉分页；loading 锁由 props.loadingMore 控制。
  if (listRef.value.scrollTop > 100 || requestedDuringLoading.value) {
    return
  }
  pendingTopCompensation.value = {
    scrollTop: listRef.value.scrollTop,
    scrollHeight: listRef.value.scrollHeight
  }
  requestedDuringLoading.value = true
  emit('loadMore')
}

watch(
  () => props.messages.length,
  async () => {
    if (props.loadingMore) {
      return
    }
    await nextTick()
    if (pendingTopCompensation.value && listRef.value) {
      const { scrollTop, scrollHeight } = pendingTopCompensation.value
      // 插入旧消息后恢复视觉位置：新高度 - 旧高度 = 需要补偿的偏移。
      const delta = listRef.value.scrollHeight - scrollHeight
      listRef.value.scrollTop = scrollTop + delta
      pendingTopCompensation.value = null
      requestedDuringLoading.value = false
      return
    }
    // 消息数量变化视为“有新内容”（发送、切换会话），强制回到最新位置。
    stickToBottom.value = true
    scrollToBottom()
  },
  { immediate: true }
)

// 流式输出：文本长度增长时，仅在用户仍停留在底部附近的情况下跟随滚动。
watch(lastMessageLength, async () => {
  if (!stickToBottom.value || props.loadingMore) {
    return
  }
  await nextTick()
  scrollToBottom()
})
</script>

<template>
  <section ref="listRef" class="message-list" @scroll="onScroll">
    <div class="message-list__inner">
      <p v-if="props.loadingMore" class="loading-hint">正在加载更多消息...</p>
      <MessageBubble
        v-for="message in props.messages"
        :key="message.id"
        :message="message"
        @open-interview="emit('openInterview', $event)"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.message-list {
  flex: 1;
  overflow: auto;
  padding: 26px 24px 20px;
  background: #f0ece2;
}

.message-list__inner {
  width: min(1040px, 100%);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #7b8290;
}
</style>
