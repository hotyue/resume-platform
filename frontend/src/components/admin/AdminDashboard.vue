<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '../../api/request'

const dashboard = ref(null)
const loading = ref(true)

const roleLabel = (role) => {
  const map = { user: '普通用户', promoter: '推广员', creator: '制作者', admin: '管理员' }
  return map[role] || role
}

const statusLabel = (s) => {
  const map = {
    pending: '待支付', paid: '已支付', awaiting_claim: '待接单',
    claimed: '已接单', in_progress: '制作中', delivered: '已交付',
    accepted: '已验收', refunded: '已退款', cancelled: '已取消', completed: '已完成', processing: '处理中'
  }
  return map[s] || s
}

async function fetchDashboard() {
  try {
    loading.value = true
    const res = await request.get('/admin/dashboard')
    dashboard.value = res.data
  } catch (e) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

defineExpose({ fetchDashboard })

onMounted(fetchDashboard)
</script>

<template>
  <div class="admin-sub">
    <div v-if="loading" class="loading">加载看板数据中...</div>
    <div v-else-if="dashboard" class="dashboard">
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
    <div v-else class="empty">暂无数据</div>
  </div>
</template>

<style scoped>
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
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
</style>
