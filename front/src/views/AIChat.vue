<template>
  <div class="ai-chat-container">
    <van-nav-bar 
      title="AI问答" 
      fixed 
      right-text="会话" 
      @click-right="goToSessions"
    />
    
    <div class="chat-content">
      <div class="messages-container" ref="messagesContainer">
        <!-- 欢迎状态（仅首次进入时显示） -->
        <div v-if="showWelcome" class="welcome-card">
          <div class="welcome-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
              <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.27A7.01 7.01 0 0 1 14 23h-4a7.01 7.01 0 0 1-6.73-5H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"/>
            </svg>
          </div>
          <h3 class="welcome-title">智能笔记助手</h3>
          <p class="welcome-desc">基于你的笔记和知识库的智能助手。帮你整理思路、优化内容、随时问答。</p>
          <div class="welcome-questions">
            <button
              v-for="(q, i) in quickQuestions"
              :key="i"
              class="quick-question"
              @click="sendQuickQuestion(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>
        <div 
          v-for="(message, index) in messages" 
          v-show="!showWelcome || message.role === 'user' || index > 0"
          :key="index"
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <!-- 思考过程区域 -->
            <div v-if="message.thinking && message.thinking.length > 0" class="thinking-section">
              <div class="thinking-header" @click="toggleThinking(message)">
                <span class="thinking-label">💬 思考过程</span>
                <span class="thinking-toggle">{{ message.thinkingCollapsed ? '展开' : '收起' }}</span>
              </div>
              <div v-show="!message.thinkingCollapsed" class="thinking-body">
                <div v-for="(step, sIndex) in message.thinking" :key="sIndex" class="thinking-step">
                  <span class="thinking-stage-label" :style="{ backgroundColor: getStageColor(step.stage) }">
                    {{ getStageLabel(step.stage) }}
                  </span>
                  <span class="thinking-step-content">{{ step.content }}</span>
                  <div v-if="step.details" class="thinking-details">
                    <template v-if="step.details.documents">
                      <div v-for="(doc, dIndex) in step.details.documents.slice(0, 3)" :key="dIndex" class="thinking-doc-item">
                        <span class="thinking-doc-source">{{ doc.source }}</span>
                        <span class="thinking-doc-score">{{ (doc.score * 100).toFixed(0) }}%</span>
                      </div>
                      <div v-if="step.details.documents.length > 3" class="thinking-doc-more">
                        ... 还有 {{ step.details.documents.length - 3 }} 个文档
                      </div>
                    </template>
                    <template v-else-if="step.details.scores">
                      <div v-for="(sc, cIndex) in step.details.scores.slice(0, 3)" :key="cIndex" class="thinking-score-item">
                        <span>#{{ sc.rank || sc.index }}</span>
                        <span>{{ (sc.score * 100).toFixed(0) }}%</span>
                        <span class="thinking-score-preview">{{ truncateText(sc.preview, 40) }}</span>
                      </div>
                    </template>
                    <template v-else-if="step.details.hypothetical_doc_preview">
                      <div class="thinking-detail-text">{{ truncateText(step.details.hypothetical_doc_preview, 80) }}</div>
                    </template>
                    <template v-else>
                      <div v-for="(val, key) in step.details" :key="key" class="thinking-detail-kv">
                        <span class="thinking-detail-key">{{ key }}:</span>
                        <span class="thinking-detail-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
            <!-- 回复正文 -->
            <div v-if="message.content" v-html="formatMessage(message.content)"></div>
            <!-- 打字指示器（无内容且无思考过程时显示） -->
            <div v-if="message.role === 'assistant' && !message.content && (!message.thinking || message.thinking.length === 0)" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import TabBar from '../components/TabBar.vue';
