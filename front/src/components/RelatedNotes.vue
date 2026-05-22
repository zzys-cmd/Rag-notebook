<template>
  <van-popup v-model:show="visible" position="right" :style="{ width: '80%', height: '100%' }">
    <div class="related-panel">
      <van-nav-bar title="相关推荐" left-text="关闭" @click-left="visible = false" />

      <div class="related-content">
        <van-loading v-if="loading" class="loading-center" />
        <van-empty v-else-if="items.length === 0" description="暂无相关推荐" />

        <div v-for="item in items" :key="item.id" class="related-card card-shadow">
          <div class="related-header">
            <span class="source-badge" :class="item.source === 'note' ? 'source-note' : 'source-kb'">
              {{ item.source === 'note' ? '笔记' : '知识库' }}
            </span>
            <span class="similarity">{{ (item.similarity * 100).toFixed(1) }}%</span>
          </div>
          <h4 class="related-title ellipsis">{{ item.title }}</h4>
          <p class="related-preview">{{ item.content_preview }}</p>
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup>
/**
 * RelatedNotes 关联推荐侧边栏 —— 从右侧滑出，展示语义相似笔记和知识库文档。
 */
import { ref, watch } from 'vue'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'

const props = defineProps({
  noteId: { type: String, default: '' },
  show: { type: Boolean, default: false },
})

const emit = defineEmits(['update:show'])

const userStore = useUserStore()
const visible = ref(false)
const loading = ref(false)
const items = ref([])

/** 双向同步 v-model:show 与内部 visible */
watch(() => props.show, (val) => {
  visible.value = val
  if (val && props.noteId) {
    fetchRelated()
  }
})

watch(visible, (val) => {
  emit('update:show', val)
})

/** 请求头 */
function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userStore.token}`,
  }
}

/** 取关联推荐 */
async function fetchRelated() {
  if (!props.noteId) return
  loading.value = true
  try {
    const res = await fetch(apiConfig.endpoints.noteRelated(props.noteId), {
      headers: getHeaders(),
    })
    const json = await res.json()
    if (json.code === 200) {
      items.value = json.data || []
    }
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.related-panel {
  height: 100%;
  background: var(--van-background, #f7f8fa);
}
.related-content {
  padding: 12px;
}
.loading-center {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.related-card {
  padding: 14px;
  margin-bottom: 10px;
  background: #fff;
  border-radius: 10px;
}
.related-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.source-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}
.source-note {
  background: #E8F0FE;
  color: #1967D2;
}
.source-kb {
  background: #FEF7E0;
  color: #B06000;
}
.similarity {
  font-size: 12px;
  color: #999;
}
.related-title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.related-preview {
  margin: 0;
  font-size: 13px;
  color: #999;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
