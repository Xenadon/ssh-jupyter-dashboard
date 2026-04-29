<template>
  <div class="file-browser" tabindex="0" @keydown="handleKeyDown">
    <!-- Breadcrumb Navigation -->
    <div class="breadcrumb-bar" @dblclick="startPathEdit">
      <!-- Breadcrumb Display -->
      <n-breadcrumb v-if="!isEditingPath">
        <n-breadcrumb-item
          v-for="(crumb, index) in displayBreadcrumbs"
          :key="index"
          :style="crumb.collapsed ? { cursor: 'default', pointerEvents: 'none' } : {}"
          @click="!crumb.collapsed && navigateTo(crumb.path)"
        >
          {{ crumb.name }}
        </n-breadcrumb-item>
      </n-breadcrumb>
      <!-- Path Input (shown when editing) -->
      <n-input
        v-else
        ref="pathInputRef"
        v-model:value="editingPath"
        size="small"
        placeholder="Enter path..."
        @keydown.enter="confirmPathEdit"
        @keydown.esc="cancelPathEdit"
        @blur="cancelPathEdit"
      />
      <div class="view-controls">
        <n-button-group>
          <n-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'">
            <template #icon>
              <n-icon><list-outline /></n-icon>
            </template>
          </n-button>
          <n-button :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'">
            <template #icon>
              <n-icon><grid-outline /></n-icon>
            </template>
          </n-button>
        </n-button-group>
        <n-button @click="refresh" :loading="loading">
          <template #icon>
            <n-icon><refresh-outline /></n-icon>
          </template>
        </n-button>
      </div>
    </div>

    <!-- File List/Grid -->
    <div
      class="file-content"
      :class="viewMode"
      @click="clearSelection"
      @dragover.prevent="handleDragOver"
      @drop.prevent="handleDrop"
      @contextmenu.prevent="handleEmptyContextMenu($event)"
    >
      <div
        v-if="loading"
        class="loading-state"
      >
        <n-spin size="large" />
        <p>Loading...</p>
      </div>

      <div
        v-else-if="items.length === 0"
        class="empty-state"
      >
        <n-empty description="Empty directory" />
      </div>

      <template v-else>
        <!-- List View -->
        <template v-if="viewMode === 'list'">
          <div class="list-header">
            <div class="col-name sortable" @click="toggleSort('name')">
              <span>Name</span>
              <n-icon v-if="sortField === 'name'" size="14" class="sort-icon">
                <caret-up-outline v-if="sortDirection === 'asc'" />
                <caret-down-outline v-else />
              </n-icon>
            </div>
            <div class="col-size sortable" @click="toggleSort('size')">
              <span>Size</span>
              <n-icon v-if="sortField === 'size'" size="14" class="sort-icon">
                <caret-up-outline v-if="sortDirection === 'asc'" />
                <caret-down-outline v-else />
              </n-icon>
            </div>
            <div class="col-date sortable" @click="toggleSort('modified')">
              <span>Modified</span>
              <n-icon v-if="sortField === 'modified'" size="14" class="sort-icon">
                <caret-up-outline v-if="sortDirection === 'asc'" />
                <caret-down-outline v-else />
              </n-icon>
            </div>
            <div class="col-perm">Permissions</div>
          </div>
          <div
            v-for="item in sortedItems"
            :key="item.path"
            class="file-item list-item"
            :data-path="item.path"
            :class="{ selected: selectedItems.has(item.path), directory: item.type === 'directory' }"
            @click.stop="handleItemClick(item, $event)"
            @dblclick.stop="handleItemDblClick(item)"
            @contextmenu.prevent="handleContextMenu(item, $event)"
            draggable="true"
            @dragstart="handleDragStart(item, $event)"
            @dragover.prevent="handleItemDragOver(item, $event)"
            @drop.prevent="handleItemDrop(item, $event)"
          >
            <div class="col-name">
              <n-icon size="20" :class="item.type">
                <folder-outline v-if="item.type === 'directory'" />
                <document-outline v-else-if="item.type === 'file'" />
                <return-down-back-outline v-else-if="item.type === 'symlink'" />
              </n-icon>
              <span class="item-name">{{ item.name }}</span>
              <span v-if="item.type === 'symlink' && item.target_type === 'broken'" class="symlink-broken" title="Broken symlink">!</span>
            </div>
            <div class="col-size">{{ formatSize(item.size) }}</div>
            <div class="col-date">{{ formatDate(item.modified) }}</div>
            <div class="col-perm">{{ item.permissions }}</div>
          </div>
        </template>

        <!-- Grid View -->
        <template v-else>
          <div
            v-for="item in items"
            :key="item.path"
            class="file-item grid-item"
            :data-path="item.path"
            :class="{ selected: selectedItems.has(item.path), directory: item.type === 'directory' }"
            @click.stop="handleItemClick(item, $event)"
            @dblclick.stop="handleItemDblClick(item)"
            @contextmenu.prevent="handleContextMenu(item, $event)"
            draggable="true"
            @dragstart="handleDragStart(item, $event)"
            @dragover.prevent="handleItemDragOver(item, $event)"
            @drop.prevent="handleItemDrop(item, $event)"
          >
            <n-icon size="48" :class="item.type">
              <folder-outline v-if="item.type === 'directory'" />
              <document-outline v-else-if="item.type === 'file'" />
              <return-down-back-outline v-else-if="item.type === 'symlink'" />
            </n-icon>
            <span class="item-name" :title="item.name">{{ item.name }}</span>
            <span class="item-size">{{ formatSize(item.size) }}</span>
          </div>
        </template>
      </template>
    </div>

    <!-- Status Bar -->
    <div class="status-bar">
      <span>{{ selectedItems.size }} selected</span>
      <span>{{ items.length }} items</span>
    </div>

    <!-- Context Menu -->
    <n-dropdown
      :show="showContextMenu"
      :options="contextMenuOptions"
      :x="contextMenuX"
      :y="contextMenuY"
      @select="handleContextMenuSelect"
      @clickoutside="showContextMenu = false"
    />

    <!-- File Editor Modal -->
    <file-editor
      v-model:show="showEditor"
      :file-path="editingFile"
      @saved="refresh"
    />

    <!-- Conflict Dialog -->
    <n-modal
      v-model:show="showConflictDialog"
      title="File Conflict"
      preset="dialog"
      positive-text="Overwrite"
      negative-text="Skip"
      @positive-click="handleConflictOverwrite"
      @negative-click="handleConflictSkip"
    >
      <p>{{ conflictMessage }}</p>
      <n-checkbox v-model:checked="applyToAll">
        Apply to all conflicts
      </n-checkbox>
    </n-modal>

    <!-- New Folder Dialog -->
    <n-modal
      v-model:show="showNewFolderDialog"
      title="New Folder"
      preset="dialog"
      positive-text="Create"
      negative-text="Cancel"
      @positive-click="createNewFolder"
    >
      <n-input v-model:value="newFolderName" placeholder="Folder name" />
    </n-modal>

    <!-- New File Dialog -->
    <n-modal
      v-model:show="showNewFileDialog"
      title="New File"
      preset="dialog"
      positive-text="Create"
      negative-text="Cancel"
      @positive-click="createNewFile"
    >
      <n-input v-model:value="newFileName" placeholder="File name" />
    </n-modal>

    <!-- Rename Dialog -->
    <n-modal
      v-model:show="showRenameDialog"
      title="Rename"
      preset="dialog"
      positive-text="Rename"
      negative-text="Cancel"
      @positive-click="confirmRename"
    >
      <n-input v-model:value="renameValue" placeholder="New name" />
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch, nextTick } from 'vue'
import {
  NButton, NButtonGroup, NBreadcrumb, NBreadcrumbItem, NIcon, NSpin,
  NEmpty, NDropdown, NModal, NInput, NCheckbox, createDiscreteApi
} from 'naive-ui'
import {
  FolderOutline, DocumentOutline, ListOutline, GridOutline,
  RefreshOutline, CaretUpOutline, CaretDownOutline, ReturnDownBackOutline
} from '@vicons/ionicons5'
import axios from 'axios'
import FileEditor from '../components/FileEditor.vue'
import configStore from '../stores/config.js'

