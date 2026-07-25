<template>
  <div class="chart-analysis">
    <!-- ========== 一级菜单 ========== -->
    <el-card style="margin-bottom:12px">
      <el-tabs v-model="mainTab" @tab-change="onMainTabChange">
        <el-tab-pane label="趋势分析" name="trend" />
        <el-tab-pane label="热度矩阵" name="heatmap" />
        <el-tab-pane label="定价象限" name="price" v-if="isAdmin()" />
      </el-tabs>
    </el-card>

    <!-- ========== 二级菜单：维度选择（定价象限不显示） ========== -->
    <el-card v-if="mainTab !== 'price'" style="margin-bottom:12px">
      <el-radio-group v-model="dimension" size="default" @change="onDimensionChange">
        <el-radio-button value="day">日</el-radio-button>
        <el-radio-button value="week">周</el-radio-button>
        <el-radio-button value="month">月</el-radio-button>
        <el-radio-button value="quarter" v-if="isAdmin()">季度</el-radio-button>
        <el-radio-button value="year" v-if="isAdmin()">年</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- ========== 控制区 ========== -->
    <el-card style="margin-bottom:12px">
      <div class="controls">
        <!-- 日期选择栏（定价象限不显示） -->
        <div class="control-row" v-if="dimension !== 'year' && mainTab !== 'price'">
          <span class="label">日期：</span>
          <el-date-picker v-if="dimension === 'day' || dimension === 'week'"
            v-model="selectedDate" type="date" value-format="YYYY-MM-DD"
            @change="reload" size="small" style="width:200px" />
          <el-date-picker v-else-if="dimension === 'month'"
            v-model="selectedMonth" type="month" value-format="YYYY-MM"
            @change="reload" size="small" style="width:200px" />
          <el-date-picker v-else-if="dimension === 'quarter'"
            v-model="selectedQuarterMonth" type="month" value-format="YYYY-MM"
            @change="reload" size="small" style="width:200px" placeholder="选择季度中任一月份" />
        </div>
        <div class="control-row" v-if="dimension === 'year' && mainTab !== 'price'">
          <span class="label">年份：</span>
          <el-date-picker v-model="selectedYear" type="year" value-format="YYYY"
            @change="reload" size="small" style="width:200px" />
        </div>

        <!-- 复选框（热度矩阵和定价象限不显示） -->
        <div class="control-row" v-if="mainTab !== 'heatmap' && mainTab !== 'price'">
          <span class="label">数据：</span>
          <el-checkbox-group v-model="checkedSeries" @change="reload">
            <el-checkbox v-for="s in currentSeries" :key="s.key" :label="s.key" :value="s.key">
              {{ s.label }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
        <!-- 定价象限X轴选择 -->
        <div class="control-row" v-if="mainTab === 'price'">
          <span class="label">X轴指标：</span>
          <el-radio-group v-model="priceXAxis" size="small" @change="reload">
            <el-radio-button value="min_price">起售价格</el-radio-button>
            <el-radio-button value="adr">平均房价(ADR)</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-card>

    <!-- ========== 热度矩阵星期分布切换（月/季度/年） ========== -->
    <el-card v-if="mainTab === 'heatmap' && (dimension === 'month' || dimension === 'quarter' || dimension === 'year')" style="margin-bottom:12px">
      <el-radio-group v-model="heatmapSubView" size="small" @change="reload">
        <el-radio-button value="matrix">热度矩阵</el-radio-button>
        <el-radio-button value="weekday">星期分布</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- ========== 图表区 ========== -->
    <el-card>
      <div ref="chartRef" class="chart-container"></div>
    </el-card>

    <!-- 视图说明卡片（趋势分析所有维度） -->
    <el-card v-if="mainTab === 'trend'" style="margin-top:12px" shadow="never">
      <template #header>
        <span style="font-weight:600">
          📈 {{ {day:'日趋势',week:'周趋势+预测',month:'月趋势+预测',quarter:'季趋势',year:'年趋势'}[dimension] }} 说明
        </span>
        <el-tag v-if="dimension==='week'||dimension==='month'" size="small" type="warning" style="margin-left:8px">含价格预测</el-tag>
      </template>
      <div class="model-explain">

        <!-- 日 -->
        <template v-if="dimension==='day'">
          <p>展示选中日期当天 <b>01:00~24:00</b> 的逐小时数据趋势。</p>
          <ul>
            <li><b>数据来源</b>：去呼呼 PMS 每小时自动采集的客房销售数据</li>
            <li><b>出租率</b>：截至该小时的累计出租率（含钟点房）</li>
            <li><b>起售价格</b>：当天最低可售房价</li>
            <li><b>单房收益 RevPar</b> = 总房费 ÷ 113 间</li>
            <li><b>平均房价 ADR</b> = 总房费 ÷ 已售房间数</li>
            <li>今天只显示已过去的小时，未来时段不展示</li>
          </ul>
        </template>

        <!-- 周 -->
        <template v-if="dimension==='week'">
          <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px">
            <template #title><strong>为什么"周"和"月"对同一天的预测结果不同？</strong></template>
            <ul style="margin:4px 0 0 16px;font-size:13px">
              <li><b>训练数据不同</b>：周维度用<b>最近60天</b>的价格数据训练</li>
              <li><b>短期趋势权重不同</b>：周维度看<b>最近7天</b>变化方向（灵敏度高）</li>
              <li><b>结论</b>：<b>周预测更灵敏</b>（适合短期定价），<b>月预测更稳健</b>（适合中长期参考）</li>
            </ul>
          </el-alert>
          <p>展示 <b>前7天实际数据 + 后7天价格预测</b>。使用<b>五路信号融合模型</b>预测未来起售价格。</p>
          <div class="signal-card"><h4>① 星期规律（20%）</h4><p>统计56天每个星期几的均价，学到"周六比周二贵"等模式。</p></div>
          <div class="signal-card"><h4>② 季节周期（30%）</h4><p>Holt-Winters 三重指数平滑，7天循环，自动选最优参数。</p></div>
          <div class="signal-card"><h4>③ 短期走势（20%）</h4><p>最近7天 vs 前7天价格变化方向，趋势衰减不无限涨跌。</p></div>
          <div class="signal-card"><h4>④ 入住率需求（15%）</h4><p>近7天入住率 vs 前7天，需求旺→上浮最多+10%。</p></div>
          <div class="signal-card" style="border-left-color:#13c2c2"><h4>⑤ ADR定价力（15%）</h4><p>ADR÷起售价比值，>1.05有涨价空间，<0.95打折多。</p></div>
          <el-divider />
          <p style="color:#909399;font-size:13px"><strong>预测 = 星期×20% + 季节×30% + 走势×20% + 需求×15% + ADR×15%</strong> ⚠️ 仅供参考</p>
        </template>

        <!-- 月 -->
        <template v-if="dimension==='month'">
          <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px">
            <template #title><strong>为什么"周"和"月"对同一天的预测结果不同？</strong></template>
            <ul style="margin:4px 0 0 16px;font-size:13px">
              <li><b>训练数据不同</b>：月维度多纳入了<b>当月初到昨天</b>的全部数据</li>
              <li><b>趋势权重不同</b>：月维度看<b>当月至今</b>整体走势（更平滑）</li>
              <li><b>结论</b>：<b>月预测更稳健</b>（适合中长期参考）</li>
            </ul>
          </el-alert>
          <p>展示 <b>当月1日~昨日实际数据 + 后15天价格预测</b>。历史月份显示整月数据。使用<b>五路信号融合模型</b>。</p>
          <div class="signal-card"><h4>① 星期规律（20%）</h4><p>统计56天每个星期几的均价。</p></div>
          <div class="signal-card"><h4>② 季节周期（30%）</h4><p>Holt-Winters 自动检测7天循环，数据越多越准。</p></div>
          <div class="signal-card"><h4>③ 短期走势（20%）</h4><p>当月 vs 上月同期价格变化。</p></div>
          <div class="signal-card"><h4>④ 入住率需求（15%）</h4><p>入住率变化反映需求强弱。</p></div>
          <div class="signal-card" style="border-left-color:#13c2c2"><h4>⑤ ADR定价力（15%）</h4><p>实际成交价 vs 起售价的溢价空间。</p></div>
        </template>

        <!-- 季 -->
        <template v-if="dimension==='quarter'">
          <p>展示选中季度完整 <b>3个月每日数据</b>趋势。当前季度只显示到昨天。</p>
          <ul>
            <li><b>数据来源</b>：日报数据聚合</li>
            <li><b>周期</b>：1~3月(Q1)、4~6月(Q2)、7~9月(Q3)、10~12月(Q4)</li>
            <li><b>用途</b>：季度对比分析，识别淡旺季规律，为定价策略提供季节参考</li>
          </ul>
        </template>

        <!-- 年 -->
        <template v-if="dimension==='year'">
          <p>展示选中年份 <b>12个月月报数据</b>趋势。当前年份只显示已过去的月份。</p>
          <ul>
            <li><b>数据来源</b>：月报数据聚合</li>
            <li><b>横轴</b>：1~12月</li>
            <li><b>用途</b>：年度营收回顾、同比分析、全年趋势概览</li>
          </ul>
        </template>

      </div>
    </el-card>

    <!-- 热度矩阵说明 -->
    <el-card v-if="mainTab === 'heatmap'" style="margin-top:12px" shadow="never">
      <template #header>
        <span style="font-weight:600">🔥 热度矩阵说明 — {{ {day:'日热度',week:'周热度',month:'月热度',quarter:'季热度',year:'年热度'}[dimension] || '' }}</span>
      </template>
      <div class="model-explain">
        <template v-if="dimension==='day'">
          <p>展示 <b>选中日期及前6天 × 24小时</b> 的热度变化矩阵。</p>
          <ul>
            <li><b>纵轴</b>：01:00~24:00（从上到下）</li>
            <li><b>横轴</b>：日期（左旧右新，最新在最右）</li>
            <li><b>颜色含义</b>：蓝色=出租率下降，红色=上升，白色=持平</li>
            <li><b>数值</b>：相邻小时出租率差值（日内导数），01:00为当日基准=0</li>
            <li><b>用途</b>：快速发现哪天哪个时段入住高峰/低谷</li>
          </ul>
        </template>
        <template v-if="dimension==='week'">
          <p>展示 <b>选中日期所在周（周一~周日）</b> 每日售出房间数。</p>
          <ul><li><b>用途</b>：一周内哪几天生意最好</li></ul>
        </template>
        <template v-if="dimension==='month'">
          <p>展示 <b>选中月份每日出租率</b> 热度分布（可选星期分布视图）。</p>
          <ul><li><b>用途</b>：发现星期几入住率高、月初月末出租率规律</li></ul>
        </template>
        <template v-if="dimension==='quarter'">
          <p>展示 <b>选中季度3个月每日出租率</b> 热度分布。</p>
          <ul><li><b>用途</b>：季度内淡旺季识别</li></ul>
        </template>
        <template v-if="dimension==='year'">
          <p>展示 <b>选中年份12个月出租率</b> 热度分布。</p>
          <ul><li><b>用途</b>：全年出租率一览，快速定位旺季/淡季月份</li></ul>
        </template>
      </div>
    </el-card>

    <!-- 定价象限说明 -->
    <el-card v-if="mainTab === 'price'" style="margin-top:12px" shadow="never">
      <template #header>
        <span style="font-weight:600">💰 定价象限 · 四象限分析</span>
        <span v-if="priceStats" style="margin-left:12px;font-size:13px;color:#999">
          共 {{ priceStats.total }} 天 &nbsp;|&nbsp; 均价 ¥{{ priceStats.avgX }} &nbsp;|&nbsp; 均出租率 {{ priceStats.avgOcc }}%
        </span>
      </template>
      <div class="model-explain">
        <p>每个气泡=一天：横轴={{ priceXAxis==='adr'?'ADR':'起售价' }}，纵轴=出租率，大小=收入，颜色=时间远近。</p>
        <el-row :gutter="16" v-if="priceStats">
          <el-col :span="12">
            <div class="signal-card" style="border-left-color:#fa8c16"><h4>⚠️ 低价高入住（{{ priceStats.qTL.count }}天 占{{ priceStats.qTL.revShare }}%）</h4><p>均价 ¥{{ priceStats.qTL.avgPrice }} → 建议提价 ¥{{ priceStats.qTL.suggestRaise }}</p></div>
          </el-col>
          <el-col :span="12">
            <div class="signal-card" style="border-left-color:#52c41a"><h4>✅ 高价高入住（{{ priceStats.qTR.count }}天 占{{ priceStats.qTR.revShare }}%）</h4><p>均价 ¥{{ priceStats.qTR.avgPrice }} → 保持策略</p></div>
          </el-col>
          <el-col :span="12" style="margin-top:8px">
            <div class="signal-card" style="border-left-color:#999"><h4>➖ 低价低入住（{{ priceStats.qBL.count }}天 占{{ priceStats.qBL.revShare }}%）</h4><p>均价 ¥{{ priceStats.qBL.avgPrice }} → 检查渠道/评价</p></div>
          </el-col>
          <el-col :span="12" style="margin-top:8px">
            <div class="signal-card" style="border-left-color:#ff4d4f"><h4>❌ 高价低入住（{{ priceStats.qBR.count }}天 占{{ priceStats.qBR.revShare }}%）</h4><p>均价 ¥{{ priceStats.qBR.avgPrice }} → 建议降至 ¥{{ priceStats.qBR.suggestDrop }} 以下</p></div>
          </el-col>
        </el-row>
        <div v-else style="color:#999;text-align:center;padding:16px">加载中...</div>
        <el-divider />
        <p style="color:#909399;font-size:13px">💡 红色虚线=均值分界线。底部滑块可缩放X轴，hover 气泡查看详情。</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import request from '@/api'
import { useRole } from '@/composables/useRole'
const { isAdmin } = useRole()

const mainTab = ref('trend')
const dimension = ref('day')
const selectedDate = ref(localDate())
const selectedMonth = ref(localDate().slice(0, 7))
const selectedQuarterMonth = ref(localDate().slice(0, 7))
const selectedYear = ref(new Date().getFullYear().toString())
const heatmapSubView = ref('matrix')  // 'matrix' | 'weekday'
const checkedSeries = ref([])
const priceXAxis = ref('min_price')   // 'min_price' | 'adr'
const priceStats = ref(null)          // 四象限统计数据
const chartRef = ref(null)
let chartInstance = null

const onMainTabChange = () => { onDimensionChange() }
const onDimensionChange = () => {
  checkedSeries.value = currentSeries.value.map(s => s.key)
  selectedDate.value = localDate()
  selectedMonth.value = localDate().slice(0, 7)
  selectedQuarterMonth.value = localDate().slice(0, 7)
  selectedYear.value = new Date().getFullYear().toString()
  heatmapSubView.value = 'matrix'
  reload()
}

// ============ 各维度指标定义 ============
const seriesDefs = {
  trend: {
    day: [
      { key: 'occupancy_rate', label: '预售占比' },
      { key: 'min_price', label: '起售价格' },
      { key: 'revpar', label: '单房收益' },
      { key: 'adr', label: '平均房价' },
    ],
    week: [
      { key: 'occupancy_rate', label: '预售占比' },
      { key: 'sold_rooms', label: '售出房间' },
      { key: 'min_price', label: '起售价格' },
      { key: 'revpar', label: '单房收益' },
      { key: 'adr', label: '平均房价' },
      { key: 'predict_price', label: '预测后7天起售价格' },
    ],
    month: [
      { key: 'occupancy_rate', label: '预售占比' },
      { key: 'sold_rooms', label: '售出房间' },
      { key: 'min_price', label: '起售价格' },
      { key: 'revpar', label: '单房收益' },
      { key: 'adr', label: '平均房价' },
      { key: 'predict_price', label: '预测后15天起售价格' },
    ],
    quarter: [
      { key: 'occupancy_rate', label: '预售占比' },
      { key: 'sold_rooms', label: '售出房间' },
      { key: 'min_price', label: '起售价格' },
      { key: 'total_revenue', label: '累计房费' },
      { key: 'adr', label: '平均房价' },
    ],
    year: [
      { key: 'sold_rooms', label: '售出房间' },
      { key: 'total_revenue', label: '累计房费' },
      { key: 'revpar', label: '单房收益' },
      { key: 'adr', label: '平均房价' },
    ],
  },
  price: {
    day: [{ key: 'min_price', label: '起售价格' }, { key: 'occupancy_rate', label: '出租率' }, { key: 'adr', label: '平均房价' }],
    week: [{ key: 'min_price', label: '起售价格' }, { key: 'occupancy_rate', label: '出租率' }, { key: 'adr', label: '平均房价' }],
    month: [{ key: 'min_price', label: '起售价格' }, { key: 'occupancy_rate', label: '出租率' }, { key: 'adr', label: '平均房价' }],
    quarter: [{ key: 'min_price', label: '起售价格' }, { key: 'occupancy_rate', label: '出租率' }, { key: 'adr', label: '平均房价' }],
    year: [{ key: 'sold_rooms', label: '售出房间' }, { key: 'total_revenue', label: '累计房费' }, { key: 'adr', label: '平均房价' }],
  },
}

const currentSeries = computed(() => {
  const defs = seriesDefs[mainTab.value] || seriesDefs.trend
  return defs[dimension.value] || defs.day || []
})

const reload = () => { nextTick(() => { const m = mainTab.value; if (m === 'trend') loadTrend(); else if (m === 'heatmap') loadHeatmap(); else if (m === 'price') loadPrice() }) }

// ============ 工具函数 ============
// ---- Holt-Winters 三重指数平滑（远期季节规律）----
const holtWinters = (data, forecastCount, period = 7, alpha = 0.3, beta = 0.1, gamma = 0.1) => {
  if (!data || data.length < period * 2) {
    if (data.length === 0) return Array(forecastCount).fill(0)
    const avg = data.reduce((a, b) => a + b, 0) / data.length
    return Array(forecastCount).fill(+avg.toFixed(2))
  }
  const n = data.length
  let level = data.slice(0, period).reduce((a, b) => a + b, 0) / period
  let trend = (data.slice(period, period * 2).reduce((a, b) => a + b, 0) / period - level) / period
  const seasonal = []
  for (let i = 0; i < period; i++) seasonal.push(data[i] - level)
  for (let i = 0; i < n; i++) {
    const oldLevel = level
    level = alpha * (data[i] - seasonal[i % period]) + (1 - alpha) * (level + trend)
    trend = beta * (level - oldLevel) + (1 - beta) * trend
    seasonal[i % period] = gamma * (data[i] - level) + (1 - gamma) * seasonal[i % period]
  }
  const forecasts = []
  let l = level, t = trend
  for (let i = 0; i < forecastCount; i++) {
    const f = l + t * (i + 1) + seasonal[(n + i) % period]
    forecasts.push(Math.max(0, +f.toFixed(2)))
  }
  return forecasts
}

// ---- 入住率需求信号：近7天 vs 前7天入住率变化 ----
const computeDemandFactor = (occList) => {
  if (!occList || occList.length < 14) return 1.0
  const valid = occList.filter(v => v != null)
  if (valid.length < 14) return 1.0
  const recent7 = valid.slice(-7), prev7 = valid.slice(-14, -7)
  const rAvg = recent7.reduce((a,b)=>a+b,0) / 7
  const pAvg = prev7.reduce((a,b)=>a+b,0) / 7
  if (pAvg < 0.01) return 1.0  // 防除零及极小值
  const occChange = (rAvg - pAvg) / pAvg  // 入住率变化率
  return Math.max(0.9, Math.min(1.1, 1 + occChange * 0.3))
}

// ---- 五路融合调价模型：HW季节 + DoW分解 + 短期趋势 + 需求信号 + ADR定价力 ----
// data: 历史起售价格数组（旧→新），count: 预测天数，refDow: 今天星期几(0=周日)
// demandFactor: 入住率需求因子(0.9~1.1)，默认1.0
// adrHistory: 历史ADR数组（可选），用于计算定价力信号
const predictPrice = (data, count, refDow = null, demandFactor = 1.0, adrHistory = null) => {
  if (!data || data.length === 0) return Array(count).fill(0)
  if (data.length === 1) return Array(count).fill(+data[0].toFixed(2))

  const n = data.length
  const dow = refDow !== null ? refDow : new Date().getDay()

  // ① Day-of-Week 价格基线（最近56天按星期几分组平均）
  const dowSums = Array(7).fill(0), dowCnt = Array(7).fill(0)
  const lookback = Math.min(56, n)
  for (let i = n - lookback; i < n; i++) {
    const d = ((dow - (n - 1 - i)) % 7 + 7) % 7
    dowSums[d] += data[i]; dowCnt[d]++
  }
  const dowAvg = dowSums.map((s, i) => dowCnt[i] > 0 ? s / dowCnt[i] : null)

  // ② Holt-Winters 远期季节预测（自动参数优化）
  let hwPred = null
  if (n >= 14) {
    const candidates = [
      [0.2,0.1,0.1],[0.3,0.1,0.1],[0.4,0.1,0.1],
      [0.3,0.05,0.1],[0.3,0.2,0.1],[0.3,0.1,0.05],[0.3,0.1,0.2],
    ]
    let best = null, bestErr = Infinity
    for (const [a,b,g] of candidates) {
      let err = 0
      for (let i = 14; i < n; i++) {
        err += Math.abs(holtWinters(data.slice(0,i),1,7,a,b,g)[0] - data[i])
      }
      if (err < bestErr) { bestErr = err; best = [a,b,g] }
    }
    hwPred = holtWinters(data, count, 7, ...best)
  }

  // ③ 短期趋势（近7日均线 + 周趋势外推）
  const recent7 = data.slice(-7)
  const basePrice = recent7.reduce((a,b)=>a+b,0) / 7
  let shortPred = Array(count).fill(+basePrice.toFixed(2))
  if (n >= 14) {
    const first7 = data.slice(-14,-7), last7 = data.slice(-7)
    const dailyTrend = (last7.reduce((a,b)=>a+b,0) - first7.reduce((a,b)=>a+b,0)) / 49
    shortPred = []
    for (let i = 0; i < count; i++) {
      const damping = Math.max(0, 1 - i / count)
      let pred = basePrice + dailyTrend * (i + 1) * damping
      pred = Math.max(basePrice * 0.8, Math.min(basePrice * 1.2, pred))
      shortPred.push(+pred.toFixed(2))
    }
  }

  // ④ DoW预测：每个未来日取对应星期几的历史均价
  const dowPred = []
  for (let i = 0; i < count; i++) {
    const td = (dow + i + 1) % 7
    dowPred.push(dowAvg[td] !== null ? dowAvg[td] : basePrice)
  }

  // ⑤ ADR定价力信号：ADR/起售价比值趋势，反映酒店真实涨价能力
  let adrPower = 1.0
  if (adrHistory && adrHistory.length >= 14) {
    const adrValid = adrHistory.filter(v => v != null && v > 0)
    const priceValid = data.slice(-adrHistory.length).filter((v,i) => adrHistory[i] != null && adrHistory[i] > 0)
    if (adrValid.length >= 14 && priceValid.length >= 14) {
      const recentAdrPrice = []
      for (let i = Math.max(0, adrHistory.length - 14); i < adrHistory.length; i++) {
        if (adrHistory[i] > 0 && data[i]) recentAdrPrice.push(adrHistory[i] / data[i])
      }
      if (recentAdrPrice.length >= 7) {
        const avgRatio = recentAdrPrice.reduce((a,b)=>a+b,0) / recentAdrPrice.length
        // 比值>1说明ADR高于起售价，有涨价空间；<1说明打折严重
        adrPower = Math.max(0.95, Math.min(1.08, avgRatio))
      }
    }
  }

  // ⑥ 五路融合：HW 30% + DoW 20% + 短期 20% + 需求 15% + ADR定价力 15%
  const results = []
  for (let i = 0; i < count; i++) {
    const hw = hwPred ? hwPred[i] : shortPred[i]
    const dw = dowPred[i]
    const st = shortPred[i]
    const demandBase = basePrice * demandFactor
    const blended = 0.30 * hw + 0.20 * dw + 0.20 * st + 0.15 * demandBase + 0.15 * basePrice * adrPower
    results.push(+blended.toFixed(2))
  }
  return results
}

const buildDayRange = (centerDate, from, to, dailyList, predictCount = 0, includeRevenue = false) => {
  const dows = ['周日','周一','周二','周三','周四','周五','周六']
  const xLabels = [], occupancy = [], minPrice = [], revpar = [], sold = [], totalRev = [], adr = []
  for (let i = from; i <= to; i++) {
    const cur = new Date(centerDate); cur.setDate(centerDate.getDate() + i)
    const ds = localDate(cur)
    xLabels.push(ds.slice(5) + '\n' + dows[cur.getDay()])
    const found = dailyList.find(r => r.data_date === ds)
    occupancy.push(found ? found.occupancy_rate : null)
    minPrice.push(found ? found.min_price : null)
    revpar.push(found ? found.revpar : null)
    sold.push(found ? found.sold_rooms : null)
    adr.push(found ? found.adr : null)
    if (includeRevenue) totalRev.push(found ? found.total_revenue : null)
  }
  const validPrices = minPrice.filter(v => v !== null)
  const validOccs = occupancy.filter(v => v !== null)
  const validAdrs = adr.filter(v => v !== null)
  const demandFactor = computeDemandFactor(validOccs)
  const predictions = predictPrice(validPrices, predictCount, centerDate.getDay(), demandFactor, validAdrs)
  const predLabels = [], predData = []
  for (let i = 0; i < predictCount; i++) {
    const cur = new Date(centerDate); cur.setDate(centerDate.getDate() + to + i + 1)
    const ds = localDate(cur)
    predLabels.push(ds.slice(5) + '\n' + dows[cur.getDay()])
    predData.push(predictions[i])
  }
  return { xLabels, occupancy_rate: occupancy, min_price: minPrice, revpar, sold_rooms: sold,
    total_revenue: includeRevenue ? totalRev : [], adr, predictLabels: predLabels, predict_price: predData, predictCount }
}

// ============ 颜色与名称 ============
const seriesColors = { occupancy_rate: '#1677ff', min_price: '#fa8c16', revpar: '#52c41a', sold_rooms: '#722ed1', total_revenue: '#eb2f96', predict_price: '#ff4d4f', adr: '#13c2c2' }
const seriesNames = { occupancy_rate: '出租率(%)', min_price: '起售价格(¥)', revpar: '单房收益(¥)', sold_rooms: '售出房间', total_revenue: '累计房费(¥)', predict_price: '预测起售价(¥)', adr: '平均房价(¥)' }
const primaryKey = { day: 'revpar', week: 'revpar', month: 'revpar', quarter: 'total_revenue', year: 'total_revenue' }

// ============ 1. 趋势分析 ============
const loadTrend = async () => {
  if (!chartRef.value) return
  const dim = dimension.value
  const today = localDate()
  const date = selectedDate.value || today
  const d = new Date(date)
  let data = { xLabels: [] }

  if (dim === 'day') {
    try {
      const hourly = await request.get('/hourly/list', { params: { date } })
      // 今天只显示已过去的小时，历史日期显示全部
      const isToday = (date === today)
      const nowHour = new Date().getHours()
      const filtered = isToday ? hourly.filter(h => h.data_hour <= nowHour) : hourly
      data = { xLabels: filtered.map(h => `${h.data_hour}:00`), occupancy_rate: filtered.map(h => h.occupancy_rate), min_price: filtered.map(h => h.min_price), revpar: filtered.map(h => h.revpar), adr: filtered.map(h => h.adr) }
    } catch(e) { console.error('day load error:', e) }
  } else if (dim === 'week') {
    // ★ 周预测：取60天数据训练，显示前7天实际(到昨天) + 后7天预测
    const isToday = date === today
    // 日报只到昨天，所以用昨天作为实际数据截止日
    const yesterday = new Date(d); yesterday.setDate(d.getDate() - 1)
    const realEnd = isToday ? -1 : 7  // 今天: 截止昨天; 历史: 截止+7天
    const trainStart = new Date(d); trainStart.setDate(d.getDate() - 60)
    const queryEnd = localDate(isToday ? yesterday : new Date(d.getTime() + 7 * 86400000))
    try {
      const daily = await request.get('/daily/list', { params: { start_date: localDate(trainStart), end_date: queryEnd } })
      // 提取60天实际值用于训练（截止昨天）
      const allPrices = [], allOccs = []
      for (let i = -60; i <= realEnd; i++) {
        const cur = new Date(d); cur.setDate(d.getDate() + i); const ds = localDate(cur)
        const found = daily.find(r => r.data_date === ds)
        allPrices.push(found ? found.min_price : null)
        allOccs.push(found ? found.occupancy_rate : null)
      }
      const validPrices = allPrices.filter(v => v !== null)
      const predictCount = isToday ? 7 : 0
      const demandFactor = computeDemandFactor(allOccs)
      const predictions = predictPrice(validPrices, predictCount, d.getDay(), demandFactor)
      // 显示前7天实际(到昨天) + 预测
      data = buildDayRange(d, -7, realEnd, daily, predictCount)
      if (predictCount > 0) {
        data.predict_price = predictions
        data.predictLabels = []
        for (let i = 0; i < predictCount; i++) {
          const cur = new Date(d); cur.setDate(d.getDate() + i + 1)
          data.predictLabels.push(localDate(cur).slice(5))
        }
      }
    } catch(e) { console.error('week load error:', e) }
  } else if (dim === 'month') {
    // ★ 月：当前月显示1日~昨日 + 预测后15天，历史月显示整月
    const selMonth = selectedMonth.value || today.slice(0, 7)
    const [my, mm] = selMonth.split('-').map(Number)
    const daysInMonth = new Date(my, mm, 0).getDate()
    const monthEnd = `${my}-${String(mm).padStart(2, '0')}-${daysInMonth}`
    const isCurrentMonth = (selMonth === today.slice(0, 7))
    const trainStart = new Date(my, mm - 1, 1)
    trainStart.setDate(trainStart.getDate() - 60)
    // 日报只到昨天，当前月查询截止昨天
    const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1)
    const queryEnd = isCurrentMonth ? localDate(yesterday) : monthEnd
    try {
      const daily = await request.get('/daily/list', { params: { start_date: localDate(trainStart), end_date: queryEnd } })
      // 当前月只到昨天，历史月显示整月
      const endDay = isCurrentMonth ? yesterday.getDate() : daysInMonth
      const xLabels = []; const occ = []; const price = []; const rp = []; const sold = []; const rev = []; const adrVals = []
      const dows = ['周日','周一','周二','周三','周四','周五','周六']
      for (let d = 1; d <= endDay; d++) {
        const ds = `${my}-${String(mm).padStart(2, '0')}-${String(d).padStart(2, '0')}`
        const dt = new Date(my, mm-1, d)
        xLabels.push(`${mm}月${d}日\n${dows[dt.getDay()]}`)
        const found = daily.find(r => r.data_date === ds)
        occ.push(found ? found.occupancy_rate : null)
        price.push(found ? found.min_price : null)
        rp.push(found ? found.revpar : null)
        sold.push(found ? found.sold_rooms : null)
        rev.push(found ? found.total_revenue : null)
        adrVals.push(found ? found.adr : null)
      }
      data = { xLabels, occupancy_rate: occ, min_price: price, revpar: rp, sold_rooms: sold, total_revenue: rev, adr: adrVals }
      // 当前月：用已有数据预测后15天
      if (isCurrentMonth) {
        const validPrices = price.filter(v => v !== null)
        const validOccs = occ.filter(v => v !== null)
        const validAdrs = adrVals.filter(v => v !== null && v > 0)
        const demandFactor = computeDemandFactor(validOccs)
        const predictions = predictPrice(validPrices, 15, new Date(today).getDay(), demandFactor, validAdrs)
        data.predict_price = predictions
        data.predictLabels = []
        const todayDate = new Date(today)
        for (let i = 0; i < 15; i++) {
          const cur = new Date(todayDate); cur.setDate(todayDate.getDate() + i + 1)
          data.predictLabels.push(localDate(cur).slice(5))
        }
      }
    } catch(e) { console.error('month load error:', e) }
  } else if (dim === 'quarter') {
    // ★ 季度：展示选中季度每日数据（3个月），当前季度只到昨天
    const selQ = selectedQuarterMonth.value || today.slice(0, 7)
    const [qy, qm] = selQ.split('-').map(Number)
    const quarter = Math.floor((qm - 1) / 3) + 1
    const startM = (quarter - 1) * 3 + 1
    const endM = startM + 2
    const qStart = `${qy}-${String(startM).padStart(2, '0')}-01`
    const qEndDay = new Date(qy, endM, 0).getDate()
    const qEnd = `${qy}-${String(endM).padStart(2, '0')}-${qEndDay}`
    // 当前季度只查询到昨天
    const isCurrentQ = (selQ.slice(0, 7) === today.slice(0, 7)) || 
      (qy === new Date().getFullYear() && quarter === Math.floor((new Date().getMonth())/3)+1)
    const yesterday = new Date(); yesterday.setDate(yesterday.getDate() - 1)
    const queryEnd = isCurrentQ ? localDate(yesterday) : qEnd
    try {
      const daily = await request.get('/daily/list', { params: { start_date: qStart, end_date: queryEnd } })
      const xLabels = []; const occ = []; const price = []; const rp = []; const sold = []; const rev = []; const adrVals = []
      const endDate = isCurrentQ ? yesterday : new Date(qEnd)
      const dows = ['周日','周一','周二','周三','周四','周五','周六']
      for (let cur = new Date(qStart); cur <= endDate; cur.setDate(cur.getDate() + 1)) {
        const ds = localDate(cur)
        xLabels.push(ds.slice(5) + '\n' + dows[cur.getDay()])
        const found = daily.find(r => r.data_date === ds)
        occ.push(found ? found.occupancy_rate : null)
        price.push(found ? found.min_price : null)
        rp.push(found ? found.revpar : null)
        sold.push(found ? found.sold_rooms : null)
        rev.push(found ? found.total_revenue : null)
        adrVals.push(found ? found.adr : null)
      }
      data = { xLabels, occupancy_rate: occ, min_price: price, revpar: rp, sold_rooms: sold, total_revenue: rev, adr: adrVals }
    } catch(e) { console.error('quarter load error:', e) }
  } else if (dim === 'year') {
    // ★ 年：展示选中年份12个月月报数据（含本月）
    const selYear = parseInt(selectedYear.value) || new Date().getFullYear()
    try {
      const monthly = await request.get('/monthly/list', { params: { year: selYear } })
      const arr = Array.isArray(monthly) ? monthly : []
      const xLabels = Array.from({ length: 12 }, (_, i) => `${i + 1}月`)
      const sold = []; const rev = []; const rp = []; const occ = []; const adrVals = []
      // 当前年份：只显示已过去的月份，未来月份用 null（图表不连接）
      const isThisYear = (selYear === new Date().getFullYear())
      const thisMonth = new Date().getMonth() + 1
      for (let m = 1; m <= 12; m++) {
        if (isThisYear && m > thisMonth) {
          sold.push(null); rev.push(null); rp.push(null); occ.push(null); adrVals.push(null)
          continue
        }
        const found = arr.find(r => r.data_month === m)
        sold.push(found ? found.sold_rooms : null)
        rev.push(found ? found.total_revenue : null)
        rp.push(found ? found.revpar : null)
        occ.push(found ? found.occupancy_rate : null)
        adrVals.push(found ? found.adr : null)
      }
      data = { xLabels, sold_rooms: sold, total_revenue: rev, revpar: rp, occupancy_rate: occ, adr: adrVals }
    } catch(e) {
      console.error('year load error:', e)
      data = { xLabels: ['加载失败'] }
    }
  }
  renderMultiSeries(data)
}

