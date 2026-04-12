<template>
  <div ref="editorRef" class="monaco-editor-container"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api'

// 导入 Monaco 语言支持
import 'monaco-editor/esm/vs/language/typescript/monaco.contribution'
import 'monaco-editor/esm/vs/language/json/monaco.contribution'
import 'monaco-editor/esm/vs/language/html/monaco.contribution'
import 'monaco-editor/esm/vs/language/css/monaco.contribution'
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution'
import 'monaco-editor/esm/vs/basic-languages/shell/shell.contribution'
import 'monaco-editor/esm/vs/basic-languages/yaml/yaml.contribution'
import 'monaco-editor/esm/vs/basic-languages/ini/ini.contribution'
import 'monaco-editor/esm/vs/basic-languages/markdown/markdown.contribution'
import 'monaco-editor/esm/vs/basic-languages/sql/sql.contribution'
import 'monaco-editor/esm/vs/basic-languages/java/java.contribution'
import 'monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution'
import 'monaco-editor/esm/vs/basic-languages/go/go.contribution'
import 'monaco-editor/esm/vs/basic-languages/rust/rust.contribution'
import 'monaco-editor/esm/vs/basic-languages/ruby/ruby.contribution'
import 'monaco-editor/esm/vs/basic-languages/php/php.contribution'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  language: {
    type: String,
    default: 'plaintext'
  },
  theme: {
    type: String,
    default: 'vs'
  },
  readOnly: {
    type: Boolean,
    default: false
  },
  options: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue', 'save', 'ready', 'change'])

const editorRef = ref(null)
let editor = null
let isInternalChange = false

// 从文件名获取语言
const getLanguageFromFilename = (filename) => {
  if (!filename) return 'plaintext'
  const ext = filename.split('.').pop().toLowerCase()
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
}

// 初始化编辑器
const initEditor = async () => {
  if (!editorRef.value) return

  const defaultOptions = {
    value: props.modelValue,
    language: props.language,
    theme: props.theme,
    automaticLayout: true,
    minimap: { enabled: true },
    scrollBeyondLastLine: false,
    fontSize: 14,
    fontFamily: 'Consolas, "Courier New", monospace',
    lineNumbers: 'on',
    roundedSelection: false,
    padding: { top: 16, bottom: 16 },
    readOnly: props.readOnly,
    ...props.options
  }

  editor = monaco.editor.create(editorRef.value, defaultOptions)

  // 监听内容变化
  editor.onDidChangeModelContent(() => {
    if (!isInternalChange) {
      const value = editor.getValue()
      emit('update:modelValue', value)
      emit('change', value)
    }
  })

  // 添加快捷键
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    emit('save', editor.getValue())
  })

  // 通知父组件编辑器已就绪
  emit('ready', editor)
}

// 设置编辑器值
const setValue = (value) => {
  if (editor) {
    isInternalChange = true
    editor.setValue(value)
    isInternalChange = false
  }
}

// 获取编辑器值
const getValue = () => {
  return editor ? editor.getValue() : ''
}

// 设置语言
const setLanguage = (language) => {
  if (editor) {
    const model = editor.getModel()
    if (model) {
      monaco.editor.setModelLanguage(model, language)
    }
  }
}

// 设置主题
const setTheme = (theme) => {
  monaco.editor.setTheme(theme)
}

// 聚焦编辑器
const focus = () => {
  if (editor) {
    editor.focus()
  }
}

// 监听 modelValue 变化
watch(() => props.modelValue, (newValue) => {
  if (editor && newValue !== editor.getValue()) {
    setValue(newValue)
  }
})

// 监听语言变化
watch(() => props.language, (newLanguage) => {
  setLanguage(newLanguage)
})

// 监听主题变化
watch(() => props.theme, (newTheme) => {
  setTheme(newTheme)
})

// 监听 readOnly 变化
watch(() => props.readOnly, (newReadOnly) => {
  if (editor) {
    editor.updateOptions({ readOnly: newReadOnly })
  }
})

// 监听 options 变化
watch(() => props.options, (newOptions) => {
  if (editor && newOptions) {
    editor.updateOptions(newOptions)
  }
}, { deep: true })

onMounted(() => {
  nextTick(() => {
    initEditor()
  })
})

onUnmounted(() => {
  if (editor) {
    editor.dispose()
    editor = null
  }
})

// 暴露方法给父组件
defineExpose({
  editor,
  setValue,
  getValue,
  setLanguage,
  setTheme,
  focus
})
</script>

<style scoped>
.monaco-editor-container {
  width: 100%;
  height: 100%;
}
</style>
