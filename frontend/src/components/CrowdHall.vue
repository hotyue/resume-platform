<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog, showDialog } from 'vant'
import request from '../api/request.js'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const activeTab = ref(0)
const pendingOrders = ref([])
const myOrders = ref([])
const isCreator = ref(false)
const loadingOrders = ref(false)

const fetchOrders = async () => {
  loadingOrders.value = true
  try {
    if (activeTab.value === 0) {
      const res = await request.get('/creator/orders?tab=pending')
      pendingOrders.value = res.data
    } else {
      const res = await request.get('/creator/orders?tab=mine')
      myOrders.value = res.data
    }
  } catch (error) {
    if (error.response?.status === 403) {
      showToast('请先申请成为制作者')
    }
  } finally {
    loadingOrders.value = false
  }
}

const onTabChange = (index) => {
  fetchOrders()
}

const takeOrder = async (order_no) => {
  showConfirmDialog({
    title: '确认接单',
    message: '接单后 24 小时内需完成交付，超时将被重新发布到众包大厅',
  })
    .then(async () => {
      try {
        await request.post('/creator/take', { order_no })
        showSuccessToast('抢单成功！')
        fetchOrders()
      } catch (error) {
        if (error.response?.status === 403) {
          showToast('只有制作者才能抢单')
        } else {
          showToast(error.response?.data?.detail || '抢单失败')
        }
      }
    })
    .catch(() => {})
}

const deliverOrder = async (order_no) => {
  let fileUrl = ''
  let remark = ''

  showDialog({
    title: '交付订单',
    message: '请填写交付文件路径和备注',
    showInput: true,
    inputValue: { type: 'textarea', placeholder: '文件路径 (如: /assets/deliveries/xxx.doc)' },
  })
    .then(async ({ value }) => {
      fileUrl = value || ''
      showDialog({
        title: '交付备注（可选）',
        message: '填写给买家的备注',
        showInput: true,
      })
        .then(async ({ value }) => {
          remark = value || ''
          showConfirmDialog({
            title: '确认交付',
            message: '交付后等待买家验收',
          })
            .then(async () => {
              try {
                await request.post('/creator/deliver', {
                  order_no,
                  file_url: fileUrl,
                  remark: remark,
                })
                showSuccessToast('已交付，等待买家验收')
                fetchOrders()
              } catch (error) {
                showToast(error.response?.data?.detail || '交付失败')
              }
            })
            .catch(() => {})
        })
        .catch(() => {})
    })
    .catch(() => {})
}

const downloadBaseTemplate = (order_no) => {
  window.location.href = `/api/v1/orders/download/${order_no}`
}

