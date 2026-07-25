<template>
  <el-container class="layout-container">
    <!-- 顶部工具栏 -->
    <el-header class="header">
      <div class="header-left">
        <h2 class="title">酒店数据分析系统 V0.91</h2>
      </div>
      <div class="header-right">
        <el-popover :width="220" trigger="click" placement="bottom" :offset="8">
          <template #reference>
            <el-tag :type="tagType" size="large" class="user-tag">
              {{ currentUser.name || '未登录' }}{{ roleIcon }}
            </el-tag>
          </template>
          <div class="user-popover">
            <div class="popover-info">
              <span class="popover-label">当前角色</span>
              <span class="popover-value">{{ roleName }}</span>
            </div>
            <el-divider style="margin:8px 0" />
            <el-button class="popover-btn" @click="handleSwitchUser">
              <el-icon><Switch /></el-icon>切换用户
            </el-button>
            <el-button class="popover-btn" @click="handleChangePin">
              <el-icon><Lock /></el-icon>修改密码
            </el-button>
            <el-button class="popover-btn popover-btn-exit" @click="handleLogout">
              <el-icon><Back /></el-icon>退出登录
            </el-button>
          </div>
        </el-popover>
        <el-tooltip content="从去呼呼PMS获取最新客房销售数据" placement="bottom">
          <el-button type="primary" :icon="Download" @click="handleAutoCollect" :loading="collecting">
            自动采集
          </el-button>
        </el-tooltip>
        <el-tooltip content="从Excel文件手动导入报表数据（客房销售+订单来源）" placement="bottom" v-if="isAdmin()">
          <el-button :icon="Upload" @click="showImportDialog = true">手动导入</el-button>
        </el-tooltip>
        <el-tooltip content="选择报表类型（小时/日/月/季/年）和日期范围，导出Excel" placement="bottom" v-if="isAdmin()">
          <el-button :icon="Download" @click="showExportDialog = true">导出报表</el-button>
        </el-tooltip>
        <el-tooltip content="生成选定日期范围的逐小时销售流速Excel报表（含可售/已售、ADR、RevPar，最多31天）" placement="bottom" v-if="isAdmin()">
          <el-button :icon="Download" @click="showFlowDialog=true">📊 订单流速表</el-button>
        </el-tooltip>
        <el-tooltip content="刷新当前页面数据" placement="bottom">
          <el-button :icon="Refresh" @click="handleRefresh">刷新</el-button>
        </el-tooltip>
      </div>
    </el-header>

    <!-- 手动导入对话框 -->
    <el-dialog v-model="showImportDialog" title="手动导入报表" width="650px" @close="resetImport">
      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        上传<strong>客房销售报表</strong>（必须）和<strong>订单来源明细</strong>（可选，用于核对和提取OTA起售价）
      </el-alert>
      
      <el-form label-width="120px">
        <el-form-item label="客房销售报表">
          <el-upload :auto-upload="false" :show-file-list="true" accept=".xls,.xlsx"
            :on-change="(f) => roomFile = f.raw" :limit="1">
            <el-button type="primary">选择客房销售报表</el-button>
            <template #tip> 从去呼呼→运营报表→客房销售报表 导出</template>
          </el-upload>
        </el-form-item>
        <el-form-item label="订单来源明细">
          <el-upload :auto-upload="false" :show-file-list="true" accept=".xls,.xlsx"
            :on-change="(f) => sourceFile = f.raw" :limit="1">
            <el-button>选择订单来源明细</el-button>
            <template #tip> （可选）从去呼呼→运营报表→客源统计 导出</template>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- 核对结果 -->
      <el-descriptions v-if="importResult" :column="2" border size="small" style="margin-top:16px">
        <el-descriptions-item label="报表日期">{{ importResult.final?.date }}</el-descriptions-item>
        <el-descriptions-item label="导入时间">{{ importResult.final?.hour }}:00</el-descriptions-item>
        <el-descriptions-item label="售出房间">{{ importResult.final?.sold_rooms }} 间</el-descriptions-item>
        <el-descriptions-item label="累计房费">¥{{ importResult.final?.total_revenue }}</el-descriptions-item>
        <el-descriptions-item label="OTA起售价">¥{{ importResult.final?.ota_min_price }}</el-descriptions-item>
        <el-descriptions-item label="数据来源">手动导入</el-descriptions-item>
      </el-descriptions>

      <el-divider v-if="importResult?.cross_check" />
      
      <el-alert v-if="importResult?.cross_check" 
        :type="importResult.cross_check.is_match ? 'success' : 'warning'"
        :title="importResult.cross_check.is_match ? '✅ 核对通过' : '⚠️ 核对不一致'"
        :description="'客房销售¥' + importResult.cross_check.room_sale_total + ' vs 订单来源¥' + importResult.cross_check.source_detail_total + '，差异¥' + importResult.cross_check.difference"
        show-icon :closable="false" style="margin-top:8px" />

      <div v-if="importResult?.source_detail?.channels?.length" style="margin-top:12px">
        <el-table :data="importResult.source_detail.channels" border size="small">
          <el-table-column prop="channel" label="渠道" />
          <el-table-column prop="pay_type" label="类型" />
          <el-table-column prop="orders" label="订单数" />
          <el-table-column prop="room_nights" label="间夜数" />
          <el-table-column prop="revenue" label="房费">
            <template #default="{row}">¥{{ row.revenue }}</template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" @click="doImport" :loading="importing" :disabled="!roomFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 订单流速表对话框 -->
    <el-dialog v-model="showFlowDialog" title="导出订单流速表" width="450px">
      <el-form label-width="80px">
        <el-form-item label="日期范围">
          <el-date-picker v-model="flowDateRange" type="daterange" value-format="YYYY-MM-DD"
            range-separator="至" style="width:100%" />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon style="margin-top:8px">
          最多支持31天范围
        </el-alert>
      </el-form>
      <template #footer>
        <el-button @click="showFlowDialog=false">取消</el-button>
        <el-button type="primary" @click="exportOrderFlow" :disabled="!flowDateRange||flowDateRange.length<2">
          下载订单流速表
        </el-button>
      </template>
    </el-dialog>

    <!-- 导出报表对话框 -->
    <el-dialog v-model="showExportDialog" title="导出报表" width="500px">
      <el-form label-width="80px">
        <el-form-item label="报表类型">
          <el-radio-group v-model="exportType">
            <el-radio-button value="hourly">小时报</el-radio-button>
            <el-radio-button value="daily">日报</el-radio-button>
            <el-radio-button value="monthly">月报</el-radio-button>
            <el-radio-button value="quarterly">季报</el-radio-button>
            <el-radio-button value="yearly">年报</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日期范围" v-if="exportType !== 'yearly' && exportType !== 'quarterly'">
          <el-date-picker
            v-if="exportType === 'hourly'"
            v-model="exportDate" type="date" value-format="YYYY-MM-DD"
            placeholder="选择日期" style="width:100%" />
          <el-date-picker
            v-else-if="exportType === 'monthly'"
            v-model="exportMonthRange" type="monthrange" value-format="YYYY-MM"
            range-separator="至" style="width:100%" />
          <el-date-picker
            v-else
            v-model="exportDateRange" type="daterange" value-format="YYYY-MM-DD"
            range-separator="至" style="width:100%" />
        </el-form-item>
        <el-form-item label="年份" v-if="exportType === 'yearly' || exportType === 'quarterly'">
          <el-date-picker v-model="exportYear" type="year" value-format="YYYY" placeholder="选择年份" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" @click="doExport" :disabled="!canExport">
          导出 {{ exportLabel }}
        </el-button>
      </template>
    </el-dialog>

    <el-container>
      <!-- 左侧菜单 -->
      <el-aside width="220px" class="aside">
        <el-menu
          :default-active="$route.path"
          router
          class="menu"
          background-color="#001529"
          text-color="#ffffff"
          active-text-color="#1677ff"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>实时仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/hourly">
            <el-icon><Clock /></el-icon>
            <span>小时数据</span>
          </el-menu-item>
          <el-menu-item index="/daily">
            <el-icon><Calendar /></el-icon>
            <span>日报数据</span>
          </el-menu-item>
          <el-menu-item index="/monthly" v-if="isAdmin()">
            <el-icon><Calendar /></el-icon>
            <span>月报数据</span>
          </el-menu-item>
          <el-menu-item index="/quarterly" v-if="isAdmin()">
            <el-icon><PieChart /></el-icon>
            <span>季报数据</span>
          </el-menu-item>
          <el-menu-item index="/yearly" v-if="isAdmin()">
            <el-icon><TrendCharts /></el-icon>
            <span>年报数据</span>
          </el-menu-item>
          <el-menu-item index="/chart">
            <el-icon><DataAnalysis /></el-icon>
            <span>图表分析</span>
          </el-menu-item>
          <el-menu-item index="/calendar">
            <el-icon><Calendar /></el-icon>
            <span>热点日历</span>
          </el-menu-item>
          <el-menu-item index="/settings" v-if="isAdmin()">
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
          <el-menu-item index="/database" v-if="isAdmin()">
            <el-icon><Coin /></el-icon>
            <span>数据库管理</span>
          </el-menu-item>
        </el-menu>
        <div style="position:absolute;bottom:8px;left:0;right:0;text-align:center;color:rgba(255,255,255,0.3);font-size:12px">
          v0.9.0 · Treesi
        </div>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Download, Refresh, DataLine, Clock, Calendar, PieChart, TrendCharts, DataAnalysis, Setting, Switch, Lock, Back, Coin } from '@element-plus/icons-vue'
