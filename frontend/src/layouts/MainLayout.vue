<template>
  <n-config-provider>
    <n-global-style />
    <div class="app-container">
      <n-layout-header bordered style="padding: 0 24px; height: 60px; display: flex; align-items: center; justify-content: space-between; background: #fff; flex-shrink: 0; z-index: 10;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div style="width: 20px; height: 20px; background: #18a058; border-radius: 4px;"></div>
          <h2 style="margin: 0; font-weight: 600; font-size: 18px; color: #333;">SSH Jupyter Console</h2>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <n-tag :type="connected ? 'success' : 'error'" size="medium" round>
            {{ connected ? '● Connected' : '○ Disconnected' }}
          </n-tag>
          <!-- Settings Button -->
          <n-button
            size="small"
            quaternary
            circle
            @click="showServerConfig = true"
            title="Server Settings"
          >
            <template #icon>
              <SettingsOutlineIcon />
            </template>
          </n-button>
        </div>
      </n-layout-header>

      <div style="display: flex; flex: 1; overflow: hidden; width: 100%;">
        <!-- Left Sidebar - Connection Config -->
        <div style="width: 380px; flex-shrink: 0; background: #f9f9f9; border-right: 1px solid #eee; padding: 20px; overflow-y: auto;">
          <n-card hoverable>
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                <span>Session Configuration</span>
                <!-- Navigation Buttons -->
                <n-button-group size="small">
                  <n-button
                    :type="activePanel === 'jupyter' ? 'primary' : 'default'"
                    @click="switchPanel('jupyter')"
                    title="Jupyter Lab"
                  >
                    <template #icon>
                      <LogoPythonIcon />
                    </template>
                  </n-button>
                  <n-button
                    :type="activePanel === 'files' ? 'primary' : 'default'"
                    @click="switchPanel('files')"
                    :disabled="!connected"
                    title="File Browser"
                  >
                    <template #icon>
                      <FolderOpenOutlineIcon />
                    </template>
                  </n-button>
                </n-button-group>
              </div>
            </template>
            <n-form label-placement="top" label-align="left" show-require-mark>
              <n-grid :cols="2" :x-gap="12">
                <n-grid-item span="2">
                   <n-form-item label="Host Server">
                    <n-input v-model:value="config.host" placeholder="grace.hprc.tamu.edu" :disabled="connected" />
                  </n-form-item>
                </n-grid-item>
                <n-grid-item>
                  <n-form-item label="NetID / User">
                    <n-input v-model:value="config.user" placeholder="User" :disabled="connected" />
                  </n-form-item>
                </n-grid-item>
                <n-grid-item>
                  <n-form-item label="2FA Code / Option">
                    <n-input
                        v-model:value="config.auth_code"
                        placeholder="1 for Push, or Code"
                        :disabled="connected"
                        title="Enter '1' for Duo Push, or your 6-digit code"
                    />
                  </n-form-item>
                </n-grid-item>
                <n-grid-item span="2">
                  <n-form-item label="Password">
                    <n-input type="password" show-password-on="click" v-model:value="config.password" placeholder="******" :disabled="connected" />
                  </n-form-item>
                </n-grid-item>
              </n-grid>

              <n-form-item label="Initialization Script">
                <n-input
                  class="code-editor"
                  v-model:value="globalInitScript"
                  type="textarea"
                  :autosize="{ minRows: 4, maxRows: 10 }"
                  placeholder="module load Anaconda3..."
                  :disabled="connected"
                />
              </n-form-item>

              <n-button
                block
                size="large"
                @click="handleConnectionAction"
                :loading="loading"
                :type="connected ? 'error' : 'primary'"
                :color="connected ? undefined : '#2080f0'"
              >
                {{ connected ? 'Disconnect & Clear' : 'Connect & Initialize' }}
              </n-button>
            </n-form>
          </n-card>
        </div>

        <!-- Main Content Area -->
        <div style="flex: 1; overflow: hidden; position: relative;">
          <!-- Jupyter Panel -->
          <div v-show="activePanel === 'jupyter'" style="height: 100%; overflow: auto;">
            <JupyterPanel ref="jupyterPanelRef" @open-file-browser="handleOpenFileBrowser" />
          </div>
          <!-- File Browser Panel -->
          <div v-show="activePanel === 'files'" style="height: 100%; overflow: auto;">
            <FileBrowser ref="fileBrowserRef" :path="currentFilePath" @path-changed="handlePathChanged" />
          </div>
        </div>
      </div>

      <!-- Terminal Section - Full Width -->
      <div style="height: 220px; background: #1e1e1e; flex-shrink: 0; border-top: 1px solid #333; display: flex; flex-direction: column; width: 100%;">
        <div style="padding: 5px 15px; background: #2d2d2d; color: #aaa; font-size: 12px; font-weight: bold; display: flex; justify-content: space-between;">
          <span>TERMINAL / LOGS (Interactive for 2FA)</span>
          <span :style="{color: connected ? '#18a058' : '#666'}">{{ connected ? '● Live' : '○ Offline' }}</span>
        </div>
        <div ref="terminalContainer" style="flex: 1; overflow: hidden; padding: 5px;"></div>
      </div>

      <!-- Server Config Modal -->
      <n-modal
        v-model:show="showServerConfig"
        title="Server Configuration"
        preset="card"
        style="width: 400px;"
      >
        <n-form label-placement="top">
          <n-form-item label="Host">
            <n-input v-model:value="serverHost" placeholder="127.0.0.1" />
          </n-form-item>
          <n-form-item label="Port">
            <n-input-number v-model:value="serverPort" :min="1" :max="65535" style="width: 100%;" />
          </n-form-item>
          <n-alert type="info" :show-icon="false" style="margin-top: 12px;">
            <p style="font-size: 12px; margin: 0;">
              Current endpoint: {{ configStore.baseUrl.value }}
            </p>
            <p style="font-size: 11px; margin: 8px 0 0 0; color: #888;">
              Note: Backend restart required for port changes to take effect.
              Use: <code>SSH_JUPYTER_PORT={{ serverPort }} uvicorn main:app</code>
            </p>
          </n-alert>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showServerConfig = false">Cancel</n-button>
            <n-button type="primary" @click="saveServerConfig">Save</n-button>
          </n-space>
        </template>
      </n-modal>
    </div>
  </n-config-provider>
