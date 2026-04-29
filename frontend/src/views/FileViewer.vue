<template>
  <div class="file-viewer">
    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <n-spin size="large" />
      <p>Loading file information...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <n-result status="error" :title="errorTitle" :description="errorMessage">
        <template #footer>
          <n-button @click="closeTab">Back</n-button>
        </template>
      </n-result>
    </div>

    <!-- Large File State -->
    <div v-else-if="isLargeFile" class="large-file-state">
      <n-result status="info" title="Large File" :description="largeFileMessage">
        <template #icon>
          <n-icon size="64" :component="FileTrayFullOutline" />
        </template>
        <template #footer>
          <n-space>
            <n-button type="primary" @click="downloadFile">Download File</n-button>
            <n-button @click="closeTab">Back</n-button>
          </n-space>
        </template>
      </n-result>
    </div>

    <!-- Non-text File State -->
    <div v-else-if="!isTextFile" class="non-text-state">
      <n-result status="info" title="Opening File" description="The file is being opened in the browser...">
        <template #icon>
          <n-icon size="64" :component="DocumentOutline" />
        </template>
        <template #footer>
          <n-space>
            <n-button type="primary" @click="downloadFile">Download File</n-button>
            <n-button @click="closeTab">Back</n-button>
          </n-space>
        </template>
      </n-result>
    </div>

    <!-- Editor State -->
    <div v-else class="editor-state">
      <!-- Sidebar -->
      <div v-show="showSidebar" class="editor-sidebar">
        <div class="sidebar-header">
          <span>{{ isTableFile && showTablePreview ? 'Table Settings' : 'Editor Settings' }}</span>
          <n-button text size="small" @click="showSidebar = false">
            <template #icon>
              <n-icon :component="ChevronBackOutline" />
            </template>
          </n-button>
        </div>
        <div class="sidebar-content">
          <!-- Table Settings -->
          <template v-if="isTableFile && showTablePreview">
            <!-- Delimiter -->
            <div class="setting-item">
              <label>Delimiter</label>
              <n-select
                v-model:value="tableDelimiterOption"
                :options="delimiterOptions"
                size="small"
                @update:value="onDelimiterOptionChange"
              />
            </div>
            <div v-if="tableDelimiterOption === 'custom'" class="setting-item">
              <label>Custom Delimiter</label>
              <n-input
                v-model:value="tableDelimiter"
                size="small"
                placeholder="Enter delimiter"
                maxlength="4"
              />
            </div>

            <!-- First Row as Header -->
            <div class="setting-item setting-item--row">
              <label>First Row as Header</label>
              <n-switch v-model:value="useFirstRowAsHeader" size="small" />
            </div>

            <!-- Reset Sort -->
            <div v-if="svTableRef?.hasSorting" class="setting-item">
              <n-button size="small" block @click="svTableRef.resetSort()">
                Reset Sort
              </n-button>
            </div>
          </template>

          <!-- Editor Settings -->
          <template v-else>
            <!-- Theme -->
            <div class="setting-item">
              <label>Theme</label>
              <n-select
                v-model:value="editorTheme"
                :options="themeOptions"
                size="small"
                @update:value="onThemeChange"
              />
            </div>

            <!-- Font Size -->
            <div class="setting-item">
              <label>Font Size</label>
              <n-select
                v-model:value="fontSize"
                :options="fontSizeOptions"
                size="small"
                @update:value="onFontSizeChange"
              />
            </div>

            <!-- Font Family -->
            <div class="setting-item">
              <label>Font Family</label>
              <n-select
                v-model:value="fontFamily"
                :options="fontFamilyOptions"
                size="small"
                @update:value="onFontFamilyChange"
              />
            </div>

            <!-- Language -->
            <div class="setting-item">
              <label>Language</label>
              <n-select
                v-model:value="selectedLanguage"
                :options="languageOptions"
                size="small"
                filterable
                :consistent-menu-width="false"
                @update:value="onLanguageChange"
              />
            </div>
          </template>
        </div>
      </div>

      <!-- Main Content -->
      <div class="editor-main">
        <!-- Toolbar -->
        <div class="editor-toolbar">
          <div class="toolbar-left">
            <n-button v-if="!showSidebar" text size="small" class="sidebar-toggle" @click="showSidebar = true">
              <template #icon>
                <n-icon :component="SettingsOutline" />
              </template>
            </n-button>
            <div class="file-info">
              <n-icon size="20" :component="DocumentTextOutline" />
              <span class="file-name">{{ fileName }}</span>
              <n-tag size="small" type="info">{{ formatSize(fileSize) }}</n-tag>
              <n-tag v-if="isDirty" size="small" type="warning">Modified</n-tag>
            </div>
          </div>
          <div class="toolbar-actions">
            <n-button
              v-if="isMarkdown"
              size="small"
              :type="showPreview ? 'primary' : 'default'"
              @click="showPreview = !showPreview"
            >
              <template #icon>
                <n-icon :component="showPreview ? CreateOutline : EyeOutline" />
              </template>
              {{ showPreview ? 'Edit' : 'Preview' }}
            </n-button>
            <n-button
              v-if="isTableFile"
              size="small"
              :type="showTablePreview ? 'primary' : 'default'"
              @click="showTablePreview = !showTablePreview"
            >
              <template #icon>
                <n-icon :component="showTablePreview ? CreateOutline : EyeOutline" />
              </template>
              {{ showTablePreview ? 'Edit' : 'Preview' }}
            </n-button>
            <n-button size="small" @click="downloadFile">
              <template #icon>
                <n-icon :component="DownloadOutline" />
              </template>
              Download
            </n-button>
            <n-button size="small" type="primary" :loading="saving" @click="saveFile">
              <template #icon>
                <n-icon :component="SaveOutline" />
              </template>
              Save (Ctrl+S)
            </n-button>
            <n-button size="small" @click="closeTab">
              <template #icon>
                <n-icon :component="CloseOutline" />
              </template>
              Back
            </n-button>
          </div>
        </div>

        <!-- Editor / Preview -->
        <div class="editor-wrapper">
          <div
            v-if="isMarkdown && showPreview"
            class="markdown-preview"
            :class="editorTheme === 'vs-dark' || editorTheme === 'hc-black' ? 'markdown-preview--dark' : ''"
            v-html="renderedMarkdown"
          />
          <SvTablePreview
            v-else-if="isTableFile && showTablePreview"
            ref="svTableRef"
            :content="fileContent"
            :delimiter="tableDelimiter"
            :use-first-row-as-header="useFirstRowAsHeader"
          />
          <MonacoEditor
            v-else
            ref="monacoEditorRef"
            v-model="fileContent"
            :language="selectedLanguage"
            :theme="editorTheme"
            :options="editorOptions"
            @save="saveFile"
            @ready="handleEditorReady"
            @change="handleContentChange"
          />
        </div>

        <!-- Status Bar -->
        <div class="status-bar">
          <span>{{ selectedLanguage }}</span>
          <span v-if="cursorPosition">Ln {{ cursorPosition.lineNumber }}, Col {{ cursorPosition.column }}</span>
          <span v-if="isDirty" class="unsaved-indicator">● Unsaved</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NSpin, NResult, NButton, NSpace, NIcon, NTag, NSelect, NSwitch, NInput,
  createDiscreteApi
} from 'naive-ui'
import {
  DocumentOutline, DocumentTextOutline, DownloadOutline,
  SaveOutline, CloseOutline, FileTrayFullOutline,
  SettingsOutline, ChevronBackOutline, EyeOutline, CreateOutline
} from '@vicons/ionicons5'
import axios from 'axios'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import MonacoEditor from '../components/MonacoEditor.vue'
import SvTablePreview from '../components/SvTablePreview.vue'
import configStore from '../stores/config.js'

