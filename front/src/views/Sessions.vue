<template>
  <div class="sessions-container">
    <van-nav-bar title="会话管理" fixed />
    
    <div class="sessions-content">
      <div class="sessions-header">
        <div class="header-title">
          <van-icon name="chat-o" size="24" color="#1989fa" />
          <h2>历史会话</h2>
        </div>
        <van-button type="primary" @click="createNewSession">
          新会话
        </van-button>
      </div>
      
      <div v-if="sessionStore.isLoading" class="loading">
        <van-loading type="spinner" color="#1989fa" />
        <p>加载中...</p>
      </div>
      
      <div v-else-if="sessionStore.sessions.length === 0" class="empty-sessions">
        <div class="empty-icon">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            <line x1="9" y1="10" x2="15" y2="10"/>
            <line x1="12" y1="7" x2="12" y2="13"/>
          </svg>
        </div>
        <p>暂无会话记录</p>
        <p class="empty-sub">开始一段新的对话吧</p>
        <van-button type="primary" round @click="createNewSession">
          创建新会话
        </van-button>
      </div>
      
      <div v-else class="sessions-list">
        <van-cell-group>
          <van-cell
            v-for="session in sessionStore.sessions"
            :key="session.session_id"
            :title="session.title || '新会话'"
            :value="formatSessionTime(session.created_at)"
            is-link
            @click="selectSession(session)"
            :class="{ active: sessionStore.currentSession?.session_id === session.session_id }"
          >
            <template #right-icon>
              <span class="delete-btn" @click.stop="deleteSession(session.session_id)">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  <line x1="10" y1="11" x2="10" y2="17"/>
                  <line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
              </span>
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </div>
    
    <!-- 新会话对话框 -->
    <van-popup v-model:show="showNewSessionDialog" position="bottom">
      <div class="new-session-dialog">
        <h3>新会话</h3>
        <van-field
          v-model="newSessionQuery"
          type="textarea"
          rows="3"
          placeholder="请输入您的问题..."
          maxlength="200"
        />
        <div class="dialog-buttons">
          <van-button @click="showNewSessionDialog = false">取消</van-button>
          <van-button type="primary" @click="confirmNewSession" :disabled="!newSessionQuery.trim()">
            开始对话
          </van-button>
        </div>
      </div>
    </van-popup>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { showToast, Toast } from 'vant';
import TabBar from '../components/TabBar.vue';
import { useSessionStore } from '../store/session';
import { useUserStore } from '../store/user';

const router = useRouter();
const route = useRoute();
const sessionStore = useSessionStore();
const userStore = useUserStore();

const showNewSessionDialog = ref(false);
const newSessionQuery = ref('');

// 监听路由变化，确保每次访问会话管理页面时自动刷新会话列表
watch(() => route.path, async (newPath) => {
  if (newPath === '/sessions') {
    await loadSessions();
  }
});

// 加载会话列表
const loadSessions = async () => {
  // 检查是否登录
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    router.push('/login');
    return;
  }
  
  // 获取用户ID（假设从用户信息中获取）
  if (!userStore.userInfo) {
    const result = await userStore.getUserInfoDetail();
    if (!result.success) {
      showToast('获取用户信息失败');
      return;
    }
  }
  
  if (userStore.userInfo) {

    
    // 尝试获取用户ID，支持不同的字段名
    let userId = userStore.userInfo.uuid || userStore.userInfo.id || userStore.userInfo.user_id;
    
    if (userId) {
      await sessionStore.getUserSessions(userId);
    } else {
      // 显示详细的错误信息
      showToast('获取用户ID失败，请检查用户信息结构');
      console.error('用户信息中没有找到ID字段:', userStore.userInfo);
    }
  } else {
    showToast('获取用户信息失败');
  }
};

// 组件挂载时获取会话列表
onMounted(async () => {
  await loadSessions();
});

// 获取会话标题（使用第一条消息作为标题）
const getSessionTitle = (session) => {
  if (session.history && session.history.length > 0) {
    const firstMessage = session.history[0][0]; // 第一条用户消息
    return firstMessage.length > 20 ? firstMessage.substring(0, 20) + '...' : firstMessage;
  }
  return '新会话';
};

// 格式化会话时间
const formatSessionTime = (timeString) => {
  if (!timeString) return '';
  try {
    const date = new Date(timeString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    return timeString;
  }
};

// 选择会话
const selectSession = (session) => {
  // 跳转到带会话ID的路由
  router.push(`/aichat/${session.session_id}`);
};

// 删除会话
const deleteSession = async (sessionId) => {

  
  const result = await sessionStore.deleteSession(sessionId);
  if (result.success) {
    showToast('会话删除成功');
  } else {
    showToast(result.message || '删除失败');
  }
};

// 打开新会话对话框
const createNewSession = () => {
  showNewSessionDialog.value = true;
};

// 确认创建新会话
const confirmNewSession = async () => {
  if (!newSessionQuery.value.trim()) return;
  
  // 显示加载状态，保存返回的toast实例
  const toastInstance = showToast({
    type: 'loading',
    message: '创建会话中...',
    forbidClick: true,
    duration: 0
  });
  
  try {
    const result = await sessionStore.createSession(newSessionQuery.value);
    if (result.success && result.data?.session_id) {
      showToast('会话创建成功');
      showNewSessionDialog.value = false;
      newSessionQuery.value = '';
      // 跳转到带会话ID的聊天页面
      router.push(`/aichat/${result.data.session_id}`);
    } else {
      showToast(result.message || '创建会话失败');
    }
  } catch (error) {
    showToast('创建会话失败');
    console.error('创建会话失败:', error);
  } finally {
    // 使用toast实例的关闭方法
    if (toastInstance && toastInstance.close) {
      toastInstance.close();
    }
  }
};
</script>

<style scoped>
.sessions-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
  background-color: var(--color-bg);
}

.sessions-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.sessions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text);
}

.sessions-header h2 {
  font-size: 18px;
  font-weight: 600;
  font-family: var(--font-heading);
  color: var(--color-text);
  margin: 0;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.loading p {
  margin-top: 16px;
  color: var(--color-text-light);
}

.empty-sessions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  animation: fadeIn 0.4s ease-out;
}

.empty-icon {
  color: var(--color-text-lightest);
  margin-bottom: 4px;
}

.empty-sessions p {
  margin: 8px 0 4px;
  color: var(--color-text-lighter);
  font-size: 15px;
}

.empty-sub {
  font-size: 13px;
  color: var(--color-text-lightest);
  margin-bottom: 20px !important;
}

.sessions-list {
  margin-top: 10px;
}

.sessions-list :deep(.van-cell) {
  border-radius: 8px;
  margin-bottom: 6px;
  background: var(--color-card);
  box-shadow: 0 1px 2px var(--color-shadow);
}

.active {
  background-color: rgba(212, 145, 74, 0.10) !important;
  border-left: 3px solid var(--color-primary);
}

.delete-btn {
  display: flex;
  align-items: center;
  padding: 4px;
  cursor: pointer;
  color: var(--color-text-lighter);
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
}

.delete-btn:hover {
  color: var(--color-text);
}

.delete-btn:active {
  background: var(--color-border-light);
}

.new-session-dialog {
  background-color: var(--color-card);
  border-radius: 16px 16px 0 0;
  padding: 20px;
}

.new-session-dialog h3 {
  font-size: 18px;
  font-weight: 600;
  font-family: var(--font-heading);
  color: var(--color-text);
  margin: 0 0 20px;
  text-align: center;
}

.dialog-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
  gap: 8px;
}

.dialog-buttons van-button {
  flex: 1;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
</style>