const { message, dialog } = createDiscreteApi(['message', 'dialog'])

const connected = inject('connected')

// Emits
const emit = defineEmits(['path-changed'])

// Get base URL for API
const getBaseUrl = () => configStore.baseUrl.value

// Props
const props = defineProps({
  path: {
    type: String,
    default: '~'
  }
})

// State
const loading = ref(false)
const items = ref([])
const viewMode = ref('list') // 'list' or 'grid'
const selectedItems = ref(new Set())
const currentPath = ref('~')

// Directory content cache (path -> items[])
const dirCache = new Map()

// Sorting state
const sortField = ref('name') // 'name', 'size', 'modified'
const sortDirection = ref('asc') // 'asc' or 'desc'

// Sorted items computed property
const sortedItems = computed(() => {
  const sorted = [...items.value]

  // Always keep '..' at the top if it exists
  const parentDir = sorted.find(item => item.name === '..')
  const regularItems = sorted.filter(item => item.name !== '..')

  // Separate directories (including dir-symlinks) and files
  const directories = regularItems.filter(item => item.type === 'directory' || (item.type === 'symlink' && item.target_type === 'directory'))
  const files = regularItems.filter(item => item.type !== 'directory' && !(item.type === 'symlink' && item.target_type === 'directory'))

  // Sort function for items
  const sortItems = (a, b) => {
    let comparison = 0

    switch (sortField.value) {
      case 'name':
        comparison = a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
        break
      case 'size':
        comparison = (a.size || 0) - (b.size || 0)
        break
      case 'modified':
        comparison = (a.modified || 0) - (b.modified || 0)
        break
    }

    return sortDirection.value === 'asc' ? comparison : -comparison
  }

  // Sort directories and files separately
  directories.sort(sortItems)
  files.sort(sortItems)

  // Combine: parent dir (..) -> directories -> files
  const result = []
  if (parentDir) result.push(parentDir)
  result.push(...directories)
  result.push(...files)

  return result
})

// Request cancellation
let currentRequestController = null
let currentRequestPath = null

