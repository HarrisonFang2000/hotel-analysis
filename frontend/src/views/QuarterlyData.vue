<template>
  <div class="quarterly-data">
    <el-card>
      <template #header>
        <div class="page-header">
          <span>季报数据</span>
          <el-date-picker v-model="year" type="year" value-format="YYYY" @change="loadData" />
        </div>
      </template>
      <el-table :data="tableData" border stripe>
        <el-table-column prop="data_quarter" label="周期" width="130">
          <template #default="{row}">{{row.data_year}}年Q{{row.data_quarter}}</template>
        </el-table-column>
        <el-table-column prop="days" label="天数" width="100" align="right" />
        <el-table-column prop="sold_rooms" label="已售房间数" width="130" align="right" />
        <el-table-column prop="occupancy_rate" label="平均出租率" width="150" align="right">
          <template #default="{row}">{{row.occupancy_rate}}%</template>
        </el-table-column>
        <el-table-column prop="revpar" label="平均单房收益" width="150" align="right">
          <template #default="{row}">¥{{row.revpar}}</template>
        </el-table-column>
        <el-table-column prop="adr" label="平均房价" width="130" align="right">
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
import { ref, onMounted } from 'vue'
import request from '@/api'

const year = ref(new Date().getFullYear().toString())
const tableData = ref([])

const loadData = async () => {
  tableData.value = await request.get('/quarterly/list', { params: { year: year.value } })
}

onMounted(() => loadData())
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
