import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // 允许通过局域网/公网 IP 访问
    port: 5173,
    origin: 'http://207.56.224.26:5173',
    hmr: {
      protocol: 'ws',
      host: '207.56.224.26',
      port: 5173
    },
    watch: {
      usePolling: true // 解决 Docker 挂载卷在某些宿主机下热更新失效的问题
    },
    proxy: {
      '/api': {
        target: 'http://resume_api:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'http://resume_api:8000',
        changeOrigin: true,
        ws: true
      },
      '/static': {
        target: 'http://resume_api:8000',
        changeOrigin: true
      }
    }
  }
})
