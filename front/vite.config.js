import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true, // 允许局域网访问
    proxy: {
      // AI相关接口代理到8000端口
      '/api/agent': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true
      },
      '/api/rag': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/api/session': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/knowledge/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      // chat API 子路径代理（避免匹配前端的 /chat 页面路由）
      '/chat/agent/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true
      },
      '/chat/rag/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/chat/session/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/chat/sessions': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/chat/reorder': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      // 用户相关接口代理到8001端口
      '/user': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      '/file': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      // 笔记相关接口代理（加尾部斜杠避免匹配 /notes 页面路由）
      '/note/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      // 回顾相关接口代理
      '/review/': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})