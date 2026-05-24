import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
const BACKEND_TARGET = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000';
const USER_TARGET = process.env.VITE_USER_TARGET || 'http://127.0.0.1:8001';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true, // 允许局域网访问
    proxy: {
      // AI相关接口代理到8000端口
      '/api/agent': {
        target: BACKEND_TARGET,
        changeOrigin: true,
        ws: true
      },
      '/api/rag': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/api/session': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/knowledge/': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      // chat API 子路径代理（避免匹配前端的 /chat 页面路由）
      '/chat/agent/': {
        target: BACKEND_TARGET,
        changeOrigin: true,
        ws: true
      },
      '/chat/rag/': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/chat/session/': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/chat/sessions': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/chat/reorder': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      '/health': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      // 用户相关接口代理到8001端口
      '/user': {
        target: USER_TARGET,
        changeOrigin: true
      },
      '/file': {
        target: USER_TARGET,
        changeOrigin: true
      },
      // 笔记相关接口代理（加尾部斜杠避免匹配 /notes 页面路由）
      '/note/': {
        target: BACKEND_TARGET,
        changeOrigin: true
      },
      // 回顾相关接口代理
      '/review/': {
        target: BACKEND_TARGET,
        changeOrigin: true
      }
    }
  }
})