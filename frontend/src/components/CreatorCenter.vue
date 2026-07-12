<script setup>
import { ref, onMounted, computed } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import request from '../api/request.js'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import DeliveryDialog from './DeliveryDialog.vue'

const router = useRouter()
const auth = useAuthStore()

// 交付弹窗
const showDeliveryDialog = ref(false)
const deliveringOrderNo = ref('')
const deliveringOrderAmount = ref(0)
const deliveringOrderName = ref('')

// 申请相关
const hasApplied = ref(false)
const appStatus = ref(null)
const application = ref(null)
const loadingApp = ref(true)
const walletInfo = ref({})

// 申请表单
const showApplyForm = ref(false)
const form = ref({ real_name: '', phone: '', wechat: '', specialty: '', portfolio_desc: '', experience: '' })
const submitting = ref(false)
const agreed = ref(false)

// 协议弹窗
const showAgreement = ref(false)
const pendingApply = ref(false) // 点击"立即申请"后先弹协议，确认后打开表单

// 打开申请流程：先弹协议 → 同意 → 弹表单
const openApply = () => {
  pendingApply.value = true
  showAgreement.value = true
}

// 协议确认回调
const onAgree = () => {
  agreed.value = true
  showAgreement.value = false
  if (pendingApply.value) {
    pendingApply.value = false
    showApplyForm.value = true
  }
}

// 订单相关
const orders = ref([])
const loadingOrders = ref(false)

// 当前用户 ID（从 auth store 获取）
const currentUserId = computed(() => auth.userId)

// =========== 申请状态 ===========

const fetchApplicationStatus = async () => {
  if (!currentUserId.value) return
  loadingApp.value = true
  try {
    const res = await request.get('/creator/application')
    const data = res.data
    if (data) {
      hasApplied.value = true
      application.value = data
      appStatus.value = data.status
    } else {
      hasApplied.value = false
    }
  } catch (e) {
    if (!auth.isLoggedIn) return
    if (e.response?.status !== 401) {
      showToast('获取申请状态失败')
    }
  } finally {
    loadingApp.value = false
  }
}

const fetchWallet = async () => {
  try {
    const res = await request.get('/user/wallet')
    walletInfo.value = res.data
  } catch (e) {
    // 静默失败
  }
}

const handleResign = async () => {
  showConfirmDialog({
    title: '退出制作者',
    message: '退出后将失去接单权限，保证金门槛将清除',
  }).then(async () => {
    try {
      await request.post('/creator/resign', { force: false })
      showSuccessToast('已退出制作者')
      auth.logout()
      router.push('/')
    } catch (e) {
      const msg = e.response?.data?.detail || '退出失败，请稍后重试'
      if (msg.includes('force=true')) {
        // 有未完成订单，询问是否强制退出
        showConfirmDialog({
          title: '存在未完成订单',
          message: msg + '\n\n是否强制退出？将扣除全部余额并将订单重新发布',
          confirmButtonText: '强制退出',
          cancelButtonText: '取消',
        }).then(async () => {
          try {
            await request.post('/creator/resign', { force: true })
            showSuccessToast('已强制退出制作者')
            auth.logout()
            router.push('/')
          } catch (e2) {
            showConfirmDialog({
              title: '强制退出失败',
              message: e2.response?.data?.detail || '操作失败',
            }).catch(() => {})
          }
        }).catch(() => {})
      } else {
        showConfirmDialog({
          title: '退出失败',
          message: msg,
        }).catch(() => {})
      }
    }
  })
}

