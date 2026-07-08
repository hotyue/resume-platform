<script setup>
import { ref } from 'vue'
import ResumeList from './components/ResumeList.vue'
import CrowdHall from './components/CrowdHall.vue'
import UserCenter from './components/UserCenter.vue'

const activeTab = ref(0)
</script>

<template>
  <van-config-provider theme="light">
    <van-nav-bar title="简历模板大全" fixed placeholder safe-area-inset-top />

    <main class="main-content">
      <ResumeList v-if="activeTab === 0" />
      <CrowdHall v-else-if="activeTab === 1" />
      <UserCenter v-else-if="activeTab === 2" />
    </main>

    <van-tabbar v-model="activeTab" safe-area-inset-bottom>
      <van-tabbar-item icon="home-o">模板商城</van-tabbar-item>
      <van-tabbar-item icon="friends-o">众包大厅</van-tabbar-item>
      <van-tabbar-item icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </van-config-provider>
</template>

<style>
body {
  margin: 0;
  background-color: #f7f8fa; 
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Segoe UI, Arial, Roboto, sans-serif;
}
.main-content {
  padding-bottom: 50px; 
  min-height: calc(100vh - 46px - 50px);
}
</style>
