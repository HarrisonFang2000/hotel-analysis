<template>
  <div class="db-manager">
    <div class="db-layout">
      <!-- 左侧表列表 - 固定宽度 -->
      <div class="db-sidebar">
        <div class="sidebar-title">📋 数据表</div>
        <div class="sidebar-list" v-loading="loadingTables">
          <div v-for="t in tables" :key="t.name"
            :class="['table-item', { active: t.name === activeTable }]"
            @click="selectTable(t.name)">
            <span class="tname">{{ formatTableName(t.name) }}</span>
            <el-tag size="small">{{ t.rows }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 右侧数据区 - 占剩余宽度 -->
      <div class="db-main" v-loading="loadingData">
        <div v-if="activeTable" class="main-header">
          <div class="header-left">
            <b>{{ formatTableName(activeTable) }}</b>
            <span class="info-text">{{ columns.length }} 列 · {{ total }} 行</span>
          </div>
          <div class="toolbar">
            <el-input v-model="searchText" size="small" placeholder="搜索..." style="width:130px" clearable />
            <el-button size="small" @click="loadData(1)">🔄</el-button>
            <el-button size="small" type="success" @click="showAdd=true" v-if="isAdmin">➕ 新增</el-button>
            <el-button size="small" type="primary" @click="exportTable">📥 导出</el-button>
            <el-button size="small" @click="showDDLFn">📐 DDL</el-button>
            <el-button size="small" @click="showStatsFn">📊</el-button>
            <el-button v-if="isSuperAdmin" size="small" type="danger" plain @click="showSql = true">🔧 SQL</el-button>
            <el-popconfirm v-if="isSuperAdmin&&canTruncate" title="清空将删除全部数据且不可恢复！" @confirm="truncateTable">
              <template #reference><el-button size="small" type="danger" plain>🗑 清空</el-button></template>
            </el-popconfirm>
          </div>
        </div>

          <!-- 数据表格 -->
          <el-table v-if="activeTable" :data="rows" border stripe size="small" max-height="520"
            @selection-change="onSelect">
            <el-table-column type="selection" width="40" />
            <el-table-column v-for="col in columns" :key="col.name" :prop="col.name"
              :label="col.name" :width="colWidth(col)" show-overflow-tooltip>
              <template #default="{ row }">
                <span :style="{ color: row[col.name] === null ? '#ccc' : '#333' }">
                  {{ row[col.name] ?? 'NULL' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right" v-if="isAdmin">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="editRow(row)">✏️</el-button>
                <el-popconfirm v-if="isSuperAdmin" title="确认删除？" @confirm="deleteRow(row.id)">
                  <template #reference>
                    <el-button size="small" text type="danger">🗑</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div v-if="activeTable && total > pageSize" style="margin-top:12px;text-align:center">
            <el-pagination background layout="prev, pager, next" :total="total"
              :page-size="pageSize" v-model:current-page="page" @change="loadData" />
          </div>

          <el-empty v-if="!activeTable" description="请从左侧选择要浏览的数据表" />
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑数据" width="520px">
      <el-form label-width="100px">
        <el-form-item v-for="col in editableCols" :key="col" :label="col">
          <el-input v-model="editForm[col]" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="doEdit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- DDL 弹窗 -->
    <el-dialog v-model="showDDL" title="建表DDL" width="600px">
      <el-input v-model="ddlText" type="textarea" :rows="10" readonly />
    </el-dialog>

    <!-- 新增行弹窗 -->
    <el-dialog v-model="showAdd" title="新增数据行" width="500px">
      <el-form label-width="110px">
        <el-form-item v-for="col in columns" :key="col.name" :label="col.name" v-show="col.name!=='id'">
          <el-input v-model="addForm[col.name]" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd=false">取消</el-button>
        <el-button type="primary" @click="doAdd" :loading="saving">插入</el-button>
      </template>
    </el-dialog>

    <!-- 统计弹窗 -->
    <el-dialog v-model="showStats" title="数据库统计" width="450px">
      <el-descriptions :column="1" border size="small" v-if="stats">
        <el-descriptions-item label="数据库文件">{{ stats.db_file }}</el-descriptions-item>
        <el-descriptions-item label="文件大小">{{ stats.db_size_kb }} KB</el-descriptions-item>
        <el-descriptions-item label="数据页">{{ stats.page_count }}</el-descriptions-item>
        <el-descriptions-item label="空闲页">{{ stats.freelist }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="stats?.tables||[]" size="small" style="margin-top:12px">
        <el-table-column prop="name" label="表名" />
        <el-table-column prop="rows" label="行数" width="80" />
        <el-table-column prop="columns" label="列数" width="60" />
      </el-table>
    </el-dialog>
    <el-dialog v-model="showSql" title="SQL 查询（仅超管）" width="700px">
      <el-input v-model="sqlText" type="textarea" :rows="4" placeholder="SELECT * FROM daily_data LIMIT 10" />
      <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center">
        <span style="color:#999;font-size:12px">仅允许 SELECT 查询</span>
        <el-button type="primary" @click="runSql" :loading="sqlRunning">执行</el-button>
      </div>
      <el-table v-if="sqlResult" :data="sqlResult.rows" border size="small" max-height="300" style="margin-top:12px">
        <el-table-column v-for="c in sqlResult.columns" :key="c" :prop="c" :label="c" show-overflow-tooltip />
      </el-table>
      <div v-if="sqlResult" style="margin-top:8px;color:#999">{{ sqlResult.count }} 行</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import request from '@/api'
import { useRole } from '@/composables/useRole'
import { ElMessage } from 'element-plus'

const { isAdmin, isSuperAdmin } = useRole()

const tables = ref([])
const activeTable = ref('')
const columns = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loadingTables = ref(false)
const loadingData = ref(false)
const selectedRows = ref([])

// 编辑
const editVisible = ref(false)
const editForm = ref({})
const editRowId = ref(null)
const editableCols = ref([])
const saving = ref(false)

// SQL
const showSql = ref(false)
const sqlText = ref('')
const sqlRunning = ref(false)
const sqlResult = ref(null)

// DDL
const showDDL = ref(false)
const ddlText = ref('')

// 新增
const showAdd = ref(false)
const addForm = ref({})

// 统计
const showStats = ref(false)
const stats = ref(null)

// 搜索
const searchText = ref('')

const canTruncate = computed(() => {
  const protected_ = ['users','sys_config','schema_version']
  return !protected_.includes(activeTable.value)
})

const formatTableName = (name) => {
  const map = {
    hourly_data: '小时数据', daily_data: '日报数据', monthly_data: '月报数据',
    quarterly_data: '季报数据', yearly_data: '年报数据', sys_config: '系统配置',
    users: '用户管理', import_record: '导入记录', operation_log: '操作日志',
    audit_log: '审计日志', collect_log: '采集日志'
  }
  return map[name] || name
}

const colWidth = (col) => {
  const name = col.name.toLowerCase()
  if (name === 'id') return 60
  if (name.includes('date') || name.includes('time')) return 140
  if (name.includes('desc') || name.includes('msg') || name.includes('detail')) return 200
  return 110
}

const loadTables = async () => {
  loadingTables.value = true
  try {
    tables.value = (await request.get('/db/tables')) || []
  } catch (e) {
    ElMessage.error('加载表列表失败')
  }
  loadingTables.value = false
}

const selectTable = (name) => {
  activeTable.value = name
  page.value = 1
  loadData(1)
}

const loadData = async (p) => {
  if (!activeTable.value) return
  loadingData.value = true
  try {
    const res = await request.get(`/db/table/${activeTable.value}`, { params: { page: p || page.value, page_size: pageSize.value } })
    columns.value = res.columns
    rows.value = res.rows
    total.value = res.total
    page.value = res.page
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  }
  loadingData.value = false
}

const onSelect = (rows) => { selectedRows.value = rows }

const editRow = (row) => {
  editRowId.value = row.id
  const skipCols = ['id', 'create_time', 'update_time']
  editableCols.value = columns.value.map(c => c.name).filter(n => !skipCols.includes(n))
  editForm.value = {}
  editableCols.value.forEach(k => { editForm.value[k] = row[k] ?? '' })
  editVisible.value = true
}

const doEdit = async () => {
  saving.value = true
  try {
    await request.put(`/db/table/${activeTable.value}/row/${editRowId.value}`, editForm.value)
    ElMessage.success('保存成功')
    editVisible.value = false
    loadData(page.value)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
  saving.value = false
}

const deleteRow = async (id) => {
  try {
    await request.delete(`/db/table/${activeTable.value}/row/${id}`)
    ElMessage.success('已删除')
    loadData(page.value)
    loadTables()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

const exportTable = () => {
  const csv = [columns.value.map(c => c.name).join(',')]
  rows.value.forEach(r => {
    csv.push(columns.value.map(c => {
      const v = r[c.name]
      return v != null ? '"' + String(v).replace(/"/g, '""') + '"' : ''
    }).join(','))
  })
  const blob = new Blob(['\uFEFF' + csv.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `${activeTable.value}.csv`; a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

const runSql = async () => {
  if (!sqlText.value.trim()) return
  sqlRunning.value = true
  try {
    sqlResult.value = await request.post('/db/execute', { sql: sqlText.value })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '执行失败')
  }
  sqlRunning.value = false
}

const showDDLFn = async () => {
  try {
    const r = await request.get(`/db/table/${activeTable.value}/ddl`)
    ddlText.value = r.ddl
    showDDL.value = true
  } catch (e) { ElMessage.error('获取失败') }
}

const doAdd = async () => {
  saving.value = true
  try {
    const data = {}
    for (const k in addForm.value) { if (addForm.value[k] !== '' && addForm.value[k] != null) data[k] = addForm.value[k] }
    await request.post(`/db/table/${activeTable.value}/row`, data)
    ElMessage.success('插入成功')
    showAdd.value = false
    addForm.value = {}
    loadData(page.value); loadTables()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '失败') }
  saving.value = false
}

const doSearch = () => {
  loadData(1) // 可扩展为服务端搜索
}

const showStatsFn = async () => {
  try { stats.value = await request.get('/db/stats'); showStats.value = true }
  catch { ElMessage.error('获取失败') }
}

const truncateTable = async () => {
  try {
    await request.delete(`/db/table/${activeTable.value}`)
    ElMessage.success('已清空')
    loadData(1); loadTables()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '失败') }
}

loadTables()
</script>

<style scoped>
.db-manager { width: 100%; height: calc(100vh - 80px); overflow: hidden; }
.db-layout { display: flex; height: 100%; }
.db-sidebar {
  width: 200px; min-width: 200px; height: 100%;
  background: #fff; border-right: 1px solid #e8e8e8;
  display: flex; flex-direction: column;
}
.sidebar-title {
  padding: 12px 14px; font-weight: 600; font-size: 15px;
  border-bottom: 1px solid #e8e8e8; flex-shrink: 0;
}
.sidebar-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.table-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 9px 14px; margin: 1px 6px; border-radius: 6px;
  cursor: pointer; transition: background 0.15s; font-size: 13px;
}
.table-item:hover { background: #f0f5ff; }
.table-item.active { background: #e6f4ff; color: #1677ff; font-weight: 600; }
.tname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.db-main {
  flex: 1; height: 100%; overflow-y: auto;
  padding: 12px 16px; background: #fafafa;
}
.empty-hint { text-align: center; color: #999; padding-top: 100px; }
.main-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; padding: 8px 0; flex-wrap: wrap; gap: 8px;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.info-text { color: #999; font-size: 13px; }
.toolbar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
</style>
