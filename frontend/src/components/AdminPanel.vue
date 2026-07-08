<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog, showDialog, showLoadingToast, closeToast } from 'vant'
import request from '../api/request.js'

const activeTab = ref(0)

// ========== 数据看板 ==========
const dashboard = ref(null)

// ========== 入驻审核 ==========
const applications = ref([])
const appStatus = ref('pending')
const appLoading = ref(false)

// ========== 订单管理 ==========
const orders = ref([])
const orderTotal = ref(0)
const orderPage = ref(1)
const orderStatusFilter = ref('')
const orderSearch = ref('')
const orderLoading = ref(false)
const orderDetail = ref(null)
const showOrderDetail = ref(false)

// ========== 提现审核 ==========
const withdrawals = ref([])
const withdrawTotal = ref(0)
const withdrawPage = ref(1)
const withdrawStatusFilter = ref('pending')
const withdrawLoading = ref(false)

// ========== 分佣配置 ==========
const commissionConfig = ref({ level_1_rate: 0.15, level_2_rate: 0.08, level_3_rate: 0.05 })
const editingLevel = ref(null)
const newRate = ref('')

// ========== 用户管理 ==========
const userList = ref([])
const userTotal = ref(0)
const userPage = ref(1)
const userSearch = ref('')
const userRoleFilter = ref('')
const userLoading = ref(false)
const showUserEdit = ref(false)
const editingUser = ref(null)
const editUserRole = ref('')
const editUserBalance = ref('')

// ========== 角色选择器 ==========
const showRolePicker = ref(false)
const onRoleSelect = (action) => {
  editUserRole.value = action.value
  showRolePicker.value = false
}

// ========== 数据看板 ==========
const fetchDashboard = async () => {
  try {
    const res = await request.get('/api/v1/admin/dashboard')
    dashboard.value = res.data
  } catch (e) {
    console.error('获取看板数据失败', e)
  }
}

// ========== 入驻审核 ==========
const appTabs = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' },
]

const fetchApplications = async (status) => {
  appLoading.value = true
  try {
    const url = status ? `/api/v1/admin/applications?status=${status}` : '/api/v1/admin/applications'
    const res = await request.get(url)
    applications.value = res.data
  } catch (e) {
    showToast('获取申请列表失败')
  } finally {
    appLoading.value = false
  }
}

const handleAppReview = async (app, action) => {
  const label = action === 'approved' ? '通过' : '拒绝'
  showConfirmDialog({
    title: `确认${label}`,
    message: `${label}「${app.real_name}」的入驻申请？`,
  }).then(async () => {
    try {
      await request.post('/api/v1/admin/applications/review', {
        application_id: app.id,
        status: action,
        remark: action === 'approved' ? '审核通过，欢迎加入' : '请完善资料后重新申请',
      })
      showSuccessToast(`${label}成功`)
      await fetchApplications(appStatus.value)
      await fetchDashboard()
    } catch (e) {
      showToast(e.response?.data?.detail || '操作失败')
    }
  }).catch(() => {})
}

// ========== 订单管理 ==========
const fetchOrders = async () => {
  orderLoading.value = true
  try {
    let url = `/api/v1/admin/orders?page=${orderPage.value}&page_size=20`
    if (orderStatusFilter.value) url += `&status=${orderStatusFilter.value}`
    if (orderSearch.value) url += `&search=${encodeURIComponent(orderSearch.value)}`
    const res = await request.get(url)
    orders.value = res.data.orders
    orderTotal.value = res.data.total
  } catch (e) {
    showToast('获取订单列表失败')
  } finally {
    orderLoading.value = false
  }
}

const viewOrderDetail = async (orderNo) => {
  try {
    const res = await request.get(`/api/v1/admin/orders/${orderNo}`)
    orderDetail.value = res.data
    showOrderDetail.value = true
  } catch (e) {
    showToast('获取订单详情失败')
  }
}

const statusLabel = (s) => {
  const map = { pending: '待支付', paid: '已支付', processing: '处理中', completed: '已完成' }
  return map[s] || s
}

const statusType = (s) => {
  const map = { pending: 'warning', paid: 'primary', processing: 'default', completed: 'success' }
  return map[s] || 'default'
}

