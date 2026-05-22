<template>
  <div class="quick-toolbar">
    <button
      v-for="btn in buttons"
      :key="btn.action"
      class="qbtn"
      :title="btn.title"
      @mousedown.prevent="handleAction(btn)"
    >
      {{ btn.label }}
    </button>
  </div>
</template>

<script setup>
/**
 * QuickToolbar 快捷 Markdown 按钮栏 —— 对标 WangEditor 式交互。
 * 选中文字后点击按钮 → 自动用对应 Markdown 语法包裹。
 * 无选中文字时 → 插入语法 + 占位文字。
 */
import { ref, onMounted, inject } from 'vue'

const props = defineProps({
  /** 父组件传入的 MarkdownEditor 组件 ref */
  editorRef: { type: Object, default: null },
})

/** 8 个快捷按钮配置 */
const buttons = [
  { label: 'B', title: '加粗', action: 'bold', template: '**$1**', placeholder: '粗体文字' },
  { label: 'H1', title: '一级标题', action: 'h1', template: '# $1', placeholder: '一级标题' },
  { label: 'H2', title: '二级标题', action: 'h2', template: '## $1', placeholder: '二级标题' },
  { label: 'H3', title: '三级标题', action: 'h3', template: '### $1', placeholder: '三级标题' },
  { label: '</>', title: '行内代码', action: 'code', template: '`$1`', placeholder: '代码' },
  { label: '"', title: '引用', action: 'quote', template: '> $1', placeholder: '引用文字' },
  { label: '•', title: '无序列表', action: 'list', template: '- $1', placeholder: '列表项' },
  { label: '🔗', title: '链接', action: 'link', template: '[$1](https://)', placeholder: '链接文字' },
]

/**
 * 获取 CodeMirror 实例。
 * 优先通过组件 ref 暴露的方法获取，兜底走 DOM 查询。
 */
function getCodeMirror() {
  // 通过 MarkdownEditor 暴露的 getEditorCm() 方法获取
  if (props.editorRef?.getEditorCm) {
    const cm = props.editorRef.getEditorCm()
    if (cm) return cm
  }

  // 兜底：DOM 查询 CodeMirror 实例
  const el = document.querySelector('.bytemd .CodeMirror')
  return el?.CodeMirror || null
}

/**
 * 执行 Markdown 包裹逻辑。
 * 有选区 → 包裹选中文字；无选区 → 插入语法 + 占位文字 → 选中占位文字。
 */
function handleAction(btn) {
  const cm = getCodeMirror()
  if (!cm) return

  const selection = cm.getSelection()
  const hasSelection = selection && selection.length > 0

  if (hasSelection) {
    // 有选中文字：直接包裹
    const wrapped = btn.template.replace('$1', selection)
    cm.replaceSelection(wrapped)
  } else {
    // 无选中文字：插入语法 + 占位文字，并选中占位文字方便用户替换
    const wrapped = btn.template.replace('$1', btn.placeholder)
    const doc = cm.getDoc()
    const cursor = doc.getCursor()
    doc.replaceRange(wrapped, cursor)

    // 选中占位文字区域
    const placeholderStart = wrapped.indexOf(btn.placeholder)
    if (placeholderStart !== -1) {
      const from = { line: cursor.line, ch: cursor.ch + placeholderStart }
      const to = { line: cursor.line, ch: from.ch + btn.placeholder.length }
      doc.setSelection(from, to)
    }
  }

  // 写入后聚焦编辑器
  cm.focus()
}

onMounted(() => {
  // 编辑器中 Ctrl+B 等快捷键也走自定义工具栏逻辑？不需要，保留 CodeMirror 原生行为。
})
</script>

<style scoped>
.quick-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 16px;
  background: #fafafa;
  border-bottom: 1px solid #ebedf0;
  flex-shrink: 0;
  overflow-x: auto;
}
.qbtn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 28px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  color: #555;
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
  font-family: 'Noto Sans SC', 'SF Mono', monospace;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.qbtn:hover {
  background: #e8e8e8;
  color: #333;
  border-color: #d0d0d0;
}
.qbtn:active {
  background: #d0d0d0;
}
</style>