import { showToast } from 'vant';
import { marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
import 'highlight.js/lib/common';
import { apiConfig } from '../config/api';
import { useUserStore } from '../store/user';
import { useSessionStore } from '../store/session';

// 从cookie中获取CSRF token
const getCsrfToken = () => {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return cookieValue || '';
};

// 聊天消息
const messages = ref([
  { role: 'assistant', content: '你好！我是智能笔记助手，帮你整理笔记、优化内容、回答关于笔记的问题。' }
]);
const userInput = ref('');
const messagesContainer = ref(null);
const isLoading = ref(false);
const sessionId = ref('');
const hasJumped = ref(false);
const autoCollapseTimer = ref(null);

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const sessionStore = useSessionStore();

// 欢迎状态：没有任何用户消息时显示
const showWelcome = computed(() => {
  return messages.value.length === 1 && messages.value[0].role === 'assistant';
});

// 快捷提问
const quickQuestions = [
  '帮我整理笔记要点',
  '如何写出更好的笔记？',
  '总结这篇笔记的核心内容',
  '为我的笔记添加标签建议',
];

const sendQuickQuestion = (question) => {
  userInput.value = question;
  sendMessage();
};

// 配置marked使用marked-highlight插件
marked.use(markedHighlight({
  langPrefix: 'hljs language-',
  highlight(code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    return hljs.highlight(code, { language }).value;
  }
}));

// 格式化消息内容（支持Markdown和代码高亮）
const formatMessage = (content) => {
  if (!content) return '';
  try {
    // 使用marked解析Markdown，并用DOMPurify清理HTML
    const parsed = marked(content, {
      breaks: true,
      gfm: true,
      headerIds: false,
      mangle: false
    });
    const sanitized = DOMPurify.sanitize(parsed);
    return sanitized;
  } catch (error) {
    console.error('Markdown解析错误:', error);
    return content;
  }
};

// 思考过程阶段配置（温润色调）
const stageConfig = {
  retrieval:  { label: '检索',   color: '#B8926E' },
  hyde:       { label: 'HyDE',   color: '#8B7E6F' },
  reorder:    { label: '重排序', color: '#D4914A' },
  summarize:  { label: '总结',   color: '#7D9B7A' }
};

const getStageLabel = (stage) => {
  return stageConfig[stage]?.label || stage || '处理中';
};

const getStageColor = (stage) => {
  return stageConfig[stage]?.color || '#999';
};

const truncateText = (text, maxLen) => {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
};

// localStorage 存储最近 5 条思考过程
const THINKING_HISTORY_KEY = 'ai_thinking_history';

const saveThinkingToHistory = (sessionId, query, thinking) => {
  if (!sessionId || !thinking || thinking.length === 0) return;
  try {
    let history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
    history = history.filter(e => e.sessionId !== sessionId);
    history.unshift({ sessionId, query, thinking, timestamp: Date.now() });
    localStorage.setItem(THINKING_HISTORY_KEY, JSON.stringify(history.slice(0, 5)));
  } catch (e) { /* ignore */ }
};

const loadThinkingFromHistory = (sessionId) => {
  if (!sessionId) return null;
  try {
    const history = JSON.parse(localStorage.getItem(THINKING_HISTORY_KEY) || '[]');
    return history.find(e => e.sessionId === sessionId)?.thinking || null;
  } catch (e) {
    return null;
  }
};

// 切换思考过程展开/折叠（用户手动操作时取消自动折叠定时器）
const toggleThinking = (message) => {
  message.thinkingCollapsed = !message.thinkingCollapsed;
  if (autoCollapseTimer.value) {
    clearTimeout(autoCollapseTimer.value);
    autoCollapseTimer.value = null;
  }
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return;
  
  // 检查是否登录
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    return;
  }
  
  // 添加用户消息
  const userMessage = userInput.value.trim();
  messages.value.push({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位（含思考过程字段）
  messages.value.push({ role: 'assistant', content: '', thinking: [], thinkingCollapsed: false, thinkingAutoCollapsed: false });
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    messages.value[messages.value.length - 1].content = `发生错误: ${error.message || '请检查网络连接和API设置'}`;
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 获取AI响应（使用SSE）
const fetchAIResponse = async (userMessage) => {
  try {
    // 确保使用正确的相对路径，通过Vite代理访问
    const url = '/chat/agent/query/stream';
    // 从localStorage获取token
    const token = localStorage.getItem('jwt_token') || userStore.token;
    // console.log('发送AI请求到:', url);
    // console.log('使用的token:', token);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        session_id: sessionId.value || undefined,
        query: userMessage
      })
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    // 处理SSE流
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiResponse = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (!data) continue;
        
        try {
          const json = JSON.parse(data);
          
          switch (json.type) {
            case 'step':
              break;
            case 'thinking':
              {
                const idx = messages.value.length - 1;
                if (messages.value[idx].role === 'assistant') {
                  const newStep = {
                    stage: json.stage || '',
                    content: json.content || '',
                    details: json.details || null
                  };
                  // 完整替换消息对象以强制 Vue 重新渲染
                  messages.value[idx] = {
                    ...messages.value[idx],
                    thinking: [...messages.value[idx].thinking, newStep]
                  };
                  // 等待 Vue DOM 刷新 + 浏览器 paint
                  await nextTick();
                  await new Promise(resolve => requestAnimationFrame(resolve));
                  scrollToBottom();
                }
              }
              break;
            case 'response':
              {
                const lastMsg = messages.value[messages.value.length - 1];
                // 第一条 response 到达时延迟折叠思考过程（仅一次）
                if (!lastMsg.thinkingAutoCollapsed && lastMsg.thinking.length > 0) {
                  lastMsg.thinkingAutoCollapsed = true;
                  if (autoCollapseTimer.value) clearTimeout(autoCollapseTimer.value);
                  autoCollapseTimer.value = setTimeout(() => {
                    lastMsg.thinkingCollapsed = true;
                    autoCollapseTimer.value = null;
                  }, 1500);
                }
                const content = json.content || '';
                if (content) {
                  aiResponse += content;
                  
                  // 逐字符显示打字机效果
                  const displayContent = lastMsg.content || '';
                  const remainingContent = aiResponse.substring(displayContent.length);
                  
                  for (const char of remainingContent) {
                    lastMsg.content += char;
                  await new Promise(resolve => setTimeout(resolve, 0));
                    scrollToBottom();
                    // 控制打字速度，每个字符延迟8ms
                    await new Promise(resolve => setTimeout(resolve, 8));
                  }
                }
                // 保存会话ID（不立即跳转，避免中断SSE）
                if (json.session_id && typeof json.session_id === 'string' && json.session_id.trim()) {
                  sessionId.value = json.session_id;
                }
              }
              break;
            case 'done':
              {
                const sid = json.session_id;
                if (sid && typeof sid === 'string' && sid.trim()) {
                  sessionId.value = sid;
                  // 保存思考过程到 localStorage
                  const lastMsg = messages.value[messages.value.length - 1];
                  if (lastMsg && lastMsg.role === 'assistant') {
                    saveThinkingToHistory(sid, userMessage, lastMsg.thinking);
                  }
                  // 如果当前路由没有sessionId参数，跳转到带sessionId的路由
                  if (!route.params.sessionId) {
                    router.push(`/aichat/${sid}`);
                  }
                }
              }
              break;
            case 'error':
              throw new Error(json.content || 'API错误');
              break;
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e);
        }
      }
    }
  }
  
  // 如果没有收到任何内容
  if (!aiResponse) {
    messages.value[messages.value.length - 1].content = '抱歉，我无法生成回复。请检查API设置或稍后再试。';
  }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