// Clipboard for copy/cut/paste
const clipboard = ref({
  items: [],
  operation: null // 'copy' or 'cut'
})

// Context menu
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuTarget = ref(null)

// Dialogs
const showEditor = ref(false)
const editingFile = ref('')
const showConflictDialog = ref(false)
const conflictMessage = ref('')
const applyToAll = ref(false)
const showNewFolderDialog = ref(false)
const newFolderName = ref('')
const showNewFileDialog = ref(false)
const newFileName = ref('')
const showRenameDialog = ref(false)
const renameValue = ref('')
const renameTarget = ref(null)

// Undo/Redo stack
const historyStack = ref([])
const historyIndex = ref(-1)

// Prefix search for character keys
const searchBuffer = ref('')
let searchTimeout = null
const SEARCH_TIMEOUT_MS = 500

// Path editing
const isEditingPath = ref(false)
const editingPath = ref('')
const pathInputRef = ref(null)

// Start path editing
const startPathEdit = () => {
  editingPath.value = currentPath.value
  isEditingPath.value = true
  // Focus input on next tick
  setTimeout(() => {
    pathInputRef.value?.focus()
  }, 0)
}

// Confirm path edit
const confirmPathEdit = () => {
  if (editingPath.value && editingPath.value !== currentPath.value) {
    navigateTo(editingPath.value)
  }
  isEditingPath.value = false
}

// Cancel path edit
const cancelPathEdit = () => {
  isEditingPath.value = false
  editingPath.value = ''
}

// Breadcrumbs
const breadcrumbs = computed(() => {
  const path = currentPath.value

  // 根目录 /
  if (path === '/') {
    return [{ name: 'Root', path: '/' }]
  }

  // 绝对路径（以 / 开头）
  if (path.startsWith('/')) {
    const parts = path.slice(1).split('/').filter(p => p)
    const crumbs = [{ name: 'Root', path: '/' }]
    let buildPath = ''
    parts.forEach(part => {
      buildPath += '/' + part
      crumbs.push({ name: part, path: buildPath })
    })
    return crumbs
  }

  // 相对路径（以 ~ 或 $ 开头，或普通相对路径）
  const parts = path.split('/').filter(p => p)
  const firstPart = parts[0] || ''

  // 确定起始面包屑
  let crumbs = []
  let buildPath = ''

  if (firstPart.startsWith('~')) {
    crumbs = [{ name: 'Home (~)', path: '~' }]
    // 如果有 ~ 后面的部分，如 ~/subdir
    if (path.includes('/')) {
      const subParts = path.slice(firstPart.length + 1).split('/').filter(p => p)
      subParts.forEach(part => {
        buildPath += '/' + part
        crumbs.push({ name: part, path: firstPart + buildPath })
      })
    }
  } else if (firstPart.startsWith('$')) {
    // 环境变量路径如 $SCRATCH/subdir
    crumbs = [{ name: firstPart, path: firstPart }]
    if (parts.length > 1) {
      parts.slice(1).forEach(part => {
        buildPath += '/' + part
        crumbs.push({ name: part, path: firstPart + buildPath })
      })
    }
  } else {
    // 普通相对路径
    crumbs = [{ name: 'Home', path: '~' }]
    parts.forEach(part => {
      buildPath += (buildPath ? '/' : '') + part
      crumbs.push({ name: part, path: buildPath })
    })
  }

  return crumbs
})

const displayBreadcrumbs = computed(() => {
  const crumbs = breadcrumbs.value
  if (crumbs.length <= 8) return crumbs
  // 层次 > 8 时，将第2-5级（索引1-4）合并为 "..."
  return [
    crumbs[0],
    { name: '...', path: null, collapsed: true },
    ...crumbs.slice(5)
  ]
})

// Check if any file is selected or targeted
const hasSelectedOrTargeted = computed(() => {
  return selectedItems.value.size > 0 || contextMenuTarget.value !== null
})

// Context menu options
const contextMenuOptions = computed(() => {
  const hasSelection = hasSelectedOrTargeted.value

  const options = [
    { label: 'Open', key: 'open', disabled: !hasSelection },
    { label: 'Download', key: 'download', disabled: !hasSelection },
    { type: 'divider' },
    { label: 'Copy', key: 'copy', disabled: !hasSelection },
    { label: 'Cut', key: 'cut', disabled: !hasSelection },
    { label: 'Paste', key: 'paste', disabled: clipboard.value.items.length === 0 },
    { type: 'divider' },
    { label: 'Rename', key: 'rename', disabled: !hasSelection },
    { label: 'Delete', key: 'delete', disabled: !hasSelection },
    { type: 'divider' },
    { label: 'Copy Current Path', key: 'copy_path' },
    { label: 'Copy Target Path', key: 'copy_target_path', disabled: !hasSelection }
  ]

  // Add "New File" and "New Folder" when right-clicking on empty area
  if (!contextMenuTarget.value) {
    options.unshift(
      { label: 'New File', key: 'new_file' },
      { label: 'New Folder', key: 'new_folder' },
      { type: 'divider' }
    )
  } else {
    // Add Duplicate option for files/directories (after Rename)
    const renameIndex = options.findIndex(o => o.key === 'rename')
    if (renameIndex !== -1) {
      options.splice(renameIndex, 0, { label: 'Duplicate', key: 'duplicate', disabled: !hasSelection })
    }
  }

  return options
})

