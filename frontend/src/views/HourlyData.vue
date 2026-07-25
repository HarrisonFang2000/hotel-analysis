<template>
  <div class="hourly-data">
    <!-- 图表区（上） -->
    <el-card>
      <div ref="chartRef" style="height: 400px"></div>
    </el-card>

    <!-- 美团底价更新 -->
    <el-card style="margin-top: 16px">
      <div style="display:flex; align-items:center; gap:12px">
        <span style="font-weight:600; white-space:nowrap">美团底价：</span>
        <el-input-number v-model="meituanPrice" :min="0" :step="10" :precision="2" style="width:180px" placeholder="填入美团最低价" />
        <el-tooltip content="将填入的美团最低价批量更新到今天所有小时（1-24点）的起售价格字段，并重新计算日报和月报" placement="top">
          <el-button type="primary" @click="updateMinPrice" :loading="updatingPrice">
            一键更新当天所有小时起售价格
          </el-button>
        </el-tooltip>
        <span style="color:#999; font-size:13px">填入美团今日客人端最低价，更新后自动重算日报</span>
      </div>
    </el-card>

    <!-- 表格区（下） -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="page-header">
          <span>小时数据</span>
          <div class="header-actions">
            <el-tooltip content="下载当前日期24小时CSV模板文件，已有数据自动预填" placement="bottom"><el-button @click="downloadTemplate" v-if="isAdmin()">📤 模板</el-button></el-tooltip>
            <el-tooltip content="上传CSV文件批量导入小时数据（列：日期,小时,已售,房费,起售价）" placement="bottom"><el-button type="success" @click="triggerUpload" :loading="importing" v-if="isAdmin()">📥 导入</el-button></el-tooltip>
            <el-tooltip content="删除选中的多条小时数据（24点结算数据不可选中删除）" placement="bottom"><el-button type="danger" @click="batchDelete" :disabled="selectedRows.length===0" v-if="isAdmin()">批量删除({{selectedRows.length}})</el-button></el-tooltip>
            <el-tooltip content="用日报数据补全当前日期缺失的24点结算记录" placement="bottom"><el-button type="warning" @click="backfillH24" :loading="backfilling" v-if="isAdmin() && isHistoryDate">🔄 回填h24</el-button></el-tooltip>
            <el-input-number v-model="intervalMinutes" :min="10" :max="1440" :step="10" size="small" style="width:160px" @change="saveInterval" v-if="isAdmin()" />
            <span class="unit-label" v-if="isAdmin()">分钟</span>
            <el-tooltip content="立即从去呼呼PMS拉取当前日期最新客房销售数据并入库" placement="bottom"><el-button type="primary" @click="recordNow" :loading="recording">一键记录</el-button></el-tooltip>
            <el-date-picker v-model="currentDate" type="date" value-format="YYYY-MM-DD" @change="loadData" size="small" />
          </div>
        </div>
      </template>
      <el-table :data="tableData" border stripe size="small" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="40" v-if="isAdmin()" :selectable="row => row.data_hour !== 24" />
        <el-table-column prop="data_hour" label="时间" width="100">
          <template #default="{ row }">
            {{ row.data_hour }}:00
            <el-tag v-if="row.data_hour === 24" type="warning" size="small">当日结算</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sold_rooms" label="已售" width="100" align="right" />
        <el-table-column prop="available_rooms" label="可售" width="100" align="right" />
        <el-table-column prop="occupancy_rate" label="出租率" width="100" align="right">
          <template #default="{ row }">{{ row.occupancy_rate }}%</template>
        </el-table-column>
        <el-table-column prop="min_price" label="起售价格" width="130" align="right">
          <template #default="{ row }">¥{{ row.min_price }}</template>
        </el-table-column>
        <el-table-column prop="revpar" label="单房收益" width="130" align="right">
          <template #default="{ row }">¥{{ row.revpar }}</template>
        </el-table-column>
        <el-table-column prop="adr" label="平均房价" width="130" align="right">
          <template #default="{ row }">¥{{ row.adr }}</template>
        </el-table-column>
        <el-table-column prop="total_revenue" label="累计房费" align="right">
          <template #default="{ row }">¥{{ row.total_revenue }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center" v-if="isAdmin()">
          <template #default="{ row }">
            <el-button v-if="row.id && row.data_hour !== 24" type="danger" size="small" link @click="deleteRow(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import request from '@/api'
import { useRole } from '@/composables/useRole'
const { isAdmin } = useRole()

const isHistoryDate = computed(() => currentDate.value < new Date().toISOString().slice(0, 10))

const currentDate = ref(localDate())
const intervalMinutes = ref(60)
const tableData = ref([])
const chartRef = ref(null)
let chartInstance = null
const recording = ref(false)
const meituanPrice = ref(null)
const updatingPrice = ref(false)
const importing = ref(false)
const backfilling = ref(false)
const selectedRows = ref([])

const onSelectionChange = (rows) => { selectedRows.value = rows }

const loadInterval = async () => {
  try {
    const configs = await request.get('/config/list')
    const item = configs.find(c => c.key === 'collection_interval')
    if (item) intervalMinutes.value = parseInt(item.value) || 60
  } catch { /* ignore */ }
}

