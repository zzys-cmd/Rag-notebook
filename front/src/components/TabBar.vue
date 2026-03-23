<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/aichat" icon="chat-o">{{ $t('nav.aiChat') }}</van-tabbar-item>
    <van-tabbar-item to="/sessions" icon="list">{{ $t('nav.sessions') }}</van-tabbar-item>
    <van-tabbar-item to="/my" icon="user-o">{{ $t('nav.my') }}</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)

// 根据当前路由路径设置激活的标签
const setActiveTab = () => {
  const path = route.path
  if (path.includes('/aichat')) {
    active.value = 0
  } else if (path.includes('/sessions')) {
    active.value = 1
  } else if (path.includes('/my')) {
    active.value = 2
  }
}

// 初始化时设置激活标签
setActiveTab()

// 监听路由变化，更新激活标签
watch(() => route.path, () => {
  setActiveTab()
})
</script>

<style scoped>
/* 自定义样式可以在这里添加 */
</style>