// Load directory contents
const loadDirectory = async (path, { forceRefresh = false } = {}) => {
  if (!connected.value) {
    message.warning('Please connect to SSH first')
    return
  }

  // Use cached content if available and not forcing refresh
  if (!forceRefresh && dirCache.has(path)) {
    const cached = dirCache.get(path)
    items.value = cached.items
    currentPath.value = cached.expandedPath
    const dirName = cached.expandedPath.split('/').filter(Boolean).pop() || '/'
    document.title = dirName
    emit('path-changed', cached.expandedPath)
    selectedItems.value.clear()
    return
  }

  // Cancel previous request if exists
  if (currentRequestController) {
    currentRequestController.abort()
    currentRequestController = null
  }

  // Track the path we're requesting
  currentRequestPath = path
  loading.value = true

  // Create new abort controller for this request
  currentRequestController = new AbortController()

  try {
    const res = await axios.post(
      `${getBaseUrl()}/api/sftp/list`,
      { path },
      { signal: currentRequestController.signal }
    )

    // Only update state if this is still the most recent request
    if (currentRequestPath !== path) {
      return
    }

    if (res.data.status === 'success') {
      items.value = res.data.items
      // Use expanded path from server
      const expandedPath = res.data.current_path
      currentPath.value = expandedPath
      // Cache the result
      dirCache.set(expandedPath, { items: res.data.items, expandedPath })
      // Update page title to current directory name
      const dirName = expandedPath.split('/').filter(Boolean).pop() || '/'
      document.title = dirName
      // 通知父组件路径已更新（父组件决定是否更新URL）
      emit('path-changed', expandedPath)
      selectedItems.value.clear()
    } else if (res.data.status === 'cancelled') {
      // Don't show error for cancelled requests, keep loading state for new request
      return
    } else {
      message.error(res.data.message)
    }
  } catch (e) {
    // Only handle error if this is still the most recent request
    if (currentRequestPath !== path) {
      return
    }

    // Check if this was an abort error (cancelled by newer request)
    if (e.name === 'AbortError' || e.name === 'CanceledError') {
      // Don't show error, keep loading state for new request
      return
    }
    message.error('Failed to load directory')
  } finally {
    // Only turn off loading if this is still the most recent request
    if (currentRequestPath === path) {
      loading.value = false
      currentRequestController = null
    }
  }
}

const refresh = () => {
  dirCache.delete(currentPath.value)
  loadDirectory(currentPath.value, { forceRefresh: true })
}

// Navigation
const navigateTo = (path) => {
  loadDirectory(path)
}