// ============ 2. 热度矩阵（真正的2D热力图）============
const loadHeatmap = async () => {
  if (!chartRef.value) return
  const dim = dimension.value

  // 月/季度/年：支持切换到星期分布视图
  if ((dim === 'month' || dim === 'quarter' || dim === 'year') && heatmapSubView.value === 'weekday') {
    return loadHeatmapWeekday()
  }

  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  const today = localDate()

  try {
    if (dim === 'day') {
      // 日：选中日期及前6天 × 24小时，热度=日内出租率变化（导数），01:00为当日基准
      const selDate = selectedDate.value || today
      const d = new Date(selDate)
      const dows = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
      const days = []
      for (let i = -6; i <= 0; i++) {
        const cur = new Date(d); cur.setDate(d.getDate() + i)
        days.push(localDate(cur))
      }
      const allHourly = []
      for (const day of days) {
        try { const h = await request.get('/hourly/list', { params: { date: day } }); allHourly.push(h) }
        catch { allHourly.push([]) }
      }
      const hours = Array.from({ length: 24 }, (_, i) => `${i + 1}:00`)
      // X轴标签：日期+星期
      const dayLabels = days.map(dd => {
        const dt = new Date(dd)
        return dd.slice(5) + ' ' + dows[dt.getDay()]
      })
      // 热度 = 日内相邻小时出租率差值（导数），01:00 基准=0
      const heatData = []
      for (let hi = 0; hi < 24; hi++) {
        for (let di = 0; di < 7; di++) {
          const curr = allHourly[di]?.[hi]
          const prev = hi > 0 ? allHourly[di]?.[hi - 1] : null
          const currOcc = curr?.occupancy_rate || 0
          const prevOcc = prev?.occupancy_rate || 0
          const delta = prev ? (currOcc - prevOcc) : 0  // 01:00 基准=0
          heatData.push([di, hi, Math.round(delta * 10) / 10])
        }
      }
      const absMax = Math.max(...heatData.map(d => Math.abs(d[2])), 1)
      renderHeatmap2D(dayLabels, hours, heatData, -absMax, absMax, 'delta')
    } else if (dim === 'week') {
      // 周：选中日期所在周（周一到周日）
      const selDate = selectedDate.value || today
      const d = new Date(selDate)
      const dayOfWeek = d.getDay() || 7 // 周日=7
      const monday = new Date(d); monday.setDate(d.getDate() - dayOfWeek + 1)
      const dayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
      const heatData = []
      for (let di = 0; di < 7; di++) {
        const cur = new Date(monday); cur.setDate(monday.getDate() + di)
        const ds = localDate(cur)
        try {
          const daily = await request.get('/daily/list', { params: { start_date: ds, end_date: ds } })
          heatData.push([di, 0, daily?.[0]?.sold_rooms || 0])
        } catch { heatData.push([di, 0, 0]) }
      }
      const maxVal = Math.max(...heatData.map(d => d[2]), 1)
      renderHeatmap2D(dayLabels, ['售出房间'], heatData, 0, maxVal)
    } else if (dim === 'month') {
      // 月：选中月份每日出租率
      const selMonth = selectedMonth.value || today.slice(0, 7)
      const [y, m] = selMonth.split('-').map(Number)
      const daysInMonth = new Date(y, m, 0).getDate()
      const startStr = `${y}-${String(m).padStart(2, '0')}-01`
      const endStr = `${y}-${String(m).padStart(2, '0')}-${daysInMonth}`
      const daily = await request.get('/daily/list', { params: { start_date: startStr, end_date: endStr } })
      const dayLabels = Array.from({ length: daysInMonth }, (_, i) => `${i + 1}日`)
      const heatData = []
      for (let i = 0; i < daysInMonth; i++) {
        const ds = `${y}-${String(m).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`
        const found = daily.find(r => r.data_date === ds)
        heatData.push([i, 0, found ? found.occupancy_rate : 0])
      }
      renderHeatmap2D(dayLabels, ['出租率%'], heatData, 0, 100)
    } else if (dim === 'quarter') {
      // 季度：选中月份所属季度（3个月每日出租率）
      const selQ = selectedQuarterMonth.value || today.slice(0, 7)
      const [qy, qm] = selQ.split('-').map(Number)
      const quarter = Math.floor((qm - 1) / 3) + 1
      const startM = (quarter - 1) * 3 + 1
      const monthLabels = []
      const allDays = []
      for (let m = startM; m < startM + 3; m++) {
        monthLabels.push(`${m}月`)
        const daysInM = new Date(qy, m, 0).getDate()
        const s = `${qy}-${String(m).padStart(2, '0')}-01`
        const e = `${qy}-${String(m).padStart(2, '0')}-${daysInM}`
        try { const d = await request.get('/daily/list', { params: { start_date: s, end_date: e } }); allDays.push(d) }
        catch { allDays.push([]) }
      }
      const maxDays = Math.max(...allDays.map(d => d.length), 1)
      const dayLabels = Array.from({ length: maxDays }, (_, i) => `${i + 1}日`)
      const heatData = []
      for (let di = 0; di < maxDays; di++) {
        for (let mi = 0; mi < 3; mi++) {
          const row = allDays[mi]?.[di]
          heatData.push([mi, di, row ? row.occupancy_rate : null])
        }
      }
      renderHeatmap2D(monthLabels, dayLabels, heatData, 0, 100)
    } else if (dim === 'year') {
      // 年：选中年份12个月出租率
      const selYear = selectedYear.value || new Date().getFullYear().toString()
      const y = parseInt(selYear)
      const monthly = await request.get('/monthly/list', { params: { year: y } })
      const monthLabels = Array.from({ length: 12 }, (_, i) => `${i + 1}月`)
      const heatData = []
      for (let i = 0; i < 12; i++) {
        const found = (monthly || []).find(r => r.data_month === i + 1)
        heatData.push([i, 0, found ? found.occupancy_rate : 0])
      }
      renderHeatmap2D(monthLabels, ['出租率%'], heatData, 0, 100)
    }
  } catch (e) {
    console.error('Heatmap error:', e)
    chartInstance.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } })
  }
}

