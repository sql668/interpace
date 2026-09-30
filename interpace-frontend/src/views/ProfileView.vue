<script setup lang="ts">
/**
 * 我的画像（T9.4）。
 *
 * 这个页面有两个作用，第二个比第一个更重要：
 * 1. 展示系统记住了什么；
 * 2. **让用户能改、能删**——记忆一旦不可见不可纠错，用户就会开始怀疑模型在乱猜。
 *    这也是 D19「记忆必须可见可删」的落点。
 *
 * 界面上**只展示四档掌握程度**，不展示 0-100 的分数：分数是内部结构，
 * 用户看到「73 分」只会纠结为什么不是 80，看到「熟悉」才知道下一步该干嘛。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, Delete, Plus } from '@element-plus/icons-vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import { tabs } from '@/constants/nav-tabs'
import {
  approveMemory,
  createMemory,
  deleteMemory,
  getProfile,
  listMemoryLogs,
  rejectMemory,
  updateMemory,
  updateProfileIntent
} from '@/api/userProfile'
import {
  CATEGORY_OPTIONS,
  MASTERY_OPTIONS,
  type MemoryCategory,
  type ProfileMemoryItem,
  type ProfileMemoryLogItem
} from '@/types/userProfile'

const router = useRouter()

const activeTab = ref('profile')
const loading = ref(false)
const savingIntent = ref(false)
const creating = ref(false)
const memories = ref<ProfileMemoryItem[]>([])
const logs = ref<ProfileMemoryLogItem[]>([])

const intent = reactive({
  target_job: '',
  years_experience: '',
  target_level: ''
})

// 新增条目的表单
const draft = reactive<{ category: MemoryCategory; name: string; mastery: number }>({
  category: 0,
  name: '',
  mastery: 70
})

// 按类别分组展示：一眼看出「系统认为我会什么、哪里弱、习惯怎么答」
const grouped = computed(() =>
  CATEGORY_OPTIONS.map((option) => ({
    ...option,
    items: memories.value.filter((item) => item.category === option.value)
  }))
)

const pendingCount = computed(
  () => memories.value.filter((item) => item.pending_approval === 1).length
)

/** 待确认的条目单独拎出来：它们是「系统猜的」，要用户点头才算数（T9.9） */
const pendingItems = computed(() =>
  memories.value.filter((item) => item.pending_approval === 1)
)

const handleTabClick = async (tabKey: string) => {
  const target = tabs.find((tab) => tab.key === tabKey)
  if (!target) return
  activeTab.value = tabKey
  await router.push(target.path)
}

