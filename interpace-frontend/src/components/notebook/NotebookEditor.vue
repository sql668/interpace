<script setup lang="ts">
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import type { IDomEditor, IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import { computed, onBeforeUnmount, shallowRef } from 'vue'

const props = defineProps<{
  title: string
  content: string
}>()

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
      <el-input v-model="noteTitle" class="title-input" placeholder="请输入笔记标题" />
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

.title-input {
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
