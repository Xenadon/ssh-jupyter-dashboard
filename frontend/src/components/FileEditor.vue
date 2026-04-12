<template>
  <n-modal
    v-model:show="showModal"
    :title="`Edit: ${fileName}`"
    preset="card"
    style="width: 90vw; max-width: 1200px;"
    :mask-closable="false"
    @after-leave="handleClose"
  >
    <div class="editor-container">
      <!-- Loading Overlay -->
      <div v-if="loading" class="loading-overlay">
        <n-spin size="large" />
        <p class="loading-text">Loading file...</p>
      </div>
      <MonacoEditor
        ref="monacoEditorRef"
        v-model="fileContent"
        :language="fileLanguage"
        theme="vs"
        @save="saveFile"
        @ready="handleEditorReady"
      />
    </div>
    <template #footer>
      <n-space justify="end">
        <n-button @click="showModal = false">Cancel</n-button>
        <n-button type="primary" :loading="saving" @click="saveFile">Save (Ctrl+S)</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { NModal, NButton, NSpace, NSpin, createDiscreteApi } from 'naive-ui'
import axios from 'axios'
import MonacoEditor from './MonacoEditor.vue'
import configStore from '../stores/config.js'

const { message } = createDiscreteApi(['message'])

const getBaseUrl = () => configStore.baseUrl.value

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  filePath: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:show', 'saved'])

const showModal = ref(props.show)
const monacoEditorRef = ref(null)
const saving = ref(false)
const loading = ref(false)
const fileContent = ref('')
const originalContent = ref('')

const fileName = computed(() => {
  return props.filePath.split('/').pop() || 'Untitled'
})

// 从文件名获取语言
const fileLanguage = computed(() => {
  const ext = fileName.value.split('.').pop().toLowerCase()
  const langMap = {
    'js': 'javascript',
    'ts': 'typescript',
    'vue': 'html',
    'py': 'python',
    'java': 'java',
    'c': 'c',
    'cpp': 'cpp',
    'h': 'cpp',
    'hpp': 'cpp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'yaml': 'yaml',
    'yml': 'yaml',
    'json': 'json',
    'xml': 'xml',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'sql': 'sql',
    'md': 'markdown',
    'txt': 'plaintext',
    'log': 'plaintext',
    'conf': 'ini',
    'cfg': 'ini',
    'ini': 'ini',
    'properties': 'ini'
  }
  return langMap[ext] || 'plaintext'
})

// Watch for show prop changes
watch(() => props.show, async (newVal) => {
  showModal.value = newVal
  if (newVal && props.filePath) {
    await nextTick()
    await loadFile()
  }
})

// Watch for internal show changes
watch(showModal, (newVal) => {
  emit('update:show', newVal)
})

// 编辑器就绪处理
const handleEditorReady = () => {
  // 编辑器已就绪
}

// Load file content
const loadFile = async () => {
  if (!props.filePath) return

  loading.value = true
  try {
    const res = await axios.post(`${getBaseUrl()}/api/sftp/read`, {
      path: props.filePath
    })

    if (res.data.status === 'success') {
      if (res.data.is_binary) {
        message.error('Cannot edit binary files')
        showModal.value = false
        return
      }

      fileContent.value = res.data.content
      originalContent.value = res.data.content
    } else {
      message.error(res.data.message)
      showModal.value = false
    }
  } catch (e) {
    message.error('Failed to load file')
    showModal.value = false
  } finally {
    loading.value = false
  }
}

// Save file
const saveFile = async () => {
  const content = fileContent.value
  if (content === originalContent.value) {
    message.info('No changes to save')
    showModal.value = false
    return
  }

  saving.value = true
  try {
    const res = await axios.post(`${getBaseUrl()}/api/sftp/write`, {
      path: props.filePath,
      content: content
    })

    if (res.data.status === 'success') {
      message.success('File saved')
      originalContent.value = content
      emit('saved')
      showModal.value = false
    } else {
      message.error(res.data.message)
    }
  } catch (e) {
    message.error('Failed to save file')
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  fileContent.value = ''
  originalContent.value = ''
}

onUnmounted(() => {
  fileContent.value = ''
  originalContent.value = ''
})
</script>

<style scoped>
.editor-container {
  height: 60vh;
  min-height: 400px;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.loading-text {
  color: #666;
  margin-top: 16px;
  font-size: 14px;
}
</style>
