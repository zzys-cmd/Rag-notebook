<template>
  <div class="note-list-page">
    <van-nav-bar title="我的笔记" fixed right-text="新建" @click-right="createNote" />

    <div class="list-content">
      <!-- 搜索栏 -->
      <div class="search-bar">
        <van-search v-model="searchQuery" placeholder="搜索笔记..." shape="round" @search="handleSearch" />
      </div>

      <!-- 分类筛选栏 -->
      <div class="category-tabs">
        <span
          v-for="c in categories"
          :key="c.key"
          class="category-item"
          :class="{ active: currentCategory === c.key }"
          @click="filterByCategory(c.key)"
        >
          {{ c.label }}
        </span>
      </div>

      <!-- 笔记列表 -->
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-list
          v-model:loading="loading"
          :finished="finished"
          finished-text="没有更多了"
          @load="onLoad"
        >
          <div
            v-for="note in notes"
            :key="note.id"
            class="note-card card-shadow"
            @click="goToEditor(note.id)"
          >
            <h3 class="note-title">{{ note.title }}</h3>
            <p class="note-preview">{{ getPreview(note.content) }}</p>
            <div class="note-meta">
              <div class="note-tags">
                <span v-if="note.category" class="note-category">{{ categoryMap[note.category] || note.category }}</span>
                <TagBadge
                  v-for="tag in (note.tags || [])"
                  :key="tag"
                  :tag="tag"
                  :color="getCategoryColor(note.category)"
                />
              </div>
              <span class="note-date">{{ formatDate(note.updated_at) }}</span>
            </div>
          </div>
        </van-list>
      </van-pull-refresh>

      <van-empty v-if="!loading && notes.length === 0" description="还没有笔记，点击右上角创建" />
    </div>

    <TabBar />
  </div>
</template>

<script setup>
/**
 * NoteList 笔记列表页 —— 卡片式展示，支持分类筛选、搜索、下拉刷新、无限滚动。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'
import TagBadge from '../components/TagBadge.vue'
import TabBar from '../components/TabBar.vue'

const router = useRouter()
const userStore = useUserStore()

/** 笔记数据 */
const notes = ref([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const searchQuery = ref('')
const currentCategory = ref('all')
const page = ref(1)
const pageSize = 20

/** 分类选项 */
const categories = [
  { key: 'all', label: '全部' },
  { key: 'work', label: '工作' },
  { key: 'study', label: '学习' },
  { key: 'life', label: '生活' },
  { key: 'project', label: '项目' },
]

/** 获取 token */
const token = computed(() => userStore.token)

/** 请求头 */
function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token.value}`,
  }
}

/** 截取笔记预览文本（移除 Markdown 标记，取前 100 字） */
function getPreview(content) {
  if (!content) return ''
  const text = content.replace(/[#*`~>\[\]()!|-]/g, '').replace(/\s+/g, ' ').trim()
  return text.length > 100 ? text.slice(0, 100) + '...' : text
}

/** 格式化日期 */
function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

/** 分类名称映射 */
const categoryMap = { work: '工作', study: '学习', life: '生活', project: '项目' }

/** 根据分类返回颜色 */
function getCategoryColor(category) {
  const map = { work: 'work', study: 'study', life: 'life', project: 'project' }
  return map[category] || 'default'
}

/** 加载笔记列表 */
async function fetchNotes(isRefresh = false) {
  if (loading.value || finished.value) return
  loading.value = true

  if (isRefresh) {
    page.value = 1
    finished.value = false
  }

  const params = new URLSearchParams({ page: page.value, page_size: pageSize })
  if (currentCategory.value !== 'all') {
    params.append('category', currentCategory.value)
  }

  try {
    const url = `${apiConfig.endpoints.noteList}?${params.toString()}`
    const res = await fetch(url, { headers: getHeaders() })
    const json = await res.json()
    if (json.code === 200) {
      const newNotes = json.data.notes || []
      if (isRefresh) {
        notes.value = newNotes
      } else {
        notes.value = [...notes.value, ...newNotes]
      }
      if (newNotes.length < pageSize) {
        finished.value = true
      }
      // 成功获取数据后递增页码，供下次加载使用
      page.value++
    }
  } catch (e) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

/** 搜索笔记 */
async function handleSearch() {
  if (!searchQuery.value.trim()) return
  try {
    const url = `${apiConfig.endpoints.noteSearch}?q=${encodeURIComponent(searchQuery.value)}`
    const res = await fetch(url, { headers: getHeaders() })
    const json = await res.json()
    if (json.code === 200) {
      notes.value = json.data.notes || []
      finished.value = true
    }
  } catch (e) {
    showToast('搜索失败')
  }
}

/** 分类筛选 */
function filterByCategory(key) {
  currentCategory.value = key
  notes.value = []
  page.value = 1
  finished.value = false
  searchQuery.value = ''
  fetchNotes(true)
}

/** 无限滚动加载 */
function onLoad() {
  if (searchQuery.value.trim()) return
  fetchNotes(false)
}

/** 页面挂载时自动触发首次加载 */
onMounted(() => {
  fetchNotes(true)
})

/** 下拉刷新 */
async function onRefresh() {
  await fetchNotes(true)
  refreshing.value = false
}

/** 创建新笔记 */
function createNote() {
  // 新建笔记前清除旧草稿，确保编辑器空白
  localStorage.removeItem('note_draft')
  router.push('/notes/new')
}

/** 进入编辑器 */
function goToEditor(id) {
  router.push(`/notes/${id}`)
}
</script>

<style scoped>
.note-list-page {
  min-height: 100vh;
  background: var(--van-background, #f7f8fa);
  display: flex;
  flex-direction: column;
}
.list-content {
  flex: 1;
  overflow-y: auto;
  padding-top: 46px;
  padding-bottom: 60px;
}
.search-bar {
  padding: 0 12px;
}
.category-tabs {
  display: flex;
  gap: 8px;
  padding: 0 16px 12px;
  overflow-x: auto;
}
.category-item {
  padding: 4px 14px;
  border-radius: 16px;
  background: #fff;
  font-size: 13px;
  color: #666;
  white-space: nowrap;
  flex-shrink: 0;
}
.category-item.active {
  background: var(--van-primary-color, #D4914A);
  color: #fff;
}
.note-card {
  margin: 0 16px 12px;
  padding: 16px;
  background: #fff;
  border-radius: 10px;
}
.note-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 600;
  color: #333;
}
.note-preview {
  margin: 0 0 12px;
  font-size: 14px;
  color: #999;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.note-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.note-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.note-category {
  font-size: 12px;
  color: #999;
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 4px;
}
.note-date {
  font-size: 12px;
  color: #bbb;
  flex-shrink: 0;
}
</style>