import request from '@/api'
import { useRole } from '@/composables/useRole'

const { currentUser, checkRole, login, logout, isAdmin } = useRole()

const tagType = computed(() => {
  const m = { super_admin: 'danger', admin: 'warning', operator: 'success' }
  return m[currentUser.value.role] || 'info'
})
const roleIcon = computed(() => {
  const m = { super_admin: ' 👑', admin: ' 🔑', operator: ' 🔒' }
  return m[currentUser.value.role] || ' 🔓'
})
const roleName = computed(() => {
  const m = { super_admin: '超级管理员', admin: '管理员', operator: '前台' }
  return m[currentUser.value.role] || '游客'
})

const handleSwitchUser = async () => {
  const ok = await login()
  if (ok) location.reload()
}

const handleLogout = async () => {
  const ok = await logout()
  if (ok) location.reload()
}

const handleChangePin = async () => {
  try {
    const { value: oldPin } = await ElMessageBox.prompt('请输入当前密码', '修改密码 - 验证身份', { inputType: 'password' })
    if (!oldPin) return
    // 先验证旧密码
    try {
      await request.post('/role/verify-pin', { pin: oldPin })
    } catch (e) {
      ElMessage.error('旧密码错误')
      return
    }
    // 旧密码正确，再问新密码
    const { value: newPin } = await ElMessageBox.prompt('请输入新密码（1-20位）', '修改密码 - 设置新密码', {
      inputType: 'password', inputPattern: /^.{1,20}$/, inputErrorMessage: '1-20位任意字符'
    })
    if (!newPin) return
    await request.put('/role/change-pin', { old_pin: oldPin, new_pin: newPin })
    ElMessage.success('密码修改成功')
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e?.response?.data?.detail || '修改失败')
    }
  }
}

