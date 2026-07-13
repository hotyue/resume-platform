<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import request from '../api/request.js'
import { showToast, showSuccessToast, showDialog, showLoadingToast, closeToast } from 'vant'

const router = useRouter()
const auth = useAuthStore()

const activeTab = ref(0)
const userInfo = ref(null)
const loading = ref(true)
const teamData = ref(null)
const teamLoading = ref(false)
const commissionList = ref([])
const commissionLoading = ref(false)
const stats = ref(null)
const statsLoading = ref(false)

const showWithdraw = ref(false)
const withdrawAmount = ref('')
const paymentInfo = ref('')

// 季度选择
const selectedQuarter = ref('')
const quarterOptions = computed(() => {
  const now = new Date()
  const year = now.getFullYear()
  const q = Math.ceil((now.getMonth() + 1) / 3)
  const opts = []
  for (let y = year - 1; y <= year; y++) {
    for (let n = 1; n <= 4; n++) {
      opts.push({ text: `${y} Q${n}`, value: `${y}-Q${n}` })
    }
  }
  // 默认选中当前季度
  const current = `${year}-Q${q}`
  if (!selectedQuarter.value) selectedQuarter.value = current
  return opts
})

// =========== 充值 ===========
const showRecharge = ref(false)
const rechargeAmount = ref('')
const rechargeMethod = ref('wechat')
const rechargeLoading = ref(false)
const qrCodeData = ref('')

const handleRecharge = async () => {
  if (!rechargeAmount.value || parseFloat(rechargeAmount.value) <= 0) {
    return showToast('请输入有效的充值金额')
  }
  rechargeLoading.value = true
  try {
    const res = await request.post('/user/recharge', {
      amount: parseFloat(rechargeAmount.value),
      method: rechargeMethod.value,
    })
    showSuccessToast(`充值成功！金额: ¥${res.data.amount}`)
    showRecharge.value = false
    rechargeAmount.value = ''
    qrCodeData.value = ''
    await fetchUserInfo()
  } catch (e) {
    showToast(e.response?.data?.detail || '充值失败')
  } finally {
    rechargeLoading.value = false
  }
}

// =========== 退款 ===========
const showRefund = ref(false)
const refundReason = ref('')
const refunding = ref(false)
const currentRefundOrder = ref(null)

const openRefund = (order) => {
  currentRefundOrder.value = order
  refundReason.value = ''
  showRefund.value = true
}

const submitRefund = async () => {
  if (!refundReason.value.trim()) {
    return showToast('请填写退款原因')
  }
  refunding.value = true
  try {
    const res = await request.post('/orders/refund', {
      order_no: currentRefundOrder.value.order_no,
      reason: refundReason.value,
    })
    showSuccessToast('退款申请已提交，等待管理员审核')
    showRefund.value = false
    refundReason.value = ''
    currentRefundOrder.value = null
    await fetchCustomOrders()
    await fetchUserInfo()
  } catch (e) {
    showToast(e.response?.data?.detail || '退款申请失败')
  } finally {
    refunding.value = false
  }
}

// =========== 定制订单 ===========
const customOrders = ref([])
const customLoading = ref(false)
const reviewForm = ref({ order_no: '', result: 'accepted', buyer_remark: '' })
const showReviewDialog = ref(false)
const reviewing = ref(false)

const fetchCustomOrders = async () => {
  customLoading.value = true
  try {
    const res = await request.get('/orders/my')
    customOrders.value = res.data
  } catch (e) {
    showToast('获取定制订单失败')
  } finally {
    customLoading.value = false
  }
}

const openReview = (order) => {
  reviewForm.value = { order_no: order.order_no, result: 'accepted', buyer_remark: '' }
  showReviewDialog.value = true
}