const { message } = createDiscreteApi(['message'])

// Editor theme options
const themeOptions = [
  { label: 'Dark (VS)', value: 'vs-dark' },
  { label: 'Light (VS)', value: 'vs' },
  { label: 'High Contrast Dark', value: 'hc-black' },
  { label: 'High Contrast Light', value: 'hc-light' }
]

// Font size options
const fontFamilyOptions = [
  { label: 'Monospace', value: 'monospace' },
  { label: 'Consolas', value: 'Consolas, monospace' },
  { label: 'Fira Code', value: '"Fira Code", monospace' },
  { label: 'JetBrains Mono', value: '"JetBrains Mono", monospace' },
  { label: 'Source Code Pro', value: '"Source Code Pro", monospace' },
  { label: 'Cascadia Code', value: '"Cascadia Code", monospace' },
  { label: 'Courier New', value: '"Courier New", monospace' },
  { label: 'Menlo', value: 'Menlo, monospace' },
  { label: 'SF Mono', value: '"SF Mono", monospace' },
]

const fontSizeOptions = [
  { label: '12px', value: 12 },
  { label: '13px', value: 13 },
  { label: '14px', value: 14 },
  { label: '15px', value: 15 },
  { label: '16px', value: 16 },
  { label: '18px', value: 18 },
  { label: '20px', value: 20 },
  { label: '22px', value: 22 },
  { label: '24px', value: 24 }
]

