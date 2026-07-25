import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '@/layout/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '实时仪表盘' }
      },
      {
        path: 'hourly',
        name: 'HourlyData',
        component: () => import('@/views/HourlyData.vue'),
        meta: { title: '小时数据' }
      },
      {
        path: 'daily',
        name: 'DailyData',
        component: () => import('@/views/DailyData.vue'),
        meta: { title: '日报数据' }
      },
      {
        path: 'monthly',
        name: 'MonthlyData',
        component: () => import('@/views/MonthlyData.vue'),
        meta: { title: '月报数据' }
      },
      {
        path: 'quarterly',
        name: 'QuarterlyData',
        component: () => import('@/views/QuarterlyData.vue'),
        meta: { title: '季报数据' }
      },
      {
        path: 'yearly',
        name: 'YearlyData',
        component: () => import('@/views/YearlyData.vue'),
        meta: { title: '年报数据' }
      },
      {
        path: 'chart',
        name: 'ChartAnalysis',
        component: () => import('@/views/ChartAnalysis.vue'),
        meta: { title: '图表分析' }
      },
      {
        path: 'calendar',
        name: 'Calendar',
        component: () => import('@/views/Calendar.vue'),
        meta: { title: '热点日历' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' }
      },
      {
        path: 'database',
        name: 'DatabaseManager',
        component: () => import('@/views/DatabaseManager.vue'),
        meta: { title: '数据库管理' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