const load = async () => {
  loading.value = true
  try {
    const data = await getProfile()
    intent.target_job = data.intent.target_job ?? ''
    intent.years_experience = data.intent.years_experience ?? ''
    intent.target_level = data.intent.target_level ?? ''
    memories.value = data.memories
    logs.value = await listMemoryLogs(20)
  } catch {
    ElMessage.error('画像加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const saveIntent = async () => {
  savingIntent.value = true
  try {
    const data = await updateProfileIntent({
      target_job: intent.target_job,
      years_experience: intent.years_experience,
      target_level: intent.target_level
    })
    memories.value = data.memories
    ElMessage.success('已保存，之后的回答会参考这些信息')
  } catch {
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    savingIntent.value = false
  }
}

const handleCreate = async () => {
  if (!draft.name.trim()) {
    ElMessage.warning('请填写条目名')
    return
  }
  creating.value = true
  try {
    await createMemory({
      category: draft.category,
      name: draft.name.trim(),
      mastery: draft.mastery
    })
    draft.name = ''
    await load()
    ElMessage.success('已添加')
  } catch {
    ElMessage.error('添加失败，请稍后重试')
  } finally {
    creating.value = false
  }
}

const handleMasteryChange = async (item: ProfileMemoryItem, value: number) => {
  try {
    const updated = await updateMemory(item.id, { mastery: value })
    // 就地替换，避免整页重载导致滚动位置跳动
    memories.value = memories.value.map((row) => (row.id === item.id ? updated : row))
  } catch {
    ElMessage.error('修改失败，请稍后重试')
    await load()
  }
}

const handleDelete = async (item: ProfileMemoryItem) => {
  try {
    await ElMessageBox.confirm(`确认删除「${item.name}」吗？`, '删除记忆', {
      type: 'warning'
    })
  } catch {
    return // 用户取消
  }
  try {
    await deleteMemory(item.id)
    memories.value = memories.value.filter((row) => row.id !== item.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  }
}

// 批准：这条记忆才开始影响对话（批准前它在提示词里是看不到的）
const handleApprove = async (item: ProfileMemoryItem) => {
  try {
    const updated = await approveMemory(item.id)
    memories.value = memories.value.map((row) => (row.id === item.id ? updated : row))
    ElMessage.success(`已批准「${updated.name}」，之后的回答会参考它`)
    await load()
  } catch {
    ElMessage.error('批准失败，请稍后重试')
  }
}

// 拒绝：条目会被删掉，但原文留在变更日志里可回溯
const handleReject = async (item: ProfileMemoryItem) => {
  try {
    await rejectMemory(item.id)
    memories.value = memories.value.filter((row) => row.id !== item.id)
    ElMessage.info('已拒绝，这条不会再影响回答')
    await load()
  } catch {
    ElMessage.error('拒绝失败，请稍后重试')
  }
}

onMounted(load)
</script>

<template>
  <div class="profile-page">
    <AppHeader :tabs="tabs" :active-tab="activeTab" @tab-click="handleTabClick" />

    <main class="profile-page__content">
      <header class="profile-page__title">
        <h2>我的画像</h2>
        <p>
          系统会把你在这里看到的信息带进之后的每一次回答。记错的、不想让它知道的，直接删掉。
        </p>
      </header>

      <!-- 意图类：用户想要什么 -->
      <section class="card">
        <h3 class="card__title">求职意向</h3>
        <div class="intent-grid">
          <label class="field">
            <span>目标岗位</span>
            <el-input v-model="intent.target_job" placeholder="如 Python 后端" />
          </label>
          <label class="field">
            <span>工作经验</span>
            <el-input v-model="intent.years_experience" placeholder="如 3 年" />
          </label>
          <label class="field">
            <span>目标级别</span>
            <el-input v-model="intent.target_level" placeholder="初级 / 中级 / 高级" />
          </label>
        </div>
        <div class="card__actions">
          <el-button type="primary" :loading="savingIntent" @click="saveIntent">
            保存
          </el-button>
        </div>
      </section>

      <!-- 能力类：用户会什么（逐条带来源，能解释、能改、能删） -->
      <!-- 待确认：自动抽取的记忆在批准前不影响对话，这里逐条批准或拒绝 -->
      <section v-if="pendingItems.length" class="card card--pending">
        <h3 class="card__title">
          <el-icon><Bell /></el-icon>
          待你确认（{{ pendingItems.length }} 条）
        </h3>
        <p class="pending-tip">
          这些是系统从你的答题与面试表现里**自动推断**出来的，**在你确认之前不会影响回答**。
          觉得不准就拒绝，拒绝后不会留下痕迹（原文仍可在下面的变更记录里回溯）。
        </p>
        <div v-for="item in pendingItems" :key="item.id" class="memory-row">
          <span class="memory-row__name">
            <el-tag size="small">{{ item.category_label }}</el-tag>
            {{ item.name }}
          </span>
          <span class="memory-row__mastery-text">{{ item.mastery_label }}</span>
          <span class="memory-row__source">来源：{{ item.source_label }}</span>
          <el-button size="small" type="primary" @click="handleApprove(item)">批准</el-button>
          <el-button size="small" @click="handleReject(item)">拒绝</el-button>
        </div>
      </section>

      <section class="card">
        <h3 class="card__title">
          能力与薄弱点
          <span v-if="pendingCount" class="pending-hint">
            有 {{ pendingCount }} 条待你确认（确认前不会影响回答）
          </span>
        </h3>

        <p v-if="loading" class="hint">正在加载…</p>
        <p v-else-if="!memories.length" class="hint">
          还没有记录。去做几道题、跑一场模拟面试，或者直接在这里手动添加。
        </p>

        <div v-for="group in grouped" :key="group.value" class="memory-group">
          <template v-if="group.items.length">
            <p class="memory-group__label">{{ group.label }}</p>
            <div v-for="item in group.items" :key="item.id" class="memory-row">
              <span class="memory-row__name">
                {{ item.name }}
                <el-tag v-if="item.pending_approval === 1" size="small" type="warning">
                  待确认
                </el-tag>
              </span>
              <el-select
                :model-value="item.mastery"
                size="small"
                class="memory-row__mastery"
                @change="(value: number) => handleMasteryChange(item, value)">
                <el-option
                  v-for="option in MASTERY_OPTIONS"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value" />
              </el-select>
              <!-- 来源要能说清「这条是谁说的」：你的自述 / 简历 / 答题表现 / 模型推断 -->
              <span class="memory-row__source">
                来源：{{ item.source_label }}
                <template v-if="item.evidence_count > 1">
                  · 已观察 {{ item.evidence_count }} 次
                </template>
              </span>
              <el-button
                class="memory-row__delete"
                link
                type="danger"
                :icon="Delete"
                @click="handleDelete(item)">
                删除
              </el-button>
            </div>
          </template>
        </div>

        <!-- 手动新增 -->
        <div class="create-row">
          <el-select v-model="draft.category" size="small" class="create-row__category">
            <el-option
              v-for="option in CATEGORY_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value" />
          </el-select>
          <el-input v-model="draft.name" size="small" placeholder="条目名，如 MySQL 索引优化" />
          <el-select v-model="draft.mastery" size="small" class="create-row__mastery">
            <el-option
              v-for="option in MASTERY_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value" />
          </el-select>
          <el-button type="primary" size="small" :icon="Plus" :loading="creating" @click="handleCreate">
            添加
          </el-button>
        </div>
      </section>

      <!-- 变更记录：回答「系统原来记的是什么」（T9.9） -->
      <section v-if="logs.length" class="card">
        <h3 class="card__title">变更记录</h3>
        <p class="hint">系统改过什么、原来是什么，都可以在这里核对。</p>
        <ul class="log-list">
          <li v-for="log in logs" :key="log.id" class="log-item">
            <span class="log-item__action">{{ log.action_label }}</span>
            <span class="log-item__name">[{{ log.category_label }}] {{ log.name }}</span>
            <span class="log-item__time">
              {{ new Date(log.created_at * 1000).toLocaleString('zh-CN', { hour12: false }) }}
            </span>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>

<style scoped lang="scss">
.profile-page {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.profile-page__content {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: min(960px, 100%);
  margin: 0 auto;
  box-sizing: border-box;
}

.profile-page__title h2 {
  margin: 0 0 6px;
  font-size: 22px;
}

.profile-page__title p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #6b7280;
}

.card {
  border: 1px solid #e2e6ee;
  border-radius: 12px;
  background: #fff;
  padding: 16px 20px;
}

.card__title {
  margin: 0 0 12px;
  font-size: 16px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.pending-hint {
  font-size: 13px;
  font-weight: 400;
  color: #b3641a;
}

.intent-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
}

.card__actions {
  margin-top: 14px;
}

.memory-group {
  margin-top: 10px;
}

.memory-group__label {
  margin: 0 0 6px;
  font-size: 13px;
  color: #8b93a2;
}

.memory-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #eceff5;
  font-size: 14px;
}

.memory-row__name {
  flex: 1;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  word-break: break-word;
}

.memory-row__mastery {
  width: 110px;
  flex-shrink: 0;
}

.memory-row__source {
  flex-shrink: 0;
  font-size: 12px;
  color: #9aa2b1;
}

.memory-row__delete {
  flex-shrink: 0;
}

.create-row {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #eef1f6;
}

.create-row__category {
  width: 110px;
  flex-shrink: 0;
}

.create-row__mastery {
  width: 110px;
  flex-shrink: 0;
}

.hint {
  margin: 0;
  font-size: 14px;
  color: #8b93a2;
}

.card--pending {
  border-color: #f0d6a8;
  background: #fffcf5;
}

.pending-tip {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #8a6d00;
}

.memory-row__mastery-text {
  flex-shrink: 0;
  font-size: 13px;
  color: #4b5563;
}

.log-list {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.log-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed #eceff5;
  font-size: 13px;
}

.log-item:last-child {
  border-bottom: none;
}

.log-item__action {
  flex-shrink: 0;
  color: #4385f1;
}

.log-item__name {
  flex: 1;
  color: #3c4552;
  word-break: break-word;
}

.log-item__time {
  flex-shrink: 0;
  color: #9aa2b1;
  font-size: 12px;
}
</style>