// Language options
const languageOptions = [
  { label: 'Plain Text', value: 'plaintext' },
  { label: 'Batch', value: 'bat' },
  { label: 'C', value: 'c' },
  { label: 'C++', value: 'cpp' },
  { label: 'C#', value: 'csharp' },
  { label: 'CSS', value: 'css' },
  { label: 'Dockerfile', value: 'dockerfile' },
  { label: 'Go', value: 'go' },
  { label: 'GraphQL', value: 'graphql' },
  { label: 'HTML', value: 'html' },
  { label: 'INI', value: 'ini' },
  { label: 'Java', value: 'java' },
  { label: 'JavaScript', value: 'javascript' },
  { label: 'JSON', value: 'json' },
  { label: 'Julia', value: 'julia' },
  { label: 'Kotlin', value: 'kotlin' },
  { label: 'LaTeX', value: 'latex' },
  { label: 'Less', value: 'less' },
  { label: 'Lua', value: 'lua' },
  { label: 'Makefile', value: 'makefile' },
  { label: 'Markdown', value: 'markdown' },
  { label: 'Objective-C', value: 'objective-c' },
  { label: 'Perl', value: 'perl' },
  { label: 'PHP', value: 'php' },
  { label: 'PowerShell', value: 'powershell' },
  { label: 'Python', value: 'python' },
  { label: 'R', value: 'r' },
  { label: 'Ruby', value: 'ruby' },
  { label: 'Rust', value: 'rust' },
  { label: 'SCSS', value: 'scss' },
  { label: 'Shell', value: 'shell' },
  { label: 'SQL', value: 'sql' },
  { label: 'Swift', value: 'swift' },
  { label: 'TypeScript', value: 'typescript' },
  { label: 'XML', value: 'xml' },
  { label: 'YAML', value: 'yaml' }
]

const route = useRoute()
const router = useRouter()
const getBaseUrl = () => configStore.baseUrl.value

// Props from route
const props = defineProps({
  path: {
    type: String,
    default: ''
  }
})

// State
const loading = ref(true)
const error = ref(false)
const errorTitle = ref('Error')
const errorMessage = ref('')
const fileInfo = ref(null)
const fileContent = ref('')
const originalContent = ref('')
const saving = ref(false)
const isDirty = ref(false)
const cursorPosition = ref(null)
const monacoEditorRef = ref(null)

// Markdown preview state
const showPreview = ref(false)

// Table preview state
const showTablePreview = ref(true)
const tableDelimiter = ref(',')
const tableDelimiterOption = ref('comma')
const useFirstRowAsHeader = ref(true)
const svTableRef = ref(null)

const delimiterOptions = [
  { label: 'Comma (,)', value: 'comma' },
  { label: 'Tab (\\t)', value: 'tab' },
  { label: 'Pipe (|)', value: 'pipe' },
  { label: 'Semicolon (;)', value: 'semicolon' },
  { label: 'Space', value: 'space' },
  { label: 'Custom', value: 'custom' },
]

const delimiterMap = {
  comma: ',',
  tab: '\t',
  pipe: '|',
  semicolon: ';',
  space: ' ',
}