// 跳转到会话管理页面
const goToSessions = () => {
  router.push('/sessions');
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(() => {
    scrollToBottom();
  });
}, { deep: true });

// 监听路由参数变化，重新加载会话历史
watch(() => route.params.sessionId, async (newSessionId) => {
  if (newSessionId) {
    try {
      const result = await sessionStore.getSession(newSessionId);
      if (result.success && sessionStore.currentSession) {
        loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      showToast('加载会话历史失败');
    }
  }
}, { immediate: true });

// 组件挂载时检查是否有当前会话或路由参数中的会话ID
onMounted(async () => {
  // 检查路由参数中是否有sessionId
  const routeSessionId = route.params.sessionId;
  
  if (routeSessionId) {
    // 从路由参数获取会话ID，加载会话历史
    try {
      const result = await sessionStore.getSession(routeSessionId);
      if (result.success && sessionStore.currentSession) {
        loadSessionHistory(sessionStore.currentSession);
      } else {
        showToast('加载会话历史失败');
      }
    } catch (error) {
      console.error('加载会话历史失败:', error);
      showToast('加载会话历史失败');
    }
  } else if (sessionStore.currentSession) {
    // 从store中加载会话历史
    loadSessionHistory(sessionStore.currentSession);
  }
  
  scrollToBottom();
});

// 加载会话历史
const loadSessionHistory = (session) => {
  if (session.history && session.history.length > 0) {
    // 清空当前消息
    messages.value = [];
    // 加载历史消息
    session.history.forEach(([userMsg, aiMsg]) => {
      messages.value.push({ role: 'user', content: userMsg });
      messages.value.push({ role: 'assistant', content: aiMsg, thinking: [], thinkingCollapsed: true, thinkingAutoCollapsed: true });
    });
    // 设置会话ID
    sessionId.value = session.session_id;
    // 从 localStorage 恢复思考过程
    const saved = loadThinkingFromHistory(session.session_id);
    if (saved && messages.value.length > 0) {
      const last = messages.value[messages.value.length - 1];
      if (last.role === 'assistant') {
        last.thinking = saved;
      }
    }
  }
};
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
  background-color: var(--color-bg);
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ==================== 欢迎卡片 ==================== */
.welcome-card {
  text-align: center;
  padding: 40px 32px 24px;
  animation: fadeIn 0.5s ease-out;
}

.welcome-icon {
  color: var(--color-primary);
  margin-bottom: 12px;
  opacity: 0.8;
}

.welcome-title {
  font-family: var(--font-heading);
  font-size: 20px;
  color: var(--color-text);
  margin: 0 0 8px;
  font-weight: 600;
}

.welcome-desc {
  font-size: 14px;
  color: var(--color-text-light);
  line-height: 1.6;
  margin: 0 0 20px;
}

.welcome-questions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  max-width: 320px;
  margin: 0 auto;
}