// ========== 提现审核 ==========
const fetchWithdrawals = async () => {
  withdrawLoading.value = true
  try {
    let url = `/api/v1/admin/withdrawals?page=${withdrawPage.value}&page_size=20`
    if (withdrawStatusFilter.value) url += `&status=${withdrawStatusFilter.value}`
    const res = await request.get(url)
    withdrawals.value = res.data.withdrawals
    withdrawTotal.value = res.data.total
  } catch (e) {
    showToast('获取提现列表失败')
  } finally {
    withdrawLoading.value = false
  }
}

const withdrawTabs = [
  { key: 'pending', label: '待处理' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' },
]

const handleWithdrawReview = async (w, action) => {
  const label = action === 'approved' ? '通过' : '拒绝'
  showConfirmDialog({
    title: `确认${label}`,
    message: `${label}「${w.username}」的 ¥${w.amount} 提现申请？`,
  }).then(async () => {
    try {
      await request.post('/api/v1/admin/withdrawals/review', {
        request_id: w.id,
        status: action,
        remark: action === 'approved' ? '已转账' : '资料不完整',
      })
      showSuccessToast(`${label}成功`)
      await fetchWithdrawals()
      await fetchDashboard()
    } catch (e) {
      showToast(e.response?.data?.detail || '操作失败')
    }
  }).catch(() => {})
}

// ========== 分佣配置 ==========
const fetchCommissionConfig = async () => {
  try {
    const res = await request.get('/api/v1/admin/commission-config')
    commissionConfig.value = res.data
  } catch (e) {
    console.error('获取分佣配置失败', e)
  }
}

const startEditRate = (level) => {
  const key = `level_${level}_rate`
  editingLevel.value = level
  newRate.value = (commissionConfig.value[key] * 100).toFixed(0)
}

const cancelEditRate = () => {
  editingLevel.value = null
  newRate.value = ''
}

const saveRate = async (level) => {
  const rate = parseFloat(newRate.value) / 100
  if (isNaN(rate) || rate < 0 || rate > 1) {
    showToast('请输入有效的比例（0-100）')
    return
  }
  try {
    await axios.put('/api/v1/admin/commission-config', { level, rate })
    showSuccessToast(`第${level}级分佣比例已更新为 ${newRate.value}%`)
    editingLevel.value = null
    newRate.value = ''
    await fetchCommissionConfig()
  } catch (e) {
    showToast(e.response?.data?.detail || '更新失败')
  }
}

// ========== 用户管理 ==========
const fetchUsers = async () => {
  userLoading.value = true
  try {
    let url = `/api/v1/admin/users?page=${userPage.value}&page_size=50`
    if (userSearch.value) url += `&search=${encodeURIComponent(userSearch.value)}`
    if (userRoleFilter.value) url += `&role=${userRoleFilter.value}`
    const res = await request.get(url)
    userList.value = res.data.users
    userTotal.value = res.data.total
  } catch (e) {
    showToast('获取用户列表失败')
  } finally {
    userLoading.value = false
  }
}

const openUserEdit = (u) => {
  editingUser.value = u
  editUserRole.value = u.role
  editUserBalance.value = u.wallet_balance.toFixed(2)
  showUserEdit.value = true
}

const saveUserEdit = async () => {
  try {
    const payload = { role: editUserRole.value }
    if (editUserBalance.value !== undefined) payload.wallet_balance = parseFloat(editUserBalance.value)
    await axios.put(`/api/v1/admin/users/${editingUser.value.id}`, payload)
    showSuccessToast('用户信息已更新')
    showUserEdit.value = false
    await fetchUsers()
  } catch (e) {
    showToast(e.response?.data?.detail || '更新失败')
  }
}

const roleLabel = (role) => {
  const map = { user: '普通用户', promoter: '推广员', creator: '制作者', admin: '管理员' }
  return map[role] || role
}

const appStatusLabel = (s) => {
  const map = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }
  return map[s] || s
}

const appStatusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'default'
}

const withdrawStatusLabel = (s) => {
  const map = { pending: '待处理', approved: '已通过', rejected: '已拒绝' }
  return map[s] || s
}

const withdrawStatusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger' }
  return map[s] || 'default'
}

const onAdminTabChange = (index) => {
  activeTab.value = index
}

onMounted(() => {
  fetchDashboard()
  fetchApplications('pending')
  fetchOrders()
  fetchWithdrawals()
  fetchCommissionConfig()
  fetchUsers()
})
</script>

