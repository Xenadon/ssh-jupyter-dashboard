import { ref, computed } from 'vue'
import axios from 'axios'

// Default config
const defaultConfig = {
  server: {
    port: 8000,
    host: '127.0.0.1'
  }
}

// Load from localStorage
const loadStoredConfig = () => {
  try {
    const stored = localStorage.getItem('app_config')
    if (stored) {
      return { ...defaultConfig, ...JSON.parse(stored) }
    }
  } catch (e) {
    console.error('Failed to load config', e)
  }
  return { ...defaultConfig }
}

// Reactive config state
const config = ref(loadStoredConfig())

// Computed base URL for API
// Use relative path when served from backend (same origin), otherwise use configured host/port
const baseUrl = computed(() => {
  // Check if we're running in dev mode (Vite dev server on port 5173)
  const isDev = window.location.port === '5173'
  if (isDev) {
    const host = config.value.server?.host || '127.0.0.1'
    const port = config.value.server?.port || 8000
    return `http://${host}:${port}`
  }
  // Production: use relative path (same origin as backend)
  return ''
})

// Save config to localStorage
const saveConfig = (newConfig) => {
  config.value = { ...config.value, ...newConfig }
  localStorage.setItem('app_config', JSON.stringify(config.value))
}

// Update server config
const updateServerConfig = (host, port) => {
  config.value.server = { host, port: parseInt(port) }
  localStorage.setItem('app_config', JSON.stringify(config.value))
}

// Save editor config to backend (app_config.json)
const saveEditorConfig = async (editorConfig) => {
  saveConfig({ editor: editorConfig })
  try {
    await axios.post(`${baseUrl.value}/api/config/editor`, editorConfig)
  } catch (e) {
    console.warn('Failed to persist editor config to backend', e)
  }
}

// Load editor config from backend on startup
const loadEditorConfig = async () => {
  try {
    const res = await axios.get(`${baseUrl.value}/api/config`)
    if (res.data?.editor) {
      saveConfig({ editor: res.data.editor })
    }
  } catch (e) {
    console.warn('Failed to load editor config from backend', e)
  }
}

export default {
  config,
  baseUrl,
  saveConfig,
  updateServerConfig,
  saveEditorConfig,
  loadEditorConfig
}