// 预览交付文件
const previewDelivery = async (order, fileType) => {
  try {
    const url = `/api/v1/orders/${order.order_no}/delivery-url?type=${fileType}`
    const token = localStorage.getItem('token')
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || '下载失败')
    }
    const blob = await res.blob()
    const disposition = res.headers.get('content-disposition') || ''
    // 优先用后端返回的文件名（RFC 5987 编码需要解码）
    let filename = `${order.order_no}.${fileType === 'word' ? 'docx' : 'pdf'}`
    const match = disposition.match(/filename\*?=UTF-8''(.+)/)
    if (match) {
      filename = decodeURIComponent(match[1])
    } else {
      const match2 = disposition.match(/filename="?(.+)"?$/)
      if (match2) filename = match2[1]
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) {
    showToast(e.message || '下载失败')
  }
}

const submitReview = async () => {
  reviewing.value = true
  try {
    await request.post('/orders/review', reviewForm.value)
    showSuccessToast(reviewForm.value.result === 'accepted' ? '验收通过' : '已退回重做')
    showReviewDialog.value = false
    await fetchCustomOrders()
  } catch (e) {
    showToast(e.response?.data?.detail || '操作失败')
  } finally {
    reviewing.value = false
  }
}

const orderStatusLabel = (s) => {
  const map = {
    awaiting_claim: '待抢单',
    in_progress: '制作中',
    delivered: '待验收',
    accepted: '已验收',
    rejected: '已退回',
    completed: '已完成',
    paid: '已支付',
    cancelled: '已取消',
  }
  return map[s] || s
}