const onDelimiterOptionChange = (val) => {
  if (val !== 'custom') {
    tableDelimiter.value = delimiterMap[val]
  }
}

// Sidebar and settings state
const showSidebar = ref(true)
const editorTheme = ref('vs')
const fontSize = ref(14)
const fontFamily = ref('monospace')
const selectedLanguage = ref('plaintext')
const isNarrowScreen = ref(false)

// Default threshold (2MB)
const DEFAULT_MAX_SIZE = 2 * 1024 * 1024

// Computed
const filePath = computed(() => {
  // Get path from props or route params
  return props.path || route.params.path || route.query.path || ''
})

const fileName = computed(() => {
  if (!fileInfo.value) return ''
  return fileInfo.value.name
})

const fileSize = computed(() => {
  if (!fileInfo.value) return 0
  return fileInfo.value.size
})

const maxFileSize = computed(() => {
  if (!fileInfo.value || !fileInfo.value.viewer_config) return DEFAULT_MAX_SIZE
  return fileInfo.value.viewer_config.max_file_size || DEFAULT_MAX_SIZE
})

const isLargeFile = computed(() => {
  return fileSize.value > maxFileSize.value
})

const isTextFile = computed(() => {
  if (!fileInfo.value) return false
  return fileInfo.value.is_text
})

const largeFileMessage = computed(() => {
  return `File size (${formatSize(fileSize.value)}) exceeds the maximum allowed size (${formatSize(maxFileSize.value)}). Please download the file instead.`
})