const collecting = ref(false)
const showImportDialog = ref(false)
const showFlowDialog = ref(false)
const showExportDialog = ref(false)
const flowDateRange = ref([])
const importing = ref(false)
const roomFile = ref(null)
const sourceFile = ref(null)
const importResult = ref(null)

// 导出相关
const exportType = ref('daily')
const exportDate = ref(localDate())
const exportDateRange = ref([])
const exportMonthRange = ref([])
const exportYear = ref(new Date().getFullYear().toString())

const exportLabel = computed(() => {
  const m = { hourly: '小时报', daily: '日报', monthly: '月报', quarterly: '季报', yearly: '年报' }
  return m[exportType.value] || ''
})

const canExport = computed(() => {
  if (exportType.value === 'hourly') return !!exportDate.value
  if (exportType.value === 'yearly' || exportType.value === 'quarterly') return !!exportYear.value
  if (exportType.value === 'monthly') return exportMonthRange.value?.length === 2
  return exportDateRange.value?.length === 2
})

const doExport = () => {
  let start, end
  const t = exportType.value
  if (t === 'hourly') { start = exportDate.value; end = exportDate.value }
  else if (t === 'yearly') { start = exportYear.value + '-01-01'; end = exportYear.value + '-12-31' }
  else if (t === 'quarterly') { start = exportYear.value + '-01-01'; end = exportYear.value + '-12-31' }
  else if (t === 'monthly') { start = exportMonthRange.value[0]; end = exportMonthRange.value[1] }
  else { start = exportDateRange.value[0]; end = exportDateRange.value[1] }
  
  window.open(`/api/io/export/report?type=${t}&start_date=${start}&end_date=${end}`)
  showExportDialog.value = false
}