// Toggle sort field and direction
const toggleSort = (field) => {
  if (sortField.value === field) {
    // Toggle direction if same field
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    // Set new field and default to ascending
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

// Format helpers
const formatSize = (bytes) => {
  if (bytes === 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

const formatDate = (timestamp) => {
  if (!timestamp) return '-'
  return new Date(timestamp * 1000).toLocaleString()
}

// Selection handling
const handleItemClick = (item, event) => {
  if (event.ctrlKey || event.metaKey) {
    // Toggle selection
    if (selectedItems.value.has(item.path)) {
      selectedItems.value.delete(item.path)
    } else {
      selectedItems.value.add(item.path)
    }
  } else if (event.shiftKey && selectedItems.value.size > 0) {
    // Range selection
    const paths = items.value.map(i => i.path)
    const selectedArray = Array.from(selectedItems.value)
    const lastSelected = selectedArray[selectedArray.length - 1]
    const startIdx = paths.indexOf(lastSelected)
    const endIdx = paths.indexOf(item.path)
    const [start, end] = startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx]
    for (let i = start; i <= end; i++) {
      selectedItems.value.add(paths[i])
    }
  } else {
    // Single selection
    selectedItems.value.clear()
    selectedItems.value.add(item.path)
  }
}

const clearSelection = () => {
  selectedItems.value.clear()
}

// Double click handling
const handleItemDblClick = (item) => {
  if (item.type === 'directory') {
    navigateTo(item.path)
  } else if (item.type === 'symlink') {
    if (item.target_type === 'directory') {
      navigateTo(item.path)
    } else if (item.target_type === 'file') {
      openFile(item)
    } else {
      message.error('Broken symlink')
    }
  } else {
    openFile(item)
  }
}

// File operations
const openFile = async (item) => {
  // Open file in new tab using the /view/:path route
  // Path is not URL-encoded as per requirements
  const baseUrl = window.location.origin
  const viewerUrl = `${baseUrl}/view/${item.path}`
  window.open(viewerUrl, '_blank')
}

const downloadFile = async (path) => {
  try {
    // Create a form to submit the download request
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = `${getBaseUrl()}/api/sftp/download`
    form.target = '_blank'

    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = 'path'
    input.value = path

    form.appendChild(input)
    document.body.appendChild(form)
    form.submit()
    document.body.removeChild(form)

    message.success('Download started')
  } catch (e) {
    message.error('Download failed')
  }
}

// Context menu
const handleContextMenu = (item, event) => {
  contextMenuTarget.value = item
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  showContextMenu.value = true
}

// Handle right-click on empty area
const handleEmptyContextMenu = (event) => {
  // Only handle if clicking on the container itself, not on a file item
  if (event.target.closest('.file-item')) {
    return
  }
  contextMenuTarget.value = null
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  showContextMenu.value = true
}

const handleContextMenuSelect = async (key) => {
  showContextMenu.value = false

  switch (key) {
    case 'open':
      if (contextMenuTarget.value) {
        handleItemDblClick(contextMenuTarget.value)
      } else if (selectedItems.value.size > 0) {
        // Open the first selected item
        const firstSelected = Array.from(selectedItems.value)[0]
        const item = items.value.find(i => i.path === firstSelected)
        if (item) handleItemDblClick(item)
      }
      break
    case 'download':
      if (contextMenuTarget.value) {
        downloadFile(contextMenuTarget.value.path)
      } else if (selectedItems.value.size > 0) {
        // Download the first selected item
        const firstSelected = Array.from(selectedItems.value)[0]
        downloadFile(firstSelected)
      }
      break
    case 'copy':
      if (selectedItems.value.size > 0) {
        clipboard.value = {
          items: Array.from(selectedItems.value),
          operation: 'copy'
        }
        message.success('Copied to clipboard')
      } else if (contextMenuTarget.value) {
        clipboard.value = {
          items: [contextMenuTarget.value.path],
          operation: 'copy'
        }
        message.success('Copied to clipboard')
      }
      break
    case 'cut':
      if (selectedItems.value.size > 0) {
        clipboard.value = {
          items: Array.from(selectedItems.value),
          operation: 'cut'
        }
        message.success('Cut to clipboard')
      } else if (contextMenuTarget.value) {
        clipboard.value = {
          items: [contextMenuTarget.value.path],
          operation: 'cut'
        }
        message.success('Cut to clipboard')
      }
      break
    case 'paste':
      await pasteItems()
      break
    case 'rename':
      if (contextMenuTarget.value) {
        renameTarget.value = contextMenuTarget.value
        renameValue.value = contextMenuTarget.value.name
        showRenameDialog.value = true
      } else if (selectedItems.value.size === 1) {
        // Rename the single selected item
        const selectedPath = Array.from(selectedItems.value)[0]
        const item = items.value.find(i => i.path === selectedPath)
        if (item) {
          renameTarget.value = item
          renameValue.value = item.name
          showRenameDialog.value = true
        }
      }
      break
    case 'delete':
      await deleteItems()
      break
    case 'new_folder':
      showNewFolderDialog.value = true
      break
    case 'new_file':
      showNewFileDialog.value = true
      break
    case 'duplicate':
      await duplicateItem()
      break
    case 'copy_path':
      await navigator.clipboard.writeText(currentPath.value)
      message.success('Current path copied')
      break
    case 'copy_target_path':
      if (contextMenuTarget.value) {
        await navigator.clipboard.writeText(contextMenuTarget.value.path)
        message.success('Target path copied')
      } else if (selectedItems.value.size > 0) {
        // Copy the first selected item's path
        const firstSelected = Array.from(selectedItems.value)[0]
        await navigator.clipboard.writeText(firstSelected)
        message.success('Target path copied')
      }
      break
  }
}

// Operations
const pasteItems = async () => {
  if (clipboard.value.items.length === 0) return

  for (const srcPath of clipboard.value.items) {
    const filename = srcPath.split('/').pop()
    const dstPath = `${currentPath.value}/${filename}`

    try {
      if (clipboard.value.operation === 'copy') {
        await axios.post(`${getBaseUrl()}/api/sftp/copy`, {
          old_path: srcPath,
          new_path: dstPath
        })
      } else {
        await axios.post(`${getBaseUrl()}/api/sftp/rename`, {
          old_path: srcPath,
          new_path: dstPath
        })
        // Add to history for undo
        addToHistory({ type: 'move', src: srcPath, dst: dstPath })
      }
    } catch (e) {
      message.error(`Failed to ${clipboard.value.operation} ${filename}`)
    }
  }

  clipboard.value = { items: [], operation: null }
  refresh()
  message.success('Paste completed')
}

const deleteItems = async () => {
  const targets = Array.from(selectedItems.value).length > 0
    ? Array.from(selectedItems.value)
    : (contextMenuTarget.value ? [contextMenuTarget.value.path] : [])

  if (targets.length === 0) return

  dialog.warning({
    title: 'Confirm Delete',
    content: `Are you sure you want to delete ${targets.length} item(s)?`,
    positiveText: 'Delete',
    negativeText: 'Cancel',
    onPositiveClick: async () => {
      for (const path of targets) {
        try {
          await axios.post(`${getBaseUrl()}/api/sftp/remove`, { path })
        } catch (e) {
          message.error(`Failed to delete ${path.split('/').pop()}`)
        }
      }
      refresh()
      message.success('Deleted')
    }
  })
}

const createNewFolder = async () => {
  if (!newFolderName.value) return

  const path = `${currentPath.value}/${newFolderName.value}`
  try {
    await axios.post(`${getBaseUrl()}/api/sftp/mkdir`, { path })
    showNewFolderDialog.value = false
    newFolderName.value = ''
    refresh()
    message.success('Folder created')
  } catch (e) {
    message.error('Failed to create folder')
  }
}

const createNewFile = async () => {
  if (!newFileName.value) return

  const path = `${currentPath.value}/${newFileName.value}`
  try {
    await axios.post(`${getBaseUrl()}/api/sftp/write`, { path, content: '' })
    showNewFileDialog.value = false
    newFileName.value = ''
    refresh()
    message.success('File created')
  } catch (e) {
    message.error('Failed to create file')
  }
}

const duplicateItem = async () => {
  let targetItem = contextMenuTarget.value
  if (!targetItem && selectedItems.value.size === 1) {
    const selectedPath = Array.from(selectedItems.value)[0]
    targetItem = items.value.find(i => i.path === selectedPath)
  }
  if (!targetItem) return

  const name = targetItem.name
  const firstDot = name.indexOf('.')
  let newName = ''
  if (firstDot > 0) {
    const base = name.substring(0, firstDot)
    const ext = name.substring(firstDot)
    newName = `${base}-copy${ext}`
  } else {
    newName = `${name}-copy`
  }

  const oldPath = targetItem.path
  const newPath = `${currentPath.value}/${newName}`

  try {
    await axios.post(`${getBaseUrl()}/api/sftp/copy`, {
      old_path: oldPath,
      new_path: newPath
    })
    refresh()
    message.success('Duplicated')
  } catch (e) {
    message.error('Failed to duplicate')
  }
}

const confirmRename = async () => {
  if (!renameValue.value || !renameTarget.value) return

  const oldPath = renameTarget.value.path
  const newPath = `${currentPath.value}/${renameValue.value}`

  try {
    await axios.post(`${getBaseUrl()}/api/sftp/rename`, {
      old_path: oldPath,
      new_path: newPath
    })
    addToHistory({ type: 'rename', src: oldPath, dst: newPath })
    showRenameDialog.value = false
    renameTarget.value = null
    renameValue.value = ''
    refresh()
    message.success('Renamed')
  } catch (e) {
    message.error('Failed to rename')
  }
}

// History for undo/redo
const addToHistory = (action) => {
  // Remove any redo actions
  historyStack.value = historyStack.value.slice(0, historyIndex.value + 1)
  historyStack.value.push(action)
  historyIndex.value++
}

const undo = async () => {
  if (historyIndex.value < 0) return

  const action = historyStack.value[historyIndex.value]
  try {
    if (action.type === 'move' || action.type === 'rename') {
      await axios.post(`${getBaseUrl()}/api/sftp/rename`, {
        old_path: action.dst,
        new_path: action.src
      })
    }
    historyIndex.value--
    refresh()
    message.success('Undone')
  } catch (e) {
    message.error('Undo failed')
  }
}

const redo = async () => {
  if (historyIndex.value >= historyStack.value.length - 1) return

  historyIndex.value++
  const action = historyStack.value[historyIndex.value]
  try {
    if (action.type === 'move' || action.type === 'rename') {
      await axios.post(`${getBaseUrl()}/api/sftp/rename`, {
        old_path: action.src,
        new_path: action.dst
      })
    }
    refresh()
    message.success('Redone')
  } catch (e) {
    message.error('Redo failed')
  }
}

// Get currently selected item (first one if multiple selected)
const getFirstSelectedItem = () => {
  if (selectedItems.value.size === 0) return null
  const firstPath = Array.from(selectedItems.value)[0]
  return items.value.find(i => i.path === firstPath)
}

// Get index of currently selected item (first one if multiple selected)
const getFirstSelectedIndex = () => {
  if (selectedItems.value.size === 0) return -1
  const firstPath = Array.from(selectedItems.value)[0]
  return items.value.findIndex(i => i.path === firstPath)
}

// Select item by index and scroll into view
const selectItemByIndex = (index) => {
  if (index < 0 || index >= items.value.length) return

  const item = items.value[index]
  selectedItems.value.clear()
  selectedItems.value.add(item.path)

  // Scroll into view
  nextTick(() => {
    const element = document.querySelector(`[data-path="${CSS.escape(item.path)}"]`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

// Calculate grid columns based on container width and item width
const getGridColumns = () => {
  const container = document.querySelector('.file-content.grid')
  if (!container) return 1

  const containerWidth = container.clientWidth
  const itemMinWidth = 120
  const gap = 16
  const columns = Math.floor((containerWidth + gap) / (itemMinWidth + gap))
  return Math.max(1, columns)
}

// Keyboard shortcuts
const handleKeyDown = (event) => {
  // Check if any modal/dialog is open - skip navigation
  if (showRenameDialog.value || showNewFolderDialog.value || showNewFileDialog.value || showEditor.value || showConflictDialog.value) {
    return
  }

  // Check if focus is in an input element
  const activeElement = document.activeElement
  if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
    return
  }

  // Enter key to open folder or file
  if (event.key === 'Enter') {
    event.preventDefault()
    const selectedItem = getFirstSelectedItem()
    if (selectedItem) {
      handleItemDblClick(selectedItem)
    }
    return
  }

  // Arrow keys navigation
  if (event.key === 'ArrowUp' || event.key === 'ArrowDown' || event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()

    if (items.value.length === 0) return

    const currentIndex = getFirstSelectedIndex()
    let newIndex = -1

    if (viewMode.value === 'list') {
      // List view: Up/Down only
      if (event.key === 'ArrowUp') {
        if (currentIndex === -1) {
          newIndex = items.value.length - 1
        } else {
          newIndex = Math.max(0, currentIndex - 1)
        }
      } else if (event.key === 'ArrowDown') {
        if (currentIndex === -1) {
          newIndex = 0
        } else {
          newIndex = Math.min(items.value.length - 1, currentIndex + 1)
        }
      }
    } else {
      // Grid view: Up/Down/Left/Right
      const columns = getGridColumns()

      if (currentIndex === -1) {
        // No selection, select first item
        newIndex = 0
      } else {
        if (event.key === 'ArrowUp') {
          newIndex = Math.max(0, currentIndex - columns)
        } else if (event.key === 'ArrowDown') {
          newIndex = Math.min(items.value.length - 1, currentIndex + columns)
        } else if (event.key === 'ArrowLeft') {
          newIndex = Math.max(0, currentIndex - 1)
        } else if (event.key === 'ArrowRight') {
          newIndex = Math.min(items.value.length - 1, currentIndex + 1)
        }
      }
    }

    if (newIndex !== -1 && newIndex !== currentIndex) {
      selectItemByIndex(newIndex)
    }
    return
  }

  // F2 for rename (no Ctrl/Meta required)
  if (event.key === 'F2') {
    event.preventDefault()
    if (selectedItems.value.size === 1) {
      const selectedPath = Array.from(selectedItems.value)[0]
      const item = items.value.find(i => i.path === selectedPath)
      if (item) {
        renameTarget.value = item
        renameValue.value = item.name
        showRenameDialog.value = true
      }
    } else if (selectedItems.value.size > 1) {
      message.error('Please select only one file to rename')
    }
    return
  }

  // Delete key for delete
  if (event.key === 'Delete') {
    event.preventDefault()
    if (selectedItems.value.size > 0) {
      deleteItems()
    }
    return
  }

  // Prefix search with character keys (when no modifiers and not in input)
  if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.length === 1) {
    // Check if any modal/dialog is open
    if (showRenameDialog.value || showNewFolderDialog.value || showNewFileDialog.value || showEditor.value || showConflictDialog.value) {
      return
    }

    // Check if focus is in an input element
    const activeElement = document.activeElement
    if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
      return
    }

    event.preventDefault()

    // Append to buffer
    searchBuffer.value += event.key.toLowerCase()

    // Reset timeout
    if (searchTimeout) {
      clearTimeout(searchTimeout)
    }
    searchTimeout = setTimeout(() => {
      searchBuffer.value = ''
    }, SEARCH_TIMEOUT_MS)

    // Find starting index for circular search
    let startIndex = 0
    if (selectedItems.value.size === 1) {
      const selectedPath = Array.from(selectedItems.value)[0]
      const selectedIndex = items.value.findIndex(i => i.path === selectedPath)
      if (selectedIndex !== -1) {
        startIndex = selectedIndex + 1 // Start from next item
      }
    }

    // Circular search: from startIndex to end, then from 0 to startIndex
    let matchedIndex = -1
    const buffer = searchBuffer.value

    // First pass: from startIndex to end
    for (let i = startIndex; i < items.value.length; i++) {
      if (items.value[i].name.toLowerCase().startsWith(buffer)) {
        matchedIndex = i
        break
      }
    }

    // Second pass: from 0 to startIndex (circular)
    if (matchedIndex === -1 && startIndex > 0) {
      for (let i = 0; i < startIndex; i++) {
        if (items.value[i].name.toLowerCase().startsWith(buffer)) {
          matchedIndex = i
          break
        }
      }
    }

    if (matchedIndex !== -1) {
      const matchedItem = items.value[matchedIndex]
      selectedItems.value.clear()
      selectedItems.value.add(matchedItem.path)

      // Scroll into view
      nextTick(() => {
        const element = document.querySelector(`[data-path="${CSS.escape(matchedItem.path)}"]`)
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      })
    }

    return
  }

  if (!event.ctrlKey && !event.metaKey) return

  switch (event.key.toLowerCase()) {
    case 'a':
      event.preventDefault()
      items.value.forEach(item => selectedItems.value.add(item.path))
      break
    case 'c':
      if (selectedItems.value.size > 0) {
        clipboard.value = {
          items: Array.from(selectedItems.value),
          operation: 'copy'
        }
        message.success('Copied')
      }
      break
    case 'x':
      if (selectedItems.value.size > 0) {
        clipboard.value = {
          items: Array.from(selectedItems.value),
          operation: 'cut'
        }
        message.success('Cut')
      }
      break
    case 'v':
      event.preventDefault()
      pasteItems()
      break
    case 'z':
      event.preventDefault()
      if (event.shiftKey) {
        redo()
      } else {
        undo()
      }
      break
  }
}

// Drag and drop
const handleDragStart = (item, event) => {
  if (!selectedItems.value.has(item.path)) {
    selectedItems.value.clear()
    selectedItems.value.add(item.path)
  }

  const paths = Array.from(selectedItems.value)
  event.dataTransfer.setData('application/json', JSON.stringify({
    paths,
    sourcePath: currentPath.value
  }))
  event.dataTransfer.effectAllowed = 'move'
}

const handleDragOver = (event) => {
  event.dataTransfer.dropEffect = 'move'
}

const handleDrop = async (event) => {
  const files = event.dataTransfer.files
  if (files.length > 0) {
    // External file upload
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('path', currentPath.value)

      try {
        await axios.post(`${getBaseUrl()}/api/sftp/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
      } catch (e) {
        message.error(`Failed to upload ${file.name}`)
      }
    }
    refresh()
    message.success('Upload completed')
  }
}

const handleItemDragOver = (item, event) => {
  if (item.type === 'directory') {
    event.dataTransfer.dropEffect = event.ctrlKey ? 'copy' : 'move'
  }
}

const handleItemDrop = async (item, event) => {
  if (item.type !== 'directory') return

  const data = event.dataTransfer.getData('application/json')
  if (!data) return

  const { paths, sourcePath } = JSON.parse(data)
  const isCopy = event.ctrlKey

  for (const srcPath of paths) {
    const filename = srcPath.split('/').pop()
    const dstPath = `${item.path}/${filename}`

    try {
      if (isCopy) {
        await axios.post(`${getBaseUrl()}/api/sftp/copy`, {
          old_path: srcPath,
          new_path: dstPath
        })
      } else {
        await axios.post(`${getBaseUrl()}/api/sftp/rename`, {
          old_path: srcPath,
          new_path: dstPath
        })
      }
    } catch (e) {
      message.error(`Failed to ${isCopy ? 'copy' : 'move'} ${filename}`)
    }
  }

  refresh()
  message.success(isCopy ? 'Copied' : 'Moved')
}

// Conflict handling
const handleConflictOverwrite = () => {
  showConflictDialog.value = false
}

const handleConflictSkip = () => {
  showConflictDialog.value = false
}


// Initialize - 第一次挂载时加载
const isFirstMount = ref(true)
onMounted(() => {
  if (isFirstMount.value) {
    isFirstMount.value = false
    currentPath.value = props.path || '~'
    if (connected.value) {
      loadDirectory(currentPath.value)
    }
  }
})

// Watch for path prop changes
watch(() => props.path, (newPath) => {
  if (newPath && newPath !== currentPath.value) {
    currentPath.value = newPath
    if (connected.value) {
      loadDirectory(newPath)
    }
  }
})

// Watch for connected changes - 连接成功后自动加载
watch(() => connected.value, (isConnected) => {
  if (isConnected && items.value.length === 0) {
    loadDirectory(currentPath.value)
  }
})
</script>

<style scoped>
.file-browser {
  display: flex;
  flex-direction: column;
  height: 100%;
  outline: none;
}

.breadcrumb-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #eee;
  cursor: text;
}

.breadcrumb-bar :deep(.n-breadcrumb) {
  flex: 1;
}

.breadcrumb-bar .n-input {
  margin-right: 12px;
}

.view-controls {
  display: flex;
  gap: 8px;
}

.file-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
  background: #fafafa;
}

.file-content.list {
  display: flex;
  flex-direction: column;
}

.file-content.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 16px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.list-header {
  display: flex;
  padding: 8px 16px;
  background: #f0f0f0;
  font-weight: 600;
  color: #666;
  font-size: 13px;
  border-bottom: 1px solid #ddd;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.2s;
}

.file-item:hover {
  background: #e6f7ff;
}

.file-item.selected {
  background: #bae7ff;
}

.file-item.list-item {
  display: flex;
}

.file-item.grid-item {
  flex-direction: column;
  justify-content: center;
  padding: 16px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  background: #fff;
}

.file-item.grid-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.file-item.grid-item.selected {
  border-color: #1890ff;
  background: #e6f7ff;
}

.col-name {
  flex: 2;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.col-size {
  width: 100px;
  color: #666;
}

.col-date {
  flex: 1;
  color: #666;
}

.col-perm {
  width: 100px;
  color: #666;
}

.sortable {
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.sortable:hover {
  color: #18a058;
}

.sort-icon {
  display: flex;
  align-items: center;
}

.item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grid-item .item-name {
  margin-top: 8px;
  max-width: 100%;
  text-align: center;
}

.item-size {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.file-item .directory {
  color: #faad14;
}

.file-item .file {
  color: #1890ff;
}

.file-item .symlink {
  color: #52c41a;
}

.symlink-broken {
  margin-left: 4px;
  color: #ff4d4f;
  font-weight: bold;
  font-size: 12px;
}

.status-bar {
  display: flex;
  justify-content: space-between;
  padding: 8px 24px;
  background: #fff;
  border-top: 1px solid #eee;
  font-size: 12px;
  color: #666;
}
</style>
