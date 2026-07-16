<script setup>
import { ref, onMounted, watch } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../../api/request'

const users = ref([])
const userLoading = ref(true)
const userActiveTab = ref(0)
const userTabs = [
  { key: '', label: '全部' },
  { key: 'user', label: '普通用户' },
  { key: 'promoter', label: '推广员' },
  { key: 'creator', label: '制作者' },
  { key: 'admin', label: '管理员' }
]

async function fetchUsers(role = '') {
  try {
    userLoading.value = true
    const params = { role }
    const res = await request.get('/admin/users', { params })
    users.value = res.data?.users || []
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    userLoading.value = false
  }
}

async function updateUserRole(userId, newRole) {
  try {
    await request.put(`/admin/users/${userId}`, { role: newRole })
    showSuccessToast('已更新角色')
    await fetchUsers(userTabs[userActiveTab.value].key)
  } catch (e) {
    showToast(e.response?.data?.detail || '更新失败')
  }
}

async function updateBalance(userId, newBalance) {
  try {
    await request.put(`/admin/users/${userId}`, { wallet_balance: newBalance })
    showSuccessToast('已更新余额')
    await fetchUsers(userTabs[userActiveTab.value].key)
  } catch (e) {
    showToast(e.response?.data?.detail || '更新失败')
  }
}

const roleLabel = (r) => {
  const map = { user: '普通用户', promoter: '推广员', creator: '制作者', admin: '管理员' }
  return map[r] || r
}

async function openRolePicker(u) {
  editingUser.value = u
  selectedRole.value = u.role
  showRoleDialog.value = true
}

async function confirmRole() {
  if (!editingUser.value) return
  showRoleDialog.value = false
  await updateUserRole(editingUser.value.id, selectedRole.value)
}

const showRoleDialog = ref(false)
const editingUser = ref(null)
const selectedRole = ref('user')

defineExpose({ fetchUsers, userActiveTab })

onMounted(() => fetchUsers())
watch(userActiveTab, (idx) => fetchUsers(userTabs[idx].key))
</script>

<template>
  <div class="admin-sub">
    <van-tabs v-model:active="userActiveTab" :swipeable="false" color="#1989fa">
      <van-tab v-for="t in userTabs" :key="t.key" :title="t.label" />
    </van-tabs>
    <div v-if="userLoading" class="loading">加载中...</div>
    <div v-else-if="users.length === 0" class="empty">暂无用户</div>
    <div v-else class="user-list">
      <div v-for="u in users" :key="u.id" class="user-card">
        <div class="user-header">
          <span class="user-name">{{ u.username }}</span>
          <van-tag round :type="u.role === 'admin' ? 'danger' : u.role === 'creator' ? 'primary' : 'default'">{{ roleLabel(u.role) }}</van-tag>
        </div>
        <div class="user-info">ID: {{ u.id }}</div>
        <div class="user-info">余额: ¥{{ u.wallet_balance?.toFixed(2) }}</div>
        <div class="user-info">冻结保证金: ¥{{ u.deposit_frozen?.toFixed(2) || '0.00' }}</div>
        <div class="user-info">推广人: {{ u.parent_id || '无' }}</div>
        <div class="user-info">团队: {{ u.team_size || 0 }} 人</div>
        <div class="user-time">{{ u.created_at }}</div>
        <div class="user-actions">
          <van-button size="small" type="warning" plain @click="() => openRolePicker(u)">改角色</van-button>
          <van-button size="small" type="primary" plain @click="() => { const b = prompt('输入新余额:'); if(b !== null) updateBalance(u.id, parseFloat(b)) }">改余额</van-button>
        </div>
      </div>
    </div>

    <van-dialog v-model:show="showRoleDialog" :show-confirm-button="false" title="修改角色">
      <div style="padding: 20px;">
        <div class="role-option" :class="{ active: selectedRole === 'user' }" @click="selectedRole = 'user'">
          普通用户
        </div>
        <div class="role-option" :class="{ active: selectedRole === 'admin' }" @click="selectedRole = 'admin'">
          管理员
        </div>
      </div>
      <div style="padding: 10px 20px;">
        <van-button type="primary" block @click="confirmRole">确认</van-button>
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.user-list { padding: 5px 0; }
.user-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.user-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.user-name { font-weight: bold; font-size: 15px; }
.user-info { font-size: 13px; color: #666; margin-bottom: 3px; }
.user-time { font-size: 11px; color: #ccc; margin-top: 6px; }
.user-actions { display: flex; gap: 8px; margin-top: 10px; justify-content: flex-end; }
.role-option { padding: 12px 16px; margin-bottom: 8px; border-radius: 8px; border: 1px solid #ebedf0; text-align: center; cursor: pointer; transition: all 0.2s; }
.role-option:hover { background: #f7f8fa; }
.role-option.active { background: #1989fa; color: white; border-color: #1989fa; }
</style>
