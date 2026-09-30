<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { downloadResumeWord } from '@/api/resume'

const props = defineProps<{
  /** 包含「优化后的简历」的助手消息 ID */
  messageId: number
}>()

const downloading = ref(false)

const handleDownload = async () => {
  if (downloading.value) return
  downloading.value = true
  try {
    const fileName = await downloadResumeWord(props.messageId)
    ElMessage.success(`已导出 ${fileName}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导出失败，请稍后重试')
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <button type="button" class="resume-download" :disabled="downloading" @click="handleDownload">
    <el-icon><Download /></el-icon>
    {{ downloading ? '导出中…' : '下载 Word' }}
  </button>
</template>

<style scoped lang="scss">
.resume-download {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #cfd8e6;
  border-radius: 8px;
  background: #f7f9fc;
  color: #2f4660;
  font-size: 14px;
  padding: 8px 12px;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
