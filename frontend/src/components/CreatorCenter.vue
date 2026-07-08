<script setup>
import { ref, onMounted, computed } from 'vue'
import { showToast, showSuccessToast, showConfirmDialog } from 'vant'
import axios from 'axios'

const activeTab = ref(0)

// 申请相关
const hasApplied = ref(false)
const appStatus = ref(null)
const application = ref(null)
const loadingApp = ref(true)

// 申请表单
const showApplyForm = ref(false)
const form = ref({ real_name: '', phone: '', wechat: '', specialty: '', portfolio_desc: '', experience: '' })
const submitting = ref(false)

// 订单相关
const orderTab = ref('pending')
const orders = ref([])
const loadingOrders = ref(false)

// 当前演示用户的 ID（实际项目接入登录后替换）
const CURRENT_USER_ID = 4  // 简历制作者_赵老师

// =========== 申请状态 ===========

const fetchApplicationStatus = async () => {
  loadingApp.value = true
  try {
    const res = await axios.get(`/api/v1/creator/application-status/${CURRENT_USER_ID}`)
    hasApplied.value = res.data.has_applied
    if (res.data.has_applied) {
      application.value = res.data
      appStatus.value = res.data.status
    }
  } catch (e) {
    showToast('获取申请状态失败')
  } finally {
    loadingApp.value = false
  }
}

const submitApplication = async () => {
  if (!form.value.real_name || !form.value.phone || !form.value.wechat) {
    return showToast('请填写真实姓名、手机号和微信号')
  }
  submitting.value = true
  try {
    const res = await axios.post('/api/v1/creator/apply', {
      user_id: CURRENT_USER_ID,
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
    const res = await axios.get(`/api/v1/creator/orders?tab=${orderTab.value}`)
    orders.value = res.data
  } catch (e) {
    showToast('获取订单列表失败')
  } finally {
    loadingOrders.value = false
  }
}

const handleTakeOrder = async (orderNo) => {
  try {
    const res = await axios.post('/api/v1/creator/take', { order_no: orderNo })
    showSuccessToast('接单成功')
    await fetchOrders()
  } catch (e) {
    showToast(e.response?.data?.detail || '接单失败')
  }
}

const handleDeliver = async (orderNo) => {
  showConfirmDialog({ title: '确认交付', message: '确认完成此订单？制作者将获得订单金额的30%作为报酬。' })
    .then(async () => {
      try {
        await axios.post('/api/v1/creator/deliver', { order_no: orderNo })
        showSuccessToast('交付成功，报酬已到账')
        await fetchOrders()
      } catch (e) {
        showToast(e.response?.data?.detail || '交付失败')
      }
    }).catch(() => {})
}

const statusLabel = (s) => {
  const map = { pending: '待审核', approved: '已通过', rejected: '已拒绝', paid: '待接单', processing: '制作中', completed: '已完成' }
  return map[s] || s
}

const statusType = (s) => {
  const map = { pending: 'warning', approved: 'success', rejected: 'danger', paid: 'primary', processing: 'warning', completed: 'success' }
  return map[s] || 'default'
}

const onOrderTabChange = (index) => {
  orderTab.value = index === 0 ? 'pending' : 'mine'
  fetchOrders()
}

onMounted(() => {
  fetchApplicationStatus()
  fetchOrders()
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
        </van-cell-group>

        <div v-if="application.status === 'rejected'" class="apply-actions">
          <van-button type="primary" round block @click="showApplyForm = true" style="margin-top:15px">
            重新申请
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
              <van-button v-if="o.status === 'processing'" type="success" size="small" round @click="handleDeliver(o.order_no)">
                确认交付
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

.apply-form { padding: 10px 0; }
.field-hint { font-size: 11px; color: #999; }
</style>