// 从文件名获取语言
const fileLanguage = computed(() => {
  if (!fileInfo.value) return 'plaintext'
  const ext = fileInfo.value.extension
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

// Check if current file is markdown
const isMarkdown = computed(() => {
  return selectedLanguage.value === 'markdown'
})

// Check if current file is a table file
const isTableFile = computed(() => {
  const ext = fileInfo.value?.extension
  const tableExts = fileInfo.value?.viewer_config?.table_extensions || []
  return tableExts.includes(ext)
})

// KaTeX marked extension
const katexExtension = {
  extensions: [
    {
      name: 'blockMath',
      level: 'block',
      start(src) { return src.indexOf('$$') },
      tokenizer(src) {
        const match = src.match(/^\$\$([\s\S]+?)\$\$/)
        if (match) return { type: 'blockMath', raw: match[0], math: match[1].trim() }
      },
      renderer(token) {
        return `<div class="katex-block">${katex.renderToString(token.math, { displayMode: true, throwOnError: false })}</div>\n`
      }
    },
    {
      name: 'inlineMath',
      level: 'inline',
      start(src) { return src.indexOf('$') },
      tokenizer(src) {
        const match = src.match(/^\$([^\$\n]+?)\$/)
        if (match) return { type: 'inlineMath', raw: match[0], math: match[1].trim() }
      },
      renderer(token) {
        return katex.renderToString(token.math, { displayMode: false, throwOnError: false })
      }
    }
  ]
}
marked.use(katexExtension)

// KaTeX allowed tags/attributes for DOMPurify
const KATEX_ALLOWED_TAGS = [
  'math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 'mi', 'mspace',
  'mover', 'munder', 'munderover', 'msup', 'msub', 'msubsup', 'mfrac',
  'mroot', 'msqrt', 'mtable', 'mtr', 'mtd', 'mlabeledtr', 'mrow', 'menclose',
  'mstyle', 'mpadded', 'mphantom', 'mglyph', 'svg', 'path', 'line', 'circle',
  'g', 'rect', 'use', 'defs', 'symbol', 'marker', 'clippath', 'stop',
  'lineargradient', 'radialgradient', 'mask', 'text', 'tspan', 'span', 'div'
]

// Rendered markdown HTML
const renderedMarkdown = computed(() => {
  if (!isMarkdown.value) return ''
  const html = marked.parse(fileContent.value || '')
  return DOMPurify.sanitize(html, {
    ADD_TAGS: KATEX_ALLOWED_TAGS,
    ADD_ATTR: [
      'xmlns', 'viewBox', 'width', 'height', 'preserveAspectRatio', 'x', 'y',
      'cx', 'cy', 'r', 'd', 'fill', 'stroke', 'stroke-width', 'transform',
      'clip-path', 'clip-rule', 'fill-rule', 'marker-end', 'marker-start',
      'marker-mid', 'xlink:href', 'href', 'aria-hidden', 'focusable',
      'role', 'style', 'class', 'x1', 'y1', 'x2', 'y2', 'offset',
      'stop-color', 'stop-opacity', 'gradientUnits', 'gradientTransform',
      'patternUnits', 'id', 'refx', 'refy', 'markerwidth', 'markerheight',
      'orient', 'maskcontentunits', 'maskunits', 'color', 'display',
      'dominant-baseline', 'text-anchor', 'overflow', 'font-family',
      'font-size', 'font-style', 'font-weight', 'letter-spacing',
      'stroke-dasharray', 'stroke-dashoffset', 'stroke-linecap',
      'stroke-linejoin', 'stroke-miterlimit', 'stroke-opacity', 'fill-opacity',
      'visibility', 'pointer-events', 'shape-rendering', 'rx', 'ry'
    ],
    FORCE_BODY: true
  })
})

// Editor options computed property
const editorOptions = computed(() => {
  return {
    fontSize: fontSize.value,
    fontFamily: fontFamily.value,
  }
})

// Format file size
const formatSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

// Load file information
const loadFileInfo = async () => {
  if (!filePath.value) {
    error.value = true
    errorTitle.value = 'Invalid Path'
    errorMessage.value = 'No file path specified'
    loading.value = false
    return
  }

  loading.value = true
  error.value = false

  try {
    const res = await axios.post(`${getBaseUrl()}/api/sftp/file-info`, {
      path: filePath.value
    })

    if (res.data.status === 'success') {
      fileInfo.value = res.data
      document.title = res.data.name
      selectedLanguage.value = fileLanguage.value

      // Auto-infer table delimiter from extension
      const extDelimMap = { csv: ',', tsv: '\t', psv: '|', ssv: ';' }
      const extOptMap = { csv: 'comma', tsv: 'tab', psv: 'pipe', ssv: 'semicolon' }
      const ext = res.data.extension
      if (ext in extDelimMap) {
        tableDelimiter.value = extDelimMap[ext]
        tableDelimiterOption.value = extOptMap[ext]
        showTablePreview.value = true
      }

      // Handle based on file type and size
      if (isLargeFile.value) {
        // Large file - trigger download directly and close tab
        loading.value = false
        downloadFile()
        setTimeout(() => closeTab(), 100)
        return
      }

      if (!isTextFile.value) {
        // Non-text file - redirect to download
        loading.value = false
        // Auto-redirect to download
        setTimeout(() => {
          window.location.href = `${getBaseUrl()}/api/sftp/download/${encodeURIComponent(res.data.name)}?path=${encodeURIComponent(filePath.value)}`
        }, 500)
        return
      }

      // Text file - load content
      await loadFileContent()
    } else {
      error.value = true
      errorTitle.value = 'Failed to Load File'
      errorMessage.value = res.data.message || 'Unknown error'
    }
  } catch (e) {
    error.value = true
    errorTitle.value = 'Error'
    errorMessage.value = e.message || 'Failed to load file information'
  } finally {
    loading.value = false
  }
}

// Load file content
const loadFileContent = async () => {
  try {
    const res = await axios.post(`${getBaseUrl()}/api/sftp/read`, {
      path: filePath.value
    })

    if (res.data.status === 'success') {
      if (res.data.is_binary) {
        error.value = true
        errorTitle.value = 'Binary File'
        errorMessage.value = 'Cannot display binary files in the editor'
        return
      }

      fileContent.value = res.data.content
      originalContent.value = res.data.content
      isDirty.value = false
    } else {
      error.value = true
      errorTitle.value = 'Failed to Load Content'
      errorMessage.value = res.data.message || 'Unknown error'
    }
  } catch (e) {
    error.value = true
    errorTitle.value = 'Error'
    errorMessage.value = e.message || 'Failed to load file content'
  }
}

// Handle editor ready
const handleEditorReady = (editor) => {
  // Set up cursor position tracking
  editor.onDidChangeCursorPosition((e) => {
    cursorPosition.value = {
      lineNumber: e.position.lineNumber,
      column: e.position.column
    }
  })
}

// Handle content change
const handleContentChange = () => {
  isDirty.value = fileContent.value !== originalContent.value
}

// Load editor settings (from backend first, fallback to localStorage)
const loadEditorSettings = async () => {
  await configStore.loadEditorConfig()
  const editorConfig = configStore.config.value?.editor
  if (editorConfig) {
    editorTheme.value = editorConfig.theme || 'vs'
    fontSize.value = editorConfig.fontSize || 14
    fontFamily.value = editorConfig.fontFamily || 'monospace'
  }
  selectedLanguage.value = fileLanguage.value
}

// Save editor settings to global config and backend
const saveEditorSettings = () => {
  configStore.saveEditorConfig({
    theme: editorTheme.value,
    fontSize: fontSize.value,
    fontFamily: fontFamily.value,
    language: selectedLanguage.value
  })
}

// Handle theme change
const onThemeChange = (value) => {
  editorTheme.value = value
  saveEditorSettings()
}

// Handle font size change
const onFontSizeChange = (value) => {
  fontSize.value = value
  saveEditorSettings()
}

// Handle font family change
const onFontFamilyChange = (value) => {
  fontFamily.value = value
  saveEditorSettings()
}

// Handle language change (language is session-only, not persisted)
const onLanguageChange = (value) => {
  selectedLanguage.value = value
}

// Check screen width for responsive sidebar
const checkScreenWidth = () => {
  isNarrowScreen.value = window.innerWidth < 900
  if (isNarrowScreen.value) {
    showSidebar.value = false
  }
}

// Handle keyboard shortcuts
const handleKeyDown = (event) => {
  // Ctrl+B to toggle sidebar
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
    event.preventDefault()
    showSidebar.value = !showSidebar.value
  }
}

// Save file
const saveFile = async () => {
  if (!isDirty.value) {
    message.info('No changes to save')
    return
  }

  saving.value = true
  try {
    const res = await axios.post(`${getBaseUrl()}/api/sftp/write`, {
      path: filePath.value,
      content: fileContent.value
    })

    if (res.data.status === 'success') {
      message.success('File saved successfully')
      originalContent.value = fileContent.value
      isDirty.value = false
    } else {
      message.error(res.data.message || 'Failed to save file')
    }
  } catch (e) {
    message.error(e.message || 'Failed to save file')
  } finally {
    saving.value = false
  }
}

// Download file
const downloadFile = () => {
  const url = `${getBaseUrl()}/api/sftp/download/${encodeURIComponent(res.data.name)}?path=${encodeURIComponent(filePath.value)}`
  window.location.href = url
}

// Back to file browser
const closeTab = () => {
  const currentPath = filePath.value || ''
  const lastSlash = currentPath.lastIndexOf('/')
  const parentPath = lastSlash > 0 ? currentPath.substring(0, lastSlash) : '~'
  router.push(`/files/${encodeURIComponent(parentPath)}`)
}

// Handle beforeunload - warn about unsaved changes
const handleBeforeUnload = (e) => {
  if (isDirty.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

// Watch for content changes
watch(fileContent, () => {
  handleContentChange()
})

onMounted(() => {
  loadFileInfo()
  loadEditorSettings()
  checkScreenWidth()
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('resize', checkScreenWidth)
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('resize', checkScreenWidth)
  window.removeEventListener('keydown', handleKeyDown)
})

watch(fileLanguage, (newLang) => {
  selectedLanguage.value = newLang
})
</script>

<style scoped>
.file-viewer {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.loading-state,
.error-state,
.large-file-state,
.non-text-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f5f5f5;
  color: #333;
}

.loading-state p {
  margin-top: 16px;
  font-size: 14px;
}

.editor-state {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.editor-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: #fafafa;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  color: #333;
  font-weight: 600;
  font-size: 15px;
}

.sidebar-content {
  padding: 16px;
  overflow-y: auto;
}

.setting-item {
  margin-bottom: 16px;
}

.setting-item label {
  display: block;
  color: #666;
  font-size: 12px;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-item--row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-item--row label {
  margin-bottom: 0;
}

.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sidebar-toggle {
  color: #666;
}

.sidebar-toggle:hover {
  color: #333;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #333;
}

.file-name {
  font-weight: 500;
  font-size: 14px;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.editor-wrapper {
  flex: 1;
  overflow: hidden;
}

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 16px;
  background: #e8e8e8;
  color: #333;
  font-size: 12px;
  border-top: 1px solid #d0d0d0;
}

.unsaved-indicator {
  color: #e6a23c;
  font-weight: bold;
}

/* Markdown Preview */
.markdown-preview {
  height: 100%;
  overflow-y: auto;
  padding: 32px 48px;
  background: #fff;
  color: #24292f;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  box-sizing: border-box;
}

.markdown-preview.markdown-preview--dark {
  background: #1e1e1e;
  color: #d4d4d4;
}

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3),
.markdown-preview :deep(h4),
.markdown-preview :deep(h5),
.markdown-preview :deep(h6) {
  margin-top: 24px;
  margin-bottom: 12px;
  font-weight: 600;
  line-height: 1.25;
}

.markdown-preview :deep(h1) { font-size: 2em; border-bottom: 1px solid #d0d0d0; padding-bottom: 8px; }
.markdown-preview :deep(h2) { font-size: 1.5em; border-bottom: 1px solid #d0d0d0; padding-bottom: 6px; }
.markdown-preview :deep(h3) { font-size: 1.25em; }

.markdown-preview.markdown-preview--dark :deep(h1),
.markdown-preview.markdown-preview--dark :deep(h2) {
  border-bottom-color: #444;
}

.markdown-preview :deep(p) {
  margin: 0 0 16px;
}

.markdown-preview :deep(a) {
  color: #0969da;
  text-decoration: none;
}

.markdown-preview.markdown-preview--dark :deep(a) {
  color: #58a6ff;
}

.markdown-preview :deep(code) {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 0.875em;
  padding: 2px 5px;
  background: #f0f0f0;
  border-radius: 4px;
}

.markdown-preview.markdown-preview--dark :deep(code) {
  background: #2d2d2d;
  color: #ce9178;
}

.markdown-preview :deep(pre) {
  padding: 16px;
  overflow: auto;
  background: #f6f8fa;
  border-radius: 6px;
  margin: 0 0 16px;
}

.markdown-preview :deep(pre code) {
  padding: 0;
  background: transparent;
  font-size: 0.875em;
  color: inherit;
}

.markdown-preview.markdown-preview--dark :deep(pre) {
  background: #2d2d2d;
}

.markdown-preview.markdown-preview--dark :deep(pre code) {
  color: #d4d4d4;
}

.markdown-preview :deep(blockquote) {
  margin: 0 0 16px;
  padding: 0 16px;
  border-left: 4px solid #d0d7de;
  color: #656d76;
}

.markdown-preview.markdown-preview--dark :deep(blockquote) {
  border-left-color: #444;
  color: #8b949e;
}

.markdown-preview :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 16px;
}

.markdown-preview :deep(th),
.markdown-preview :deep(td) {
  border: 1px solid #d0d7de;
  padding: 8px 12px;
}

.markdown-preview.markdown-preview--dark :deep(th),
.markdown-preview.markdown-preview--dark :deep(td) {
  border-color: #444;
}

.markdown-preview :deep(th) {
  background: #f6f8fa;
  font-weight: 600;
}

.markdown-preview.markdown-preview--dark :deep(th) {
  background: #2d2d2d;
}

.markdown-preview :deep(ul),
.markdown-preview :deep(ol) {
  margin: 0 0 16px;
  padding-left: 28px;
}

.markdown-preview :deep(li) {
  margin-bottom: 4px;
}

.markdown-preview :deep(hr) {
  border: none;
  border-top: 1px solid #d0d7de;
  margin: 24px 0;
}

.markdown-preview.markdown-preview--dark :deep(hr) {
  border-top-color: #444;
}

.markdown-preview :deep(img) {
  max-width: 100%;
  height: auto;
}
</style>
