<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import HistoryList from '@/components/history/HistoryList.vue'

type SessionItem = {
  id: number | string
  title: string
}

defineProps<{
  sessions: SessionItem[]
  activeSessionId: number | string
}>()

const emit = defineEmits<{
  createSession: []
  sessionClick: [id: number | string]
  editSession: [id: number | string]
  removeSession: [id: number | string]
}>()
</script>

<template>
  <aside class="side-bar">
    <!-- 侧栏只负责触发事件，具体业务由各页面视图处理。 -->
    <el-button class="create-btn" @click="emit('createSession')">
      <el-icon><Plus /></el-icon>
      新建会话
    </el-button>
    <p class="section-title">历史会话</p>
    <HistoryList
      :sessions="sessions"
      :active-session-id="activeSessionId"
      @session-click="emit('sessionClick', $event)"
      @edit-session="emit('editSession', $event)"
      @remove-session="emit('removeSession', $event)"
    />
  </aside>
</template>

<style scoped lang="scss">
.side-bar {
  width: 320px;
  border-right: 1px solid #d9d9d9;
  background-color: #f5f6f7;
  padding: 18px 16px 22px 16px;
  display: flex;
  flex-direction: column;
}

.create-btn {
  width: 100%;
  height: 48px;
  border: none;
  border-radius: 6px;
  background: #f5c709;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin-top: 4px;
  margin-bottom: 20px;
}

.section-title {
  color: #4d525a;
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 14px;
}
</style>
