<template>
  <div class="daily-data">
    <!-- 图表区（上） -->
    <el-card style="margin-bottom:16px">
      <div ref="chartRef" style="height:380px"></div>
    </el-card>

    <!-- 表格区（下） -->
    <el-card>
      <template #header>
        <div class="page-header">
          <span>日报数据</span>
          <div class="header-actions">
            <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" @change="loadData" size="small" />
            <el-tooltip content="下载日报CSV模板文件（列：日期,已售,房费,起售价）" placement="bottom"><el-button @click="downloadTemplate" v-if="isAdmin()">📤 模板</el-button></el-tooltip>
            <el-tooltip content="上传CSV文件批量导入日报数据，自动计算出租率/RevPar/ADR等指标" placement="bottom"><el-button type="success" @click="triggerDailyUpload" :loading="importingDaily" v-if="isAdmin()">📥 导入</el-button></el-tooltip>
            <el-tooltip content="导出当前日期范围内的日报数据为CSV文件" placement="bottom"><el-button @click="exportData" v-if="isAdmin()">导出</el-button></el-tooltip>
            <el-tooltip content="批量删除选中日期的日报及对应小时数据，并重算月报" placement="bottom"><el-button type="danger" @click="batchDelete" :disabled="selectedRows.length===0" v-if="isAdmin()">批量删除({{selectedRows.length}})</el-button></el-tooltip>
          </div>
        </div>
      </template>
      <el-table :data="tableData" border stripe size="small" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="40" v-if="isAdmin()" />
        <el-table-column prop="data_date" label="日期" width="120" />
        <el-table-column prop="min_price" label="起售价格" width="120" align="right">
          <template #default="{row}">¥{{row.min_price}}</template>
        </el-table-column>
        <el-table-column prop="sold_rooms" label="售出房间" width="110" align="right" />
        <el-table-column prop="remain_rooms" label="剩余房间" width="110" align="right" />
        <el-table-column prop="occupancy_rate" label="出租率" width="100" align="right">
          <template #default="{row}">{{row.occupancy_rate}}%</template>
        </el-table-column>
        <el-table-column prop="revpar" label="单房收益" width="120" align="right">
          <template #default="{row}">¥{{row.revpar}}</template>
        </el-table-column>
        <el-table-column prop="adr" label="平均房价" width="120" align="right">
          <template #default="{row}">¥{{row.adr}}</template>
        </el-table-column>
        <el-table-column prop="total_revenue" label="累计房费" align="right">
          <template #default="{row}">¥{{row.total_revenue}}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center" v-if="isAdmin()">
          <template #default="{row}">
            <el-button type="danger" size="small" link @click="deleteRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import request from '@/api'
import { useRole } from '@/composables/useRole'
const { isAdmin } = useRole()

const dateRange = ref([])
const tableData = ref([])
const selectedRows = ref([])
const chartRef = ref(null)
let chartInstance = null

const onSelectionChange = (rows) => { selectedRows.value = rows }

const loadData = async () => {
  if (dateRange.value?.length === 2) {
    tableData.value = await request.get('/daily/list', {
      params: { start_date: dateRange.value[0], end_date: dateRange.value[1] }
    })
    await nextTick()
    renderChart()
  }
}

const renderChart = () => {
  if (!chartRef.value || tableData.value.length === 0) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  
  const today = localDate()
  // 图表排除今天（未完整），但表格保留
  const sorted = [...tableData.value]
    .filter(d => d.data_date !== today)
    .sort((a, b) => a.data_date.localeCompare(b.data_date))
  if (sorted.length === 0) return
  chartInstance.setOption({
    tooltip: { trigger: 'axis', position: 'top' },
    legend: { data: ['累计房费', '单房收益', '平均房价'] },
    grid: { left: 80, right: 80, bottom: 40 },
    xAxis: { type: 'category', data: sorted.map(d => d.data_date.slice(5)) },
    yAxis: [
      { type: 'value', name: '累计房费(元)', position: 'left' },
      { type: 'value', name: '单房收益/平均房价(元)', position: 'right' }
    ],
    series: [
      { name: '累计房费', type: 'bar', data: sorted.map(d => d.total_revenue), itemStyle: { color: '#1677ff' }, yAxisIndex: 0 },
      { name: '单房收益', type: 'line', data: sorted.map(d => d.revpar), itemStyle: { color: '#fa8c16' }, smooth: true, yAxisIndex: 1 },
      { name: '平均房价', type: 'line', data: sorted.map(d => d.adr), itemStyle: { color: '#52c41a' }, lineStyle: { type: 'dashed' }, smooth: true, yAxisIndex: 1 }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, minValueSpan: 1 },
      { type: 'slider', xAxisIndex: 0, bottom: 0, height: 20 }
    ]
  })
}

const deleteRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.data_date} 的日报数据？将同时删除当日小时数据`, '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await request.delete(`/hourly/date/${row.data_date}`)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

const exportData = () => {
  if (dateRange.value?.length === 2) {
    window.open(`/api/io/export/excel?start_date=${dateRange.value[0]}&end_date=${dateRange.value[1]}`)
  }
}

const downloadTemplate = () => {
  window.open('/api/daily/export-template', '_blank')
}

const importingDaily = ref(false)
const dailyUploadInput = ref(null)
const triggerDailyUpload = () => {
  if (!dailyUploadInput.value) {
    const input = document.createElement('input')
    input.type = 'file'; input.accept = '.csv'
    input.onchange = (e) => {
      const file = e.target.files[0]
      if (file) doDailyImport(file)
      input.value = ''
    }
    dailyUploadInput.value = input
  }
  dailyUploadInput.value.click()
}
const doDailyImport = async (file) => {
  importingDaily.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const result = await request.post('/daily/batch-import', form, { timeout: 60000 })
    ElMessage.success(`导入完成: 更新${result.updated}条, 跳过${result.skipped}条`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importingDaily.value = false
  }
}

const batchDelete = async () => {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedRows.value.length} 条日报？将同时删除小时数据`, '批量删除', { type: 'warning' })
  } catch { return }
  const dates = selectedRows.value.map(r => r.data_date)
  await request.post('/daily/batch-delete', dates)
  ElMessage.success(`已删除 ${dates.length} 条`)
  selectedRows.value = []
  await loadData()
}

const handleResize = () => chartInstance?.resize()

onMounted(() => {
  const end = localDateObj()
  const start = localDateObj()
  start.setMonth(start.getMonth() - 1)
  dateRange.value = [localDate(start), localDate(end)]
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; gap: 10px; }
</style>