// 热度矩阵-星期分布视图（月/季度/年维度）网格：横轴=日期，纵轴=星期几
const loadHeatmapWeekday = async () => {
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  const dim = dimension.value
  const today = localDate()
  const weekNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

  try {
    let startStr, endStr, titleSuffix
    if (dim === 'month') {
      const sel = selectedMonth.value || today.slice(0, 7)
      const [y, m] = sel.split('-').map(Number)
      const days = new Date(y, m, 0).getDate()
      startStr = `${y}-${String(m).padStart(2, '0')}-01`
      endStr = `${y}-${String(m).padStart(2, '0')}-${days}`
      titleSuffix = `${y}年${m}月`
    } else if (dim === 'quarter') {
      const sel = selectedQuarterMonth.value || today.slice(0, 7)
      const [y, m] = sel.split('-').map(Number)
      const q = Math.floor((m - 1) / 3) + 1
      const sm = (q - 1) * 3 + 1
      const em = sm + 2
      startStr = `${y}-${String(sm).padStart(2, '0')}-01`
      const lastDay = new Date(y, em, 0).getDate()
      endStr = `${y}-${String(em).padStart(2, '0')}-${lastDay}`
      titleSuffix = `${y}年Q${q}`
    } else {
      const y = parseInt(selectedYear.value) || new Date().getFullYear()
      startStr = `${y}-01-01`; endStr = `${y}-12-31`
      titleSuffix = `${y}年`
    }

    const daily = await request.get('/daily/list', { params: { start_date: startStr, end_date: endStr } })
    if (!daily || daily.length === 0) {
      chartInstance.setOption({ title: { text: '暂无数据', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } })
      return
    }

    // 构建日期→指标映射
    const dateMap = {}
    daily.forEach(r => { dateMap[r.data_date] = r })

    // 确定日期范围和网格
    const d1 = new Date(startStr)
    const d2 = new Date(endStr)
    const totalDays = Math.floor((d2 - d1) / 86400000) + 1

    // 计算需要多少列（按周分组）
    // 找到起始日是周几，补全前面空格
    const startDayOfWeek = d1.getDay() || 7 // 周一=1 ... 周日=7
    // 列数 = 完整周数 * 7，取足够覆盖所有日期的列数
    const weeks = Math.ceil((totalDays + startDayOfWeek - 1) / 7)
    const cols = weeks

    // 列标签：用每周的起始日期
    const colLabels = []
    const heatData = []
    let maxVal = 1

    for (let w = 0; w < weeks; w++) {
      const weekStart = new Date(d1)
      weekStart.setDate(d1.getDate() - (startDayOfWeek - 1) + w * 7)
      colLabels.push(localDate(weekStart).slice(5)) // MM-DD

      for (let dow = 0; dow < 7; dow++) {
        const cellDate = new Date(weekStart)
        cellDate.setDate(weekStart.getDate() + dow)
        const ds = localDate(cellDate)
        const found = dateMap[ds]
        // 检查日期是否在范围内
        if (cellDate >= d1 && cellDate <= d2 && found) {
          const val = found.occupancy_rate || 0
          heatData.push([w, dow, val, ds]) // 附带实际日期 YYYY-MM-DD
          if (val > maxVal) maxVal = val
        }
      }
    }

    renderHeatmap2D(colLabels, weekNames, heatData, 0, Math.max(maxVal, 100))
  } catch (e) {
    console.error('Weekday heatmap error:', e)
    chartInstance.setOption({ title: { text: '加载失败', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } })
  }
}

