<template>
  <div class="knowledgebase-container">
    <van-nav-bar
      :title="$t('knowledgebase.title')"
      left-arrow
      @click-left="onClickLeft"
    />

    <div class="knowledgebase-content">
      <div class="upload-area" @click="openFilePicker" @dragover.prevent @drop.prevent="handleDrop">
        <div class="upload-icon">
          <van-icon name="upload" size="48" />
        </div>
        <p class="upload-text">{{ $t('knowledgebase.uploadText') }}</p>
        <p class="upload-hint">{{ $t('knowledgebase.uploadHint') }}</p>
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".md,.txt,.pdf,.docx,.pptx"
          class="file-input"
          @change="handleFileSelect"
        />
      </div>

      <div v-if="selectedFiles.length > 0" class="file-list">
        <h3 class="section-title">{{ $t('knowledgebase.selectedFiles') }}</h3>
        <van-cell-group inset>
          <van-cell
            v-for="(file, index) in selectedFiles"
            :key="index"
            :title="file.name"
            :value="formatFileSize(file.size)"
            is-link
            @click="removeFile(index)"
          >
            <template #right-icon>
              <van-icon name="delete" color="#f44" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>

      <van-button
        v-if="selectedFiles.length > 0 && !uploading"
        type="primary"
        block
        @click="uploadFiles"
      >
        {{ $t('knowledgebase.uploadButton') }}
      </van-button>

      <div v-if="uploading" class="upload-progress">
        <h3 class="section-title">{{ $t('knowledgebase.uploadProgress') }}</h3>
        <div v-for="(progress, index) in uploadProgressList" :key="index" class="progress-item">
          <div class="progress-header">
            <span class="progress-filename">{{ progress.filename }}</span>
            <span class="progress-status" :class="getStatusClass(progress.status)">
              {{ getStatusText(progress.status) }}
            </span>
          </div>
          <van-progress :percentage="progress.percentage" v-if="progress.percentage !== null" />
          <p class="progress-message">{{ progress.message }}</p>
        </div>
        <div v-if="uploadComplete" class="upload-result">
          <van-icon name="success" size="32" color="#07c160" />
          <p>{{ $t('knowledgebase.uploadComplete') }}</p>
          <p>{{ successCount }} {{ $t('knowledgebase.success') }}, {{ failedCount }} {{ $t('knowledgebase.failed') }}</p>
        </div>
      </div>

      <div v-if="!uploading" class="document-list">
        <div class="list-header">
          <h3 class="section-title">{{ $t('knowledgebase.documentList') }}</h3>
          <div class="list-actions">
            <span class="document-count">{{ documents.length }} {{ $t('knowledgebase.total') }}</span>
            <van-button
              v-if="documents.length > 0"
              size="small"
              type="danger"
              plain
              @click="handleCleanAll"
            >
              {{ $t('knowledgebase.cleanAll') }}
            </van-button>
          </div>
        </div>
        
        <van-cell-group inset v-if="documents.length > 0">
          <van-cell
            v-for="doc in documents"
            :key="doc.id"
            :title="doc.original_filename || doc.filename"
            is-link
            @click="viewDocumentDetail(doc)"
          >
            <template #icon>
              <van-icon name="file-text-o" size="18" />
            </template>
            <template #label>
              <div class="doc-meta">
                <span class="chunk-count">{{ doc.chunk_count }} {{ $t('knowledgebase.chunks') }}</span>
              </div>
            </template>
            <template #right-icon>
              <van-icon 
                name="delete" 
                color="#ee0a24" 
                size="18" 
                class="delete-icon"
                @click.stop="handleDeleteDocument(doc)"
              />
            </template>
          </van-cell>
        </van-cell-group>

        <div v-else-if="!loadingDocuments" class="empty-state">
          <van-icon name="file-text-o" size="48" color="#ccc" />
          <p>{{ $t('knowledgebase.empty') }}</p>
        </div>

        <van-loading v-if="loadingDocuments" />
      </div>
    </div>

    <van-action-sheet
      v-model:show="showActions"
      :actions="documentActions"
      :title="currentDocument?.original_filename || currentDocument?.filename"
      @select="onActionSelect"
      cancel-text="取消"
    />

    <van-popup v-model:show="showDetail" position="bottom" :style="{ height: '70%' }" round>
      <div class="detail-header">
        <h4>{{ $t('knowledgebase.documentContent') }}</h4>
        <div class="header-actions">
          <van-button
            size="small"
            type="primary"
            plain
            @click="viewDocumentChunks"
          >
            {{ $t('knowledgebase.viewChunks') }}
          </van-button>
          <van-icon name="close" @click="showDetail = false" />
        </div>
      </div>
      <div class="detail-content">
        <van-loading v-if="loadingDetail" />
        <template v-else>
          <div class="detail-meta">
            <span>{{ currentDocument?.chunk_count }} {{ $t('knowledgebase.chunks') }}</span>
          </div>
          <div class="detail-content-full">
            <pre>{{ currentDocument?.content || currentDocument?.preview }}</pre>
          </div>
        </template>
      </div>
    </van-popup>

    <van-popup v-model:show="showChunks" position="bottom" :style="{ height: '70%' }" round>
      <div class="detail-header">
        <h4>{{ $t('knowledgebase.chunkList') }}</h4>
        <van-icon name="close" @click="showChunks = false" />
      </div>
      <div class="detail-content">
        <van-loading v-if="loadingChunks" />
        <template v-else>
          <div class="chunks-header">
            <span>{{ currentDocument?.filename }}</span>
            <span class="chunks-total">{{ totalChunks }} {{ $t('knowledgebase.chunks') }}</span>
          </div>
          <div
            v-for="chunk in chunks"
            :key="chunk.chunk_id"
            class="chunk-item"
          >
            <div class="chunk-index">{{ chunk.index + 1 }}</div>
            <div class="chunk-content">{{ chunk.content }}</div>
          </div>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { showToast, showDialog } from 'vant';
