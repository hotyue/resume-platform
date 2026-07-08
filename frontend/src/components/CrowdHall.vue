<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import axios from 'axios'

const activeTab = ref(0)
const pendingOrders = ref([])
const myOrders = ref([])

const fetchOrders = async () => {
  try {
    const res1 = await axios.get('/api/v1/creator/orders?tab=pending')
    pendingOrders.value = res1.data
    const res2 = await axios.get('/api/v1/creator/orders?tab=my')
    myOrders.value = res2.data
  } catch (error) { showToast("获取订单失败") }
}

const takeOrder = async (order_no) => {
  try {
    await axios.post('/api/v1/creator/take', { order_no })
    showSuccessToast("抢单成功！")
    fetchOrders()
  } catch (error) { showToast("抢单失败") }
}

const deliverOrder = async (order_no) => {
  try {
    await axios.post('/api/v1/creator/deliver', { order_no })
    showSuccessToast("交付成功，佣金已入账！")
    fetchOrders()
  } catch (error) { showToast("交付失败") }
}

// 核心修复：添加创作者下载基础模板底稿的函数
const downloadBaseTemplate = (order_no) => {
  window.location.href = `/api/v1/orders/download/${order_no}`
}

onMounted(() => fetchOrders())
</script>

<template>
  <div class="crowd-hall">
    <van-tabs v-model:active="activeTab" color="#ee0a24" sticky>
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
            <van-tag :type="o.status === 'completed' ? 'success' : 'warning'">{{ o.status === 'completed' ? '已交付' : '制作中' }}</van-tag>
            <span class="order-no">{{ o.order_no }}</span>
          </div>
          <div class="content">
            <p><strong>模板:</strong> {{ o.template_name }}</p>
            <p class="reqs"><strong>需求:</strong> {{ o.requirements }}</p>
          </div>
          <div class="footer">
            <van-button v-if="o.status === 'processing'" type="success" size="small" round block @click="deliverOrder(o.order_no)">确认交付完成成品</van-button>
            <van-button type="primary" size="small" round block plain style="margin-top:8px" @click="downloadBaseTemplate(o.order_no)">下载客户订购的底稿模板</van-button>
          </div>
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<style scoped>
.crowd-hall { padding-bottom: 20px; background: #f7f8fa; min-height: 100vh;}
.order-card { background: #fff; margin: 15px; border-radius: 8px; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }
.price { color: #ee0a24; font-weight: bold; font-size: 16px; }
.order-no { font-size: 12px; color: #999; }
.content p { margin: 5px 0; font-size: 14px; color: #333; }
.reqs { color: #666; background: #f9f9f9; padding: 10px; border-radius: 4px; margin-top: 10px!important; }
.footer { margin-top: 15px; }
</style>
