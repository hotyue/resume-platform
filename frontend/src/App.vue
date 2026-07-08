<script setup>
import { ref } from 'vue'
import ResumeList from './components/ResumeList.vue'

const activeTab = ref(0)
</script>

<template>
  <van-config-provider theme="light">
    <van-nav-bar title="简历模板大全" fixed placeholder safe-area-inset-top />

    <main class="main-content">
      <ResumeList v-if="activeTab === 0" />
      <div v-else class="placeholder-view">
        <p>众包代做大厅 (开发中...)</p>
      </div>
    </main>

    <van-tabbar v-model="activeTab" safe-area-inset-bottom route>
      <van-tabbar-item icon="home-o">模板商城</van-tabbar-item>
      <van-tabbar-item icon="friends-o">众包大厅</van-tabbar-item>
      <van-tabbar-item icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </van-config-provider>
</template>

<style>
body {
  margin: 0;
  background-color: #f7f8fa; /* Vant 默认灰背景 */
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Segoe UI, Arial, Roboto, 'PingFang SC', 'miui', 'Hiragino Sans GB', 'Microsoft Yahei', sans-serif;
}
.main-content {
  padding-bottom: 50px; /* 留出底部 Tab 栏的空间 */
  min-height: calc(100vh - 46px - 50px);
}
.placeholder-view {
  text-align: center;
  padding: 50px 20px;
  color: #969799;
}
</style>