.quick-question {
  all: unset;
  display: inline-block;
  font-size: 13px;
  color: var(--color-text-light);
  background: var(--color-card);
  padding: 10px 18px;
  border-radius: 24px;
  cursor: pointer;
  box-shadow: 0 1px 3px var(--color-shadow);
  border: 1px solid var(--color-border-light);
  transition: all 0.15s ease;
  line-height: 1.4;
  font-family: var(--font-body);
}

.quick-question:active {
  transform: scale(0.97);
  background: var(--color-surface);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* ==================== 消息容器 ==================== */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

.message {
  margin-bottom: 14px;
  max-width: 80%;
  animation: fadeIn 0.3s ease-out;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  word-break: break-word;
  line-height: 1.6;
}

/* 用户气泡 — 暖灰底 + 深棕文字 + 原角 */
.user-message .message-content {
  background-color: #EDE4D8;
  color: var(--color-text);
  border-bottom-right-radius: 4px;
  box-shadow: 0 1px 2px var(--color-shadow);
}

/* AI 气泡 — 卡片底 + 暖棕文字 + 微阴影 */
.ai-message .message-content {
  background-color: var(--color-card);
  color: var(--color-text);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px var(--color-shadow);
}

/* ==================== 输入区域 ==================== */
.input-container {
  display: flex;
  padding: 8px 12px;
  border-top: 1px solid var(--color-border-light);
  background-color: var(--color-card);
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  margin-right: 10px;
  --van-field-background: var(--color-surface);
  --van-field-border-radius: 10px;
}

.send-button {
  align-self: flex-end;
}

/* ==================== Markdown 排版 ==================== */
:deep(p) {
  margin: 6px 0;
  line-height: 1.7;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

:deep(li) {
  margin: 3px 0;
  line-height: 1.6;
}

:deep(a) {
  color: var(--color-primary);
  text-decoration: none;
}

:deep(a:hover) {
  text-decoration: underline;
}

:deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
  margin: 10px 0 6px;
  font-weight: 600;
  color: var(--color-text);
}

:deep(h1) { font-size: 1.4em; }
:deep(h2) { font-size: 1.25em; }
:deep(h3) { font-size: 1.1em; }

:deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding: 6px 12px;
  margin: 8px 0;
  color: var(--color-text-light);
  background-color: var(--color-surface);
  border-radius: 0 6px 6px 0;
  font-size: 0.95em;
}