const renderHeatmap2D = (xLabels, yLabels, data, min, max, mode = 'normal') => {
  const dateMap = {}
  const cleanData = data.filter(d => d[2] != null).map(d => {
    if (d[3]) dateMap[`${d[0]}_${d[1]}`] = d[3]
    return [d[0], d[1], d[2]]
  })
  const isDelta = (mode === 'delta')
  const isOcc = (mode === 'occupancy')

  // delta 分段色阶
  const piecewiseDelta = {
    pieces: [
      { min: -999, max: -5, color: '#0033cc', label: '↓≥5%' },
      { min: -5, max: -2, color: '#3366ee', label: '↓2~5%' },
      { min: -2, max: -0.5, color: '#88aaff', label: '↓0.5~2%' },
      { min: -0.5, max: 0.5, color: '#f5f5f5', label: '≈0' },
      { min: 0.5, max: 2, color: '#ffaa88', label: '↑0.5~2%' },
      { min: 2, max: 5, color: '#ee5533', label: '↑2~5%' },
      { min: 5, max: 999, color: '#cc1100', label: '↑≥5%' },
    ],
  }

  // 出租率分段色阶——每段颜色鲜明跳变
  const occPieces = {
    pieces: [
      { min: -999, max: 10, color: '#e8f5e9', label: '0-10%' },
      { min: 10, max: 25, color: '#a5d6a7', label: '10-25%' },
      { min: 25, max: 40, color: '#4caf50', label: '25-40%' },
      { min: 40, max: 55, color: '#ffeb3b', label: '40-55%' },
      { min: 55, max: 70, color: '#ff9800', label: '55-70%' },
      { min: 70, max: 85, color: '#f44336', label: '70-85%' },
      { min: 85, max: 100, color: '#b71c1c', label: '85-100%' },
    ],
  }

  const visualMap = isDelta
    ? {
        type: 'piecewise',
        pieces: piecewiseDelta.pieces,
        orient: 'horizontal', left: 'center', bottom: 5,
        textStyle: { color: '#333', fontSize: 10 },
        itemWidth: 18, itemHeight: 12,
      }
    : isOcc
    ? {
        type: 'piecewise',
        pieces: occPieces.pieces,
        orient: 'horizontal', left: 'center', bottom: 5,
        textStyle: { color: '#333', fontSize: 10 },
        itemWidth: 16, itemHeight: 12,
      }
    : {
        min, max, calculable: true,
        orient: 'horizontal', left: 'center', bottom: 5,
        textStyle: { color: '#333' },
        inRange: { color: ['#0a3d8f', '#3b7dd8', '#8ab8f0', '#ffffff', '#f5a0a0', '#e84545', '#b0121a'] }
      }

  chartInstance.setOption({
    tooltip: {
      confine: true,
      position: 'top',
      formatter: p => {
        const val = p.value[2]
        const ds = dateMap[`${p.value[0]}_${p.value[1]}`] || ''
        const label = isDelta ? '出租率变化' : '出租率'
        if (ds && ds.length === 10) {
          const dt = new Date(ds)
          const dows = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
          const vStr = val != null ? (isDelta ? (val > 0 ? '+' : '') + val.toFixed(1) + '%' : val.toFixed(1) + '%') : '-'
          return `${ds.slice(5)} ${dows[dt.getDay()]} ${xLabels[p.value[0]]?.replace(/.* /,'') || ''}<br/>${label}: ${vStr}`
        }
        // X轴标签可能已含日期+星期，直接展示
        const xl = xLabels[p.value[0]] || ''
        const yl = yLabels[p.value[1]] || ''
        const vStr = val != null ? val.toFixed(1) : '-'
        return `${xl} / ${yl}<br/>值: ${vStr}`
      }
    },
    grid: { left: 60, right: 30, top: 20, bottom: 70 },
    xAxis: { type: 'category', data: xLabels, axisLabel: { rotate: xLabels.length > 10 ? 45 : 0 } },
    yAxis: { type: 'category', data: yLabels },
    visualMap,
    series: [{
      type: 'heatmap',
      data: cleanData,
      itemStyle: { borderWidth: 0.5, borderColor: '#e8e8e8' },
      label: { show: cleanData.length <= 50, formatter: p => p.value[2] != null ? (isDelta ? (p.value[2] > 0 ? '+' : '') + p.value[2].toFixed(0) : p.value[2].toFixed(0)) : '' },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } }
    }],
  })
}


