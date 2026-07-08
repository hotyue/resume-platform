<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const templates = ref([])
const loading = ref(true)
const refreshing = ref(false) // 下拉刷新状态

const loadTemplates = async () => {
  try {
    const res = await axios.get('/api/v1/templates?limit=50')
    templates.value = res.data
  } catch (error) {
    console.error("加载模板失败:", error)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const onRefresh = () => {
  loadTemplates()
}

// 增强的图片路径处理函数
const getImageUrl = (relPath) => {
  if (!relPath) return '';
  let normalizedPath = relPath.replace(/\\/g, '/');
  let encodedPath = encodeURI(normalizedPath);
  return `/static/${encodedPath}`;
}

onMounted(() => {
  loadTemplates()
})
</script>

<template>
  <div class="resume-list">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <div v-if="loading && !refreshing" class="loading-state">加载中...</div>
      
      <van-grid :column-num="2" :gutter="10" v-else>
        <van-grid-item v-for="item in templates" :key="item.id">
          <div class="template-card">
            <div class="image-wrapper">
               <img :src="getImageUrl(item.jpg_path)" :alt="item.name" class="cover-img" />
            </div>
            
            <div class="info">
              <div class="title van-ellipsis">{{ item.category }} - {{ item.name }}</div>
              <div class="action-bar">
                <span class="price">¥{{ item.price }}</span>
                <van-button type="primary" size="mini" plain round>下载</van-button>
              </div>
            </div>
          </div>
        </van-grid-item>
      </van-grid>
    </van-pull-refresh>
  </div>
</template>

<style scoped>
.resume-list {
  padding: 10px;
  /* 确保下拉刷新区域能撑满屏幕，实现类似原生的滚动体验 */
  min-height: calc(100vh - 96px); 
}
.loading-state {
  text-align: center;
  padding: 40px;
  color: #999;
}
.template-card {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
/* 核心修复：使用 aspect-ratio 实现精确的 A4 纸张比例 (210:297) */
.image-wrapper {
  width: 100%;
  aspect-ratio: 210 / 297; 
  overflow: hidden;
  background-color: #f0f2f5;
  display: flex;
  justify-content: center;
  align-items: center;
}
.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.info {
  padding: 10px;
}
.title {
  font-size: 13px;
  color: #323233;
  margin-bottom: 8px;
  font-weight: 500;
}
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.price {
  color: #ee0a24;
  font-size: 16px;
  font-weight: bold;
}
</style>