</template>

<script setup>
import { ref, onMounted, computed, provide, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import JupyterPanel from '../views/JupyterPanel.vue'
import FileBrowser from '../views/FileBrowser.vue'
import {
  createDiscreteApi,
  NConfigProvider, NGlobalStyle, NLayoutHeader,
  NCard, NForm, NFormItem, NInput, NButton, NButtonGroup, NTag, NGrid, NGridItem, NSpace, NIcon, NModal, NDivider, NAlert, NInputNumber
} from 'naive-ui'
import { LogoPython, FolderOpenOutline, SettingsOutline } from '@vicons/ionicons5'
import axios from 'axios'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import configStore from '../stores/config.js'

const { message } = createDiscreteApi(['message'])

// Icon components
const LogoPythonIcon = LogoPython
const FolderOpenOutlineIcon = FolderOpenOutline
const SettingsOutlineIcon = SettingsOutline

const route = useRoute()
const router = useRouter()

const connected = ref(false)
const loading = ref(false)
const config = ref({ host: '', user: '', password: '', auth_code: '1' })
const globalInitScript = ref('')

// Panel switching state
const activePanel = ref('jupyter')
const currentFilePath = ref('~')  // 缓存文件浏览器的当前路径
const jupyterPanelRef = ref(null)
const fileBrowserRef = ref(null)

// 监听路由变化来切换面板
watch(() => route.name, (newRouteName) => {
  if (newRouteName === 'jupyter') {
    activePanel.value = 'jupyter'
  } else if (newRouteName === 'files') {
    activePanel.value = 'files'
    // 如果有路径参数，更新缓存
    if (route.params.path) {
      currentFilePath.value = route.params.path
    }
  }
}, { immediate: true })

// Server config dialog
const showServerConfig = ref(false)
const serverHost = ref(configStore.config.value.server.host)
const serverPort = ref(configStore.config.value.server.port)

// Get current base URL for API calls
const getBaseUrl = () => configStore.baseUrl.value

const terminalContainer = ref(null)
let term = null
let fitAddon = null
let ws = null

// Provide state to child components
provide('connected', connected)
provide('config', config)
provide('terminal', { getTerm: () => term, getWs: () => ws })
provide('baseUrl', configStore.baseUrl)

// Load connection state from server on mount
onMounted(async () => {
  setTimeout(() => {
    initTerminal()
  }, 100)

  // 从后端同步真实状态
  await syncStatusFromServer()
})

// 从服务器同步状态
const syncStatusFromServer = async () => {
  try {
    // 首先加载 config.json 中的表单默认值（host, user, password, init_script）
    await loadSavedConfig()

    const res = await axios.get(`${getBaseUrl()}/api/status`)
    if (res.data.status === 'success') {
      const data = res.data

      // 更新SSH连接状态
      connected.value = data.ssh.connected
      if (data.ssh.connected) {
        // 如果已连接，使用服务器返回的真实 host/user
        config.value.host = data.ssh.host || ''
        config.value.user = data.ssh.user || ''
        // 如果已连接，初始化WebSocket
        initWebSocket()
      }
      // 如果未连接，保留 loadSavedConfig 加载的表单默认值

      // 触发JupyterPanel更新 - 通过provide/inject传递状态
      // 使用window事件通知子组件
      window.dispatchEvent(new CustomEvent('server-status-updated', { detail: data }))
    }
  } catch (e) {
    console.error('Failed to sync status:', e)
    connected.value = false
  }
}

const initTerminal = () => {
  term = new Terminal({
    theme: { background: '#1e1e1e', foreground: '#cccccc', cursor: '#ffffff' },
    fontFamily: 'Consolas, monospace',
    fontSize: 13,
    cursorBlink: true,
    convertEol: true,
  })
  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalContainer.value)

  fitAddon.fit()
  window.addEventListener('resize', () => fitAddon.fit())

  term.onData(data => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data)
  })
}