import { useI18n } from 'vue-i18n';
import { useUserStore } from '../store/user';

const router = useRouter();
const { t } = useI18n();
const userStore = useUserStore();

const fileInput = ref(null);
const selectedFiles = ref([]);
const uploading = ref(false);
const uploadProgressList = ref([]);
const uploadComplete = ref(false);
const successCount = ref(0);
const failedCount = ref(0);

const documents = ref([]);
const loadingDocuments = ref(false);
const showDetail = ref(false);
const showChunks = ref(false);
const currentDocument = ref(null);
const loadingDetail = ref(false);
const loadingChunks = ref(false);
const chunks = ref([]);
const totalChunks = ref(0);

const showActions = ref(false);
const documentActions = ref([
  { name: '查看内容', action: 'viewContent' },
  { name: '查看切片', action: 'viewChunks' },
  { name: '删除文档', action: 'deleteDoc', color: '#ee0a24' }
]);

const onClickLeft = () => {
  router.back();
};

const openFilePicker = () => {
  fileInput.value?.click();
};

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files);
  selectedFiles.value = [...selectedFiles.value, ...files];
  event.target.value = '';
};

const handleDrop = (event) => {
  const files = Array.from(event.dataTransfer.files);
  selectedFiles.value = [...selectedFiles.value, ...files];
};

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1);
};

const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const uploadFiles = async () => {
  if (selectedFiles.value.length === 0) {
    showToast(t('knowledgebase.noFiles'));
    return;
  }

  const token = userStore.token;
  if (!token) {
    showToast(t('common.login'));
    router.push('/login');
    return;
  }

  uploading.value = true;
  uploadComplete.value = false;
  uploadProgressList.value = [];
  successCount.value = 0;
  failedCount.value = 0;

  const formData = new FormData();
  selectedFiles.value.forEach((file) => {
    formData.append('files', file);
    uploadProgressList.value.push({
      filename: file.name,
      percentage: 0,
      status: 'processing',
      message: t('knowledgebase.starting')
    });
  });

  try {
    const response = await fetch('http://127.0.0.1:8000/api/vector/add/multiple/stream', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';

      for (const event of events) {
        if (!event.trim()) continue;
        parseEvent(event);
      }
    }
  } catch (error) {
    console.error('Upload error:', error);
    showToast(t('knowledgebase.uploadError'));
    uploadProgressList.value.forEach((item) => {
      if (item.status !== 'completed') {
        item.status = 'failed';
        item.message = t('knowledgebase.uploadError');
      }
    });
    failedCount.value = uploadProgressList.value.filter(p => p.status === 'failed').length;
  } finally {
    uploading.value = false;
    uploadComplete.value = true;
    await fetchDocuments();
    selectedFiles.value = [];
  }
};