const orderStatusType = (s) => {
  const map = {
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    rejected: 'danger',
    completed: 'success',
    paid: 'primary',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

const handleLogout = () => {
  showDialog({
    title: '退出登录',
    message: '确定要退出当前账号吗？',
  }).then(() => {
    auth.logout()
    router.push('/')
  }).catch(() => {})
}

const fetchUserInfo = async () => {
  try {
    const res = await request.get('/user/me')
    userInfo.value = res.data
  } catch (error) {
    // 用户已退出登录时不弹错误提示
    if (auth.isLoggedIn) {
      showToast('获取用户信息失败')
    }
  } finally {
    loading.value = false
  }
}

const fetchTeam = async () => {
  teamLoading.value = true
  try {
    const params = selectedQuarter.value ? { quarter: selectedQuarter.value } : {}
    const res = await request.get('/user/team', { params })
    teamData.value = res.data
  } catch (e) {
    showToast('获取团队信息失败')
  } finally {
    teamLoading.value = false
  }
}

const fetchCommissionHistory = async () => {
  commissionLoading.value = true
  try {
    const res = await request.get('/user/commission-history')
    commissionList.value = res.data
  } catch (e) {
    showToast('获取佣金记录失败')
  } finally {
    commissionLoading.value = false
  }
}

const fetchStats = async () => {
  statsLoading.value = true
  try {
    const id = auth.userId
    if (!id) return
    const res = await request.get(`/user/stats/${id}`)
    stats.value = res.data
  } catch (e) {
    // ignore
  } finally {
    statsLoading.value = false
  }
}

const onTabChange = (index) => {
  activeTab.value = index
  if (index === 0) fetchTeam()
  if (index === 1) fetchCommissionHistory()
  if (index === 3) fetchCustomOrders()
}

const copyText = async (text, msg) => {
  if (!text) return showToast(msg || '暂无内容')
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // fallback for HTTP / non-secure context
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  showSuccessToast(msg || '已复制')
}

const copyInviteLink = () => {
  copyText(userInfo.value?.invite_url, '暂无邀请链接')
}

const copyInviteCode = () => {
  copyText(userInfo.value?.invite_code, '暂无邀请码')
}

const submitWithdraw = async () => {
  const amount = parseFloat(withdrawAmount.value)
  if (!withdrawAmount.value || isNaN(amount) || amount <= 0) {
    return showToast('请输入有效的提现金额')
  }
  if (amount < 50) {
    return showToast('最低提现金额为50元')
  }
  const avail = userInfo.value?.available_balance || 0
  if (amount > avail) {
    return showToast(`可提现额度不足（当前可提: ¥${avail.toFixed(2)}）`)
  }
  if (!paymentInfo.value) {
    return showToast('请输入收款账号')
  }
  try {
    showLoadingToast({ message: '提交中...', forbidClick: true })
    await request.post('/user/withdraw', {
      amount,
      payment_info: paymentInfo.value,
    })
    closeToast()
    showSuccessToast('提现申请已提交，请等待管理员审核')
    showWithdraw.value = false
    withdrawAmount.value = ''
    paymentInfo.value = ''
    // 刷新用户信息
    await fetchUserInfo()
  } catch (e) {
    closeToast()
    showToast(e.response?.data?.detail || '提现申请提交失败')
  }
}

const withdrawAvailable = computed(() => {
  return (userInfo.value?.available_balance || 0).toFixed(2)
})

const teamCount = computed(() => {
  if (!teamData.value) return 0
  return (teamData.value.total_l1 || 0) +
         (teamData.value.total_l2 || 0) +
         (teamData.value.total_l3 || 0)
})

const roleLabel = (role) => {
  const map = { admin: '管理员', promoter: '推广合伙人', creator: '制作者', user: '普通用户' }
  return map[role] || role
}

const roleLabels = (roles) => {
  if (!roles) return []
  return roles.map(r => roleLabel(r))
}

const roleTagType = (role) => {
  const map = { user: '', admin: 'danger', creator: 'success', promoter: 'warning' }
  return map[role] || 'primary'
}

const formatTime = (t) => {
  if (!t) return '—'
  return t.replace('T', ' ').substring(0, 16)
}

const statusTagType = (s) => {
  const map = { pending: 'warning', in_progress: 'primary', delivered: 'primary', accepted: 'success', completed: 'success', cancelled: 'danger', refunded: 'default' }
  return map[s] || 'default'
}

const statusLabel = (s) => {
  const map = { pending: '待处理', in_progress: '制作中', delivered: '已交付', accepted: '已验收', completed: '已完成', cancelled: '已取消', refunded: '已退款' }
  return map[s] || s
}

onMounted(() => {
  fetchUserInfo().then(() => {
    fetchStats()
    fetchTeam()
  })
})
</script>

<template>
  <div class="user-center">
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="userInfo">
      <!-- 钱包概览 -->
      <div class="wallet-card">
        <div class="user-info">
          <van-image round width="50" height="50" src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg" />
          <div class="details">
            <div class="name">{{ userInfo.username }}</div>
            <div class="roles-row">
              <van-tag v-for="role in userInfo.roles" :key="role" :type="roleTagType(role)" round size="medium">
                {{ roleLabel(role) }}
              </van-tag>
            </div>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-item">
            <div class="stat-val">¥{{ (userInfo.wallet_balance || 0).toFixed(2) }}</div>
            <div class="stat-lbl">账户余额</div>
          </div>
          <div class="stat-item" v-if="userInfo.deposit_frozen > 0">
            <div class="stat-val">¥{{ userInfo.deposit_frozen.toFixed(2) }}</div>
            <div class="stat-lbl">保证金</div>
          </div>
          <div class="stat-item">
            <div class="stat-val">¥{{ (userInfo.total_commission || 0).toFixed(2) }}</div>
            <div class="stat-lbl">推荐分佣</div>
          </div>
        </div>
        <div class="balance-actions">
          <van-button size="small" type="warning" round @click="showRecharge = true">
            💰 充值
          </van-button>
          <van-button size="small" type="primary" round @click="showWithdraw = true"
            :disabled="(userInfo.available_balance || 0) < 50">
            提现
          </van-button>
          <van-button size="small" round plain @click="copyInviteLink">
            邀请
          </van-button>
        </div>
        <div class="tips" v-if="(userInfo.available_balance || 0) < 50">
          可提现 ¥{{ withdrawAvailable }}（满50元可提，保证金不可提）
        </div>
      </div>

      <!-- 推荐分佣说明 -->
      <div class="commission-rules">
        <div class="rule-item" v-for="(r, i) in [
          { level: '直接上级', rate: '30%', desc: '下级下单获得佣金' },
          { level: '上上级', rate: '10%', desc: '间接下级下单获得佣金' },
        ]" :key="i">
          <span class="rule-level">{{ r.level }}</span>
          <span class="rule-rate">{{ r.rate }}</span>
          <span class="rule-desc">{{ r.desc }}</span>
        </div>
      </div>

      <!-- 三 Tab：团队 / 佣金明细 / 邀请 -->
      <van-tabs @change="onTabChange" color="#ee0a24">
        <van-tab title="我的团队">
          <div v-if="teamLoading" class="loading">加载团队信息...</div>
          <div v-else-if="teamData" class="team-tree">
            <!-- 季度选择 -->
            <div class="quarter-selector">
              <van-dropdown-menu active-color="#ee0a24">
                <van-dropdown-item v-model="selectedQuarter" :options="quarterOptions" @change="fetchTeam" />
              </van-dropdown-menu>
            </div>

            <div class="team-summary">团队共 <strong>{{ teamCount }}</strong> 人（含直接+间接）</div>

            <!-- 我 -->
            <div class="tree-node level-self">
              <van-icon name="contact" /> {{ teamData.level_0.username }}
              <van-tag v-for="role in (teamData.level_0.roles || [])" :key="role" :type="roleTagType(role)" size="mini" round>
                {{ roleLabel(role) }}
              </van-tag>
              <span class="node-balance">¥{{ teamData.level_0.wallet_balance?.toFixed(2) }}</span>
              <span class="node-contrib">贡献 ¥{{ teamData.level_0.contribution?.toFixed(2) }}</span>
            </div>

            <!-- 一级 -->
            <div v-if="teamData.level_1?.length" class="level-section">
              <div class="level-header">
                <van-icon name="down" /> 一级成员（直接邀请）
                <span class="level-count">{{ teamData.level_1.length }}/{{ teamData.total_l1 }} 人</span>
              </div>
              <div v-for="m in teamData.level_1" :key="m.id" class="tree-node level-1">
                <van-icon name="user" /> {{ m.username }}
                <van-tag v-for="role in (m.roles || [])" :key="role" :type="roleTagType(role)" size="mini" round>
                  {{ roleLabel(role) }}
                </van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
                <span class="node-contrib">贡献 ¥{{ m.contribution?.toFixed(2) }}</span>
              </div>
            </div>
            <div v-else class="empty-hint">暂无一级成员</div>

            <!-- 二级 -->
            <div v-if="teamData.level_2?.length" class="level-section">
              <div class="level-header">
                <van-icon name="down" /> 二级成员（间接邀请）
                <span class="level-count">{{ teamData.level_2.length }}/{{ teamData.total_l2 }} 人</span>
              </div>
              <div v-for="m in teamData.level_2" :key="m.id" class="tree-node level-2">
                <van-icon name="user" /> {{ m.username }}
                <van-tag v-for="role in (m.roles || [])" :key="role" :type="roleTagType(role)" size="mini" round>
                  {{ roleLabel(role) }}
                </van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
                <span class="node-contrib">贡献 ¥{{ m.contribution?.toFixed(2) }}</span>
              </div>
            </div>

            <!-- 三级 -->
            <div v-if="teamData.level_3?.length" class="level-section">
              <div class="level-header">
                <van-icon name="down" /> 三级成员
                <span class="level-count">{{ teamData.level_3.length }}/{{ teamData.total_l3 }} 人</span>
              </div>
              <div v-for="m in teamData.level_3" :key="m.id" class="tree-node level-3">
                <van-icon name="user" /> {{ m.username }}
                <van-tag v-for="role in (m.roles || [])" :key="role" :type="roleTagType(role)" size="mini" round>
                  {{ roleLabel(role) }}
                </van-tag>
                <span class="node-balance">¥{{ m.wallet_balance?.toFixed(2) }}</span>
                <span class="node-contrib">贡献 ¥{{ m.contribution?.toFixed(2) }}</span>
              </div>
            </div>
          </div>
        </van-tab>

        <van-tab title="佣金明细">
          <div v-if="commissionLoading" class="loading">加载佣金记录...</div>
          <div v-else-if="commissionList.length === 0" class="empty-hint">暂无佣金记录</div>
          <div v-else class="commission-list">
            <div class="list-header">共 {{ commissionList.length }} 条记录</div>
            <div v-for="r in commissionList" :key="r.id" class="commission-card">
              <div class="cc-header">
                <div class="cc-left">
                  <van-tag :type="r.level === 0 ? 'danger' : 'warning'" size="mini" round>
                    {{ r.level === 0 ? 'L1 30%' : 'L2 10%' }}
                  </van-tag>
                  <span class="cc-order-no">{{ r.order_no }}</span>
                </div>
                <div class="cc-amount">+ ¥{{ r.amount.toFixed(2) }}</div>
              </div>
              <div class="cc-body">
                <div class="cc-row">
                  <span class="cc-label">订单类型</span>
                  <span class="cc-val">{{ r.order_type === 'custom_service' ? '定制简历' : '下载模板' }}</span>
                </div>
                <div class="cc-row">
                  <span class="cc-label">订单金额</span>
                  <span class="cc-val">¥{{ r.order_amount?.toFixed(2) || '0.00' }}</span>
                </div>
                <div class="cc-row">
                  <span class="cc-label">下单用户</span>
                  <span class="cc-val">{{ r.buyer_name || '未知' }}</span>
                </div>
                <div v-if="r.creator_name" class="cc-row">
                  <span class="cc-label">制作者</span>
                  <span class="cc-val">{{ r.creator_name }}</span>
                </div>
                <div v-if="r.template_name" class="cc-row">
                  <span class="cc-label">模板名称</span>
                  <span class="cc-val cc-template">{{ r.template_name }}</span>
                </div>
                <div class="cc-row">
                  <span class="cc-label">下单日期</span>
                  <span class="cc-val">{{ formatTime(r.ordered_at) }}</span>
                </div>
                <div v-if="r.delivered_at" class="cc-row">
                  <span class="cc-label">交付日期</span>
                  <span class="cc-val">{{ formatTime(r.delivered_at) }}</span>
                </div>
                <div v-if="r.accepted_at" class="cc-row">
                  <span class="cc-label">验收日期</span>
                  <span class="cc-val cc-accepted">{{ formatTime(r.accepted_at) }}</span>
                </div>
                <div class="cc-row">
                  <span class="cc-label">订单状态</span>
                  <span class="cc-val">
                    <van-tag :type="statusTagType(r.order_status)" size="mini" round>
                      {{ statusLabel(r.order_status) }}
                    </van-tag>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </van-tab>

        <van-tab title="邀请推广">
          <div class="invite-panel">
            <div class="invite-section">
              <div class="invite-label">你的邀请码</div>
              <div class="invite-code-box" @click="copyInviteCode">
                <span class="code-text">{{ userInfo.invite_code }}</span>
                <van-icon name="copy" />
              </div>
            </div>

            <div class="invite-section">
              <div class="invite-label">邀请链接</div>
              <div class="invite-url-box">
                <div class="url-text van-ellipsis">{{ userInfo.invite_url }}</div>
                <van-button size="mini" type="primary" @click="copyInviteLink">复制</van-button>
              </div>
            </div>

            <div class="invite-instructions">
              <h4>推广规则</h4>
              <ul>
                <li>下级用户下单，你获得 <strong>30%</strong> 佣金</li>
                <li>间接下级下单，你获得 <strong>10%</strong> 佣金</li>
                <li>不限次数，佣金即时到账</li>
                <li>佣金满 50 元可申请提现</li>
              </ul>
            </div>
          </div>
        </van-tab>
        <van-tab title="我的定制订单">
          <div v-if="customLoading" class="loading">加载订单中...</div>
          <div v-else-if="customOrders.length === 0" class="empty-hint">暂无定制订单</div>
          <div v-else class="order-list">
            <div v-for="o in customOrders" :key="o.order_no" class="custom-order-card">
              <div class="co-header">
                <van-tag :type="orderStatusType(o.status)" round size="small">{{ orderStatusLabel(o.status) }}</van-tag>
                <span class="co-no">{{ o.order_no }}</span>
              </div>
              <div class="co-body">
                <p><strong>{{ o.template_name }}</strong></p>
                <p class="co-req">{{ o.custom_requirements || '暂无需求描述' }}</p>
                <p class="co-amount">¥{{ o.amount.toFixed(2) }}</p>
                <p v-if="o.creator_name" class="co-creator">👤 接单人: {{ o.creator_name }}</p>
                <p v-if="o.status === 'delivered'" class="co-frozen">⏳ 等待验收（7天自动通过）</p>
                <!-- 预览交付文件 -->
                <div v-if="['delivered', 'accepted'].includes(o.status)" class="co-preview">
                  <van-button size="mini" plain type="primary" @click="previewDelivery(o, 'pdf')">📄 预览PDF</van-button>
                  <van-button size="mini" plain type="primary" @click="previewDelivery(o, 'word')">📝 预览Word</van-button>
                </div>
              </div>
              <div class="co-footer">
                <div class="co-actions-row" v-if="o.status === 'delivered'">
                  <van-button size="small" round block type="primary" @click="openReview(o)">验收订单</van-button>
                  <van-button size="small" round block plain type="danger" @click="openRefund(o)">申请退款</van-button>
                </div>
                <van-button v-if="o.status === 'in_progress'" size="small" round block plain type="danger" @click="openRefund(o)">申请退款</van-button>
                <van-button v-if="o.status === 'accepted'" size="small" round block plain type="success">已验收通过</van-button>
                <van-button v-if="o.status === 'rejected'" size="small" round block plain type="warning">已退回重做</van-button>
                <van-button v-if="o.status === 'refund_requested'" size="small" round block plain type="default">退款审核中</van-button>
              </div>
            </div>
          </div>
        </van-tab>
      </van-tabs>
    </div>

    <!-- 充值弹窗 -->
    <van-dialog v-model:show="showRecharge" title="账户充值" show-cancel-button @confirm="handleRecharge" :before-confirm="handleRecharge">
      <div class="recharge-form">
        <van-field v-model="rechargeAmount" type="digit" label="充值金额" placeholder="请输入充值金额" />
        <van-radio-group v-model="rechargeMethod" direction="horizontal" class="recharge-methods">
          <van-radio name="wechat">微信支付</van-radio>
          <van-radio name="alipay">支付宝</van-radio>
        </van-radio-group>
        <p class="form-tips">充值后即时到账，可用于保证金和下单</p>
      </div>
    </van-dialog>

    <!-- 提现弹窗 -->
    <van-dialog v-model:show="showWithdraw" title="佣金提现申请" show-cancel-button @confirm="submitWithdraw">
      <div class="withdraw-form">
        <div class="withdraw-info">
          <p>可提现额度：<strong>¥{{ withdrawAvailable }}</strong></p>
          <p class="withdraw-hint">（余额 ¥{{ (userInfo.wallet_balance || 0).toFixed(2) }} - 冻结保证金 ¥{{ (userInfo.deposit_frozen || 0).toFixed(2) }}）</p>
        </div>
        <van-field v-model="withdrawAmount" type="digit" label="提现金额" placeholder="请输入提现金额" />
        <van-field v-model="paymentInfo" label="收款账号" placeholder="请输入支付宝账号/微信号" />
        <p class="form-tips">注：最低提现50元，管理员将在48小时内人工审核并转账</p>
      </div>
    </van-dialog>

    <!-- 验收弹窗 -->
    <van-dialog v-model:show="showReviewDialog" :show-cancel-button="true" @confirm="submitReview" :before-close="() => true" :close-on-click-overlay="false">
      <div class="review-form">
        <van-radio-group v-model="reviewForm.result" direction="horizontal">
          <van-radio name="accepted" icon-size="20px">✅ 验收通过</van-radio>
          <van-radio name="rejected" icon-size="20px">❌ 退回重做</van-radio>
        </van-radio-group>
        <van-field v-model="reviewForm.buyer_remark" rows="2" autosize type="textarea" placeholder="验收备注（可选）" />
      </div>
    </van-dialog>

    <!-- 退款弹窗 -->
    <van-dialog v-model:show="showRefund" title="申请退款" show-cancel-button confirm-button-text="提交申请" @confirm="submitRefund" :before-close="() => true" :close-on-click-overlay="false">
      <div class="refund-form">
        <div class="refund-info" v-if="currentRefundOrder">
          <p>订单号：{{ currentRefundOrder.order_no }}</p>
          <p>订单金额：¥{{ currentRefundOrder.amount?.toFixed(2) }}</p>
          <p class="refund-note">⚠️ 退款金额：¥{{ (currentRefundOrder.amount / 2)?.toFixed(2) }}（平台与创作者各承担50%）</p>
        </div>
        <van-field v-model="refundReason" rows="3" autosize type="textarea" label="退款原因" placeholder="请详细说明退款原因" />
        <p class="form-tips">退款申请提交后需管理员审核，仅可退款一次</p>
      </div>
    </van-dialog>

    <!-- 退出登录 -->
    <div class="logout-section">
      <van-button type="danger" block round plain hairline @click="handleLogout">退出登录</van-button>
    </div>
  </div>
</template>

<style scoped>
.user-center { padding: 15px; background: #f7f8fa; min-height: calc(100vh - 96px); }
.loading { text-align: center; margin-top: 50px; color: #999; padding: 30px 0; }
.empty-hint { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }

/* 钱包卡片 */
.wallet-card {
  background: linear-gradient(135deg, #ff6034 0%, #ee0a24 100%);
  border-radius: 12px; padding: 20px; color: white; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(238,10,36,0.3);
}
.user-info { display: flex; align-items: center; margin-bottom: 15px; }
.details { margin-left: 15px; }
.name { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
.roles-row { display: flex; gap: 6px; flex-wrap: wrap; }
.stats-row { display: flex; justify-content: space-around; text-align: center; margin-bottom: 15px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.2); border-bottom: 1px solid rgba(255,255,255,0.2); }
.stat-val { font-size: 20px; font-weight: bold; font-family: DIN, sans-serif; }
.stat-lbl { font-size: 12px; opacity: 0.85; margin-top: 3px; }
.balance-actions { display: flex; gap: 10px; justify-content: center; margin-bottom: 5px; }
.tips { font-size: 12px; margin-top: 5px; opacity: 0.8; text-align: center; }

/* 分佣比例说明 */
.commission-rules { display: flex; gap: 8px; margin-bottom: 15px; }
.rule-item { flex: 1; background: white; border-radius: 8px; padding: 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.rule-level { display: block; font-size: 12px; color: #999; }
.rule-rate { display: block; font-size: 20px; font-weight: bold; color: #ee0a24; margin: 3px 0; }
.rule-desc { display: block; font-size: 11px; color: #666; }

/* 团队树 */
.team-tree { padding: 5px 0; }
.team-summary { text-align: center; font-size: 13px; color: #666; margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px; }
.quarter-selector { margin-bottom: 10px; }
.tree-node { display: flex; align-items: center; gap: 6px; padding: 10px 12px; margin-bottom: 5px; background: white; border-radius: 8px; font-size: 14px; border-left: 3px solid #ee0a24; flex-wrap: wrap; }
.level-self { border-left-color: #ee0a24; font-weight: bold; }
.level-1 { border-left-color: #ff976a; margin-left: 15px; }
.level-2 { border-left-color: #ffc8a2; margin-left: 30px; }
.level-3 { border-left-color: #ffe0cc; margin-left: 45px; }
.node-balance { font-size: 12px; color: #999; }
.node-contrib { font-size: 11px; color: #ee0a24; background: #fff0f0; padding: 2px 6px; border-radius: 4px; }
.level-section { margin-top: 10px; }
.level-header { font-size: 12px; color: #999; padding: 5px 0; margin-left: 5px; display: flex; justify-content: space-between; align-items: center; }
.level-count { font-size: 11px; color: #bbb; }

/* 佣金明细 */
.commission-list { padding: 5px 0; }
.commission-card { background: white; border-radius: 10px; padding: 12px; margin-bottom: 8px; border: 1px solid #f0f0f0; }
.cc-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #f5f5f5; }
.cc-left { display: flex; align-items: center; gap: 6px; }
.cc-order-no { font-size: 13px; color: #333; font-weight: 500; }
.cc-amount { font-size: 16px; font-weight: bold; color: #07c160; }
.cc-body { display: flex; flex-direction: column; gap: 5px; }
.cc-row { display: flex; justify-content: space-between; font-size: 12px; line-height: 1.8; }
.cc-label { color: #999; }
.cc-val { color: #333; font-weight: 400; }
.cc-template { color: #1989fa; }
.cc-accepted { color: #07c160; font-weight: 500; }

/* 邀请 */
.invite-panel { padding: 10px 0; }
.invite-section { margin-bottom: 15px; }
.invite-label { font-size: 13px; color: #666; margin-bottom: 6px; }
.invite-code-box { display: flex; align-items: center; justify-content: space-between; background: white; border-radius: 8px; padding: 12px 15px; cursor: pointer; }
.code-text { font-size: 20px; font-weight: bold; letter-spacing: 2px; color: #ee0a24; user-select: all; }
.invite-url-box { display: flex; align-items: center; gap: 8px; background: white; border-radius: 8px; padding: 10px 12px; }
.url-text { flex: 1; font-size: 12px; color: #666; }
.invite-instructions { background: white; border-radius: 8px; padding: 15px; margin-top: 10px; }
.invite-instructions h4 { margin: 0 0 10px; font-size: 14px; }
.invite-instructions ul { margin: 0; padding-left: 18px; font-size: 13px; color: #666; line-height: 1.8; }

/* 提现 */
.withdraw-form { padding: 15px 0; }
.withdraw-info { margin-bottom: 10px; padding: 10px; background: #f7f8fa; border-radius: 6px; }
.withdraw-info p { margin: 4px 0; font-size: 13px; }
.withdraw-hint { font-size: 11px; color: #999; }
.form-tips { font-size: 12px; color: #999; text-align: center; margin-top: 10px; }

/* 充值 */
.recharge-form { padding: 15px 0; }
.recharge-methods { margin: 12px 0; }
.recharge-methods .van-radio { margin-right: 15px; }

/* 退款 */
.refund-form { padding: 15px 0; }
.refund-info { background: #fff7cc; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 13px; }
.refund-info p { margin: 4px 0; }
.refund-note { color: #ee0a24; font-weight: bold; }

/* 定制订单 */
.co-actions-row { display: flex; gap: 8px; margin-bottom: 8px; }

.logout-section { padding: 20px 15px 30px; }

/* 定制订单 */
.custom-order-card { background: white; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
.co-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.co-no { font-size: 11px; color: #999; }
.co-body p { margin: 4px 0; font-size: 13px; }
.co-req { color: #666; font-size: 12px; line-height: 1.4; }
.co-amount { color: #ee0a24; font-weight: bold; font-size: 15px; }
.co-frozen { font-size: 11px; color: #ff976a; margin-top: 6px; padding: 4px 8px; background: #fffbe6; border-radius: 4px; text-align: center; }
.co-preview { display: flex; gap: 8px; margin-top: 8px; }
.co-footer { margin-top: 10px; }

/* 验收弹窗 */
.review-form { padding: 15px 10px; }
.review-form .van-radio-group { margin-bottom: 12px; }
.review-form .van-radio { margin-right: 15px; }
.review-form .van-field { margin-top: 10px; }
</style>