<template>
  <div class="admin-panel">
    <div class="header-card">
      <van-icon name="manager-o" size="28" />
      <span>管理后台</span>
    </div>

    <van-tabs v-model:active="activeTab" @change="onAdminTabChange" color="#1989fa" sticky offset-bottom="56">
      <!-- Tab 0: 数据看板 -->
      <van-tab title="📊 数据看板">
        <div v-if="dashboard" class="dashboard">
          <!-- 核心指标 -->
          <div class="metrics-grid">
            <div class="metric-card revenue">
              <div class="metric-val">¥{{ dashboard.total_revenue?.toFixed(2) || '0.00' }}</div>
              <div class="metric-lbl">累计营收</div>
            </div>
            <div class="metric-card orders">
              <div class="metric-val">{{ dashboard.total_orders || 0 }}</div>
              <div class="metric-lbl">总订单</div>
            </div>
            <div class="metric-card users">
              <div class="metric-val">{{ dashboard.total_users || 0 }}</div>
              <div class="metric-lbl">总用户</div>
            </div>
            <div class="metric-card commission">
              <div class="metric-val">¥{{ dashboard.total_commission_paid?.toFixed(2) || '0.00' }}</div>
              <div class="metric-lbl">佣金支出</div>
            </div>
          </div>

          <!-- 今日 / 本月 -->
          <div class="period-row">
            <div class="period-card">
              <div class="period-lbl">今日</div>
              <div class="period-stat">{{ dashboard.today_orders || 0 }} 笔订单</div>
              <div class="period-stat">¥{{ dashboard.today_revenue?.toFixed(2) || '0.00' }}</div>
            </div>
            <div class="period-card">
              <div class="period-lbl">本月</div>
              <div class="period-stat">{{ dashboard.month_orders || 0 }} 笔订单</div>
              <div class="period-stat">¥{{ dashboard.month_revenue?.toFixed(2) || '0.00' }}</div>
            </div>
          </div>

          <!-- 待处理事项 -->
          <div class="pending-card" v-if="dashboard.pending_orders > 0 || dashboard.pending_withdrawals > 0 || dashboard.pending_applications > 0">
            <div class="pending-title">待处理事项</div>
            <div v-if="dashboard.pending_orders > 0" class="pending-row">
              <span>⏳ 待支付订单</span>
              <span class="pending-num">{{ dashboard.pending_orders }}</span>
            </div>
            <div v-if="dashboard.pending_withdrawals > 0" class="pending-row">
              <span>💰 待审核提现</span>
              <span class="pending-num">{{ dashboard.pending_withdrawals }}</span>
            </div>
            <div v-if="dashboard.pending_applications > 0" class="pending-row">
              <span>📋 待审核入驻</span>
              <span class="pending-num">{{ dashboard.pending_applications }}</span>
            </div>
          </div>

          <!-- 角色分布 -->
          <div class="section-title">角色分布</div>
          <div class="role-row">
            <div class="role-item" v-for="(count, role) in dashboard.role_stats" :key="role">
              <div class="role-count">{{ count }}</div>
              <div class="role-name">{{ roleLabel(role) }}</div>
            </div>
          </div>

          <!-- 订单状态分布 -->
          <div class="section-title">订单状态</div>
          <div class="role-row">
            <div class="role-item" v-for="(count, status) in dashboard.order_status_stats" :key="status">
              <div class="role-count">{{ count }}</div>
              <div class="role-name">{{ statusLabel(status) }}</div>
            </div>
          </div>

          <!-- 7天趋势 -->
          <div class="section-title">近7天趋势</div>
          <div class="trend-table">
            <div class="trend-header">
              <span class="trend-col">日期</span>
              <span class="trend-col">订单</span>
              <span class="trend-col">营收</span>
            </div>
            <div v-for="d in dashboard.daily_trend" :key="d.date" class="trend-row">
              <span class="trend-col">{{ d.date }}</span>
              <span class="trend-col">{{ d.orders }}</span>
              <span class="trend-col">¥{{ d.revenue.toFixed(2) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="loading">加载看板数据中...</div>
      </van-tab>

      <!-- Tab 1: 入驻审核 -->
      <van-tab title="📋 入驻审核">
        <van-tabs :swipeable="false" color="#1989fa">
          <van-tab v-for="t in appTabs" :key="t.key" :title="t.label">
            <div @click="appStatus = t.key; fetchApplications(t.key)" style="cursor:pointer"></div>
            <div v-if="appLoading" class="loading">加载中...</div>
            <div v-else-if="applications.length === 0" class="empty">暂无记录</div>
            <div v-else class="app-list">
              <div v-for="app in applications" :key="app.id" class="app-card">
                <div class="app-header">
                  <span class="app-name">{{ app.real_name }}</span>
                  <van-tag round :type="appStatusType(app.status)">{{ appStatusLabel(app.status) }}</van-tag>
                </div>
                <div class="app-info"><van-icon name="contact" /> {{ app.username }}</div>
                <div class="app-info"><van-icon name="phone-o" /> {{ app.phone }}</div>
                <div class="app-info"><van-icon name="chat-o" /> {{ app.wechat }}</div>
                <div v-if="app.specialty" class="app-tags">
                  <van-tag v-for="s in app.specialty.split(',')" :key="s" plain size="small" style="margin-right:4px">{{ s.trim() }}</van-tag>
                </div>
                <div v-if="app.portfolio_desc" class="app-desc">作品: {{ app.portfolio_desc }}</div>
                <div v-if="app.experience" class="app-desc">经验: {{ app.experience }}</div>
                <div v-if="app.review_remark" class="app-remark">备注: {{ app.review_remark }}</div>
                <div class="app-time">申请时间: {{ app.created_at }}</div>
                <div v-if="app.status === 'pending'" class="app-actions">
                  <van-button type="success" size="small" round @click="handleAppReview(app, 'approved')">通过</van-button>
                  <van-button type="danger" size="small" round plain @click="handleAppReview(app, 'rejected')">拒绝</van-button>
                </div>
              </div>
            </div>
          </van-tab>
        </van-tabs>
      </van-tab>

      <!-- Tab 2: 订单管理 -->
      <van-tab title="📦 订单管理">
        <div class="filter-row">
          <van-field v-model="orderSearch" placeholder="搜索订单号/模板名" clearable @blur="fetchOrders" />
          <div class="status-chips">
            <van-tag v-for="s in ['', 'pending', 'paid', 'processing', 'completed']" :key="s"
              :type="orderStatusFilter === s ? 'primary' : 'default'"
              plain size="medium" style="margin:4px" @click="orderStatusFilter = s; orderPage = 1; fetchOrders()">
              {{ s ? statusLabel(s) : '全部' }}
            </van-tag>
          </div>
        </div>
        <div v-if="orderLoading" class="loading">加载中...</div>
        <div v-else-if="orders.length === 0" class="empty">暂无订单</div>
        <div v-else class="order-list">
          <div v-for="o in orders" :key="o.order_no" class="order-card" @click="viewOrderDetail(o.order_no)">
            <div class="order-header">
              <span class="order-no">{{ o.order_no }}</span>
              <van-tag :type="statusType(o.status)" round size="small">{{ statusLabel(o.status) }}</van-tag>
            </div>
            <div class="order-body">
              <div class="order-row">
                <span class="order-label">模板</span>
                <span>{{ o.template_category }}-{{ o.template_name }}</span>
              </div>
              <div class="order-row">
                <span class="order-label">金额</span>
                <span class="order-amount">¥{{ o.amount.toFixed(2) }}</span>
              </div>
              <div class="order-row">
                <span class="order-label">类型</span>
                <span>{{ o.order_type === 'custom_service' ? '定制服务' : '模板下载' }}</span>
              </div>
              <div class="order-row">
                <span class="order-label">时间</span>
                <span>{{ o.created_at }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="pagination" v-if="orderTotal > 20">
          <span>共 {{ orderTotal }} 条</span>
          <van-button size="small" :disabled="orderPage <= 1" @click="orderPage--; fetchOrders()">上一页</van-button>
          <span class="page-num">第 {{ orderPage }} 页</span>
          <van-button size="small" :disabled="orderPage * 20 >= orderTotal" @click="orderPage++; fetchOrders()">下一页</van-button>
        </div>
      </van-tab>

      <!-- Tab 3: 提现审核 -->
      <van-tab title="💰 提现审核">
        <div class="status-chips" style="margin-bottom:12px">
          <van-tag v-for="s in withdrawTabs" :key="s.key"
            :type="withdrawStatusFilter === s.key ? 'primary' : 'default'"
            plain size="medium" style="margin:4px" @click="withdrawStatusFilter = s.key; withdrawPage = 1; fetchWithdrawals()">
            {{ s.label }}
          </van-tag>
        </div>
        <div v-if="withdrawLoading" class="loading">加载中...</div>
        <div v-else-if="withdrawals.length === 0" class="empty">暂无提现记录</div>
        <div v-else class="withdraw-list">
          <div v-for="w in withdrawals" :key="w.id" class="withdraw-card">
            <div class="withdraw-header">
              <span class="withdraw-user">{{ w.username }}</span>
              <van-tag :type="withdrawStatusType(w.status)" round size="small">{{ withdrawStatusLabel(w.status) }}</van-tag>
            </div>
            <div class="withdraw-amount">¥{{ w.amount.toFixed(2) }}</div>
            <div class="withdraw-info">收款: {{ w.payment_info }}</div>
            <div v-if="w.admin_remark" class="withdraw-remark">备注: {{ w.admin_remark }}</div>
            <div class="withdraw-time">{{ w.created_at }}</div>
            <div v-if="w.status === 'pending'" class="withdraw-actions">
              <van-button type="success" size="small" round @click="handleWithdrawReview(w, 'approved')">通过</van-button>
              <van-button type="danger" size="small" round plain @click="handleWithdrawReview(w, 'rejected')">拒绝</van-button>
            </div>
          </div>
        </div>
        <div class="pagination" v-if="withdrawTotal > 20">
          <span>共 {{ withdrawTotal }} 条</span>
          <van-button size="small" :disabled="withdrawPage <= 1" @click="withdrawPage--; fetchWithdrawals()">上一页</van-button>
          <span class="page-num">{{ withdrawPage }}</span>
          <van-button size="small" :disabled="withdrawPage * 20 >= withdrawTotal" @click="withdrawPage++; fetchWithdrawals()">下一页</van-button>
        </div>
      </van-tab>

      <!-- Tab 4: 系统设置 -->
      <van-tab title="⚙️ 系统设置">
        <!-- 分佣比例 -->
        <div class="settings-section">
          <div class="settings-title">分佣比例配置</div>
          <div class="rate-card" v-for="level in [1, 2, 3]" :key="level">
            <div class="rate-label">第 {{ level }} 级分佣</div>
            <div v-if="editingLevel !== level" class="rate-value" @click="startEditRate(level)">
              {{ (commissionConfig[`level_${level}_rate`] * 100).toFixed(0) }}% <van-icon name="edit" />
            </div>
            <div v-else class="rate-edit">
              <van-field v-model="newRate" type="number" placeholder="百分比" style="width:100px" />
              <van-button type="primary" size="small" round @click="saveRate(level)">保存</van-button>
              <van-button size="small" round plain @click="cancelEditRate">取消</van-button>
            </div>
          </div>
        </div>

        <!-- 用户管理 -->
        <div class="settings-section">
          <div class="settings-title">用户管理</div>
          <div class="filter-row">
            <van-field v-model="userSearch" placeholder="搜索用户名" clearable @blur="fetchUsers" />
            <div class="status-chips">
              <van-tag v-for="r in ['', 'user', 'promoter', 'creator']" :key="r"
                :type="userRoleFilter === r ? 'primary' : 'default'"
                plain size="medium" style="margin:4px" @click="userRoleFilter = r; userPage = 1; fetchUsers()">
                {{ r ? roleLabel(r) : '全部' }}
              </van-tag>
            </div>
          </div>
          <div v-if="userLoading" class="loading">加载中...</div>
          <div v-else-if="userList.length === 0" class="empty">暂无用户</div>
          <div v-else class="user-list">
            <div v-for="u in userList" :key="u.id" class="user-card" @click="openUserEdit(u)">
              <div class="user-header">
                <span class="user-name">{{ u.username }}</span>
                <van-tag round size="small">{{ roleLabel(u.role) }}</van-tag>
              </div>
              <div class="user-body">
                <span>ID: {{ u.id }}</span>
                <span>余额: ¥{{ u.wallet_balance?.toFixed(2) || '0.00' }}</span>
                <span>团队: {{ u.team_size || 0 }}人</span>
              </div>
            </div>
          </div>
        </div>
      </van-tab>
    </van-tabs>

    <!-- 订单详情弹窗 -->
    <van-dialog v-model:show="showOrderDetail" title="订单详情" show-cancel-button cancel-text="关闭">
      <div v-if="orderDetail" class="detail-content">
        <div class="detail-row"><span class="detail-label">订单号</span><span>{{ orderDetail.order.order_no }}</span></div>
        <div class="detail-row"><span class="detail-label">状态</span><van-tag :type="statusType(orderDetail.order.status)" round>{{ statusLabel(orderDetail.order.status) }}</van-tag></div>
        <div class="detail-row"><span class="detail-label">金额</span><span class="order-amount">¥{{ orderDetail.order.amount?.toFixed(2) }}</span></div>
        <div class="detail-row"><span class="detail-label">类型</span><span>{{ orderDetail.order.order_type === 'custom_service' ? '定制服务' : '模板下载' }}</span></div>
        <div v-if="orderDetail.order.template" class="detail-row"><span class="detail-label">模板</span><span>{{ orderDetail.order.template.category }}-{{ orderDetail.order.template.name }}</span></div>
        <div v-if="orderDetail.order.user" class="detail-row"><span class="detail-label">用户</span><span>{{ orderDetail.order.user.username }} ({{ orderDetail.order.user.role }})</span></div>
        <div v-if="orderDetail.order.creator" class="detail-row"><span class="detail-label">制作者</span><span>{{ orderDetail.order.creator.username }}</span></div>
        <div v-if="orderDetail.order.ref_user" class="detail-row"><span class="detail-label">推广员</span><span>{{ orderDetail.order.ref_user.username }}</span></div>
        <div v-if="orderDetail.order.custom_requirements" class="detail-row"><span class="detail-label">需求</span><span>{{ orderDetail.order.custom_requirements }}</span></div>
        <div class="detail-row"><span class="detail-label">创建时间</span><span>{{ orderDetail.order.created_at }}</span></div>

        <div v-if="orderDetail.commissions?.length > 0" class="commission-section">
          <div class="section-title">分佣记录</div>
          <div v-for="c in orderDetail.commissions" :key="c.id" class="commission-row">
            <van-tag size="mini" :type="c.level === 1 ? 'danger' : c.level === 2 ? 'warning' : 'default'" round>
              {{ c.level === 1 ? '一级' : c.level === 2 ? '二级' : '三级' }}
            </van-tag>
            <span>用户#{{ c.user_id }}</span>
            <span>比例 {{ (c.rate * 100).toFixed(0) }}%</span>
            <span class="ci-amount">+¥{{ c.amount.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </van-dialog>

    <!-- 用户编辑弹窗 -->
    <van-dialog v-model:show="showUserEdit" title="编辑用户" show-cancel-button @confirm="saveUserEdit">
      <div class="edit-user-form" v-if="editingUser">
        <div class="edit-row">
          <span class="edit-label">用户名</span>
          <span>{{ editingUser.username }} (ID: {{ editingUser.id }})</span>
        </div>
        <van-field v-model="editUserRole" label="角色" readonly is-link @click="showRolePicker = true" />
        <van-field v-model="editUserBalance" label="余额" type="digit" />
      </div>
    </van-dialog>

    <!-- 角色选择器 -->
    <van-action-sheet v-model:show="showRolePicker" :actions="[{name:'普通用户',value:'user'},{name:'推广员',value:'promoter'},{name:'制作者',value:'creator'},{name:'管理员',value:'admin'}]" @select="onRoleSelect" />
  </div>
</template>

<script>
</script>

<style scoped>
.admin-panel { padding: 15px; background: #f7f8fa; min-height: calc(100vh - 96px); }
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.header-card { display: flex; align-items: center; gap: 8px; padding: 15px; background: linear-gradient(135deg, #1989fa, #0e7eff); border-radius: 12px; color: white; font-size: 18px; font-weight: bold; margin-bottom: 15px; }

/* ========== 数据看板 ========== */
.metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
.metric-card { border-radius: 10px; padding: 16px; text-align: center; color: white; }
.metric-card.revenue { background: linear-gradient(135deg, #ff6034, #ee0a24); }
.metric-card.orders { background: linear-gradient(135deg, #1989fa, #0e7eff); }
.metric-card.users { background: linear-gradient(135deg, #07c160, #06ad56); }
.metric-card.commission { background: linear-gradient(135deg, #ff976a, #ff6034); }
.metric-val { font-size: 22px; font-weight: bold; font-family: DIN, sans-serif; }
.metric-lbl { font-size: 12px; opacity: 0.9; margin-top: 4px; }

.period-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
.period-card { background: white; border-radius: 10px; padding: 15px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.period-lbl { font-size: 13px; color: #999; margin-bottom: 8px; }
.period-stat { font-size: 16px; font-weight: bold; color: #333; }

.pending-card { background: #fff7cc; border-radius: 10px; padding: 12px; margin-bottom: 15px; border: 1px solid #ffe58f; }
.pending-title { font-size: 14px; font-weight: bold; color: #d48806; margin-bottom: 8px; }
.pending-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; color: #666; }
.pending-num { font-weight: bold; color: #d48806; }

.section-title { font-size: 15px; font-weight: bold; color: #333; margin: 15px 0 10px; }
.role-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.role-item { flex: 1; min-width: 70px; background: white; border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.role-count { font-size: 20px; font-weight: bold; color: #1989fa; }
.role-name { font-size: 11px; color: #999; margin-top: 3px; }

.trend-table { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.trend-header { display: flex; background: #f7f8fa; padding: 10px; font-size: 12px; color: #999; font-weight: bold; }
.trend-row { display: flex; padding: 10px; border-top: 1px solid #f0f0f0; font-size: 13px; }
.trend-col { flex: 1; text-align: center; }

/* ========== 申请审核 ========== */
.app-list { padding: 5px 0; }
.app-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.app-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.app-name { font-weight: bold; font-size: 15px; }
.app-info { font-size: 13px; color: #666; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; }
.app-tags { margin: 8px 0; }
.app-desc { font-size: 12px; color: #666; margin-top: 6px; padding: 8px; background: #f7f8fa; border-radius: 6px; }
.app-remark { font-size: 12px; color: #999; margin-top: 6px; font-style: italic; }
.app-time { font-size: 11px; color: #ccc; margin-top: 6px; }
.app-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }

/* ========== 订单 ========== */
.filter-row { margin-bottom: 12px; }
.filter-row .van-field { margin-bottom: 8px; }
.status-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.order-list { padding: 5px 0; }
.order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); cursor: pointer; }
.order-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.order-no { font-weight: bold; font-size: 14px; font-family: monospace; }
.order-body { font-size: 13px; }
.order-row { display: flex; padding: 3px 0; color: #666; }
.order-label { width: 50px; color: #999; flex-shrink: 0; }
.order-amount { font-weight: bold; color: #ee0a24; }

/* ========== 提现 ========== */
.withdraw-list { padding: 5px 0; }
.withdraw-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.withdraw-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.withdraw-user { font-weight: bold; font-size: 15px; }
.withdraw-amount { font-size: 22px; font-weight: bold; color: #ee0a24; margin-bottom: 6px; }
.withdraw-info { font-size: 13px; color: #666; margin-bottom: 4px; }
.withdraw-remark { font-size: 12px; color: #999; font-style: italic; margin-top: 4px; }
.withdraw-time { font-size: 11px; color: #ccc; margin-top: 6px; }
.withdraw-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }

/* ========== 系统设置 ========== */
.settings-section { margin-bottom: 20px; }
.settings-title { font-size: 15px; font-weight: bold; color: #333; margin-bottom: 12px; padding-left: 8px; border-left: 3px solid #1989fa; }
.rate-card { background: white; border-radius: 8px; padding: 12px 15px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.rate-label { font-size: 14px; color: #333; }
.rate-value { font-size: 18px; font-weight: bold; color: #1989fa; cursor: pointer; display: flex; align-items: center; gap: 6px; }
.rate-edit { display: flex; align-items: center; gap: 8px; }

/* 用户卡片 */
.user-list { padding: 5px 0; }
.user-card { background: white; border-radius: 10px; padding: 12px 15px; margin-bottom: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); cursor: pointer; }
.user-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.user-name { font-weight: bold; font-size: 14px; }
.user-body { font-size: 12px; color: #999; display: flex; gap: 15px; }

/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 15px 0; font-size: 13px; color: #999; }
.page-num { font-weight: bold; color: #666; }

/* 详情弹窗 */
.detail-content { padding: 10px 5px; max-height: 60vh; overflow-y: auto; }
.detail-row { display: flex; padding: 6px 0; font-size: 13px; border-bottom: 1px solid #f0f0f0; }
.detail-label { width: 70px; color: #999; flex-shrink: 0; }
.commission-section { margin-top: 15px; }
.commission-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; }
.ci-amount { color: #07c160; font-weight: bold; margin-left: auto; }

/* 编辑表单 */
.edit-user-form { padding: 15px 0; }
.edit-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 13px; color: #666; }
.edit-label { color: #999; }
</style>
