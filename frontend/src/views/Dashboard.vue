<template>
  <div class="dashboard">
    <!-- 首次使用提示 -->
    <el-alert v-if="isFirstRun" title="🎉 欢迎使用酒店数据分析系统！" type="success" :closable="false" show-icon style="margin-bottom:16px">
      <template #default>
        <p style="margin:4px 0">系统已就绪，请按以下步骤开始使用：</p>
        <ol style="margin:4px 0;padding-left:20px">
          <li>点击左侧菜单「<b>日报数据</b>」→ 点击「<b>自动采集今日</b>」按钮</li>
          <li>系统将通过浏览器自动登录去呼呼 PMS 获取数据</li>
          <li>如需修改密码，点击右上角头像 →「修改密码」</li>
        </ol>
        <p style="margin:4px 0;color:#909399;font-size:12px">
          💡 提示：自动采集需要电脑安装 Edge 或 Chrome 浏览器。<br>
          💡 系统启动后会在任务栏右下角显示托盘图标，关闭浏览器不影响后台运行。
        </p>
      </template>
    </el-alert>

    <!-- 指标卡 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">当日出租率</div>
            <div class="stat-value" style="color: #1677ff">{{ stats.occupancy_rate || 0 }}%</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">已售房间</div>
            <div class="stat-value" style="color: #52c41a">{{ stats.sold_rooms || 0 }} / 113</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">单房收益(RevPar)</div>
            <div class="stat-value" style="color: #fa8c16">¥{{ stats.revpar || 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-label">平均房价(ADR)</div>
            <div class="stat-value" style="color: #722ed1">¥{{ stats.adr || 0 }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图：营收概览 -->
    <el-card class="chart-card">
      <template #header><span>📊 营收趋势（累计房费 · RevPar · ADR）</span></template>
      <div ref="revenueChartRef" class="chart" style="height: 300px"></div>
    </el-card>

    <!-- 趋势图：出租率 -->
    <el-card class="chart-card">
      <template #header><span>📈 出租率趋势</span></template>
      <div ref="occChartRef" class="chart" style="height: 250px"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import request from '@/api'

const revenueChartRef = ref(null)
const occChartRef = ref(null)
let revenueChart = null
let occChart = null
const stats = ref({})
const isFirstRun = ref(false)
const today = localDate()

const initCharts = async () => {
  const raw = await request.get('/chart/hourly/trend', { params: { date: today } })

  // 今天只显示已过去的小时（不含24:00结算点）
  const nowHour = new Date().getHours()
  const maxHour = Math.min(nowHour, 23)  // 23 = 不含24:00
  const idx = (i) => i  // hours 索引 0~23 对应 1:00~24:00
  const slice = (arr) => arr.slice(0, maxHour)
  const data = {
    hours: raw.hours.slice(0, maxHour),
    total_revenue: slice(raw.total_revenue),
    revpar: slice(raw.revpar),
    occupancy_rate: slice(raw.occupancy_rate),
    adr: slice(raw.adr),
  }

  // 检测首次运行
  const hasData = data.total_revenue.some(v => v > 0)
  isFirstRun.value = !hasData

  // 统计卡片数据（取最新有数据的小时）
  let lastIdx = -1
  for (let i = data.total_revenue.length - 1; i >= 0; i--) {
    if (data.total_revenue[i] > 0) { lastIdx = i; break }
  }
  if (lastIdx >= 0) {
    stats.value = {
      occupancy_rate: data.occupancy_rate[lastIdx],
      sold_rooms: data.occupancy_rate[lastIdx] > 0 ? Math.round(data.occupancy_rate[lastIdx] * 113 / 100) : 0,
      revpar: data.revpar[lastIdx],
      adr: data.adr[lastIdx]
    }
  }

  // ---- 营收图：左轴=累计房费(柱) + 右轴=RevPar/ADR(线) ----
  if (revenueChartRef.value) {
    // RevPar/ADR 数据驱动范围——小变化也可见
    const rpVals = data.revpar.filter(v => v > 0)
    const adrVals = data.adr.filter(v => v > 0)
    const allRight = [...rpVals, ...adrVals]
    const rightMin = allRight.length ? Math.floor(Math.min(...allRight) / 10) * 10 : 0
    const rightMax = allRight.length ? Math.ceil(Math.max(...allRight) / 10) * 10 : 300

    revenueChart = echarts.init(revenueChartRef.value)
    revenueChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', crossStyle: { color: '#999' } },
        formatter: params => {
          const h = params[0].axisValue  // 已格式化如 "1:00"
          let s = `<b>${h}</b><br/>`
          params.forEach(p => {
            const v = p.seriesName.includes('率') ? p.value + '%' : '¥' + (p.value || 0)
            s += `${p.marker} ${p.seriesName}: ${v}<br/>`
          })
          return s
        }
      },
      legend: {
        data: ['累计房费', '单房收益(RevPar)', '平均房价(ADR)'],
        top: 0,
        left: 'center'
      },
      grid: { left: 60, right: 70, top: 36, bottom: 20 },
      xAxis: {
        type: 'category',
        data: data.hours,
        axisLabel: { interval: 2, rotate: 0 },
        axisTick: { alignWithLabel: true }
      },
      yAxis: [
        {
          type: 'value',
          name: '累计房费(¥)',
          position: 'left',
          min: 0,
          splitNumber: 5,
          axisLabel: { formatter: v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v },
          splitLine: { lineStyle: { type: 'dashed', color: '#eee' } }
        },
        {
          type: 'value',
          name: 'RevPar/ADR(¥)',
          position: 'right',
          min: rightMin,
          max: rightMax,
          splitNumber: 5,
          axisLabel: { formatter: '¥{value}' }
        }
      ],
      series: [
        {
          name: '累计房费',
          type: 'bar',
          data: data.total_revenue,
          yAxisIndex: 0,
          itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 24
        },
        {
          name: '单房收益(RevPar)',
          type: 'line',
          data: data.revpar,
          yAxisIndex: 1,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2, color: '#fa8c16' },
          itemStyle: { color: '#fa8c16' }
        },
        {
          name: '平均房价(ADR)',
          type: 'line',
          data: data.adr,
          yAxisIndex: 1,
          smooth: true,
          symbol: 'diamond',
          symbolSize: 6,
          lineStyle: { width: 2, type: 'dashed', color: '#722ed1' },
          itemStyle: { color: '#722ed1' }
        }
      ]
    })
  }

  // ---- 出租率图：数据驱动范围 ----
  if (occChartRef.value) {
    const occVals = data.occupancy_rate.filter(v => v > 0)
    const occMin = occVals.length ? Math.floor(Math.min(...occVals) / 5) * 5 : 0
    const occMax = occVals.length ? Math.ceil(Math.max(...occVals) / 5) * 5 + 5 : 100

    occChart = echarts.init(occChartRef.value)
    occChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: p => `<b>${p[0].axisValue}</b><br/>${p[0].marker} 出租率: ${p[0].value}%`
      },
      legend: { data: ['出租率'], top: 0, left: 'center' },
      grid: { left: 55, right: 30, top: 36, bottom: 20 },
      xAxis: {
        type: 'category',
        data: data.hours,
        axisLabel: { interval: 2, rotate: 0 }
      },
      yAxis: {
        type: 'value',
        name: '出租率(%)',
        min: occMin,
        max: occMax,
        splitNumber: 5,
        axisLabel: { formatter: '{value}%' },
        splitLine: { lineStyle: { type: 'dashed', color: '#eee' } }
      },
      series: [
        {
          name: '出租率',
          type: 'line',
          data: data.occupancy_rate,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2.5, color: '#52c41a' },
          itemStyle: { color: '#52c41a' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(82,196,26,0.25)' },
              { offset: 1, color: 'rgba(82,196,26,0.02)' }
            ])
          }
        }
      ]
    })
  }
}

const handleResize = () => {
  revenueChart?.resize()
  occChart?.resize()
}

onMounted(() => {
  initCharts()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  revenueChart?.dispose()
  occChart?.dispose()
})
</script>

<style scoped>
.stat-cards {
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
}
.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
}
.chart-card {
  width: 100%;
}
</style>
