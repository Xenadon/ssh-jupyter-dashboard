<template>
  <div class="sv-table-preview">
    <n-data-table
      :columns="dynamicColumns"
      :data="rows"
      :bordered="true"
      :single-line="false"
      :scroll-x="10000"
      :table-props="{ style: { tableLayout: 'fixed', width: 'max-content' } }"
      :sort-state="sortState"
      size="small"
      @update:sort-state="handleSortChange"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { NDataTable } from 'naive-ui'
import Papa from 'papaparse'

const props = defineProps({
  content: { type: String, default: '' },
  delimiter: { type: String, default: ',' },
  useFirstRowAsHeader: { type: Boolean, default: true },
})

const sortState = ref(null)
const columnWidths = ref([])

const parsed = computed(() => {
  if (!props.content) return { headers: [], rows: [] }
  const result = Papa.parse(props.content, { delimiter: props.delimiter, skipEmptyLines: true })
  const data = result.data
  if (!data.length) return { headers: [], rows: [] }
  if (props.useFirstRowAsHeader) {
    return { headers: data[0], rows: data.slice(1) }
  }
  const maxCols = Math.max(...data.map(r => r.length))
  return { headers: Array.from({ length: maxCols }, (_, i) => String(i + 1)), rows: data }
})

watch(
  () => parsed.value.headers,
  (headers) => { columnWidths.value = headers.map(() => 80) },
  { immediate: true }
)

// Detect numeric columns once per parse using head+tail+random sample
const numericColumns = computed(() => {
  const { headers, rows } = parsed.value
  if (!rows.length) return headers.map(() => false)
  const head = rows.slice(0, 100)
  const tail = rows.length > 100 ? rows.slice(-100) : []
  const randomPool = rows.length > 200 ? rows : []
  const random = randomPool.length
    ? Array.from({ length: 50 }, () => randomPool[Math.floor(Math.random() * randomPool.length)])
    : []
  const sample = [...new Set([...head, ...tail, ...random])]
  const isNum = (v) => v === '' || v == null || !isNaN(+v)
  return headers.map((_, i) => sample.every(r => isNum(r[i])))
})

const rows = computed(() =>
  parsed.value.rows.map(r => Object.fromEntries(r.map((v, i) => [String(i), v])))
)

const dynamicColumns = computed(() => {
  const isNum = numericColumns.value
  return parsed.value.headers.map((h, i) => {
    const key = String(i)
    const sorter = isNum[i]
      ? (a, b) => (+a[key] || 0) - (+b[key] || 0)
      : (a, b) => {
          const av = a[key] ?? '', bv = b[key] ?? ''
          return av < bv ? -1 : av > bv ? 1 : 0
        }
    return {
      title: h || `(${i + 1})`,
      key,
      sorter,
      resizable: true,
      width: columnWidths.value[i] ?? 80,
      minWidth: 40,
      ellipsis: { tooltip: true },
      onUpdateWidth: (newWidth) => { columnWidths.value[i] = newWidth },
    }
  })
})

const hasSorting = computed(() => !!(sortState.value?.order))

const handleSortChange = (state) => {
  sortState.value = state?.order ? state : null
}

const resetSort = () => {
  sortState.value = null
}

defineExpose({ resetSort, hasSorting })
</script>

<style scoped>
.sv-table-preview {
  height: 100%;
  width: 100%;
  overflow: auto;
  background: #fff;
}

.sv-table-preview :deep(.n-data-table-base-table-main),
.sv-table-preview :deep(.n-data-table-base-table-header),
.sv-table-preview :deep(.n-data-table-table),
.sv-table-preview :deep(.n-data-table-scroll-container) {
  width: max-content !important;
}
</style>