const resetImport = () => {
  roomFile.value = null
  sourceFile.value = null
  importResult.value = null
}

const doImport = async () => {
  if (!roomFile.value) return
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('room_sale_file', roomFile.value)
    if (sourceFile.value) {
      formData.append('source_detail_file', sourceFile.value)
    }
    const resp = await request.post('/io/import/excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = resp
    ElMessage.success(resp.message || '导入成功')
    setTimeout(() => location.reload(), 3000)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleAutoCollect = async () => {
  try {
    await ElMessageBox.confirm('将从去呼呼自动采集今日报表数据，确认继续？', '自动采集', {
      confirmButtonText: '开始采集',
      cancelButtonText: '取消',
      type: 'info'
    })
  } catch { return }

  collecting.value = true
  try {
    const today = localDate()
    await request.post('/io/import/auto-collect', null, { params: { date: today } })
    ElMessage.success('自动采集完成，数据已入库')
    setTimeout(() => location.reload(), 1500)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '自动采集失败')
  } finally {
    collecting.value = false
  }
}

const handleRefresh = () => {
  location.reload()
}

const exportOrderFlow = () => {
  if (flowDateRange.value?.length === 2) {
    window.open(`/api/io/export/order-flow?start_date=${flowDateRange.value[0]}&end_date=${flowDateRange.value[1]}`)
    showFlowDialog.value = false
  }
}

onMounted(() => {
  checkRole()
})
</script>

<style scoped>
.layout-container {
  width: 100%;
  height: 100%;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  line-height: 60px;
}
.title {
  font-size: 20px;
  font-weight: 600;
  color: #1677ff;
  margin: 0;
}
.header-right {
  display: flex;
  gap: 10px;
}
.aside {
  background: #001529;
  overflow-y: auto;
}
.user-tag {
  cursor: pointer;
  font-size: 14px;
  padding: 6px 14px;
  transition: all 0.2s;
}
.user-tag:hover {
  opacity: 0.85;
  transform: translateY(-1px);
}
.user-popover {
  display: flex;
  flex-direction: column;
}
.popover-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}
.popover-label {
  font-size: 13px;
  color: #909399;
}
.popover-value {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.popover-btn {
  width: 100%;
  justify-content: flex-start;
  margin: 3px 0;
  gap: 8px;
}
.popover-btn-exit {
  color: #E6A23C;
  border-color: #F5DAB1;
}
.popover-btn-exit:hover {
  color: #fff;
  background: #E6A23C;
  border-color: #E6A23C;
}
.menu {
  border-right: none;
}
.main {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