const submitApplication = async () => {
  if (!form.value.real_name || !form.value.phone || !form.value.wechat) {
    return showToast('请填写真实姓名、手机号和微信号')
  }
  if (!agreed.value) {
    return showToast('请先阅读并同意《制作者协议》')
  }
  submitting.value = true
  try {
    const res = await request.post('/creator/apply', {
      user_id: currentUserId.value,
      ...form.value,
    })
    showSuccessToast('申请已提交')
    showApplyForm.value = false
    await fetchApplicationStatus()
  } catch (e) {
    showToast(e.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

// =========== 订单管理 ===========

const fetchOrders = async () => {
  loadingOrders.value = true
  try {
    const res = await request.get('/creator/orders?tab=mine')
    orders.value = res.data
  } catch (e) {
    if (!auth.isLoggedIn) return
    if (e.response?.status === 403) {
      showToast('请先申请成为制作者')
    } else {
      showToast('获取订单列表失败')
    }
  } finally {
    loadingOrders.value = false
  }
}

const handleDeliver = (orderNo, orderAmount, orderName) => {
  deliveringOrderNo.value = orderNo
  deliveringOrderAmount.value = orderAmount || 0
  deliveringOrderName.value = orderName || ''
  showDeliveryDialog.value = true
}

const onDeliverySuccess = () => {
  fetchOrders()
}

const statusLabel = (s) => {
  const map = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝',
    revoked: '已撤销',
    awaiting_claim: '待抢单',
    in_progress: '制作中',
    delivered: '待验收',
    accepted: '已验收',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[s] || s
}

const statusType = (s) => {
  const map = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    revoked: 'danger',
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    completed: 'success',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

// =========== 辅助函数 ===========

const formatTime = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const formatTimeShort = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${pad(d.getDate())}`
}

// 倒计时格式化
const formatCountdown = (hours) => {
  if (hours === null || hours === undefined) return ''
  if (hours <= 0) return '已超时'
  if (hours < 1) {
    const mins = Math.round(hours * 60)
    return `${mins} 分钟`
  }
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h} 小时 ${m} 分钟` : `${h} 小时`
}

// 进度条节点状态
const progressStep = (order) => {
  // 0=制作中, 1=已交付, 2=已验收
  if (order.delivery_status === 'accepted') return 2
  if (order.delivery_status === 'delivered') return 1
  if (order.delivery_status === 'progress') return 0
  return -1
}

onMounted(() => {
  fetchApplicationStatus()
  fetchOrders()
  fetchWallet()
  // 每 60 秒刷新订单列表（倒计时更新）
  setInterval(fetchOrders, 60000)
})
</script>

<template>
  <div class="creator-center">
    <div class="header-card">
      <van-icon name="friends-o" size="28" />
      <span>制作者中心</span>
    </div>

    <!-- 申请状态 -->
    <div v-if="loadingApp" class="loading">加载中...</div>
    <div v-else class="status-section">
      <div v-if="!hasApplied" class="no-apply">
        <p class="no-apply-text">你还不是制作者，提交入驻申请后可接单赚取报酬</p>
        <van-button type="primary" round block @click="openApply">
          立即申请入驻
        </van-button>
        <div class="earn-info">
          <h4>制作者收益</h4>
          <ul>
            <li>每完成一单代做服务，获得订单金额的 <strong>30%</strong> 作为报酬</li>
            <li>自由接单，时间灵活</li>
            <li>报酬直接进入钱包，满 50 元可提现</li>
          </ul>
        </div>
      </div>

      <div v-else class="apply-result">
        <van-cell-group inset>
          <van-cell title="申请状态">
            <template #value>
              <van-tag :type="statusType(application.status)" round>{{ statusLabel(application.status) }}</van-tag>
            </template>
          </van-cell>
          <van-cell title="真实姓名" :value="application.real_name" />
          <van-cell title="手机号" :value="application.phone" />
          <van-cell title="微信号" :value="application.wechat" />
          <van-cell title="擅长领域" :value="application.specialty || '未填写'" />
          <van-cell v-if="application.review_remark" title="审核备注" :value="application.review_remark" />
          <van-cell v-if="appStatus === 'approved'" title="冻结保证金">
            <template #value>
              <span style="color: #07c160">¥{{ walletInfo.deposit_frozen?.toFixed(2) || '0.00' }}</span>
            </template>
          </van-cell>
        </van-cell-group>

        <div v-if="application.status === 'rejected' || application.status === 'revoked'" class="apply-actions">
          <div v-if="application.status === 'revoked'" class="revoked-notice">
            你的制作者资格已被撤销，如需再次成为制作者，请重新申请
          </div>
          <van-button type="primary" round block @click="openApply" style="margin-top:15px">
            重新申请
          </van-button>
        </div>

        <div v-if="appStatus === 'approved'" class="creator-actions">
          <van-button type="danger" round block plain @click="handleResign" style="margin-top:15px">
            退出制作者（清除保证金门槛）
          </van-button>
        </div>
      </div>
    </div>

    <!-- 已通过 → 显示订单管理 -->
    <div v-if="appStatus === 'approved'" class="orders-section">
      <div v-if="loadingOrders" class="loading">加载中...</div>
      <div v-else-if="orders.length === 0" class="empty">暂无订单</div>
      <div v-else class="order-list">
        <div v-for="o in orders" :key="o.order_no" class="order-card">
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
            <div class="oc-row">
              <span class="oc-label">接单日期</span>
              <span class="oc-val">{{ formatTime(o.claimed_at) }}</span>
            </div>
            <div v-if="o.delivered_at" class="oc-row">
              <span class="oc-label">交付日期</span>
              <span class="oc-val">{{ formatTime(o.delivered_at) }}</span>
            </div>
            <div v-if="o.accepted_at" class="oc-row">
              <span class="oc-label">验收日期</span>
              <span class="oc-val oc-accepted">{{ formatTime(o.accepted_at) }}</span>
            </div>
            <div v-if="o.requirements" class="oc-req">
              <div class="oc-req-label">需求描述</div>
              <div class="oc-req-text">{{ o.requirements }}</div>
            </div>
          </div>

          <div class="oc-actions">
            <van-button v-if="o.status === 'in_progress'" type="primary" size="small" round block @click="handleDeliver(o.order_no, o.order_amount, o.template_name)">
              提交交付
            </van-button>
            <van-button v-if="o.status === 'rejected'" type="warning" size="small" round block plain @click="handleDeliver(o.order_no, o.order_amount, o.template_name)">
              重新交付
            </van-button>
            <div v-if="o.status === 'delivered'" class="oc-status-info oc-freeze">
              <van-icon name="clock-o" size="12" /> 等待买家验收（距离自动验收 {{ formatCountdown(o.accept_hours_remaining) }}）
            </div>
            <div v-if="o.status === 'accepted' || o.status === 'completed'" class="oc-status-info oc-success">
              <van-icon name="checked" size="12" /> 验收通过，佣金已入账
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 申请表单弹窗 -->
    <van-dialog v-model:show="showApplyForm" title="制作者入驻申请" show-cancel-button
      @confirm="submitApplication" :confirm-loading="submitting" style="max-height:80vh; overflow-y:auto;">
      <div class="apply-form">
        <van-field v-model="form.real_name" label="真实姓名" placeholder="请输入真实姓名" required />
        <van-field v-model="form.phone" label="手机号" placeholder="请输入手机号" type="tel" required />
        <van-field v-model="form.wechat" label="微信号" placeholder="请输入微信号" required />
        <van-field v-model="form.specialty" label="擅长领域" placeholder="如：中文简历、英文简历、多页简历">
          <template #extra>
            <div class="field-hint">多个用逗号分隔</div>
          </template>
        </van-field>
        <van-field v-model="form.portfolio_desc" label="作品集说明" type="textarea" rows="2" placeholder="如有作品链接或参考，请填写" />
        <van-field v-model="form.experience" label="相关经验" type="textarea" rows="2" placeholder="填写简历制作相关经验" />
        <div class="agree-check">
          <van-checkbox v-model="agreed">我已阅读并同意<span @click.stop="showAgreement = true" class="inline-link">《制作者协议》</span></van-checkbox>
        </div>
      </div>
    </van-dialog>

    <!-- 制作者协议弹窗 -->
    <van-dialog v-model:show="showAgreement" title="📜 制作者协议" show-cancel-button show-confirm-button confirm-button-text="我已阅读并同意"
      @confirm="onAgree" style="max-height:80vh; overflow-y:auto; padding:20px 15px;">
      <div class="agreement-content">
        <h3>一、加入条件</h3>
        <ol>
          <li><strong>实名认证</strong>：提交真实姓名、手机号、微信号</li>
          <li><strong>保证金门槛</strong>：钱包余额需达到保证金门槛金额（以系统配置为准，默认 ¥20.00）</li>
          <li><strong>审核通过</strong>：由平台管理员审核通过后正式成为制作者</li>
        </ol>

        <h3>二、保证金制度</h3>
        <ol>
          <li>保证金为制作者接单权限的<strong>门槛阈值</strong>，不代表独立资金额度</li>
          <li>审核通过后系统将标记保证金门槛状态</li>
          <li>钱包余额低于保证金门槛时，系统暂停接单权限并提醒充值</li>
          <li>退出制作者后保证金门槛状态自动清除</li>
        </ol>

        <h3>三、工作准则</h3>
        <ol>
          <li>接单后需在 <strong>24 小时内</strong> 开始制作并上传交付文件</li>
          <li>不得拒绝已接受的订单，特殊情况需联系管理员协商</li>
          <li>交付内容需符合用户要求，不得提供低质量或虚假信息</li>
          <li>不得与用户私下交易或绕过平台收款</li>
          <li>不得泄露用户个人信息</li>
        </ol>

        <h3>四、交付规则</h3>
        <ol>
          <li>接单后 <strong>24 小时</strong> 为交付周期</li>
          <li>超时后每 <strong>8 小时</strong> 扣除 <strong>10%</strong> 订单金额作为违约金</li>
          <li>违约金累计上限为订单金额的 <strong>50%</strong></li>
          <li>超时 <strong>72 小时</strong> 未交付，订单将被重新发布到众包大厅</li>
          <li>违约金直接从钱包余额中扣除</li>
        </ol>

        <h3>五、罚则</h3>
        <ol>
          <li>连续 <strong>3 次</strong> 超时交付，平台有权暂停接单权限</li>
          <li>发现欺诈行为（故意拖延、恶意拒绝交付），平台有权：
            <ul>
              <li>强制退出制作者身份，<strong>扣除全部余额</strong></li>
              <li>将未完成订单重新发布</li>
              <li>从余额中扣除违约金</li>
            </ul>
          </li>
          <li>严重违规将被永久封禁制作者资格</li>
        </ol>

        <h3>六、退出条件</h3>
        <ol>
          <li><strong>正常退出</strong>：需完成所有进行中的订单（制作中、待验收状态）</li>
          <li>退出后保证金门槛状态自动清除</li>
          <li>退出后失去接单权限，已完成的订单不受影响</li>
          <li><strong>强制退出</strong>：管理员可在特殊情况下强制退出制作者，<strong>扣除全部余额</strong>，未完成订单重新发布</li>
        </ol>

        <h3>七、收益与提现</h3>
        <ol>
          <li>每完成一单定制服务，获得订单金额的 <strong>30%</strong> 作为报酬</li>
          <li>制作者的上级推广者获得 <strong>10%</strong> 推荐分佣</li>
          <li>报酬在买家验收通过后**立即到账**（统计字段+账户余额同步增加）</li>
          <li>7天冻结期内买家提出异议/退款，佣金将被扣除</li>
          <li>可用余额满 ¥50 可申请提现</li>
        </ol>
      </div>
    </van-dialog>

    <!-- 交付弹窗 -->
    <DeliveryDialog
      v-model:show="showDeliveryDialog"
      :order-no="deliveringOrderNo"
      :order-amount="deliveringOrderAmount"
      :order-name="deliveringOrderName"
      @success="onDeliverySuccess"
    />
  </div>
</template>

<style scoped>
.creator-center { padding: 15px; background: #f7f8fa; min-height: calc(100vh - 96px); }
.loading { text-align: center; margin-top: 30px; color: #999; }
.empty { text-align: center; color: #999; padding: 40px 0; }
.header-card { display: flex; align-items: center; gap: 8px; padding: 15px; background: linear-gradient(135deg, #07c160, #06ad56); border-radius: 12px; color: white; font-size: 18px; font-weight: bold; margin-bottom: 15px; }
.status-section { margin-bottom: 15px; }

.no-apply { padding: 10px 0; }
.no-apply-text { text-align: center; color: #666; font-size: 14px; margin-bottom: 15px; }

.agreement-link { text-align: center; color: #07c160; font-size: 13px; margin: 12px 0; cursor: pointer; }

.earn-info { background: white; border-radius: 8px; padding: 15px; margin-top: 15px; }
.earn-info h4 { margin: 0 0 10px; font-size: 14px; color: #323233; }
.earn-info ul { margin: 0; padding-left: 18px; font-size: 13px; color: #666; line-height: 2; }

.apply-result { padding: 5px 0; }
.apply-actions { padding: 0 15px; }

.orders-section { margin-top: 5px; }
.order-list { padding: 5px 0; }

/* ========== 订单卡片 ========== */
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

/* ========== 进度条 ========== */
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

/* 超时倒计时 */
.oc-countdown { display: flex; align-items: center; gap: 4px; margin-top: 8px; font-size: 12px; color: #666; padding: 4px 10px; background: #f0f9eb; border-radius: 4px; }
.oc-countdown.urgent { color: #ff9800; background: #fff8e1; }
.oc-countdown.overdue { color: #ee0a24; background: #fff2f0; }

/* 操作区 */
.oc-actions { margin-top: 10px; }
.oc-status-info { display: flex; align-items: center; gap: 4px; font-size: 12px; padding: 6px 10px; border-radius: 4px; margin-top: 5px; }
.oc-freeze { color: #666; background: #fffbe6; border: 1px solid #ffe58f; }
.oc-success { color: #07c160; background: #f0f9eb; border: 1px solid #c2e7b0; }

.apply-form { padding: 10px 0; }
.field-hint { font-size: 11px; color: #999; }

/* 协议弹窗内容 */
.agreement-content {
  font-size: 13px;
  line-height: 1.8;
  color: #333;
  text-align: left;
  max-height: 60vh;
  overflow-y: auto;
}
.agreement-content h3 {
  font-size: 15px;
  color: #323233;
  margin: 16px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #eee;
}
.agreement-content ol {
  padding-left: 20px;
  margin: 8px 0;
}
.agreement-content li {
  margin-bottom: 4px;
}
.agreement-content ul {
  padding-left: 20px;
  margin: 4px 0;
}
.agreement-content strong {
  color: #323233;
}
.agree-check {
  margin: 12px 0 5px;
  padding: 10px 5px;
  background: #f7f8fa;
  border-radius: 6px;
}
.inline-link {
  color: #07c160;
  cursor: pointer;
  font-weight: bold;
}
.revoked-notice {
  padding: 10px 15px;
  background: #fff2f0;
  border-radius: 6px;
  color: #cf1322;
  font-size: 13px;
  margin-bottom: 10px;
}
</style>
