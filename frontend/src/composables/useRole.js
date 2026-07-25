import { ref } from 'vue'
import request from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const currentUser = ref({ name: '', role: 'guest' })
const users = ref([])

export function useRole() {
  const checkRole = async () => {
    try {
      const res = await request.get('/role/check')
      currentUser.value = res.current_user || { name: '', role: 'guest' }
      users.value = res.users || []
    } catch {
      currentUser.value = { name: '', role: 'guest' }
    }
  }

  const login = async () => {
    try {
      const { value: name } = await ElMessageBox.prompt('请输入姓名', '用户登录', { inputPlaceholder: '姓名' })
      if (!name) return false
      const { value: pin } = await ElMessageBox.prompt('请输入PIN码', '用户登录', {
        inputType: 'password', inputPattern: /^.{1,20}$/, inputErrorMessage: 'PIN需1-20位'
      })
      if (!pin) return false
      const res = await request.post('/role/switch', { name, pin })
      currentUser.value = { name: res.name, role: res.role }
      ElMessage.success(res.message)
      return true
    } catch (e) {
      if (e !== 'cancel' && e !== 'close') {
        ElMessage.error(e?.response?.data?.detail || '登录失败')
      }
      return false
    }
  }

  const logout = async () => {
    try {
      await request.post('/role/logout')
      currentUser.value = { name: '', role: 'guest' }
      ElMessage.success('已退出，请重新登录')
      return true
    } catch { return false }
  }

  const isAdmin = () => currentUser.value.role === 'super_admin' || currentUser.value.role === 'admin'
  const isSuperAdmin = () => currentUser.value.role === 'super_admin'
  const isOperator = () => currentUser.value.role === 'operator'
  const isGuest = () => !currentUser.value.role || currentUser.value.role === 'guest'

  return { currentUser, users, checkRole, login, logout, isAdmin, isOperator, isSuperAdmin, isGuest }
}
