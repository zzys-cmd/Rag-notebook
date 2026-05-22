<template>
  <div class="daily-review-page">
    <van-nav-bar title="每日回顾" fixed />
    <div class="review-content">
      <van-loading v-if="loading" class="loading-center" />
      <van-empty v-else-if="reviews.length === 0 && !loading" description="今天没有需要回顾的笔记，太棒了！" />

      <div v-else class="review-list">
        <div class="review-header-bar">
          <span class="review-count">共 {{ reviews.length }} 篇待回顾</span>
          <span class="review-progress">{{ doneCount }} / {{ reviews.length }}</span>
        </div>

        <ReviewCard
          v-for="item in reviews"
          :key="item.note_id"
          :title="item.title"
          :question="getQuestion(item.note_id)"
          :tags="item.tags"
          :category="item.category"
          :review-count="item.review_count"
          :done="doneMap[item.note_id]"
          @done="handleDone(item.note_id)"
          @skip="handleSkip(item.note_id)"
        />
      </div>
    </div>
    <TabBar />
  </div>
</template>

<script setup>
/**
 * DailyReview 每日回顾页面 —— 展示待回顾笔记列表，使用艾宾浩斯曲线算法。
 * 用户滑动浏览卡片，标记已回顾或跳过。
 */
import { ref, reactive, onMounted } from 'vue'
import { showToast } from 'vant'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'
import ReviewCard from '../components/ReviewCard.vue'
import TabBar from '../components/TabBar.vue'

const userStore = useUserStore()
const loading = ref(false)
const reviews = ref([])
const questions = reactive({})   /** note_id → 回顾问题 */
const doneMap = reactive({})     /** note_id → 是否已完成 */
const doneCount = ref(0)

/** 请求头 */
function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userStore.token}`,
  }
}

/** 获取某个笔记的回顾问题（带缓存） */
function getQuestion(noteId) {
  return questions[noteId] || '请回顾这篇笔记的主要内容'
}

/** 加载今日回顾列表 */
async function loadReviews() {
  loading.value = true
  try {
    const res = await fetch(apiConfig.endpoints.reviewToday, { headers: getHeaders() })
    const json = await res.json()
    if (json.code === 200) {
      reviews.value = json.data.reviews || []
    }
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

/** 标记已回顾 */
async function handleDone(noteId) {
  try {
    const res = await fetch(apiConfig.endpoints.reviewDone(noteId), {
      method: 'POST',
      headers: getHeaders(),
    })
    const json = await res.json()
    if (json.code === 200) {
      doneMap[noteId] = true
      doneCount.value++
      showToast('已标记回顾')
    }
  } catch (e) {
    showToast('操作失败')
  }
}

/** 跳过 */
function handleSkip(noteId) {
  doneMap[noteId] = true
  doneCount.value++
}

onMounted(() => {
  loadReviews()
})
</script>

<style scoped>
.daily-review-page {
  min-height: 100vh;
  background: var(--van-background, #f7f8fa);
}
.review-content {
  padding-top: 48px;
  padding-bottom: 60px;
}
.loading-center {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}
.review-list {
  padding: 16px;
}
.review-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.review-count {
  font-size: 14px;
  color: #666;
}
.review-progress {
  font-size: 14px;
  color: var(--van-primary-color, #D4914A);
  font-weight: 600;
}
</style>