const saveInterval = async () => {
  try {
    await request.put('/config', { key: 'collection_interval', value: String(intervalMinutes.value) })
    ElMessage.success('采集间隔已更新')
  } catch { ElMessage.error('保存失败') }
}

const loadData = async () => {
  const all = await request.get('/hourly/list', { params: { date: currentDate.value } })
  // 今天的数据：只显示已过去的小时（含当前小时），未到的时段不展示
  if (!isHistoryDate.value) {
    const nowHour = new Date().getHours()
    tableData.value = all.filter(d => d.data_hour <= nowHour || d.total_revenue > 0)
  } else {
    tableData.value = all
  }
  initChart()
}

const updateMinPrice = async () => {
  if (!meituanPrice.value || meituanPrice.value <= 0) {
    ElMessage.warning('请输入有效的底价')
    return
  }
  updatingPrice.value = true
  try {
    await request.put('/hourly/update-min-price', {
      data_date: currentDate.value,
      min_price: meituanPrice.value
    })
    ElMessage.success(`已更新 ${currentDate.value} 所有小时起售价为 ¥${meituanPrice.value}`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    updatingPrice.value = false
  }
}

const downloadTemplate = () => {
  // 生成当前日期的完整24小时模板，已有数据填入，缺失留空
  const existingMap = {}
  tableData.value.forEach(r => { existingMap[r.data_hour] = r })
  const csv = ['data_date,data_hour,sold_rooms,total_revenue,min_price']
  for (let h = 1; h <= 24; h++) {
    const r = existingMap[h]
    csv.push(`${currentDate.value},${h},${r?.sold_rooms ?? ''},${r?.total_revenue ?? ''},${r?.min_price ?? ''}`)
  }
  const blob = new Blob(['\uFEFF' + csv.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `hourly_template_${currentDate.value}.csv`; a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('模板已下载，编辑后使用📥导入上传')
}

const uploadInput = ref(null)
const triggerUpload = () => {
  if (!uploadInput.value) {
    const input = document.createElement('input')
    input.type = 'file'; input.accept = '.csv'
    input.onchange = (e) => {
      const file = e.target.files[0]
      if (file) doImport(file)
      input.value = ''
    }
    uploadInput.value = input
  }
  uploadInput.value.click()
}

const doImport = async (file) => {
  importing.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const result = await request.post('/hourly/batch-import', form, {
      timeout: 60000
    })
    ElMessage.success(`导入完成: 更新${result.updated}条, 跳过${result.skipped}条`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

const batchDelete = async () => {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedRows.value.length} 条小时数据？`, '批量删除', { type: 'warning' })
  } catch { return }
  for (const row of selectedRows.value) {
    if (row.id) await request.delete(`/hourly/${row.id}`)
  }
  ElMessage.success(`已删除 ${selectedRows.value.length} 条`)
  selectedRows.value = []
  await loadData()
}

const backfillH24 = async () => {
  try {
    await ElMessageBox.confirm(
      `用 ${currentDate.value} 的日报数据回填缺失的24点小时数据？`,
      '回填h24', { type: 'info' }
    )
  } catch { return }
  backfilling.value = true
  try {
    const result = await request.post('/hourly/backfill-h24', null, { params: { date: currentDate.value } })
    if (result.filled > 0) {
      ElMessage.success(`已回填 ${result.filled} 条h24数据`)
    } else {
      ElMessage.info('该日期已有h24数据，无需回填')
    }
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '回填失败')
  } finally {
    backfilling.value = false
  }
}

const recordNow = async () => {
  recording.value = true
  try {
    const result = await request.post('/io/import/auto-collect', null, { 
      params: { date: currentDate.value } 
    })
    ElMessage.success(`采集完成: ${result.total_sold}间, ¥${result.total_revenue}`)
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '采集失败')
  } finally {
    recording.value = false
  }
}

const deleteRow = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除 ${row.data_hour}:00 的数据？`, '确认删除', { type: 'warning' })
  } catch { return }
  try {
    await request.delete(`/hourly/${row.id}`)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

const initChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  const hours = tableData.value.map(d => `${d.data_hour}:00`)
  chartInstance.setOption({
    tooltip: { trigger: 'axis', position: 'top' },
    legend: { data: ['累计房费', '单房收益', '平均房价'] },
    grid: { left: 80, right: 80 },
    xAxis: { type: 'category', data: hours },
    yAxis: [
      { type: 'value', name: '累计房费金额(元)', position: 'left' },
      { type: 'value', name: '单房收益/平均房价(元)', position: 'right' }
    ],
    series: [
      { name: '累计房费', type: 'bar', data: tableData.value.map(d => d.total_revenue), itemStyle: { color: '#1677ff' }, yAxisIndex: 0 },
      { name: '单房收益', type: 'line', data: tableData.value.map(d => d.revpar), itemStyle: { color: '#fa8c16' }, smooth: true, yAxisIndex: 1 },
      { name: '平均房价', type: 'line', data: tableData.value.map(d => d.adr), itemStyle: { color: '#52c41a' }, lineStyle: { type: 'dashed' }, smooth: true, yAxisIndex: 1 }
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: 0 }]
  })
}

const handleResize = () => chartInstance?.resize()

onMounted(async () => {
  await loadInterval()
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
.header-actions { display: flex; gap: 10px; align-items: center; }
.unit-label { font-size: 13px; color: #666; white-space: nowrap; }
</style>
