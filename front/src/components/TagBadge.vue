<template>
  <span class="tag-badge" :class="[`tag-badge--${color}`]" :style="{ fontSize: size + 'px' }">
    {{ tag }}
  </span>
</template>

<script setup>
defineProps({
  tag: { type: String, required: true },
  color: { type: String, default: 'default' },
  size: { type: Number, default: 12 },
})
</script>

<style scoped>
.tag-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
  line-height: 1.5;
  white-space: nowrap;
}
.tag-badge--default {
  background: var(--van-primary-color, #D4914A);
  color: #fff;
}
.tag-badge--work {
  background: #E8F0FE;
  color: #1967D2;
}
.tag-badge--study {
  background: #FCE8E6;
  color: #C5221F;
}
.tag-badge--life {
  background: #E6F4EA;
  color: #137333;
}
.tag-badge--project {
  background: #FEF7E0;
  color: #B06000;
}
</style>
