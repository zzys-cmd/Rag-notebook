<template>
  <div v-if="visible" class="ghost-wrapper" :style="wrapperStyle">
    <span class="ghost-text">{{ completion }}</span>
    <span class="ghost-meta">
      <span class="ghost-hint">&#8627; Tab</span>
      <span v-if="isTouchDevice" class="ghost-sep">&#183;</span>
      <span v-if="isTouchDevice" class="ghost-accept-btn" @click.stop="acceptCompletion">接受</span>
    </span>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'

const props = defineProps({
  context: { type: String, default: '' },
  position: { type: Object, default: () => ({ top: 0, left: 0 }) },
})

const emit = defineEmits(['accept'])

const userStore = useUserStore()
const visible = ref(false)
const completion = ref('')
const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0

let debounceTimer = null
let controller = null

const wrapperStyle = computed(() => ({
  top: `${props.position.top}px`,
  left: `${props.position.left}px`,
}))

function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userStore.token}`,
  }
}

function acceptCompletion() {
  if (!completion.value) return
  emit('accept', completion.value)
  visible.value = false
}

async function fetchCompletion(context) {
  if (!context || context.length < 5) return
  if (controller) controller.abort()
  controller = new AbortController()
  try {
    const res = await fetch(apiConfig.endpoints.noteAutocomplete, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ context }),
      signal: controller.signal,
    })
    const json = await res.json()
    if (json.code === 200 && json.data?.success && json.data.completion) {
      completion.value = json.data.completion
      visible.value = true
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      console.error('Autocomplete error:', e)
    }
  }
}

watch(() => props.context, (newVal) => {
  visible.value = false
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchCompletion(newVal)
  }, 500)
})

function handleKeydown(e) {
  if (!visible.value) return
  if (e.key === 'Tab') {
    e.preventDefault()
    e.stopPropagation()
    acceptCompletion()
  } else if (e.key === 'Escape') {
    visible.value = false
  } else if (e.key.length === 1) {
    visible.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown, { capture: true })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown, { capture: true })
  if (debounceTimer) clearTimeout(debounceTimer)
  if (controller) controller.abort()
})
</script>

<style scoped>
.ghost-wrapper {
  position: absolute;
  pointer-events: none;
  display: inline;
  white-space: pre-wrap;
  max-width: 60vw;
  z-index: 10;
  line-height: 1.7;
}

.ghost-text {
  opacity: 0.3;
  color: #999;
  font-family: 'Noto Sans SC', monospace;
  font-size: 15px;
  white-space: pre-wrap;
}

/* ---- 补全操作元信息（Tab 提示 + 接受按钮） ---- */
.ghost-meta {
  display: inline;
  white-space: nowrap;
  font-size: 11px;
  color: #d0d0d0;
  user-select: none;
}

.ghost-hint {
  margin-left: 4px;
}

.ghost-sep {
  margin: 0 3px;
  color: #e0e0e0;
}

.ghost-accept-btn {
  pointer-events: auto;
  cursor: pointer;
  color: #D4914A;
  -webkit-tap-highlight-color: transparent;
}
.ghost-accept-btn:active {
  color: #b87a3a;
}
</style>