:deep(hr) {
  border: 0;
  border-top: 1px solid var(--color-divider);
  margin: 14px 0;
}

:deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 6px 0;
}

:deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 0.95em;
}

:deep(th), :deep(td) {
  border: 1px solid var(--color-border);
  padding: 6px 10px;
  text-align: left;
}

:deep(th) {
  background-color: var(--color-surface);
  font-weight: 600;
}

/* 代码块 — 暖调浅底 */
:deep(pre) {
  background-color: var(--color-surface);
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  border: 1px solid var(--color-border-light);
  font-size: 0.9em;
  line-height: 1.5;
}

:deep(pre code) {
  background-color: transparent;
  padding: 0;
  border-radius: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', 'Source Code Pro', monospace;
  font-size: inherit;
  color: inherit;
}

:deep(code) {
  font-family: 'Consolas', 'Monaco', 'Courier New', 'Source Code Pro', monospace;
  background-color: var(--color-surface);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
  color: var(--color-text-light);
}

/* ==================== 打字指示器 ==================== */
.typing-indicator {
  display: flex;
  padding: 4px 0;
  gap: 4px;
}

.typing-indicator span {
  height: 7px;
  width: 7px;
  background-color: var(--color-text-lighter);
  border-radius: 50%;
  display: inline-block;
  animation: bounce 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.15s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.3s; }

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30%           { transform: translateY(-6px); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* ==================== 思考过程 ==================== */
.thinking-section {
  margin-bottom: 8px;
  border-left: 3px solid rgba(212, 145, 74, 0.25);
  background-color: var(--color-surface);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.thinking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding: 2px 0;
}

.thinking-label {
  color: var(--color-text-lighter);
  font-weight: 500;
  font-size: 12px;
}

.thinking-toggle {
  color: var(--color-text-lightest);
  font-size: 11px;
}

.thinking-body {
  margin-top: 6px;
}

.thinking-step {
  padding: 4px 0;
  border-bottom: 1px solid var(--color-border-light);
  line-height: 1.4;
}

.thinking-step:last-child {
  border-bottom: none;
}

.thinking-stage-label {
  display: inline-block;
  font-size: 10px;
  color: #fff;
  padding: 2px 7px;
  border-radius: 3px;
  margin-right: 5px;
  vertical-align: middle;
  line-height: 1.5;
  letter-spacing: 0.3px;
}

.thinking-step-content {
  color: var(--color-text-light);
  font-size: 12px;
  vertical-align: middle;
}

.thinking-details {
  margin-top: 4px;
  padding: 6px 8px;
  background-color: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
  font-size: 11px;
  color: var(--color-text-lighter);
}

.thinking-detail-text {
  color: var(--color-text-lighter);
  font-size: 11px;
  line-height: 1.4;
}

.thinking-detail-kv {
  display: flex;
  gap: 4px;
  line-height: 1.5;
}

.thinking-detail-key {
  color: var(--color-text-lightest);
  white-space: nowrap;
}

.thinking-detail-val {
  color: var(--color-text-lighter);
  word-break: break-all;
}

.thinking-doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
  line-height: 1.5;
}

.thinking-doc-source {
  color: var(--color-text-lighter);
  font-size: 11px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thinking-doc-score {
  color: var(--color-text-light);
  font-size: 11px;
  margin-left: 8px;
  white-space: nowrap;
}

.thinking-doc-more {
  color: var(--color-text-lightest);
  font-size: 11px;
  margin-top: 2px;
}

.thinking-score-item {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 2px 0;
  line-height: 1.5;
  font-size: 11px;
  color: var(--color-text-lighter);
}

.thinking-score-preview {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-lightest);
}
</style>