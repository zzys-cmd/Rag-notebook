<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/notes">
      <span>笔记</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/chat">
      <span>AI助手</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          <line x1="9" y1="10" x2="15" y2="10"/>
          <line x1="12" y1="7" x2="12" y2="13"/>
        </svg>
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/review">
      <span>回顾</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
        </svg>
      </template>
    </van-tabbar-item>
    <van-tabbar-item to="/my">
      <span>我的</span>
      <template #icon="props">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
          <circle cx="12" cy="7" r="4"/>
        </svg>
      </template>
    </van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
/**
 * TabBar 底部导航栏 —— 4 个 Tab：笔记、AI助手、回顾、我的。
 * 配合 Vue Router 的 route 属性实现页面切换。
 */
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)

function setActiveTab() {
  const path = route.path
  if (path.includes('/notes')) {
    active.value = 0
  } else if (path.includes('/chat') || path.includes('/aichat')) {
    active.value = 1
  } else if (path.includes('/review')) {
    active.value = 2
  } else if (path.includes('/my')) {
    active.value = 3
  }
}

setActiveTab()

watch(() => route.path, () => {
  setActiveTab()
})
</script>