// ============ 4. 定价象限（优化版：气泡大小=收入，颜色=时间，四象限含决策建议）============
const loadPrice = async () => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)
  const today = localDate()
  const todayDate = new Date(today)

  const useAdr = priceXAxis.value === 'adr'
  const xLabel = useAdr ? '平均房价 ADR (¥)' : '起售价格 (¥)'

  try {
    const daily = await request.get('/daily/list', { params: { start_date: '2020-01-01', end_date: today } })
    
    // 构建散点数据：[x, y, 日期, 起售价, adr, 收入, 距今天数]
    const raw = daily
      .filter(r => {
        const xVal = useAdr ? r.adr : r.min_price
        return xVal > 0 && r.occupancy_rate > 0 && r.total_revenue > 0
      })
      .map(r => {
        const xVal = useAdr ? r.adr : r.min_price
        const daysAgo = Math.floor((todayDate - new Date(r.data_date)) / 86400000)
        return [xVal, r.occupancy_rate, r.data_date, r.min_price, r.adr, r.total_revenue, daysAgo]
      })

    if (raw.length === 0) {
      chartInstance.setOption({ title: { text: '暂无数据', left: 'center', top: 'center' } })
      return
    }

    // 统计数据
    const xVals = raw.map(d => d[0])
    const avgX = xVals.reduce((a,b)=>a+b,0) / xVals.length
    const occs = raw.map(d => d[1])
    const avgOcc = occs.reduce((a,b)=>a+b,0) / occs.length
    const maxX = Math.max(...xVals) * 1.15
    const revenues = raw.map(d => d[5])
    const maxRev = Math.max(...revenues, 1)
    const minRev = Math.min(...revenues, 1)

    // 气泡大小映射（收入越高气泡越大）
    const bubbleSize = (rev) => 5 + (rev - minRev) / (maxRev - minRev || 1) * 25

    // 颜色：越近越深蓝，越远越浅灰
    const maxDays = Math.max(...raw.map(d => d[6]), 1)
    const dotColor = (daysAgo) => {
      const t = Math.min(daysAgo / maxDays, 1)
      const r = Math.round(22 + t * 180)
      const g = Math.round(119 + t * 80)
      const b = Math.round(255 - t * 100)
      return `rgba(${r},${g},${b},${0.5 + (1-t)*0.4})`
    }

    const scatterData = raw.map(d => ({
      value: [d[0], d[1], d[5], d[2], d[3], d[4], d[6]],
      symbolSize: bubbleSize(d[5]),
      itemStyle: { color: dotColor(d[6]), borderColor: '#fff', borderWidth: 1 }
    }))

    // 找出今日数据点
    const todayPt = raw.find(d => d[2] === today)
    
    // 四象限收入分析
    const qTR = raw.filter(d => d[0] >= avgX && d[1] >= avgOcc) // 高价高入住
    const qTL = raw.filter(d => d[0] < avgX && d[1] >= avgOcc)  // 低价高入住
    const qBR = raw.filter(d => d[0] >= avgX && d[1] < avgOcc)  // 高价低入住
    const qBL = raw.filter(d => d[0] < avgX && d[1] < avgOcc)   // 低价低入住
    const sumRev = (arr) => arr.reduce((s,d)=>s+d[5],0)
    const avgPrice = (arr) => arr.length ? arr.reduce((s,d)=>s+d[0],0)/arr.length : 0

    chartInstance.setOption({
      tooltip: {
        trigger: 'item',
        formatter: p => {
          const d = p.value
          const dows = ['周日','周一','周二','周三','周四','周五','周六']
          const dt = new Date(d[3])
          return `<b>${d[3]} ${dows[dt.getDay()]}</b>${d[3]===today?' 🔴今日':''}<br/>
                  起售价: ¥${d[4]} &nbsp; ADR: ¥${d[5]}<br/>
                  出租率: ${d[1]}% &nbsp; 收入: ¥${Number(d[2]).toLocaleString()}<br/>
                  距今: ${d[6]}天`
        }
      },
      legend: {
        data: ['今日', '近7天', '近30天', '更早'],
        bottom: 0,
        selectedMode: false
      },
      grid: { left: 75, right: 55, top: 55, bottom: 70 },
      xAxis: { name: xLabel, type: 'value', min: 0, max: maxX, splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } } },
      yAxis: { name: '出租率(%)', type: 'value', min: 0, max: 105, splitLine: { show: true, lineStyle: { type: 'dashed', color: '#eee' } } },
      series: [{
        type: 'scatter',
        data: scatterData,
        markLine: {
          silent: true, symbol: 'none',
          data: [
            { xAxis: avgX, label: { formatter: `均价 ¥${avgX.toFixed(0)}`, position: 'end' }, lineStyle: { type: 'dashed', color: '#ff4d4f', width: 2 } },
            { yAxis: avgOcc, label: { formatter: `均出租率 ${avgOcc.toFixed(1)}%`, position: 'end' }, lineStyle: { type: 'dashed', color: '#fa8c16', width: 2 } },
          ]
        },
        markArea: {
          silent: true,
          data: [
            [{ xAxis: avgX, yAxis: avgOcc, itemStyle: { color: 'rgba(82,196,26,0.08)' } }, { itemStyle: { color: 'rgba(82,196,26,0.08)' } }],
            [{ yAxis: avgOcc, itemStyle: { color: 'rgba(250,140,22,0.06)' } }, { xAxis: avgX, itemStyle: { color: 'rgba(250,140,22,0.06)' } }],
            [{ xAxis: avgX, itemStyle: { color: 'rgba(255,77,79,0.05)' } }, { yAxis: avgOcc, itemStyle: { color: 'rgba(255,77,79,0.05)' } }],
            [{ itemStyle: { color: 'rgba(22,119,255,0.03)' } }, { xAxis: avgX, yAxis: avgOcc, itemStyle: { color: 'rgba(22,119,255,0.03)' } }],
          ]
        }
      }],
      dataZoom: [
        { type: 'inside', xAxisIndex: 0 }, { type: 'inside', yAxisIndex: 0 },
        { type: 'slider', xAxisIndex: 0, bottom: 8, height: 16 },
      ],
    })

    // 将四象限统计数据暴露给模板
    priceStats.value = {
      avgX: avgX.toFixed(0), avgOcc: avgOcc.toFixed(1), total: raw.length,
      qTR: { count: qTR.length, avgPrice: avgPrice(qTR).toFixed(0), revShare: (sumRev(qTR)/sumRev(raw)*100).toFixed(0) },
      qTL: { count: qTL.length, avgPrice: avgPrice(qTL).toFixed(0), revShare: (sumRev(qTL)/sumRev(raw)*100).toFixed(0), suggestRaise: Math.round(avgX - avgPrice(qTL)) },
      qBR: { count: qBR.length, avgPrice: avgPrice(qBR).toFixed(0), revShare: (sumRev(qBR)/sumRev(raw)*100).toFixed(0), suggestDrop: Math.round(avgX) },
      qBL: { count: qBL.length, avgPrice: avgPrice(qBL).toFixed(0), revShare: (sumRev(qBL)/sumRev(raw)*100).toFixed(0) },
    }
  } catch { chartInstance.setOption({ title: { text: '暂无数据', left: 'center', top: 'center' } }) }
}

