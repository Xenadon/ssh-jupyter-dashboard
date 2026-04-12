<template>
  <div style="padding: 24px; overflow-y: auto;">
    <div style="margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between;">
      <h3 style="margin: 0; color: #555;">Jupyter Instances</h3>
      <n-button type="primary" dashed size="small" @click="addInstanceRow" :disabled="!connected">
        + Add Row
      </n-button>
    </div>

    <div style="background: white; border-radius: 8px; border: 1px solid #eee; box-shadow: 0 1px 2px rgba(0,0,0,0.05); min-width: 800px;">

      <div style="display: flex; gap: 12px; padding: 12px 16px; background: #fafafa; border-bottom: 1px solid #eee; font-weight: 600; color: #666; font-size: 13px;">
        <div style="width: 40px;"></div>
        <div style="flex: 2;">Workspace Directory</div>
        <div style="width: 100px;">Port</div>
        <div style="flex: 3;">Extra Options</div>
        <div style="width: 240px;">Actions</div>
        <div style="width: 40px;"></div>
      </div>

      <div style="padding: 0;">

        <div v-if="instanceRows.length === 0" style="text-align: center; padding: 30px; color: #999; font-style: italic;">
          No instances defined. Click "+ Add Row" to start.
        </div>

        <div
          v-for="(row, index) in instanceRows"
          :key="row.id"
          class="instance-row"
        >
          <div style="display: flex; align-items: flex-start; gap: 12px; width: 100%;">

            <div style="width: 40px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;">
               <n-button
                 type="default" size="small"
                 title="Open in File Browser"
                 @click="openInFileBrowser(row.dir)"
                 :disabled="!connected"
               >
                 <template #icon>
                   <n-icon><FolderOpenOutline /></n-icon>
                 </template>
               </n-button>
            </div>

            <div style="flex: 2; min-width: 0;">
               <n-input v-model:value="row.dir" placeholder="~" :disabled="row.status !== 'idle'" />
            </div>

            <div style="width: 100px; flex-shrink: 0;">
               <n-input v-model:value="row.port" placeholder="Auto" :disabled="row.status !== 'idle'" />
            </div>

            <div style="flex: 3; min-width: 0;">
               <n-input v-model:value="row.options" placeholder="e.g. --debug" :disabled="row.status !== 'idle'" />
            </div>

            <div style="width: 240px; flex-shrink: 0; display: flex; gap: 8px;">
              <n-button
                v-if="row.status === 'idle'"
                type="primary" color="#18a058" ghost size="medium"
                style="flex: 1"
                @click="startInstance(index)" :loading="row.loading"
                :disabled="!connected"
              >
                Start
              </n-button>
              <n-button
                v-else
                type="error" ghost size="medium"
                style="flex: 1"
                @click="stopInstance(index)" :loading="row.loading"
              >
                Stop
              </n-button>

              <n-button
                type="info" secondary size="medium"
                style="flex: 1"
                tag="a"
                :href="row.status === 'running' ? row.url : undefined"
                target="_blank"
                :disabled="row.status !== 'running'"
              >
                Open UI
              </n-button>
            </div>

            <div style="width: 40px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;">
              <n-button text style="font-size: 18px" type="error" @click="removeInstanceRow(index)" :disabled="row.status === 'running'">
                ×
              </n-button>
            </div>
          </div>

          <div v-if="row.status === 'running'" style="margin-top: 8px; margin-left: 52px; background: #f0fdf4; padding: 6px 12px; border-radius: 4px; font-size: 12px; color: #18a058; display: flex; gap: 20px; align-self: flex-start; width: calc(100% - 52px); box-sizing: border-box;">
              <span>↳ <strong>PID:</strong> {{ row.pid }}</span>
              <span><strong>Remote Port:</strong> {{ row.real_port }}</span>
              <span><strong>Token:</strong> {{ row.token.substring(0, 15) }}...</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { NButton, NInput, NIcon, createDiscreteApi } from 'naive-ui'
import { FolderOpenOutline } from '@vicons/ionicons5'
import axios from 'axios'
import configStore from '../stores/config.js'

const { message } = createDiscreteApi(['message'])

const connected = inject('connected')
const config = inject('config')

// Emits
const emit = defineEmits(['open-file-browser'])

// Get base URL for API
const getBaseUrl = () => configStore.baseUrl.value

const instanceRows = ref([
  { id: 1, dir: '~', port: '', options: '', status: 'idle', loading: false, pid: '', url: '', token: '', real_port: '' }
])

