<template>
  <div class="review-card card-shadow" :class="{ 'review-card--done': done }" @click="$emit('click')">
    <div class="review-card-header">
      <span class="review-round">第 {{ reviewCount + 1 }} 轮回顾</span>
      <span v-if="category" class="review-category">{{ categoryMap[category] || category }}</span>
    </div>
    <h3 class="review-title">{{ title }}</h3>
    <p class="review-question">{{ question }}</p>
    <div class="review-tags" v-if="tags && tags.length > 0">
      <TagBadge v-for="t in tags" :key="t" :tag="t" />
    </div>
    <div class="review-actions" v-if="!done">
      <van-button size="small" type="primary" @click.stop="$emit('review-now')">立即回顾</van-button>
      <van-button size="small" plain type="primary" @click.stop="$emit('done')">已回顾</van-button>
      <van-button size="small" plain type="default" @click.stop="$emit('skip')">跳过</van-button>
    </div>
    <div class="review-done-badge" v-else>已完成 ✓</div>
  </div>
</template>

<script setup>
/**
 * ReviewCard 回顾卡片组件 —— 展示单个待回顾笔记及回顾问题。
 */
import TagBadge from './TagBadge.vue'

defineProps({
  title: { type: String, default: '' },
  question: { type: String, default: '' },
  tags: { type: Array, default: () => [] },
  category: { type: String, default: '' },
  reviewCount: { type: Number, default: 0 },
  done: { type: Boolean, default: false },
})

defineEmits(['done', 'skip', 'click', 'review-now'])

const categoryMap = { work: '工作', study: '学习', life: '生活', project: '项目' }
</script>

<style scoped>
.review-card {
  padding: 20px;
  margin-bottom: 16px;
  background: #fff;
  border-radius: 12px;
  transition: opacity 0.3s;
}
.review-card--done {
  opacity: 0.6;
}
.review-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.review-round {
  font-size: 12px;
  color: var(--van-primary-color, #D4914A);
  font-weight: 600;
}
.review-category {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f0f0;
  color: #666;
}
.review-title {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 600;
  color: #333;
}
.review-question {
  margin: 0 0 12px;
  font-size: 15px;
  color: #555;
  line-height: 1.6;
  padding: 10px 14px;
  background: #f9f9f9;
  border-radius: 8px;
  border-left: 3px solid var(--van-primary-color, #D4914A);
}
.review-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.review-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
.review-done-badge {
  text-align: right;
  font-size: 14px;
  color: #07c160;
  font-weight: 600;
}
</style>
