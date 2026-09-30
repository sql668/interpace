<script setup lang="ts">
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import type { IDomEditor, IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import { computed, onBeforeUnmount, shallowRef } from 'vue'

const props = defineProps<{
  title: string
  content: string
  /** 保存状态提示文案（由页面根据自动保存状态映射而来），为空则不显示 */
  statusText?: string
}>()

const TITLE_PLACEHOLDER = '请输入笔记标题'

const emit = defineEmits<{
  updateTitle: [value: string]
  updateContent: [value: string]
}>()

const editorRef = shallowRef<IDomEditor>()

const toolbarConfig: Partial<IToolbarConfig> = {
  excludeKeys: ['fullScreen']
}

const editorConfig: Partial<IEditorConfig> = {
  placeholder: '请输入笔记内容...'
}

const noteTitle = computed({
  get: () => props.title,
  set: (value: string) => emit('updateTitle', value)
})

onBeforeUnmount(() => {
  editorRef.value?.destroy()
})

const handleEditorCreated = (editor: IDomEditor) => {
  editorRef.value = editor
}

const handleEditorChange = (editor: IDomEditor) => {
  emit('updateContent', editor.getHtml())
}
</script>

<template>
  <section class="notebook-editor">
    <div class="editor-card">
      <Toolbar
        class="editor-toolbar"
        :editor="editorRef"
        :default-config="toolbarConfig"
        mode="default"
      />
      <!-- 标题占满整行，与下方正文区对齐；保存状态放在输入框内部右端，
           既归属于标题区域，又不会飘在空白处 -->
      <el-input v-model="noteTitle" class="title-input" :placeholder="TITLE_PLACEHOLDER">
        <template #suffix>
          <span v-if="statusText" class="save-hint">{{ statusText }}</span>
        </template>
      </el-input>
      <Editor
        class="editor-content"
        :model-value="content"
        :default-config="editorConfig"
        mode="default"
        @on-created="handleEditorCreated"
        @on-change="handleEditorChange"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.notebook-editor {
  flex: 1;
  min-width: 0;
  background: #f1ece3;
  padding: 24px 26px;
}

.editor-card {
  width: min(1080px, 100%);
  margin: 0 auto;
  background: #f5f5f6;
  border: 1px solid #e1e3e8;
  border-radius: 12px;
  padding: 22px 20px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}

.editor-toolbar {
  border: 1px solid #d8dbe2;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
}

.save-hint {
  flex-shrink: 0;
  color: #9ea6b4;
  font-size: 13px;
  white-space: nowrap;
}

.title-input {
  width: 100%;

  :deep(.el-input__wrapper) {
    border-radius: 0;
    box-shadow: 0 0 0 1px #d8dbe2 inset;
  }

  :deep(.el-input__inner) {
    height: 52px;
    font-size: 28px;
    font-weight: 600;
  }
}

.editor-content {
  min-height: 440px;
  max-height: calc(100vh - 280px);
  overflow-y: auto;
  border: 1px solid #d8dbe2;
  border-radius: 0 0 10px 10px;
  background: #ffffff;
  font-size: 18px;
  line-height: 1.8;
}
</style>