// ============ 通用多系列图表渲染 ============
const renderMultiSeries = (data, chartTitle = '') => {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const checked = checkedSeries.value
  if (!checked || checked.length === 0) {
    chartInstance.setOption({ title: { text: '请选择要显示的数据', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } })
    return
  }

  const isPercent = k => k === 'occupancy_rate'
  const isCount = k => k === 'sold_rooms'
  const isMoney = k => ['min_price', 'revpar', 'total_revenue', 'predict_price', 'adr'].includes(k)

  let allLabels = [...(data.xLabels || [])]
  if (data.predictLabels && data.predictLabels.length > 0) allLabels = [...allLabels, ...data.predictLabels]

  const series = [], legendData = []
  const pk = primaryKey[dimension.value] || 'revpar'

  checked.forEach(key => {
    if (key === 'predict_price') {
      if (!data.predict_price || data.predict_price.length === 0) return
      legendData.push(seriesNames[key])
      const predictData = Array(allLabels.length - data.predict_price.length).fill(null).concat(data.predict_price)
      series.push({
        name: seriesNames[key], type: 'line', data: predictData,
        itemStyle: { color: seriesColors[key] }, lineStyle: { type: 'dashed', width: 2 },
        symbol: 'diamond', symbolSize: 6,
        yAxisIndex: isMoney(key) ? 0 : isPercent(key) ? 1 : 2, smooth: true, connectNulls: false,
      })
      return
    }
    const values = data[key]
    if (!values || values.length === 0) return
    legendData.push(seriesNames[key])
    series.push({
      name: seriesNames[key],
      type: key === pk ? 'bar' : 'line',
      data: values,
      itemStyle: { color: seriesColors[key] },
      yAxisIndex: isMoney(key) ? 0 : isPercent(key) ? 1 : 2,
      smooth: true,
      connectNulls: false,
    })
  })

  const hasMoney = checked.some(k => isMoney(k)), hasPercent = checked.some(k => isPercent(k)), hasCount = checked.some(k => isCount(k))
  const yAxis = []
  if (hasMoney) yAxis.push({ type: 'value', name: '金额(元)', position: 'left', nameTextStyle: { color: '#666' } })
  if (hasPercent) yAxis.push({ type: 'value', name: '百分比(%)', min: 0, max: 100, position: 'right', nameTextStyle: { color: '#666' } })
  if (hasCount) yAxis.push({ type: 'value', name: '房间数', position: 'right', offset: hasPercent ? 55 : 0, nameTextStyle: { color: '#666' } })
  // 右侧有双轴时增大边距防止重叠
  const gridRight = (hasPercent && hasCount) ? 130 : 70

  chartInstance.setOption({
    title: chartTitle ? { text: chartTitle, left: 'center', top: 0, textStyle: { fontSize: 14, fontWeight: 'bold', color: '#333' } } : undefined,
    tooltip: {
      trigger: 'axis',
      position: 'top',
      formatter: params => {
        const label = params[0].axisValue  // 可能是 "07-22\n周三" 格式
        const parts = label.replace('\n', ' ').split(' ')
        let header = label.replace('\n', ' ')
        // 从 data 中查找对应日期，补充星期
        params.forEach(p => {
          const v = isPercent(p.seriesName) ? p.value + '%' : (isMoney(p.seriesName) ? '¥' + (p.value || 0) : p.value)
          header += `<br/>${p.marker} ${p.seriesName}: ${v}`
        })
        return header
      }
    },
    legend: { data: legendData, top: 0 },
    grid: { left: 60, right: gridRight, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: allLabels, boundaryGap: false, axisLabel: { interval: 'auto', rotate: 0 } },
    yAxis: yAxis.length > 0 ? yAxis : [{ type: 'value' }],
    series,
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, zoomOnMouseWheel: true, moveOnMouseMove: true, moveOnMouseWheel: false },
      { type: 'slider', xAxisIndex: 0, bottom: 0, height: 22 },
      { type: 'inside', yAxisIndex: 0, zoomOnMouseWheel: 'shift' },
    ],
  })
}

// ============ 生命周期 ============
const handleResize = () => chartInstance?.resize()

onMounted(() => {
  onDimensionChange()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.chart-analysis { width: 100%; }
.controls { display: flex; flex-direction: column; gap: 8px; }
.control-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.label { font-weight: 600; min-width: 50px; color: #333; }
.chart-container { width: 100%; height: 500px; }
.model-explain { font-size: 14px; line-height: 1.8; color: #333; }
.model-explain p { margin: 4px 0; }
.signal-card { border-left: 3px solid #1677ff; padding: 8px 14px; margin: 10px 0; background: #fafafa; border-radius: 0 6px 6px 0; }
.signal-card h4 { margin: 0 0 4px 0; font-size: 15px; }
.signal-card ul { margin: 4px 0 0 16px; padding: 0; }
.signal-card li { margin: 2px 0; }
</style>