const statusLabel = (s) => {
  const map = {
    awaiting_claim: '待抢单',
    in_progress: '制作中',
    delivered: '待验收',
    accepted: '已验收',
    rejected: '已退回',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[s] || s
}

const statusType = (s) => {
  const map = {
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    rejected: 'danger',
    completed: 'success',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

const formatTime = (ts) => {
  if (!ts) return '-'
  const d = new Date(ts)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

const formatCountdown = (hours) => {
  if (hours === null || hours === undefined) return '-'
  if (hours <= 0) return '已超时'
  const h = Math.floor(hours)
  const m = Math.floor((hours - h) * 60)
  if (h > 0 && m > 0) return `${h} 小时 ${m} 分钟`
  if (h > 0) return `${h} 小时`
  return `${m} 分钟`
}

const progressStep = (order) => {
  if (order.status === 'completed' || order.status === 'accepted') return 2
  if (order.delivery_status === 'delivered' || order.status === 'delivered') return 1
  if (order.status === 'in_progress') return 0
  return -1
}

onMounted(() => {
  isCreator.value = auth.isCreator
  fetchOrders()
  // 每 60 秒刷新订单列表（倒计时更新）
  setInterval(fetchOrders, 60000)
})
</script>

<template>
  <div class="crowd-hall">
    <!-- 非制作者提示 -->
    <div v-if="!isCreator" class="not-creator">
      <van-empty description="请先申请成为制作者">
        <van-button type="primary" round to="/creator">去申请</van-button>
      </van-empty>
    </div>

    <van-tabs v-else v-model:active="activeTab" @change="onTabChange" color="#07c160">
      <!-- 任务大厅 -->
      <van-tab title="任务大厅">
        <div v-if="loadingOrders" class="loading">加载中...</div>
        <div v-else-if="pendingOrders.length === 0" class="empty">暂无待接订单</div>
        <div v-else class="order-list">
          <div v-for="o in pendingOrders" :key="o.order_no" class="order-card">
            <div class="oc-header">
              <span class="oc-order-no">ORD-{{ o.order_no ? o.order_no.slice(-8) : '' }}</span>
              <van-tag round :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
            </div>
            <div class="oc-body">
              <div class="oc-row">
                <span class="oc-label">模板名称</span>
                <span class="oc-val">{{ o.template_name }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">订单金额</span>
                <span class="oc-val">¥{{ o.order_amount?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">报酬</span>
                <span class="oc-val oc-commission">¥{{ o.commission_amount?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">下单用户</span>
                <span class="oc-val">{{ o.user_name || '未知' }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">下单日期</span>
                <span class="oc-val">{{ formatTime(o.created_at) }}</span>
              </div>
              <div v-if="o.requirements" class="oc-req">
                <div class="oc-req-label">需求描述</div>
                <div class="oc-req-text">{{ o.requirements }}</div>
              </div>
            </div>
            <van-button type="primary" size="small" round block @click="takeOrder(o.order_no)">
              立即接单
            </van-button>
          </div>
        </div>
      </van-tab>

      <!-- 我的任务 -->
      <van-tab title="我的任务">
        <div v-if="loadingOrders" class="loading">加载中...</div>
        <div v-else-if="myOrders.length === 0" class="empty">暂无订单</div>
        <div v-else class="order-list">
          <div v-for="o in myOrders" :key="o.order_no" class="order-card">
            <div class="oc-header">
              <span class="oc-order-no">ORD-{{ o.order_no ? o.order_no.slice(-8) : '' }}</span>
              <van-tag round :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
            </div>

            <!-- 进度条 -->
            <div v-if="o.creator_id" class="oc-progress">
              <div class="oc-progress-bar">
                <div class="oc-progress-track" :class="'step-' + progressStep(o)">
                  <div class="oc-progress-dot" :class="progressStep(o) >= 0 ? 'done' : ''">
                    <van-icon v-if="progressStep(o) >= 0" name="checked" size="10" color="#fff" />
                  </div>
                  <div class="oc-progress-line" :class="progressStep(o) >= 1 ? 'done' : ''"></div>
                  <div class="oc-progress-dot" :class="progressStep(o) >= 1 ? 'done' : (progressStep(o) === 0 ? 'active' : '')">
                    <van-icon v-if="progressStep(o) >= 1" name="checked" size="10" color="#fff" />
                  </div>
                  <div class="oc-progress-line" :class="progressStep(o) >= 2 ? 'done' : ''"></div>
                  <div class="oc-progress-dot" :class="progressStep(o) >= 2 ? 'done' : ''">
                    <van-icon v-if="progressStep(o) >= 2" name="checked" size="10" color="#fff" />
                  </div>
                </div>
                <div class="oc-progress-labels">
                  <span>制作中</span>
                  <span>已交付</span>
                  <span>已验收</span>
                </div>
              </div>
              <!-- 超时倒计时 -->
              <div v-if="o.status === 'in_progress'" class="oc-countdown" :class="o.hours_remaining <= 0 ? 'overdue' : (o.hours_remaining <= 2 ? 'urgent' : '')">
                <van-icon name="clock-o" size="12" />
                剩余 {{ formatCountdown(o.hours_remaining) }}
              </div>
            </div>

            <div class="oc-body">
              <div class="oc-row">
                <span class="oc-label">模板名称</span>
                <span class="oc-val">{{ o.template_name }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">订单金额</span>
                <span class="oc-val">¥{{ o.order_amount?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">报酬</span>
                <span class="oc-val oc-commission">¥{{ o.commission_amount?.toFixed(2) || '0.00' }}</span>
              </div>
              <div class="oc-row">
                <span class="oc-label">下单用户</span>
                <span class="oc-val">{{ o.user_name || '未知' }}</span>
              </div>
              <div v-if="o.requirements" class="oc-req">
                <div class="oc-req-label">需求描述</div>
                <div class="oc-req-text">{{ o.requirements }}</div>
              </div>
              <div v-if="o.claimed_at" class="oc-row">
                <span class="oc-label">接单时间</span>
                <span class="oc-val">{{ formatTime(o.claimed_at) }}</span>
              </div>
              <div v-if="o.delivered_at" class="oc-row">
                <span class="oc-label">交付时间</span>
                <span class="oc-val">{{ formatTime(o.delivered_at) }}</span>
              </div>
              <div v-if="o.accepted_at" class="oc-row">
                <span class="oc-label">验收时间</span>
                <span class="oc-val oc-accepted">{{ formatTime(o.accepted_at) }}</span>
              </div>
            </div>

            <!-- 状态提示 -->
            <div v-if="o.status === 'delivered'" class="oc-status-info oc-freeze">
              <van-icon name="clock-o" size="12" /> 等待买家验收（距离自动验收 {{ formatCountdown(o.accept_hours_remaining) }}）
            </div>
            <div v-if="o.status === 'accepted' || o.status === 'completed'" class="oc-status-info oc-success">
              <van-icon name="checked" size="12" /> 验收通过，佣金已入账
            </div>

            <!-- 操作按钮 -->
            <div class="oc-actions">
              <van-button v-if="o.status === 'in_progress'" type="primary" size="small" round block @click="deliverOrder(o.order_no)">
                提交交付
              </van-button>
              <van-button v-if="o.status === 'rejected'" type="warning" size="small" round block @click="deliverOrder(o.order_no)">
                重新交付
              </van-button>
              <van-button type="default" size="small" round block plain style="margin-top:6px" @click="downloadBaseTemplate(o.order_no)">
                下载底稿模板
              </van-button>
            </div>
          </div>
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<style scoped>
.crowd-hall { padding-bottom: 20px; background: #f7f8fa; min-height: 100vh; }
.not-creator { padding: 60px 15px; }

.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }

.order-list { padding: 5px 0; }

.order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

.oc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
.oc-order-no { font-size: 13px; color: #999; font-family: monospace; }

.oc-body { margin-bottom: 10px; }
.oc-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
.oc-label { font-size: 13px; color: #999; min-width: 60px; }
.oc-val { font-size: 13px; color: #323233; text-align: right; word-break: break-all; }
.oc-commission { color: #07c160; font-weight: 600; }
.oc-accepted { color: #07c160; }

.oc-req { margin-top: 8px; padding: 8px 10px; background: #f7f8fa; border-radius: 6px; }
.oc-req-label { font-size: 11px; color: #999; margin-bottom: 4px; }
.oc-req-text { font-size: 12px; color: #666; line-height: 1.5; }

/* 进度条 */
.oc-progress { margin: 10px 0; }
.oc-progress-bar { display: flex; flex-direction: column; align-items: center; }
.oc-progress-track { display: flex; align-items: center; width: 100%; justify-content: space-between; padding: 0 10px; }
.oc-progress-dot { width: 22px; height: 22px; border-radius: 50%; background: #ddd; display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: background 0.3s; }
.oc-progress-dot.done { background: #07c160; }
.oc-progress-dot.active { background: #1989fa; }
.oc-progress-line { flex: 1; height: 2px; background: #ddd; margin: 0 4px; transition: background 0.3s; }
.oc-progress-line.done { background: #07c160; }
.oc-progress-labels { display: flex; width: 100%; justify-content: space-between; padding: 0 10px; margin-top: 6px; }
.oc-progress-labels span { font-size: 11px; color: #999; }

/* 倒计时 */
.oc-countdown { display: flex; align-items: center; gap: 4px; margin-top: 8px; font-size: 12px; color: #666; padding: 4px 10px; background: #f0f9eb; border-radius: 4px; }
.oc-countdown.urgent { color: #ff9800; background: #fff8e1; }
.oc-countdown.overdue { color: #ee0a24; background: #fff2f0; }

/* 操作区 */
.oc-actions { margin-top: 10px; }
.oc-status-info { display: flex; align-items: center; gap: 4px; font-size: 12px; padding: 6px 10px; border-radius: 4px; margin-top: 5px; }
.oc-freeze { color: #666; background: #fffbe6; border: 1px solid #ffe58f; }
.oc-success { color: #07c160; background: #f0f9eb; border: 1px solid #c2e7b0; }
</style>