// 监听来自MainLayout的状态更新
const updateInstancesFromServer = (statusData) => {
  // 如果后端返回了instance_presets，使用它们初始化表单
  if (statusData.instance_presets && statusData.instance_presets.length > 0) {
    instanceRows.value = statusData.instance_presets.map(item => ({
      id: Date.now() + Math.random(),
      dir: item.dir,
      port: item.port,
      options: item.options,
      status: 'idle',  // 初始状态为idle，后续根据jupyter_instances更新
      loading: false,
      pid: '',
      url: '',
      token: '',
      real_port: ''
    }))
  }

  // 根据jupyter_instances更新运行状态
  if (statusData.jupyter_instances) {
    for (const jupyter of statusData.jupyter_instances) {
      // 找到对应的instanceRow并更新状态
      // 优先匹配port字段，如果没有匹配则找第一个idle的行
      let row = instanceRows.value.find(r => r.port === jupyter.local_port.toString())
      if (!row) {
        row = instanceRows.value.find(r => r.status === 'idle')
      }
      if (row && jupyter.running) {
        row.status = 'running'
        row.pid = jupyter.pid
        row.real_port = jupyter.local_port.toString()
        // URL需要重新构建，token需要重新获取
        row.url = `http://localhost:${jupyter.local_port}/lab`
      }
    }
  }
}

// 监听服务器状态更新事件
onMounted(() => {
  // 监听来自MainLayout的状态更新
  window.addEventListener('server-status-updated', handleStatusUpdate)

  // 组件挂载时主动查询状态（处理路由切换场景）
  fetchStatusFromServer()
})

// 处理状态更新事件
const handleStatusUpdate = (e) => {
  updateInstancesFromServer(e.detail)
}

// 从服务器获取状态
const fetchStatusFromServer = async () => {
  try {
    const res = await axios.get(`${getBaseUrl()}/api/status`)
    if (res.data.status === 'success') {
      updateInstancesFromServer(res.data)
    }
  } catch (e) {
    console.error('Failed to fetch status:', e)
  }
}

const saveCurrentInstances = async () => {
  if (!config.value.host || !config.value.user) return

  const cleanRows = instanceRows.value.map(row => ({
    dir: row.dir,
    port: row.port,
    options: row.options
  }))

  try {
    await axios.post(`${getBaseUrl()}/api/config/save_instances`, {
      host: config.value.host,
      user: config.value.user,
      instances: cleanRows
    })
  } catch (e) {
    console.error('Failed to update cache', e)
  }
}

const addInstanceRow = () => {
  instanceRows.value.push({
    id: Date.now(),
    dir: '~',
    port: '',
    options: '',
    status: 'idle',
    loading: false,
    pid: '', url: '', token: '', real_port: ''
  })
}

const removeInstanceRow = (index) => {
  instanceRows.value.splice(index, 1)
  saveCurrentInstances()
}

const startInstance = async (index) => {
  saveCurrentInstances()

  const row = instanceRows.value[index]
  if (!row.dir) return message.warning('Workspace Dir required')

  row.loading = true
  try {
    const res = await axios.post(`${getBaseUrl()}/api/jupyter/start`, {
      work_dir: row.dir,
      target_port: row.port,
      extra_options: row.options
    })

    if (res.data.status === 'success') {
      const result = res.data.data
      row.status = 'running'
      row.pid = result.pid
      row.real_port = result.remote_port
      row.port = result.remote_port.toString()
      row.token = result.token
      row.url = result.url
      message.success(`Started on port ${result.remote_port}`)
    } else {
      message.error(res.data.message)
    }
  } catch (e) {
    message.error('Start request failed')
  } finally {
    row.loading = false
  }
}

const stopInstance = async (index) => {
  saveCurrentInstances()

  const row = instanceRows.value[index]
  row.loading = true
  try {
    await axios.post(`${getBaseUrl()}/api/jupyter/stop`, {
      local_port: row.real_port
    })
    row.status = 'idle'
    row.pid = ''
    row.url = ''
    message.info('Instance Stopped')
  } catch (e) {
    message.error('Stop failed')
  } finally {
    row.loading = false
  }
}

// 在文件浏览器中打开指定目录
const openInFileBrowser = (dir) => {
  if (!connected.value) {
    message.warning('Please connect to SSH first')
    return
  }
  saveCurrentInstances()
  // 触发事件通知父组件
  emit('open-file-browser', dir)
}
</script>

<style scoped>
.instance-row {
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.instance-row:last-child {
  border-bottom: none;
}
</style>