const loadSavedConfig = async () => {
  try {
    const res = await axios.get(`${getBaseUrl()}/api/config`)
    const data = res.data
    if (data.ssh) {
      config.value.host = data.ssh.host || ''
      config.value.user = data.ssh.username || ''
      config.value.password = data.ssh.password || ''
    }
    if (data.init_script) {
        globalInitScript.value = data.init_script
    }
  } catch (e) { console.log('Config load skipped') }
}

const handleConnectionAction = () => {
  if (connected.value) {
    disconnectSSH()
  } else {
    connectSSH()
  }
}

const connectSSH = async () => {
  loading.value = true
  term.clear()
  term.write(`Connecting to ${config.value.host}...\r\n`)
  try {
    const res = await axios.post(`${getBaseUrl()}/api/connect`, {
      hostname: config.value.host,
      username: config.value.user,
      password: config.value.password,
      auth_code: config.value.auth_code,
      init_script: globalInitScript.value
    })

    if (res.data.status === 'success') {
      message.success(res.data.message)
      initWebSocket()
      connected.value = true

      // 连接成功后，同步状态到子组件（包括 instance_presets）
      const statusData = {
        ssh: {
          connected: true,
          host: config.value.host,
          user: config.value.user
        },
        instance_presets: res.data.saved_instances || [],
        jupyter_instances: []
      }
      window.dispatchEvent(new CustomEvent('server-status-updated', { detail: statusData }))
    } else {
      term.write(`\r\nError: ${res.data.message}`)
      message.error('Connect Failed')
    }
  } catch (e) {
    message.error('Network Error')
  } finally {
    loading.value = false
  }
}

const disconnectSSH = async () => {
  loading.value = true
  try {
    await axios.post(`${getBaseUrl()}/api/disconnect`)

    if (ws) ws.close()

    connected.value = false

    term.write('\r\n[Session Disconnected & Cleaned]\r\n')
    message.success('Disconnected')
  } catch (e) {
    message.error('Disconnect Failed')
  } finally {
    loading.value = false
  }
}

const initWebSocket = () => {
  if (ws) ws.close()
  // Use relative WebSocket path when served from backend (same origin)
  const isDev = window.location.port === '5173'
  const wsUrl = isDev
    ? `ws://${configStore.config.value.server.host}:${configStore.config.value.server.port}/ws/stream`
    : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/stream`
  ws = new WebSocket(wsUrl)
  ws.onmessage = (e) => term.write(e.data)
  ws.onclose = () => {
    if (connected.value) {
        term.write('\r\n[Disconnected unexpectedly]\r\n')
        connected.value = false
    }
  }
}

// Switch between panels
const switchPanel = (panel) => {
  if (panel === 'files' && !connected.value) {
    message.warning('Please connect to SSH first')
    return
  }
  // 更新 URL，但保持组件状态
  if (panel === 'jupyter') {
    router.push('/')
  } else if (panel === 'files') {
    // 直接拼接，保留双斜线形式（如 /files//home 表示绝对路径 /home）
    router.push(`/files/${currentFilePath.value}`)
  }
}

const saveServerConfig = () => {
  configStore.updateServerConfig(serverHost.value, serverPort.value)
  message.success(`Server config updated to ${serverHost.value}:${serverPort.value}`)
  showServerConfig.value = false
  // Reload config to apply changes
  loadSavedConfig()
}

// 处理文件浏览器路径变化
const handlePathChanged = (newPath) => {
  // 总是更新缓存
  currentFilePath.value = newPath
  // 如果当前是文件面板，同时更新URL（保留双斜线形式）
  if (activePanel.value === 'files') {
    router.replace(`/files/${newPath}`)
  }
}

// 处理从Jupyter面板打开文件浏览器
const handleOpenFileBrowser = (dir) => {
  // 更新缓存路径
  currentFilePath.value = dir || '~'
  // 切换到文件浏览器面板
  switchPanel('files')
}
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background-color: #f0f2f5;
  overflow: hidden;
}

:deep(.n-input__input-el) {
  text-align: left !important;
}

.code-editor :deep(textarea) {
  font-family: Consolas, monospace !important;
  font-size: 13px !important;
  line-height: 1.5;
}

:deep(.xterm-screen) {
  text-align: left !important;
}
</style>
