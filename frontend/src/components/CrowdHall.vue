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

const walletInfo = ref({})

const fetchWallet = async () => {
  try {
    const res = await request.get('/user/wallet')
    walletInfo.value = res.data
  } catch (e) {
    // 静默失败
  }
}

const fetchOrders = async () => {
  try {
    const res1 = await request.get('/creator/orders?tab=pending')
    pendingOrders.value = res1.data
    const res2 = await request.get('/creator/orders?tab=mine')
    myOrders.value = res2.data
  } catch (error) {
    if (error.response?.status === 403) {
      showToast('请先申请成为制作者')
    }
  }
}

const takeOrder = async (order_no) => {
  try {
    await request.post('/creator/take', { order_no })
    showSuccessToast("抢单成功！")
    fetchOrders()
  } catch (error) {
    if (error.response?.status === 403) {
      showToast('只有制作者才能抢单')
    } else {
      showToast(error.response?.data?.detail || "抢单失败")
    }
  }
}

const deliverOrder = async (order_no) => {
  // 弹窗让用户填写交付信息
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
      // 第二个弹窗填备注
      showDialog({
        title: '交付备注（可选）',
        message: '填写给买家的备注',
        showInput: true,
      })
        .then(async ({ value }) => {
          remark = value || ''
          // 确认提交
          showConfirmDialog({
            title: '确认交付',
            message: '交付后等待买家验收，验收通过后佣金进入7天冻结期',
          })
            .then(async () => {
              try {
                await request.post('/creator/deliver', {
                  order_no,
                  file_url: fileUrl,
                  remark: remark,
                })
                showSuccessToast("已交付，等待买家验收")
                fetchOrders()
              } catch (error) {
                showToast(error.response?.data?.detail || "交付失败")
              }
            })
            .catch(() => {}) // 取消
        })
        .catch(() => {}) // 取消
    })
    .catch(() => {}) // 取消
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

onMounted(() => {
  isCreator.value = auth.isCreator
  fetchOrders()
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

    <van-tabs v-else v-model:active="activeTab" color="#ee0a24" sticky>
      <van-tab title="任务大厅">
        <van-empty v-if="pendingOrders.length === 0" description="暂无可接订单" />
        <div class="order-card" v-for="o in pendingOrders" :key="o.order_no">
          <div class="header">
            <van-tag type="primary">待抢单</van-tag>
            <span class="price">佣金: ¥{{ (o.amount * 0.3).toFixed(2) }}</span>
          </div>
          <div class="content">
            <p><strong>模板:</strong> {{ o.template_name }}</p>
            <p class="reqs"><strong>需求:</strong> {{ o.requirements }}</p>
          </div>
          <div class="footer">
            <van-button type="danger" size="small" round block @click="takeOrder(o.order_no)">立即抢单</van-button>
          </div>
        </div>
      </van-tab>

      <van-tab title="我的任务">
        <van-empty v-if="myOrders.length === 0" description="您还没有正在处理的任务" />
        <div class="order-card" v-for="o in myOrders" :key="o.order_no">
          <div class="header">
            <van-tag :type="statusType(o.status)">{{ statusLabel(o.status) }}</van-tag>
            <span class="order-no">{{ o.order_no }}</span>
          </div>
          <div class="content">
            <p><strong>模板:</strong> {{ o.template_name }}</p>
            <p class="reqs"><strong>需求:</strong> {{ o.requirements }}</p>
            <p v-if="o.status === 'delivered'" class="freeze-info">⏳ 等待买家验收（7天自动验收）</p>
            <p v-if="o.status === 'accepted'" class="accepted-info">✅ 验收通过，佣金进入7天冻结期</p>
          </div>
          <div class="footer">
            <van-button v-if="o.status === 'in_progress'" type="primary" size="small" round block @click="deliverOrder(o.order_no)">提交交付</van-button>
            <van-button v-if="o.status === 'rejected'" type="warning" size="small" round block plain @click="deliverOrder(o.order_no)">重新交付</van-button>
            <van-button type="default" size="small" round block plain style="margin-top:8px" @click="downloadBaseTemplate(o.order_no)">下载底稿模板</van-button>
          </div>
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<style scoped>
.crowd-hall { padding-bottom: 20px; background: #f7f8fa; min-height: 100vh; }
.not-creator { padding: 60px 15px; }
.order-card { background: #fff; margin: 15px; border-radius: 8px; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }
.price { color: #ee0a24; font-weight: bold; font-size: 16px; }
.order-no { font-size: 12px; color: #999; }
.content p { margin: 5px 0; font-size: 14px; color: #333; }
.reqs { color: #666; background: #f9f9f9; padding: 10px; border-radius: 4px; margin-top: 10px!important; }
.footer { margin-top: 15px; }
</style>
