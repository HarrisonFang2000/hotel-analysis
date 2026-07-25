<template>
  <div class="settings-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- ========== 标签1: 账号与采集 ========== -->
      <el-tab-pane label="账号与采集" name="collect">
        <!-- 去呼呼账号 -->
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header><span style="font-weight:600">去呼呼客栈管家 - 账号</span></template>
          <el-form :model="form" label-width="140px" size="default">
            <el-form-item label="手机号/账号">
              <el-input v-model="form.quhuhu_username" placeholder="去呼呼登录手机号" style="width:300px" clearable />
            </el-form-item>
            <el-form-item label="登录密码">
              <el-input v-model="form.quhuhu_password" type="password" placeholder="去呼呼登录密码" style="width:300px" show-password clearable />
            </el-form-item>
            <el-form-item label="登录地址">
              <el-input v-model="form.quhuhu_login_url" placeholder="去呼呼登录URL" clearable />
            </el-form-item>
            <el-form-item>
              <el-tooltip content="保存去呼呼账号密码配置到数据库" placement="top"><el-button type="primary" @click="saveConfig('quhuhu')" :loading="saving">保存</el-button></el-tooltip>
              <el-tooltip content="用已保存的Cookie测试去呼呼API是否可用" placement="top"><el-button @click="testLogin" :loading="testingLogin">测试登录</el-button></el-tooltip>
              <el-tooltip content="打开浏览器登录去呼呼→自动抓取Cookie→保存到数据库（无需手动填写密码）" placement="top"><el-button type="success" @click="captureCookie" :loading="capturing">📋 一键读取Cookie</el-button></el-tooltip>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 采集参数 -->
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header><span style="font-weight:600">自动采集参数</span></template>
          <el-form :model="form" label-width="160px" size="default">
            <el-form-item label="采集间隔(分钟)">
              <el-input-number v-model="form.collection_interval" :min="10" :max="1440" :step="10" />
              <span class="form-tip">每隔N分钟自动采集</span>
            </el-form-item>
            <el-form-item label="采集偏移(分钟)">
              <el-input-number v-model="form.collect_offset_minute" :min="0" :max="10" />
              <span class="form-tip">整点后延迟N分钟执行</span>
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="form.collect_retry_times" :min="1" :max="5" />
            </el-form-item>
            <el-form-item label="订单状态筛选">
              <el-radio-group v-model="form.order_status">
                <el-radio value="全部">全部</el-radio>
                <el-radio value="未入住">未入住（预定）</el-radio>
                <el-radio value="已入住">已入住/已离店</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-tooltip content="保存自动采集间隔和偏移分钟数配置" placement="top"><el-button type="primary" @click="saveConfig('collect')" :loading="saving">保存</el-button></el-tooltip>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 历史数据采集 -->
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header><span style="font-weight:600">历史数据采集</span></template>
          <el-form :model="form" label-width="140px" size="default">
            <el-form-item label="日期范围">
              <el-date-picker v-model="historyRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" />
              <el-tooltip content="一键采集选定日期范围内的全部历史数据（每天调用一次去呼呼API）" placement="top"><el-button type="warning" @click="collectHistory" :loading="collectingHistory" style="margin-left:12px">开始批量采集</el-button></el-tooltip>
            </el-form-item>
            <el-progress v-if="historyProgress > 0 && historyProgress < 100" :percentage="historyProgress" :format="() => historyMsg" style="max-width:500px" />
          </el-form>
        </el-card>

        <!-- 美团底价 -->
        <el-card shadow="never">
          <template #header><span style="font-weight:600">美团底价</span></template>
          <el-form :model="form" label-width="160px" size="default">
            <el-form-item label="今日美团底价">
              <el-input-number v-model="form.meituan_manual_price" :min="0" :step="10" :precision="2" />
              <span class="form-tip">每天手动填入，留空自动用去呼呼价</span>
            </el-form-item>
            <el-form-item>
              <el-tooltip content="保存美团商家账号密码配置" placement="top"><el-button type="primary" @click="saveConfig('meituan')" :loading="saving">保存</el-button></el-tooltip>
              <el-tooltip content="下载起售价格CSV模板（列：日期,起售价格）" placement="top"><el-button @click="downloadTemplate">📤 下载模板</el-button></el-tooltip>
              <el-tooltip content="上传CSV文件批量更新历史日期的起售价格" placement="top"><el-button type="warning" @click="batchImportPrices" :loading="importingPrices">📥 批量导入历史</el-button></el-tooltip>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- ========== 标签2: 系统参数 ========== -->
      <el-tab-pane label="系统参数" name="system">
        <el-card shadow="never">
          <el-form :model="form" label-width="160px" size="default">
            <el-form-item label="服务端口">
              <el-input-number v-model="form.port" :min="1024" :max="65535" />
              <span class="form-tip">修改后需重启生效</span>
            </el-form-item>
            <el-form-item label="开发模式">
              <el-switch v-model="form.dev_mode" :active-value="'1'" :inactive-value="'0'" />
              <span class="form-tip">开启后显示对账校验功能</span>
            </el-form-item>
            <el-form-item label="自动备份间隔(小时)">
              <el-input-number v-model="form.auto_backup_hours" :min="1" :max="72" />
            </el-form-item>
            <el-form-item>
              <el-tooltip content="保存系统开发模式、端口号、备份间隔等设置" placement="top"><el-button type="primary" @click="saveConfig('system')" :loading="saving">保存</el-button></el-tooltip>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- ========== 标签3: 用户管理 ========== -->
      <el-tab-pane label="用户管理" name="role" v-if="isSuperAdmin()">
        <el-card shadow="never" style="margin-bottom:16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="font-weight:600">用户列表</span>
              <el-tooltip content="创建新的系统用户，设置用户名、6位PIN码和角色（超管/管理员/前台）" placement="top"><el-button type="primary" size="small" @click="showAddUser=true">➕ 添加用户</el-button></el-tooltip>
            </div>
          </template>
          <el-table :data="userList" border stripe size="small">
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{row}">{{ row.role==='super_admin'?'超级管理员':row.role==='admin'?'管理员':'前台操作' }}</template>
            </el-table-column>
            <el-table-column prop="active" label="状态" width="80">
              <template #default="{row}">
                <el-tag :type="row.active?'success':'danger'" size="small">{{ row.active?'启用':'停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="create_time" label="创建时间" width="160" />
            <el-table-column label="操作" width="160" align="center">
              <template #default="{row}">
                <el-tooltip content="修改该用户的用户名、密码或角色" placement="top"><el-button size="small" link type="primary" @click="editUser(row)">编辑</el-button></el-tooltip>
                <el-popconfirm :title="`${row.active?'停用':'启用'} ${row.name}？`" @confirm="toggleUser(row)">
                  <template #reference>
                    <el-tooltip :content="row.active?'停用后该用户无法登录系统':'重新激活该用户的登录权限'" placement="top"><el-button size="small" link :type="row.active?'warning':'success'">{{ row.active?'停用':'启用' }}</el-button></el-tooltip>
                  </template>
                </el-popconfirm>
                <el-popconfirm v-if="row.name!=='管理员'" title="确认删除？" @confirm="deleteUser(row.id)">
                  <template #reference>
                    <el-tooltip content="永久删除该用户（受保护用户不可删除）" placement="top"><el-button size="small" link type="danger">删除</el-button></el-tooltip>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 操作日志 -->
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="font-weight:600">操作日志（最近50条）</span>
              <div style="display:flex;gap:8px">
                <el-tooltip content="弹窗查看全部操作日志记录，支持滚动浏览" placement="top"><el-button size="small" @click="showAllLogs = true">📋 查看全部</el-button></el-tooltip>
                <el-tooltip content="一键下载所有操作日志为CSV文件（Excel可直接打开）" placement="top"><el-button size="small" type="primary" @click="exportAllLogs">📥 导出全部</el-button></el-tooltip>
              </div>
            </div>
          </template>
          <el-table :data="auditLogs" border stripe size="small" max-height="400">
            <el-table-column prop="user_name" label="操作人" width="100" />
            <el-table-column prop="user_role" label="角色" width="80">
              <template #default="{row}">{{ row.user_role==='super_admin'?'超管':row.user_role==='admin'?'管理':'前台' }}</template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="120" />
            <el-table-column prop="detail" label="详情" min-width="200" />
            <el-table-column prop="create_time" label="时间" width="160" />
          </el-table>
        </el-card>

        <!-- 全部日志对话框 -->
        <el-dialog v-model="showAllLogs" title="全部操作日志" width="900px" top="3vh">
          <el-table :data="allLogs" border stripe size="small" max-height="70vh" v-loading="loadingAllLogs">
            <el-table-column prop="user_name" label="操作人" width="100" />
            <el-table-column prop="user_role" label="角色" width="80">
              <template #default="{row}">{{ row.user_role==='super_admin'?'超管':row.user_role==='admin'?'管理':'前台' }}</template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="120" />
            <el-table-column prop="detail" label="详情" min-width="250" />
            <el-table-column prop="create_time" label="时间" width="170" />
          </el-table>
        </el-dialog>

        <!-- 添加/编辑用户对话框 -->
        <el-dialog v-model="showAddUser" :title="editingUser?'编辑用户':'添加用户'" width="420px">
          <el-form :model="userForm" label-width="80px">
            <el-form-item label="姓名">
              <el-input v-model="userForm.name" placeholder="用户姓名" maxlength="20" />
            </el-form-item>
            <el-form-item label="角色">
              <el-select v-model="userForm.role" style="width:100%">
                <el-option label="超级管理员" value="super_admin" />
                <el-option label="管理员" value="admin" />
                <el-option label="前台操作员" value="operator" />
              </el-select>
            </el-form-item>
            <el-form-item label="PIN码">
              <el-input v-model="userForm.pin" type="password" show-password maxlength="20" placeholder="1-20位" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showAddUser=false">取消</el-button>
            <el-button type="primary" @click="saveUser" :loading="savingPin">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ========== 标签4: 备份管理 ========== -->
      <el-tab-pane label="备份管理" name="backup">
        <div style="margin-bottom:12px;display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600">备份文件列表</span>
          <el-tooltip content="立即创建当前数据库的快照备份文件（保存到data/backup目录）" placement="top"><el-button type="primary" @click="createBackup" :loading="backingUp">📦 立即备份</el-button></el-tooltip>
        </div>
        <el-table :data="backups" border stripe size="small" max-height="400" empty-text="暂无备份">
          <el-table-column prop="filename" label="文件名" min-width="220" />
          <el-table-column prop="size_kb" label="大小(KB)" width="100" align="right" />
          <el-table-column prop="time" label="时间" width="160" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-popconfirm title="还原将覆盖当前数据，确定？" @confirm="restoreBackup(row.filename)">
                <template #reference>
                  <el-tooltip content="从选定的备份文件恢复数据库，当前数据将被覆盖" placement="top"><el-button type="warning" size="small" link>🔄 还原</el-button></el-tooltip>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ========== 标签4: 系统状态 ========== -->
      <el-tab-pane label="系统状态" name="status">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="运行状态"><el-tag type="success">运行中</el-tag></el-descriptions-item>
          <el-descriptions-item label="数据库大小">{{ status.db_size || 0 }} MB</el-descriptions-item>
          <el-descriptions-item label="最近备份">{{ status.last_backup_time || '无' }}</el-descriptions-item>
          <el-descriptions-item label="总房间数">113 间</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api'

const saving = ref(false)
const activeTab = ref('collect')
const testingLogin = ref(false)
const capturing = ref(false)
const capturingMt = ref(false)
const importingPrices = ref(false)
const collectingHistory = ref(false)
const historyRange = ref([])
const historyProgress = ref(0)
const historyMsg = ref('')
const playwrightOk = ref(false)
const status = reactive({ db_size: 0, last_backup_time: '' })
const backups = ref([])
const backingUp = ref(false)

const form = reactive({
  quhuhu_username: '',
  quhuhu_password: '',
  quhuhu_login_url: '',
  collection_interval: 60,
  collect_offset_minute: 2,
  collect_retry_times: 2,
  order_status: '全部',
  port: 8080,
  dev_mode: '0',
  auto_backup_hours: 6,
  meituan_manual_price: null,
})

const loadConfig = async () => {
  try {
    const configs = await request.get('/config/list')
    const map = {}
    configs.forEach(c => { map[c.key] = c.value })
    Object.keys(form).forEach(k => {
      if (map[k] !== undefined) form[k] = map[k]
    })
    form.collection_interval = parseInt(form.collection_interval) || 60
    form.collect_offset_minute = parseInt(form.collect_offset_minute) || 2
    form.collect_retry_times = parseInt(form.collect_retry_times) || 2
    form.port = parseInt(form.port) || 8080
    form.auto_backup_hours = parseInt(form.auto_backup_hours) || 6
  } catch (e) {
    ElMessage.error('加载配置失败')
  }
}

const loadStatus = async () => {
  try {
    const data = await request.get('/system/status')
    Object.assign(status, data)
  } catch { /* ignore */ }
}

const saveConfig = async (section) => {
  saving.value = true
  try {
    const keys = {
      quhuhu: ['quhuhu_username', 'quhuhu_password', 'quhuhu_login_url'],
      collect: ['collection_interval', 'collect_offset_minute', 'collect_retry_times', 'order_status'],
      system: ['port', 'dev_mode', 'auto_backup_hours'],
      meituan: ['meituan_manual_price'],
    }[section] || []

    for (const key of keys) {
      await request.put('/config', { key, value: String(form[key]) })
    }
    ElMessage.success('配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

const testLogin = async () => {
  if (!form.quhuhu_username || !form.quhuhu_password) {
    ElMessage.warning('请先填写账号和密码')
    return
  }
  testingLogin.value = true
  try {
    // 先保存配置
    await request.put('/config', { key: 'quhuhu_username', value: form.quhuhu_username })
    await request.put('/config', { key: 'quhuhu_password', value: form.quhuhu_password })
    if (form.quhuhu_login_url) {
      await request.put('/config', { key: 'quhuhu_login_url', value: form.quhuhu_login_url })
    }
    // 尝试自动采集（会测试登录）
    const today = localDate()
    const result = await request.post('/io/import/auto-collect', null, { params: { date: today } })
    if (result.success) {
      let msg = `登录成功！采集完成：${result.date}，房间${result.total_sold}，房费${result.total_revenue}`
      // 显示对账信息（开发模式）
      if (result.income_check) {
        const check = result.income_check
        if (check.is_match) {
          msg += `\n✅ 对账通过：营业收入=${check.income_amount} ≈ 综合计算=${check.calculated_fee}`
        } else {
          msg += `\n⚠️ 对账不通过：营业收入=${check.income_amount} vs 综合计算=${check.calculated_fee}，差异=${check.difference}`
        }
      }
      ElMessage.success(msg)
    } else {
      ElMessage.error('采集失败: ' + (result.errors?.join('; ') || '未知错误'))
    }
  } catch (e) {
    ElMessage.error('测试失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    testingLogin.value = false
  }
}

const captureCookie = async () => {
  capturing.value = true
  ElMessage.info('正在打开浏览器，请在浏览器中手动登录去呼呼…')
  try {
    // 设置较长超时（5分钟），因为要等用户手动登录
    const result = await request.post('/cookie/capture', null, { timeout: 300000 })
    if (result.success) {
      ElMessage.success({ message: result.message || `Cookie读取成功！已保存 ${result.cookie_count} 个Cookie`, duration: 8000 })
    } else {
      ElMessage.error({ message: result.message || '读取失败，请重试', duration: 8000 })
    }
  } catch (e) {
    if (e?.code === 'ECONNABORTED' || e?.message?.includes('timeout')) {
      ElMessage.warning('等待超时，请确认已登录后重试')
    } else {
      ElMessage.error('读取失败: ' + (e?.response?.data?.detail || e.message))
    }
  } finally {
    capturing.value = false
  }
}

const captureMeituanCookie = async () => {
  capturingMt.value = true
  ElMessage.info('正在打开美团登录页，请在浏览器中手动登录…')
  try {
    const result = await request.post('/meituan/cookie', null, { timeout: 300000 })
    if (result.success) {
      ElMessage.success({ message: result.message || `美团登录成功！已保存Cookie`, duration: 8000 })
    } else {
      ElMessage.error({ message: result.message || '登录超时，请重试', duration: 8000 })
    }
  } catch (e) {
    ElMessage.error('失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    capturingMt.value = false
  }
}

const downloadTemplate = () => {
  window.open('/api/hourly/export-min-price-template', '_blank')
}

const batchImportPrices = async () => {
  importingPrices.value = true
  try {
    const result = await request.post('/hourly/batch-update-min-price', null, { timeout: 120000 })
    ElMessage.success(result.message || `已更新${result.updated}天，跳过${result.skipped}天`)
  } catch (e) {
    ElMessage.error('导入失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    importingPrices.value = false
  }
}

const collectHistory = async () => {
  if (!historyRange.value || historyRange.value.length !== 2) {
    ElMessage.warning('请选择日期范围')
    return
  }
  collectingHistory.value = true
  historyProgress.value = 50
  historyMsg.value = '正在按月批量导出，请耐心等待...'
  try {
    const result = await request.post('/io/import/auto-collect-history', null, {
      params: { start_date: historyRange.value[0], end_date: historyRange.value[1] },
      timeout: 600000
    })
    historyProgress.value = 100
    historyMsg.value = `完成: ${result.success_count}/${result.total_days}天`
    ElMessage.success({
      message: result.message || `成功导入 ${result.success_count} 天数据`,
      duration: 5000
    })
    setTimeout(() => location.reload(), 2000)
  } catch (e) {
    historyProgress.value = 0
    historyMsg.value = ''
    ElMessage.error(e?.response?.data?.detail || '采集失败，请重试')
  } finally {
    collectingHistory.value = false
  }
}

// 检测 Playwright
const checkPlaywright = async () => {
  try {
    const resp = await fetch('/api/system/status')
    playwrightOk.value = true
  } catch { playwrightOk.value = false }
}

// 备份管理
const loadBackups = async () => {
  try {
    backups.value = await request.get('/backup/list')
  } catch { backups.value = [] }
}

const createBackup = async () => {
  backingUp.value = true
  try {
    await request.post('/backup/create')
    ElMessage.success('备份创建成功')
    await loadBackups()
    await loadStatus()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '备份失败')
  } finally {
    backingUp.value = false
  }
}

const restoreBackup = async (filename) => {
  try {
    await request.post('/backup/restore', null, { params: { filename } })
    ElMessage.success(`已从 ${filename} 还原，页面即将刷新`)
    setTimeout(() => location.reload(), 1500)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '还原失败')
  }
}

// ====== 用户管理 ======
import { useRole } from '@/composables/useRole'
const { users, checkRole, isSuperAdmin } = useRole()
const userList = ref([])
const auditLogs = ref([])
const showAllLogs = ref(false)
const allLogs = ref([])
const loadingAllLogs = ref(false)
const savingPin = ref(false)
const showAddUser = ref(false)
const editingUser = ref(null)
const userForm = reactive({ name: '', pin: '', role: 'operator' })

const loadUsers = async () => {
  if (!isSuperAdmin()) return
  try { userList.value = await request.get('/user/list') } catch { userList.value = [] }
}
const loadAuditLogs = async () => {
  if (!isSuperAdmin()) return
  try { auditLogs.value = await request.get('/audit/list', { params: { limit: 50 } }) } catch { auditLogs.value = [] }
}

const loadAllLogs = async () => {
  loadingAllLogs.value = true
  try { allLogs.value = await request.get('/audit/list', { params: { limit: 9999 } }) } catch { allLogs.value = [] }
  loadingAllLogs.value = false
}

const exportAllLogs = () => {
  window.open('/api/audit/export')
}

// 打开全部日志时自动加载
watch(showAllLogs, (v) => { if (v) loadAllLogs() })

const saveUser = async () => {
  if (!userForm.name || !userForm.pin) { ElMessage.warning('请填写完整'); return }
  if (userForm.pin.length > 20) { ElMessage.warning('PIN最多20位'); return }
  savingPin.value = true
  try {
    if (editingUser.value) {
      await request.put('/user/update', null, { params: { user_id: editingUser.value.id, name: userForm.name, pin: userForm.pin, role: userForm.role } })
    } else {
      await request.post('/user/create', userForm)
    }
    ElMessage.success(editingUser.value ? '已更新' : '已创建')
    showAddUser.value = false
    userForm.name = ''; userForm.pin = ''; userForm.role = 'operator'
    editingUser.value = null
    await loadUsers()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
  finally { savingPin.value = false }
}

const editUser = (row) => {
  editingUser.value = row
  userForm.name = row.name
  userForm.role = row.role
  userForm.pin = ''
  showAddUser.value = true
}

const toggleUser = async (row) => {
  try {
    await request.put('/user/update', null, { params: { user_id: row.id, active: row.active ? 0 : 1 } })
    ElMessage.success(row.active ? '已停用' : '已启用')
    await loadUsers()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

const deleteUser = async (id) => {
  try {
    await request.delete(`/user/${id}`)
    ElMessage.success('已删除')
    await loadUsers()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '操作失败') }
}

onMounted(async () => {
  loadConfig()
  loadStatus()
  loadBackups()
  await checkRole()        // ★ 先确定角色
  loadUsers()              // 再根据角色决定是否加载
  loadAuditLogs()
  checkPlaywright()
})
</script>

<style scoped>
.form-tip {
  margin-left: 12px;
  font-size: 12px;
  color: #999;
}
</style>