const parseEvent = (event) => {
  const lines = event.split('\n');
  let data = '';

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      data = line.substring(6);
    }
  }

  try {
    const eventData = JSON.parse(data);
    const { event_type, filename, message, progress, success_count, failed_count } = eventData;

    if (filename) {
      const index = uploadProgressList.value.findIndex(p => p.filename === filename);
      if (index !== -1) {
        uploadProgressList.value[index].message = message;
        
        if (event_type === 'completed') {
          uploadProgressList.value[index].status = 'completed';
          uploadProgressList.value[index].percentage = 100;
          successCount.value++;
        } else if (event_type === 'processing') {
          uploadProgressList.value[index].status = 'processing';
          if (progress !== undefined) {
            uploadProgressList.value[index].percentage = progress;
          }
        }
      }
    } else if (event_type === 'finish') {
      successCount.value = success_count;
      failedCount.value = failed_count;
    }
  } catch (e) {
    console.error('Parse event error:', e);
  }
};

const fetchDocuments = async () => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingDocuments.value = true;
  try {
    const response = await fetch('http://127.0.0.1:8000/api/vector/list', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        documents.value = result.data.documents || [];
      }
    } else {
      console.error('Failed to fetch documents');
    }
  } catch (error) {
    console.error('Fetch documents error:', error);
  } finally {
    loadingDocuments.value = false;
  }
};

const fetchDocumentDetail = async (filename) => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingDetail.value = true;
  try {
    const response = await fetch(`http://127.0.0.1:8000/api/vector/detail?filename=${encodeURIComponent(filename)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        return result.data;
      }
    } else {
      console.error('Failed to fetch document detail');
    }
  } catch (error) {
    console.error('Fetch document detail error:', error);
  } finally {
    loadingDetail.value = false;
  }
};

const fetchDocumentChunks = async (filename) => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  loadingChunks.value = true;
  chunks.value = [];
  totalChunks.value = 0;
  try {
    const response = await fetch(`http://127.0.0.1:8000/api/vector/chunks?filename=${encodeURIComponent(filename)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200 && result.data) {
        chunks.value = result.data.chunks || [];
        totalChunks.value = result.data.total_chunks || 0;
      }
    } else {
      console.error('Failed to fetch document chunks');
    }
  } catch (error) {
    console.error('Fetch document chunks error:', error);
  } finally {
    loadingChunks.value = false;
  }
};

/** 与列表展示一致：优先 original_filename，否则 filename（后端按文件名删 MD5 与向量文档） */
const deleteDocumentByFilename = async (filename) => {
  const token = userStore.token;
  if (!token || !filename) {
    return false;
  }

  try {
    const qs = new URLSearchParams({
      filename,
      delete_documents: 'true',
    });
    const response = await fetch(
      `http://127.0.0.1:8000/api/vector/delete/filename?${qs.toString()}`,
      {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      }
    );

    if (response.ok) {
      const result = await response.json();
      if (result.code === 200) {
        return true;
      }
    } else {
      console.error('Failed to delete document');
    }
  } catch (error) {
    console.error('Delete document error:', error);
  }
  return false;
};

const handleDeleteDocument = async (doc) => {
  showDialog({
    title: t('common.confirm'),
    message: t('knowledgebase.deleteConfirm', { filename: doc.original_filename || doc.filename }),
    showCancelButton: true,
  }).then(async (result) => {
    if (result) {
      const filename = doc.original_filename || doc.filename;
      const success = await deleteDocumentByFilename(filename);
      if (success) {
        showToast(t('knowledgebase.deleteSuccess'));
        await fetchDocuments();
      } else {
        showToast(t('knowledgebase.deleteFailed'));
      }
    }
  });
};

const cleanAllVectors = async () => {
  const token = userStore.token;
  if (!token) {
    return;
  }

  try {
    const response = await fetch('http://127.0.0.1:8000/api/vector/clean', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/json'
      }
    });

    if (response.ok) {
      showToast(t('knowledgebase.cleanSuccess'));
      await fetchDocuments();
    } else {
      showToast(t('knowledgebase.cleanFailed'));
    }
  } catch (error) {
    console.error('Clean vectors error:', error);
    showToast(t('knowledgebase.cleanFailed'));
  }
};

