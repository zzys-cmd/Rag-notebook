<template>
  <span v-if="visible" class="ghost-text" ref="ghostEl">
    {{ completion }}
  </span>
</template>

<script setup>
/**
 * InlineCompletion 内联补全组件 —— 幽灵文本（ghost text），对标 GitHub Copilot。
 * 通过 absolute 定位在光标位置，opacity: 0.4 渲染补全建议。
 * Tab 键接受补全，Esc / 继续输入则消失。
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { apiConfig } from '../config/api'
import { useUserStore } from '../store/user'

const props = defineProps({
  context: { type: String, default: '' },   /** 光标前上下文文本 */
  editorEl: { type: Object, default: null }, /** 编辑器 DOM 元素引用 */
})

const emit = defineEmits(['accept'])         /** Tab 键触发，返回补全文本 */

const userStore = useUserStore()
const visible = ref(false)
const completion = ref('')
const ghostEl = ref(null)

let debounceTimer = null
let controller = null  /** AbortController 用于取消重复请求 */

/** 请求头 */
function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${userStore.token}`,
  }
}

/** 请求补全 */
async function fetchCompletion(context) {
  if (!context || context.length < 5) return

  // 取消上一次未完成的请求
  if (controller) {
    controller.abort()
  }
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
      // ignore other errors
    }
  }
}

/** 上下文变化时，500ms 防抖后请求补全 */
watch(() => props.context, (newVal) => {
  visible.value = false
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    fetchCompletion(newVal)
  }, 500)
})

/** 监听键盘事件：Tab 接受，Esc / 任意输入取消 */
function handleKeydown(e) {
  if (!visible.value) return

  if (e.key === 'Tab') {
    e.preventDefault()
    emit('accept', completion.value)
    visible.value = false
  } else if (e.key === 'Escape') {
    visible.value = false
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  if (debounceTimer) clearTimeout(debounceTimer)
  if (controller) controller.abort()
})
</script>

<style scoped>
.ghost-text {
  position: absolute;
  pointer-events: none;           /** 不拦截点击事件 */
  opacity: 0.4;
  color: #999;
  font-family: 'Noto Sans SC', monospace;
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-wrap;
  z-index: 1;
}
</style>
