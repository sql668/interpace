<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { confirmProfileProposal, dismissProfileProposal } from '@/api/profile'
import type { ProfileProposalItem, ProfileProposalStatus } from '@/types/profile'
import { notifyError } from '@/utils/errorMessage'

const props = defineProps<{
  /** 待确认记录本体（由会话级列表接口一次取回，卡片不再自己请求） */
  proposal: ProfileProposalItem
}>()

const emit = defineEmits<{
  /** 记录被确认或忽略后触发，父组件据此刷新映射 */
  updated: [proposal: ProfileProposalItem]
}>()

const submitting = ref(false)
// 本地副本：确认 / 忽略后先就地更新，避免整页重拉
const current = ref<ProfileProposalItem>(props.proposal)

watch(
  () => props.proposal,
  (next) => {
    current.value = next
    syncForm(next)
  }
)

// 可编辑字段：默认填后端抽出来的值，用户改完再确认。
// 用逗号分隔的字符串录入列表字段，比做一堆标签输入框简单，也够用。
const form = reactive({
  target_job: '',
  years_experience: '',
  target_level: '',
  target_skills: '',
  weak_topics: ''
})

const status = computed<ProfileProposalStatus>(() => current.value.status)
const isPending = computed(() => status.value === 0)

const syncForm = (item: ProfileProposalItem) => {
  form.target_job = item.target_job ?? ''
  form.years_experience = item.years_experience ?? ''
  form.target_level = item.target_level ?? ''
  form.target_skills = item.target_skills.join('、')
  form.weak_topics = item.weak_topics.join('、')
}

syncForm(props.proposal)

/** 逗号 / 顿号 / 空格分隔都接受，去重后返回 */
const splitList = (text: string): string[] => {
  return Array.from(
    new Set(
      text
        .split(/[,，、\s]+/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  )
}

const handleConfirm = async () => {
  if (submitting.value) return
  submitting.value = true
  try {
    const result = await confirmProfileProposal(current.value.id, {
      target_job: form.target_job,
      years_experience: form.years_experience,
      target_level: form.target_level,
      target_skills: splitList(form.target_skills),
      weak_topics: splitList(form.weak_topics)
    })
    current.value = result.proposal
    ElMessage.success(result.message)
    emit('updated', result.proposal)
  } catch (error) {
    notifyError(error, '保存失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

const handleDismiss = async () => {
  if (submitting.value) return
  submitting.value = true
  try {
    const result = await dismissProfileProposal(current.value.id)
    current.value = result.proposal
    ElMessage.info(result.message)
    emit('updated', result.proposal)
  } catch (error) {
    notifyError(error, '操作失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="profile-card">
    <header class="profile-card__head">
      <span class="profile-card__title">从简历里读到的信息</span>
      <span v-if="!isPending" class="profile-card__done">
        {{ status === 1 ? '已写入画像' : '已忽略' }}
      </span>
    </header>

    <!-- 待确认：字段可改，改完再写入 -->
    <template v-if="isPending">
      <p class="profile-card__tip">
        确认后这些信息会用于后续所有问答，请核对一遍；不对的直接改或忽略。
      </p>
      <div class="profile-form">
        <label class="field">
          <span>目标岗位</span>
          <input v-model="form.target_job" type="text" placeholder="未识别" />
        </label>
        <label class="field">
          <span>工作经验</span>
          <input v-model="form.years_experience" type="text" placeholder="未识别" />
        </label>
        <label class="field">
          <span>目标级别</span>
          <input v-model="form.target_level" type="text" placeholder="初级 / 中级 / 高级" />
        </label>
        <label class="field">
          <span>技能</span>
          <input v-model="form.target_skills" type="text" placeholder="用顿号分隔" />
        </label>
        <label class="field">
          <span>薄弱点</span>
          <input v-model="form.weak_topics" type="text" placeholder="用顿号分隔" />
        </label>
      </div>
      <div class="profile-card__actions">
        <button
          type="button"
          class="action action--primary"
          :disabled="submitting"
          @click="handleConfirm">
          {{ submitting ? '保存中…' : '确认写入画像' }}
        </button>
        <button type="button" class="action" :disabled="submitting" @click="handleDismiss">
          忽略
        </button>
      </div>
    </template>

    <!-- 已处理：只读展示当前画像值 -->
    <template v-else>
      <div class="profile-view">
        <p><span class="label">目标岗位</span>{{ current.target_job || '—' }}</p>
        <p><span class="label">工作经验</span>{{ current.years_experience || '—' }}</p>
        <p><span class="label">目标级别</span>{{ current.target_level || '—' }}</p>
        <p><span class="label">技能</span>{{ current.target_skills.join('、') || '—' }}</p>
        <p><span class="label">薄弱点</span>{{ current.weak_topics.join('、') || '—' }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
.profile-card {
  margin-top: 12px;
  border: 1px solid #cfe0d6;
  border-radius: 12px;
  background: #f7fcf9;
  padding: 14px 16px;
}

.profile-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid #dcebe3;
}

.profile-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #2f7a56;
}

.profile-card__done {
  font-size: 13px;
  color: #7ba192;
}

.profile-card__tip {
  margin: 10px 0;
  font-size: 13px;
  color: #6b7d75;
  line-height: 1.6;
}

.profile-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #4a5a53;
}

.field input {
  border: 1px solid #cddfd6;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 14px;
  color: #2f3642;
  background: #fff;

  &:focus {
    outline: none;
    border-color: #2f7a56;
  }
}

.profile-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.action {
  border: 1px solid #cfe0d6;
  border-radius: 8px;
  background: #fff;
  color: #2f7a56;
  font-size: 14px;
  padding: 8px 14px;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.action--primary {
  border-color: #2f7a56;
  background: #2f7a56;
  color: #fff;
}

.profile-view p {
  margin: 6px 0;
  font-size: 14px;
  color: #2f3642;
}

.label {
  display: inline-block;
  min-width: 72px;
  color: #7ba192;
}

.hint {
  margin: 10px 0 0;
  font-size: 14px;
  color: #9ea6b4;
}
</style>
