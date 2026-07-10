<script setup>
import { ref, onMounted, computed } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog, showDialog } from 'vant'
import request from '../api/request.js'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()

const activeTab = ref(0)

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

// 订单相关
const orderTab = ref('pending')
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
    message: '退出后将失去接单权限，保证金将解冻回到余额',
  }).then(async () => {
    try {
      await request.post('/creator/resign')
      showSuccessToast('已退出制作者')
      auth.clearAuth()
      router.push('/login')
    } catch (e) {
      showToast(e.response?.data?.detail || '退出失败')
    }
  }).catch(() => {})
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
    const res = await request.get(`/creator/orders?tab=${orderTab.value}`)
    orders.value = res.data
  } catch (e) {
    if (e.response?.status === 403) {
      showToast('请先申请成为制作者')
    } else {
      showToast('获取订单列表失败')
    }
  } finally {
    loadingOrders.value = false
  }
}

const handleTakeOrder = async (orderNo) => {
  try {
    const res = await request.post('/creator/take', { order_no: orderNo })
    showSuccessToast('接单成功')
    await fetchOrders()
  } catch (e) {
    if (e.response?.status === 403) {
      showToast('只有制作者才能接单')
    } else {
      showToast(e.response?.data?.detail || '接单失败')
    }
  }
}

const handleDeliver = async (orderNo) => {
  let fileUrl = ''
  let remark = ''
  
  showDialog({
    title: '交付订单',
    message: '请填写交付文件路径',
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
            message: '交付后等待买家验收，验收通过后佣金进入7天冻结期',
          })
            .then(async () => {
              try {
                await request.post('/creator/deliver', {
                  order_no: orderNo,
                  file_url: fileUrl,
                  remark: remark,
                })
                showSuccessToast('已交付，等待买家验收')
                await fetchOrders()
              } catch (e) {
                showToast(e.response?.data?.detail || '交付失败')
              }
            })
            .catch(() => {})
        })
        .catch(() => {})
    })
    .catch(() => {})
}

const statusLabel = (s) => {
  const map = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝',
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
    awaiting_claim: 'primary',
    in_progress: 'warning',
    delivered: 'success',
    accepted: 'success',
    completed: 'success',
    cancelled: 'default',
  }
  return map[s] || 'default'
}

const onOrderTabChange = (index) => {
  orderTab.value = index === 0 ? 'pending' : 'mine'
  fetchOrders()
}

onMounted(() => {
  fetchApplicationStatus()
  fetchOrders()
  fetchWallet()
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
        <van-button type="primary" round block @click="showApplyForm = true">
          立即申请入驻
        </van-button>
        <div class="agreement-link" @click="showAgreement = true">
          <van-icon name="label-o" size="14" /> 点击查看《制作者协议》
        </div>
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

        <div v-if="application.status === 'rejected'" class="apply-actions">
          <van-button type="primary" round block @click="showApplyForm = true" style="margin-top:15px">
            重新申请
          </van-button>
        </div>

        <div v-if="appStatus === 'approved'" class="creator-actions">
          <van-button type="danger" round block plain @click="handleResign" style="margin-top:15px">
            退出制作者（保证金将解冻）
          </van-button>
        </div>
      </div>
    </div>

    <!-- 已通过 → 显示订单管理 -->
    <div v-if="appStatus === 'approved'" class="orders-section">
      <van-tabs @change="onOrderTabChange" color="#07c160">
        <van-tab title="待接单">
          <div v-if="loadingOrders" class="loading">加载中...</div>
          <div v-else-if="orders.length === 0" class="empty">暂无待接订单</div>
          <div v-else class="order-list">
            <div v-for="o in orders" :key="o.order_no" class="order-card">
              <div class="order-header">
                <span class="order-template">{{ o.template_name }}</span>
                <van-tag round :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
              </div>
              <div class="order-amount">报酬: <strong>¥{{ (o.amount * 0.3).toFixed(2) }}</strong></div>
              <div class="order-req">{{ o.requirements }}</div>
              <van-button type="primary" size="small" round @click="handleTakeOrder(o.order_no)">
                立即接单
              </van-button>
            </div>
          </div>
        </van-tab>
        <van-tab title="我的订单">
          <div v-if="loadingOrders" class="loading">加载中...</div>
          <div v-else-if="orders.length === 0" class="empty">暂无订单</div>
          <div v-else class="order-list">
            <div v-for="o in orders" :key="o.order_no" class="order-card">
              <div class="order-header">
                <span class="order-template">{{ o.template_name }}</span>
                <van-tag round :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
              </div>
              <div class="order-amount">报酬: <strong>¥{{ (o.amount * 0.3).toFixed(2) }}</strong></div>
              <div class="order-req">{{ o.requirements }}</div>
              <div v-if="o.status === 'delivered'" class="freeze-info">⏳ 等待买家验收（7天自动验收）</div>
              <div v-if="o.status === 'accepted'" class="accepted-info">✅ 验收通过，佣金冻结中</div>
              <van-button v-if="o.status === 'in_progress'" type="primary" size="small" round @click="handleDeliver(o.order_no)">
                提交交付
              </van-button>
              <van-button v-if="o.status === 'rejected'" type="warning" size="small" round plain @click="handleDeliver(o.order_no)">
                重新交付
              </van-button>
            </div>
          </div>
        </van-tab>
      </van-tabs>
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
    <van-dialog v-model:show="showAgreement" title="📜 制作者协议" show-confirm-button confirm-button-text="我已阅读并同意"
      @confirm="() => { agreed = true; showAgreement = false }" style="max-height:80vh; overflow-y:auto; padding:20px 15px;">
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
              <li>强制退出制作者身份</li>
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
          <li><strong>强制退出</strong>：管理员可在特殊情况下强制退出制作者，未完成订单重新发布</li>
        </ol>

        <h3>七、收益与提现</h3>
        <ol>
          <li>每完成一单定制服务，获得订单金额的 <strong>30%</strong> 作为报酬</li>
          <li>报酬在买家验收通过后进入 7 天冻结期</li>
          <li>冻结期满后自动转入可用余额</li>
          <li>可用余额满 ¥50 可申请提现</li>
        </ol>
      </div>
    </van-dialog>
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
.order-card { background: white; border-radius: 10px; padding: 15px; margin-bottom: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.order-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.order-template { font-weight: 500; font-size: 14px; }
.order-amount { font-size: 13px; color: #07c160; margin-bottom: 6px; }
.order-req { font-size: 12px; color: #666; margin-bottom: 10px; padding: 8px; background: #f7f8fa; border-radius: 6px; line-height: 1.5; }
.freeze-info { font-size: 11px; color: #666; margin: 8px 0; padding: 6px 8px; background: #fffbe6; border-radius: 4px; border: 1px solid #ffe58f; }
.accepted-info { font-size: 11px; color: #07c160; margin: 8px 0; padding: 6px 8px; background: #f0f9eb; border-radius: 4px; border: 1px solid #c2e7b0; }

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
</style>
