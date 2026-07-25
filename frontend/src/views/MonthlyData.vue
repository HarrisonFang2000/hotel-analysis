<template>
  <div class="monthly-data">
    <!-- 图表区（上）：默认显示所有月份趋势 -->
    <el-card style="margin-bottom:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>{{ selectedMonth ? `${selectedMonth.data_year}年${selectedMonth.data_month}月 每日明细` : '月报趋势（全部月份）' }}</span>
          <el-tooltip content="返回全部月份的累计房费、RevPar、ADR趋势总览图" placement="left">
            <el-button v-if="selectedMonth" size="small" type="warning" plain @click="selectedMonth=null;renderTrendChart()">
              ← 返回总览
            </el-button>
          </el-tooltip>
        </div>
      </template>
      <div ref="chartRef" style="height:400px"></div>
    </el-card>

    <!-- 表格区（下） -->
    <el-card>
      <template #header>
        <div class="page-header">
          <span>月报数据</span>
          <el-date-picker v-model="year" type="year" value-format="YYYY" @change="loadData" size="small" />
        </div>
      </template>
      <el-table :data="tableData" border stripe size="small" highlight-current-row @row-click="handleRowClick">
        <el-table-column label="周期" width="140">
          <template #default="{row}">{{row.data_year}}年{{row.data_month}}月</template>
        </el-table-column>
        <el-table-column prop="days" label="天数" width="80" align="right" />
        <el-table-column prop="sold_rooms" label="已售房间数" width="130" align="right" />
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
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import request from '@/api'

const year = ref(new Date().getFullYear().toString())
const tableData = ref([])
const allMonthlyData = ref([])
const selectedMonth = ref(null)
const chartRef = ref(null)
let chartInstance = null

const loadData = async () => {
  tableData.value = await request.get('/monthly/list', { params: { year: year.value } })
  // 首次加载全部月份趋势
  if (allMonthlyData.value.length === 0) {
    allMonthlyData.value = await request.get('/monthly/all')
    await nextTick()
    renderTrendChart()
  }
}

const handleRowClick = async (row) => {
  selectedMonth.value = row
  await nextTick()
  await loadDetailChart(row.data_year, row.data_month)
}

// 全部月份趋势图
const renderTrendChart = () => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  
  const data = allMonthlyData.value
  if (data.length === 0) return
  
  const labels = data.map(d => `${d.data_year}-${String(d.data_month).padStart(2,'0')}`)
  chartInstance.setOption({
    tooltip: { trigger: 'axis', position: 'top' },
    legend: { data: ['累计房费', '单房收益', '平均房价'] },
    grid: { left: 80, right: 80, bottom: 60 },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45 } },
    yAxis: [
      { type: 'value', name: '累计房费(元)', position: 'left' },
      { type: 'value', name: '单房收益/平均房价(元)', position: 'right' }
    ],
    series: [
      { name: '累计房费', type: 'bar', data: data.map(d => d.total_revenue), itemStyle: { color: '#1677ff' }, yAxisIndex: 0 },
      { name: '单房收益', type: 'line', data: data.map(d => d.revpar), itemStyle: { color: '#fa8c16' }, smooth: true, yAxisIndex: 1 },
      { name: '平均房价', type: 'line', data: data.map(d => d.adr), itemStyle: { color: '#52c41a' }, lineStyle: { type: 'dashed' }, smooth: true, yAxisIndex: 1 }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, bottom: 0, height: 20 }
    ]
  })
}

// 单击月份→该月每日明细
const loadDetailChart = async (y, m) => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  
  const data = await request.get('/monthly/daily-detail', { params: { year: y, month: m } })
  chartInstance.setOption({
    tooltip: { trigger: 'axis', position: 'top' },
    legend: { data: ['累计房费', '单房收益', '平均房价'] },
    grid: { left: 80, right: 80 },
    xAxis: { type: 'category', data: data.map(d => d.data_date.slice(5)) },
    yAxis: [
      { type: 'value', name: '累计房费(元)', position: 'left' },
      { type: 'value', name: '单房收益/平均房价(元)', position: 'right' }
    ],
    series: [
      { name: '累计房费', type: 'bar', data: data.map(d => d.total_revenue), itemStyle: { color: '#1677ff' }, yAxisIndex: 0 },
      { name: '单房收益', type: 'line', data: data.map(d => d.revpar), itemStyle: { color: '#fa8c16' }, smooth: true, yAxisIndex: 1 },
      { name: '平均房价', type: 'line', data: data.map(d => d.adr), itemStyle: { color: '#52c41a' }, lineStyle: { type: 'dashed' }, smooth: true, yAxisIndex: 1 }
    ],
    dataZoom: [{ type: 'inside' }]
  })
}

const handleResize = () => chartInstance?.resize()
onMounted(() => { loadData(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); chartInstance?.dispose() })
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
</style>
