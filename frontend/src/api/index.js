import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 错误去重：相同消息3秒内不重复弹
let lastErrorMsg = ''
let lastErrorTime = 0
const showError = (msg) => {
  const now = Date.now()
  if (msg !== lastErrorMsg || now - lastErrorTime > 3000) {
    lastErrorMsg = msg
    lastErrorTime = now
    ElMessage.error(msg)
  }
}

// 请求拦截器
service.interceptors.request.use(
  config => config,
  error => Promise.reject(error)
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code !== 200) {
      showError(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res.data
  },
  error => {
    const msg = error?.response?.data?.detail || error.message || '网络错误'
    showError(msg)
    return Promise.reject(error)
  }
)

export default service
