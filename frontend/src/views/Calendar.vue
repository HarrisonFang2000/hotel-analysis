<template>
  <div class="calendar-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>热点日历</span>
          <div class="header-actions">
            <el-button-group>
              <el-button :type="viewMode==='month'?'primary':''" size="small" @click="viewMode='month'">月</el-button>
              <el-button :type="viewMode==='year'?'primary':''" size="small" @click="viewMode='year'">年</el-button>
            </el-button-group>
            <el-tooltip content="回到当前月份" placement="bottom"><el-button size="small" @click="goToday">今天</el-button></el-tooltip>
            <el-button-group>
              <el-tooltip content="上一个月" placement="bottom"><el-button size="small" @click="prev"><el-icon><ArrowLeft /></el-icon></el-button></el-tooltip>
              <el-tooltip content="下一个月" placement="bottom"><el-button size="small" @click="next"><el-icon><ArrowRight /></el-icon></el-button></el-tooltip>
            </el-button-group>
            <span class="current-label">{{ currentLabel }}</span>
            <el-tooltip content="从和风天气+open-meteo获取最新天气和节假日数据" placement="bottom"><el-button size="small" :loading="syncing" @click="syncEvents">一键更新</el-button></el-tooltip>
          </div>
        </div>
      </template>

      <!-- 月视图 -->
      <div v-if="viewMode==='month'" class="month-grid">
        <div class="weekday-headers">
          <div v-for="d in ['日','一','二','三','四','五','六']" :key="d" class="weekday-cell">{{ d }}</div>
        </div>
        <div class="days-grid">
          <div v-for="(day, idx) in monthDays" :key="idx"
            :class="['day-cell', { today: day.isToday, 'other-month': !day.isCurrentMonth }]"
            @click="selectedDay=day.dateStr"
          >
            <div class="day-num" :style="{color: day.isToday?'#1677ff':''}">{{ day.day }}</div>
            <div class="day-events">
              <span v-for="(ev,ei) in getDayEvents(day.dateStr)" :key="ei"
                :class="['event-tag', ev.type]"
                :title="ev.name"
              >{{ ev.name.length>4 ? ev.name.slice(0,4)+'…' : ev.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 年视图 -->
      <div v-else class="year-grid">
        <div v-for="m in 12" :key="m" class="mini-month" @click="viewMode='month';currentYearMonth=[currentYear,m]">
          <div class="mini-title">{{ m }}月</div>
          <div class="mini-days">
            <span v-for="(d,di) in getMiniMonth(m)" :key="di"
              :class="['mini-day', { today: d.isToday }]"
              :style="{color: d.isToday?'#1677ff':''}"
            >{{ d.day }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 事件详情 -->
    <el-card v-if="selectedDay && dayEvents.length" style="margin-top:20px">
      <template #header><span>{{ selectedDay }} 事件</span></template>
      <div v-for="(ev,i) in dayEvents" :key="i" class="event-item">
        <span :class="['event-dot', ev.type]"></span>
        <span class="event-name">{{ ev.name }}</span>
        <span class="event-desc">{{ ev.desc }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import request from '@/api'

const viewMode = ref('month')
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth() + 1)
const selectedDay = ref('')
const syncing = ref(false)

// 事件数据: { 'YYYY-MM-DD': [{name, desc, type:'good'|'bad'|'neutral'}] }
const events = ref({})

const currentLabel = computed(() => {
  return viewMode.value === 'month' ? `${currentYear.value}年${currentMonth.value}月` : `${currentYear.value}年`
})

const prev = () => {
  if (viewMode.value === 'month') {
    if (currentMonth.value === 1) { currentYear.value--; currentMonth.value = 12 }
    else currentMonth.value--
  } else {
    currentYear.value--
  }
}
const next = () => {
  if (viewMode.value === 'month') {
    if (currentMonth.value === 12) { currentYear.value++; currentMonth.value = 1 }
    else currentMonth.value++
  } else {
    currentYear.value++
  }
}
const goToday = () => {
  currentYear.value = new Date().getFullYear()
  currentMonth.value = new Date().getMonth() + 1
  viewMode.value = 'month'
}

// 月视图天数计算
const monthDays = computed(() => {
  const y = currentYear.value, m = currentMonth.value
  const firstDay = new Date(y, m-1, 1).getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const daysInPrev = new Date(y, m-1, 0).getDate()
  const today = new Date().toISOString().slice(0,10)
  const result = []
  // 上月填充
  const prevYear = m === 1 ? y - 1 : y
  const prevMonth = m === 1 ? 12 : m - 1
  for (let i = firstDay-1; i >= 0; i--) {
    const d = daysInPrev - i
    const ds = `${prevYear}-${String(prevMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    result.push({ day: d, dateStr: ds, isCurrentMonth: false, isToday: ds===today })
  }
  // 当月
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    result.push({ day: d, dateStr: ds, isCurrentMonth: true, isToday: ds===today })
  }
  // 下月填充
  const nextYear = m === 12 ? y + 1 : y
  const nextMonth = m === 12 ? 1 : m + 1
  const remaining = 42 - result.length
  for (let d = 1; d <= remaining; d++) {
    const ds = `${nextYear}-${String(nextMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    result.push({ day: d, dateStr: ds, isCurrentMonth: false, isToday: ds===today })
  }
  return result
})

const getMiniMonth = (m) => {
  const y = currentYear.value
  const days = new Date(y, m, 0).getDate()
  const today = new Date().toISOString().slice(0,10)
  return Array.from({length: days}, (_,i) => ({
    day: i+1, isToday: `${y}-${String(m).padStart(2,'0')}-${String(i+1).padStart(2,'0')}`===today
  }))
}

const getDayEvents = (ds) => events.value[ds] || []
const dayEvents = computed(() => getDayEvents(selectedDay.value))

// ==================== 天气 ====================
const fetchWeather = async () => {
  try {
    const y = currentYear.value, m = currentMonth.value
    const data = await request.get('/weather/monthly', { params: { year: y, month: m } })
    // data = { "YYYY-MM-DD": { name, desc, type }, ... }
    Object.entries(data).forEach(([ds, info]) => {
      if (!events.value[ds]) events.value[ds] = []
      // 避免重复天气数据
      if (!events.value[ds].some(e => e.type === 'weather')) {
        events.value[ds].push(info)
      }
    })
  } catch { /* ignore */ }
}

// ==================== 节日 ====================
// 中国传统节日（农历→公历对照，2024-2027）
const TRADITIONAL_FESTIVALS = {
  // 元宵节 (正月十五)
  '2024-02-24':['元宵节','赏灯吃汤圆'], '2025-02-12':['元宵节','赏灯吃汤圆'], '2026-03-03':['元宵节','赏灯吃汤圆'], '2027-02-20':['元宵节','赏灯吃汤圆'],
  // 七夕 (七月初七)
  '2024-08-10':['七夕','中国情人节'], '2025-08-29':['七夕','中国情人节'], '2026-08-19':['七夕','中国情人节'], '2027-08-08':['七夕','中国情人节'],
  // 中元节 (七月十五)
  '2024-08-18':['中元节','祭祖'], '2025-09-06':['中元节','祭祖'], '2026-08-27':['中元节','祭祖'], '2027-08-16':['中元节','祭祖'],
  // 重阳节 (九月初九)
  '2024-10-11':['重阳节','登高敬老'], '2025-10-29':['重阳节','登高敬老'], '2026-10-18':['重阳节','登高敬老'], '2027-10-08':['重阳节','登高敬老'],
  // 冬至
  '2024-12-21':['冬至','吃饺子/汤圆'], '2025-12-22':['冬至','吃饺子/汤圆'], '2026-12-22':['冬至','吃饺子/汤圆'], '2027-12-22':['冬至','吃饺子/汤圆'],
  // 腊八节 (腊月初八)
  '2024-01-18':['腊八节','喝腊八粥'], '2025-01-07':['腊八节','喝腊八粥'], '2026-01-26':['腊八节','喝腊八粥'], '2027-01-15':['腊八节','喝腊八粥'],
  // 除夕
  '2024-02-09':['除夕','年夜饭'], '2025-01-28':['除夕','年夜饭'], '2026-02-16':['除夕','年夜饭'], '2027-02-05':['除夕','年夜饭'],
  // 小年 (腊月二十三/二十四)
  '2024-02-02':['小年','祭灶'], '2025-01-22':['小年','祭灶'], '2026-02-10':['小年','祭灶'], '2027-01-30':['小年','祭灶'],
}

// 舟山朱家尖普陀本地节日/活动
const LOCAL_FESTIVALS = {
  // 普陀山观音香会（农历二月十九、六月十九、九月十九）
  '2024-03-28':['普陀山香会','观音诞辰朝圣'], '2024-07-24':['普陀山香会','观音成道日'], '2024-10-21':['普陀山香会','观音出家日'],
  '2025-03-18':['普陀山香会','观音诞辰朝圣'], '2025-07-13':['普陀山香会','观音成道日'], '2025-10-10':['普陀山香会','观音出家日'],
  '2026-04-05':['普陀山香会','观音诞辰朝圣'], '2026-08-01':['普陀山香会','观音成道日'], '2026-10-29':['普陀山香会','观音出家日'],
  '2027-03-26':['普陀山香会','观音诞辰朝圣'], '2027-07-22':['普陀山香会','观音成道日'], '2027-10-18':['普陀山香会','观音出家日'],
  // 普陀山观音文化节（11月）
  '2024-11-15':['观音文化节','普陀山大型法会'], '2025-11-04':['观音文化节','普陀山大型法会'], '2026-11-22':['观音文化节','普陀山大型法会'], '2027-11-11':['观音文化节','普陀山大型法会'],
  // 朱家尖国际沙雕节（9-10月，南沙景区）
  '2024-09-20':['舟山沙雕节','朱家尖南沙'], '2025-09-19':['舟山沙雕节','朱家尖南沙'], '2026-09-18':['舟山沙雕节','朱家尖南沙'], '2027-09-17':['舟山沙雕节','朱家尖南沙'],
  // 朱家尖东海音乐节（夏季）
  '2024-07-06':['东海音乐节','朱家尖沙滩'], '2025-07-05':['东海音乐节','朱家尖沙滩'], '2026-07-04':['东海音乐节','朱家尖沙滩'], '2027-07-03':['东海音乐节','朱家尖沙滩'],
  // 舟山海鲜美食节（8-9月，沈家门渔港）
  '2024-08-15':['海鲜美食节','沈家门渔港'], '2025-08-14':['海鲜美食节','沈家门渔港'], '2026-08-13':['海鲜美食节','沈家门渔港'], '2027-08-12':['海鲜美食节','沈家门渔港'],
  // 舟山国际海岛旅游大会（9-10月）
  '2024-09-22':['海岛旅游大会','国际海岛旅游'], '2025-09-21':['海岛旅游大会','国际海岛旅游'], '2026-09-20':['海岛旅游大会','国际海岛旅游'], '2027-09-19':['海岛旅游大会','国际海岛旅游'],
  // 嵊泗列岛贻贝文化节（7-8月）
  '2024-07-20':['贻贝文化节','嵊泗枸杞岛'], '2025-07-19':['贻贝文化节','嵊泗枸杞岛'], '2026-07-18':['贻贝文化节','嵊泗枸杞岛'], '2027-07-17':['贻贝文化节','嵊泗枸杞岛'],
}

const fetchHolidays = async () => {
  // ① 全国节假日（nager.at API）
  try {
    const y = currentYear.value
    const resp = await fetch(`https://date.nager.at/api/v3/PublicHolidays/${y}/CN`)
    if (resp.ok) {
      const data = await resp.json()
      data.forEach(h => {
        if (!events.value[h.date]) events.value[h.date] = []
        events.value[h.date].push({ name: `🏖${h.localName}`, desc: '全国节假日', type: 'good' })
      })
    }
  } catch { /* ignore */ }

  // ② 中国传统节日（硬编码农历对照）
  Object.entries(TRADITIONAL_FESTIVALS).forEach(([ds, info]) => {
    if (!events.value[ds]) events.value[ds] = []
    // 避免和全国节假日重复（春节、清明、端午、中秋已在API中）
    if (!events.value[ds].some(e => e.name.includes(info[0]))) {
      events.value[ds].push({ name: `🎋${info[0]}`, desc: info[1], type: 'festival' })
    }
  })

  // ③ 舟山本地节日
  Object.entries(LOCAL_FESTIVALS).forEach(([ds, info]) => {
    if (!events.value[ds]) events.value[ds] = []
    if (!events.value[ds].some(e => e.name.includes(info[0]))) {
      events.value[ds].push({ name: `🏮${info[0]}`, desc: info[1], type: 'local' })
    }
  })
}

const syncEvents = async () => {
  syncing.value = true
  events.value = {}
  try {
    fetchHolidays()  // 本地数据，无需await
    await fetchWeather()
    ElMessage.success('事件数据已更新')
  } catch {
    ElMessage.warning('部分数据获取失败')
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  // 首次加载尝试获取数据
  setTimeout(() => syncEvents(), 500)
})
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:center; }
.header-actions { display:flex; gap:8px; align-items:center; }
.current-label { font-size:16px; font-weight:600; min-width:120px; text-align:center; }

.month-grid { margin-top:10px; }
.weekday-headers { display:grid; grid-template-columns:repeat(7,1fr); text-align:center; font-weight:600; color:#666; margin-bottom:4px; }
.weekday-cell { padding:8px; }
.days-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:2px; }
.day-cell { min-height:80px; border:1px solid #f0f0f0; border-radius:4px; padding:6px; cursor:pointer; transition:all .2s; }
.day-cell:hover { background:#e6f4ff; border-color:#1677ff; }
.day-cell.today { border:2px solid #1677ff; }
.day-cell.other-month { opacity:.4; }
.day-num { font-size:14px; font-weight:500; margin-bottom:4px; }
.day-events { display:flex; flex-wrap:wrap; gap:2px; }
.event-tag { font-size:10px; padding:1px 4px; border-radius:3px; white-space:nowrap; }
.event-tag.good { background:#fff2e8; color:#d4380d; }
.event-tag.bad { background:#e6f4ff; color:#0958d9; }
.event-tag.neutral { background:#f5f5f5; color:#999; }
.event-tag.weather { background:#e6fffb; color:#08979c; }
.event-tag.festival { background:#fff7e6; color:#d46b08; }
.event-tag.local { background:#f9f0ff; color:#531dab; }

.year-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:10px; }
.mini-month { cursor:pointer; padding:8px; border:1px solid #f0f0f0; border-radius:6px; transition:all .2s; }
.mini-month:hover { border-color:#1677ff; }
.mini-title { font-weight:600; margin-bottom:4px; }
.mini-days { display:grid; grid-template-columns:repeat(7,1fr); gap:1px; }
.mini-day { font-size:10px; text-align:center; padding:2px; }
.mini-day.today { background:#1677ff; color:#fff!important; border-radius:50%; }

.event-item { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid #f0f0f0; }
.event-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.event-dot.good { background:#d4380d; }
.event-dot.bad { background:#0958d9; }
.event-dot.neutral { background:#999; }
.event-dot.weather { background:#08979c; }
.event-dot.festival { background:#d46b08; }
.event-dot.local { background:#531dab; }
.event-name { font-weight:500; min-width:80px; }
.event-desc { color:#666; font-size:13px; }
</style>