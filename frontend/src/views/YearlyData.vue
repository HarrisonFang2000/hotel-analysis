<template>
  <div class="yearly-data">
    <el-card>
      <template #header>
        <span>年报数据</span>
      </template>
      <el-table :data="tableData" border stripe>
        <el-table-column prop="data_year" label="年份" width="100" />
        <el-table-column prop="valid_days" label="有效天数" width="120" align="right" />
        <el-table-column prop="sold_rooms" label="累计售出房间" width="150" align="right" />
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

const tableData = ref([])

const loadData = async () => {
  tableData.value = await request.get('/yearly/list')
}

onMounted(() => loadData())
</script>