const handleCleanAll = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('knowledgebase.cleanConfirm'),
    showCancelButton: true,
  }).then(async (action) => {
    if (action === 'confirm') {
      await cleanAllVectors();
    }
  });
};

const viewDocumentDetail = async (doc) => {
  currentDocument.value = doc;
  const detail = await fetchDocumentDetail(doc.filename);
  if (detail) {
    currentDocument.value = detail;
  }
  showDetail.value = true;
};

const viewDocumentChunks = async () => {
  showDetail.value = false;
  showChunks.value = true;
  await fetchDocumentChunks(currentDocument.value.filename);
};

const showDocumentActions = (doc) => {
  currentDocument.value = doc;
  showActions.value = true;
};

const onActionSelect = async (action) => {
  showActions.value = false;
  
  switch (action.action) {
    case 'viewContent':
      const detail = await fetchDocumentDetail(currentDocument.value.filename);
      if (detail) {
        currentDocument.value = detail;
      }
      showDetail.value = true;
      break;
    case 'viewChunks':
      showChunks.value = true;
      await fetchDocumentChunks(currentDocument.value.filename);
      break;
    case 'deleteDoc':
      showToast('删除功能开发中');
      break;
  }
};

const getStatusClass = (status) => {
  switch (status) {
    case 'completed': return 'status-success';
    case 'failed': return 'status-failed';
    default: return 'status-processing';
  }
};

const getStatusText = (status) => {
  switch (status) {
    case 'completed': return t('knowledgebase.completed');
    case 'failed': return t('knowledgebase.failed');
    default: return t('knowledgebase.processing');
  }
};

onMounted(() => {
  fetchDocuments();
});
</script>

<style scoped>
.knowledgebase-container {
  min-height: 100vh;
  background-color: var(--background-color);
  color: var(--text-color);
  padding-top: 46px;
  padding-bottom: 20px;
}

.knowledgebase-content {
  padding: 16px;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: #1989fa;
}

.upload-icon {
  color: #1989fa;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 16px;
  font-weight: bold;
  margin: 0 0 8px;
}

.upload-hint {
  font-size: 12px;
  color: #969799;
  margin: 0;
}

.file-input {
  display: none;
}

.file-list {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: bold;
  margin: 0;
  color: #969799;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.document-count {
  font-size: 12px;
  color: #969799;
}

.document-list {
  margin-top: 20px;
}

.doc-meta {
  font-size: 12px;
  color: #969799;
}

.delete-icon {
  cursor: pointer;
  padding: 8px;
}

.chunk-count {
  margin-right: 16px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #969799;
}

.empty-state p {
  margin: 12px 0 0;
}

.upload-progress {
  margin-top: 20px;
}

.progress-item {
  margin-bottom: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-filename {
  font-size: 14px;
}

.progress-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}

.status-processing {
  background-color: #fff7e6;
  color: #faad14;
}

.status-success {
  background-color: #f6ffed;
  color: #52c41a;
}

.status-failed {
  background-color: #fff2f0;
  color: #ff4d4f;
}

.progress-message {
  font-size: 12px;
  color: #969799;
  margin: 8px 0 0;
}

.upload-result {
  text-align: center;
  padding: 24px;
  margin-top: 20px;
}

.upload-result p {
  margin: 8px 0 0;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #eee;
}

.detail-header h4 {
  margin: 0;
  font-size: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  height: calc(100% - 60px);
}

.detail-meta {
  font-size: 12px;
  color: #969799;
  margin-bottom: 16px;
}

.detail-preview {
  font-size: 14px;
  line-height: 1.6;
  color: #666;
  white-space: pre-wrap;
}

.detail-content-full {
  font-size: 14px;
  line-height: 1.8;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.detail-content-full pre {
  margin: 0;
  padding: 0;
  font-family: inherit;
  font-size: inherit;
}

.chunks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.chunks-total {
  font-size: 12px;
  color: #969799;
}

.chunk-item {
  display: flex;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px dashed #eee;
}

.chunk-item:last-child {
  border-bottom: none;
}

.chunk-index {
  min-width: 28px;
  height: 28px;
  background-color: #1989fa;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  margin-right: 12px;
}

.chunk-content {
  flex: 1;
  font-size: 13px;
  line-height: 1.6;
  color: #666;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
