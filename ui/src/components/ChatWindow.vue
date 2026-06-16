<template>
  <div class="app-layout">
    <div class="sidebar">
      <div class="logo-section">
        <img src="@/assets/logo.png" alt="知识助手" width="120" height="120" />
        <span class="logo-text">知识助手</span>
      </div>
      <el-button class="new-chat-button" @click="newChat">
        <i class="fa-solid fa-plus"></i>
        &nbsp;新会话
      </el-button>
    </div>
    <div class="main-content">
      <div class="chat-header">
        <h2>万象智识库</h2>
        <span class="chat-description">基于企业知识库的智能问答系统</span>
      </div>
      <div class="chat-container">
        <div class="message-list" ref="messaggListRef">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="
              message.isUser ? 'message user-message' : 'message bot-message'
            "
          >
            <!-- 会话图标 -->
            <div
              :class="
                message.isUser
                  ? 'fa-solid fa-user message-icon'
                  : 'fa-solid fa-database message-icon'
              "
            ></div>
            <!-- 会话内容 -->
            <div class="message-content">
              <div class="message-body">
                <!-- 图片展示 -->
                <div v-if="message.images && message.images.length > 0" class="message-images">
                  <img
                    v-for="(img, idx) in message.images"
                    :key="idx"
                    :src="img.previewUrl"
                    class="message-image-thumb"
                    @click="previewImage(img.previewUrl)"
                  />
                </div>
                <!-- 文档展示 -->
                <div v-if="message.documents && message.documents.length > 0" class="message-documents">
                  <div v-for="(doc, idx) in message.documents" :key="idx" class="message-doc-card">
                    <i :class="docIcon(doc.filename)"></i>
                    <span class="doc-filename">{{ doc.filename }}</span>
                  </div>
                </div>
                <span v-html="convertStreamOutput(message.content)"></span>
                <!-- loading -->
                <span
                  class="loading-dots"
                  v-if="message.isThinking || message.isTyping"
                >
                  <span class="dot"></span>
                  <span class="dot"></span>
                  <span class="dot"></span>
                </span>
                <!-- TTS 播放按钮（仅机器人消息） -->
                <span
                  v-if="!message.isUser && !message.isTyping && !message.isThinking && message.content"
                  class="tts-btn"
                  @click="playTTS(message)"
                  :title="message.ttsPlaying ? '播放中...' : '朗读回答'"
                >
                  <i :class="message.ttsPlaying ? 'fa-solid fa-volume-high tts-playing' : 'fa-solid fa-volume-high'"></i>
                </span>
              </div>
            </div>
          </div>
        </div>
        <div
          class="input-container"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
          :class="{ 'drag-over': isDragOver }"
        >
          <!-- 图片和文档预览区 -->
          <div v-if="uploadedImages.length > 0 || uploadedDocuments.length > 0" class="preview-area">
            <div
              v-for="(img, index) in uploadedImages"
              :key="'img-'+index"
              class="image-preview-item"
            >
              <img :src="img.previewUrl" class="preview-thumb" />
              <span class="preview-remove" @click="removeImage(index)">
                <i class="fa-solid fa-xmark"></i>
              </span>
            </div>
            <div
              v-for="(doc, index) in uploadedDocuments"
              :key="'doc-'+index"
              class="doc-preview-tag"
            >
              <i :class="docIcon(doc.filename)"></i>
              <span class="doc-tag-name">{{ doc.filename }}</span>
              <span class="preview-remove" @click="removeDocument(index)">
                <i class="fa-solid fa-xmark"></i>
              </span>
            </div>
          </div>
          <el-input
            v-model="inputMessage"
            placeholder="请输入消息，支持图片/文档/语音"
            @keyup.enter="sendMessage"
            @paste="onPaste"
          ></el-input>
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            multiple
            style="display:none"
            @change="onFileSelect"
          />
          <input
            ref="docInputRef"
            type="file"
            accept=".pdf,.docx,.xlsx,.txt"
            multiple
            style="display:none"
            @change="onDocFileSelect"
          />
          <el-button class="upload-btn" @click="triggerUpload" :disabled="isSending" title="上传图片">
            <i class="fa-regular fa-image"></i>
          </el-button>
          <el-button class="upload-btn" @click="triggerDocUpload" :disabled="isSending" title="上传文档">
            <i class="fa-solid fa-paperclip"></i>
          </el-button>
          <el-button
            class="upload-btn mic-btn"
            :class="{ 'mic-recording': isRecording }"
            @click="toggleRecording"
            :disabled="isSending"
            title="语音输入"
          >
            <i :class="isRecording ? 'fa-solid fa-microphone' : 'fa-solid fa-microphone'"></i>
          </el-button>
          <el-button @click="sendMessage" :disabled="isSending" type="primary"
            >发送</el-button
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { v4 as uuidv4 } from 'uuid'

const API_BASE = 'http://localhost:8000'

const messaggListRef = ref()
const isSending = ref(false)
const uuid = ref()
const inputMessage = ref('')
const messages = ref([])
const useStreamResponse = ref(true)
const uploadedImages = ref([])
const uploadedDocuments = ref([])
const fileInputRef = ref(null)
const docInputRef = ref(null)
const isDragOver = ref(false)
const isRecording = ref(false)

onMounted(() => {
  // 每次页面加载时创建新会话
  createNewSession()

  // 移除 setInterval，改用手动滚动
  watch(messages, () => scrollToBottom(), { deep: true })
})

const scrollToBottom = () => {
  if (messaggListRef.value) {
    messaggListRef.value.scrollTop = messaggListRef.value.scrollHeight
  }
}

const hello = () => {
  // 修改欢迎消息
  const welcomeMsg = {
    isUser: false,
    content: '你好，我是企业知识库管理系统，你可以向我提问来获取知识库中的相关信息',
    isTyping: false,
    isThinking: false,
  }
  messages.value.push(welcomeMsg)
}

const sendMessage = () => {
  if (inputMessage.value.trim()) {
    sendRequest(inputMessage.value.trim())
    inputMessage.value = ''
  }
}

const sendRequest = (message) => {
  isSending.value = true

  const imagesForSend = uploadedImages.value.map(img => ({
    base64: img.base64,
    mime_type: img.mimeType
  }))

  const documentsForSend = uploadedDocuments.value.map(doc => ({
    base64: doc.base64,
    filename: doc.filename,
    mime_type: doc.mimeType
  }))

  const userMsg = {
    isUser: true,
    content: message,
    isTyping: false,
    isThinking: false,
    images: uploadedImages.value.length > 0
      ? uploadedImages.value.map(img => ({ previewUrl: img.previewUrl }))
      : undefined,
    documents: uploadedDocuments.value.length > 0
      ? uploadedDocuments.value.map(doc => ({ filename: doc.filename }))
      : undefined
  }
  if(messages.value.length > 0){
    messages.value.push(userMsg)
  }

  const botMsg = {
    isUser: false,
    content: '',
    isTyping: true,
    isThinking: false,
  }
  messages.value.push(botMsg)
  const lastMsg = messages.value[messages.value.length - 1]
  scrollToBottom()

  const hasImages = imagesForSend.length > 0
  const hasDocs = documentsForSend.length > 0

  if (useStreamResponse.value) {
    sendStreamRequest(message, lastMsg, imagesForSend, documentsForSend)
  } else {
    sendNormalRequest(message, lastMsg, imagesForSend, documentsForSend)
  }

  uploadedImages.value = []
  uploadedDocuments.value = []
}

// 普通响应请求
const sendNormalRequest = (message, lastMsg, images, documents) => {
  axios
    .post(
      `${API_BASE}/api/chat`,
      {
        question: message,
        session_id: String(uuid.value),
        images: images.length > 0 ? images : undefined,
        documents: documents.length > 0 ? documents : undefined
      }
    )
    .then((response) => {
      if (response && response.data && response.data.answer) {
        lastMsg.content = response.data.answer;
      }
      lastMsg.isTyping = false;
      isSending.value = false;
      scrollToBottom();
    })
    .catch((error) => {
      console.error('请求错误:', error);
      lastMsg.content = '请求失败，请重试';
      lastMsg.isTyping = false;
      isSending.value = false;
    });
}

// 流式响应请求
const sendStreamRequest = async (message, lastMsg, images, documents) => {
  const hasImages = images && images.length > 0
  const hasDocs = documents && documents.length > 0

  if (hasImages || hasDocs) {
    // 有图片或文档时使用 fetch POST + ReadableStream 实现 SSE
    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: message,
          session_id: String(uuid.value),
          images: hasImages ? images : undefined,
          documents: hasDocs ? documents : undefined
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'content') {
                lastMsg.content += data.data
                scrollToBottom()
              } else if (data.type === 'end') {
                lastMsg.isTyping = false
                isSending.value = false
              } else if (data.type === 'error') {
                lastMsg.content = '请求出错: ' + (data.data.message || '未知错误')
                lastMsg.isTyping = false
                isSending.value = false
              }
            } catch (e) {
              // parse error, skip
            }
          }
        }
      }
    } catch (error) {
      console.error('流式请求失败:', error)
      lastMsg.content = '处理失败: ' + (error.message || error.toString())
      lastMsg.isTyping = false
      isSending.value = false
    }
    return
  }

  // 无图片时保持原有 EventSource GET 方式
  const url = `${API_BASE}/api/chat/stream?question=${encodeURIComponent(message)}&session_id=${uuid.value}`;

  console.log('发送流式请求:', {
    url,
    session_id: uuid.value,
    question: message
  });

  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === 'metadata') {
        console.log('收到元数据:', data.data);
      }
      else if (data.type === 'content') {
        lastMsg.content += data.data;
        scrollToBottom();
      }
      else if (data.type === 'end') {
        lastMsg.isTyping = false;
        isSending.value = false;
        eventSource.close();
      }
      else if (data.type === 'error') {
        console.error('流式响应错误:', data.data);
        lastMsg.content = '请求出错: ' + (data.data.message || '未知错误');
        lastMsg.isTyping = false;
        isSending.value = false;
        eventSource.close();
      }
    } catch (error) {
      console.error('解析事件数据失败:', error, event.data);
      if (event.data.trim()) {
        lastMsg.content += event.data;
        scrollToBottom();
      }
    }
  };

  eventSource.onerror = (error) => {
    console.error('EventSource 错误:', error);
    lastMsg.content = '正在思考中，请稍候...';
    lastMsg.isTyping = false;
    isSending.value = false;
    eventSource.close();

    console.log('流式请求失败，尝试普通请求');
    sendNormalRequest(message, lastMsg, [], []);
  };
}

// ========== 图片处理函数 ==========

const triggerUpload = () => {
  fileInputRef.value?.click()
}

const fileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      // reader.result 格式: "data:image/png;base64,xxxx"
      const dataUrl = reader.result
      const commaIdx = dataUrl.indexOf(',')
      const mimeType = dataUrl.substring(5, dataUrl.indexOf(';'))
      const base64 = dataUrl.substring(commaIdx + 1)
      resolve({ base64, mimeType, previewUrl: dataUrl })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const addImages = async (files) => {
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    try {
      const imgData = await fileToBase64(file)
      uploadedImages.value.push(imgData)
    } catch (e) {
      console.error('图片读取失败:', e)
    }
  }
}

const onFileSelect = (event) => {
  const files = event.target.files
  if (files && files.length > 0) {
    addImages(files)
  }
  // 重置 input 以便重复选择同一文件
  event.target.value = ''
}

const onPaste = (event) => {
  const items = event.clipboardData?.items
  if (!items) return
  const imageFiles = []
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      imageFiles.push(item.getAsFile())
    }
  }
  if (imageFiles.length > 0) {
    addImages(imageFiles)
  }
}

const onDragOver = () => {
  isDragOver.value = true
}

const onDragLeave = () => {
  isDragOver.value = false
}

const onDrop = (event) => {
  isDragOver.value = false
  const files = event.dataTransfer?.files
  if (!files || files.length === 0) return
  const imgFiles = []
  const docFiles = []
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      imgFiles.push(file)
    } else {
      docFiles.push(file)
    }
  }
  if (imgFiles.length > 0) addImages(imgFiles)
  if (docFiles.length > 0) addDocuments(docFiles)
}

const removeImage = (index) => {
  uploadedImages.value.splice(index, 1)
}

const previewImage = (url) => {
  window.open(url, '_blank')
}

// ========== 文档处理函数 ==========

const docIcon = (filename) => {
  const ext = (filename || '').split('.').pop()?.toLowerCase()
  const icons = {
    pdf: 'fa-solid fa-file-pdf',
    docx: 'fa-solid fa-file-word',
    doc: 'fa-solid fa-file-word',
    xlsx: 'fa-solid fa-file-excel',
    xls: 'fa-solid fa-file-excel',
    txt: 'fa-solid fa-file-lines'
  }
  return icons[ext] || 'fa-solid fa-file'
}

const triggerDocUpload = () => {
  docInputRef.value?.click()
}

const docFileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result
      const commaIdx = dataUrl.indexOf(',')
      resolve({
        base64: dataUrl.substring(commaIdx + 1),
        mimeType: file.type || 'application/octet-stream',
        filename: file.name,
        previewUrl: dataUrl
      })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

const addDocuments = async (files) => {
  for (const file of files) {
    try {
      const docData = await docFileToBase64(file)
      uploadedDocuments.value.push(docData)
    } catch (e) {
      console.error('文档读取失败:', e)
    }
  }
}

const onDocFileSelect = (event) => {
  const files = event.target.files
  if (files && files.length > 0) {
    addDocuments(files)
  }
  event.target.value = ''
}

const removeDocument = (index) => {
  uploadedDocuments.value.splice(index, 1)
}

// ========== 语音输入函数 ==========

const toggleRecording = async () => {
  if (isRecording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

const startRecording = async () => {
  // 使用浏览器原生 SpeechRecognition（Chrome/Edge/Android 支持，实时免费）
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (SpeechRecognition) {
    startWebSpeechRecognition(SpeechRecognition)
    return
  }

  // 不支持 SpeechRecognition 的浏览器（Firefox/Safari）
  alert('您的浏览器不支持语音输入，请使用 Chrome 或 Edge 浏览器，或手动输入文字。')
}

const startWebSpeechRecognition = (SpeechRecognition) => {
  const recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.continuous = true

  let finalText = ''

  recognition.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        finalText += event.results[i][0].transcript
      } else {
        interim += event.results[i][0].transcript
      }
    }
    // 实时显示识别结果
    inputMessage.value = finalText + interim
  }

  recognition.onerror = (event) => {
    console.error('语音识别错误:', event.error)
    if (event.error === 'not-allowed') {
      alert('请允许麦克风权限后重试')
    }
    isRecording.value = false
  }

  recognition.onend = () => {
    isRecording.value = false
    inputMessage.value = finalText || inputMessage.value
  }

  recognition.start()
  isRecording.value = true

  // 15秒超时
  setTimeout(() => {
    if (isRecording.value) {
      recognition.stop()
    }
  }, 15000)
}

const stopRecording = () => {
  isRecording.value = false
}

// ========== TTS 语音输出函数（使用浏览器原生 speechSynthesis）==========

const playTTS = (message) => {
  if (message.ttsPlaying) return

  const synth = window.speechSynthesis

  // 如果正在播放，停止
  if (synth.speaking) {
    synth.cancel()
    message.ttsPlaying = false
    return
  }

  // 清理文本中的 HTML 标签
  const text = message.content.replace(/<[^>]*>/g, '').substring(0, 500)

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  utterance.pitch = 1.0

  utterance.onstart = () => { message.ttsPlaying = true }
  utterance.onend = () => { message.ttsPlaying = false }
  utterance.onerror = () => { message.ttsPlaying = false }

  message.ttsPlaying = true
  synth.speak(utterance)
}

// 初始化 UUID
const initUUID = () => {
  let storedUUID = localStorage.getItem('user_uuid')
  if (!storedUUID) {
    storedUUID = uuidToNumber(uuidv4())
    localStorage.setItem('user_uuid', storedUUID)
  }
  uuid.value = storedUUID
}

const uuidToNumber = (uuid) => {
  let number = 0
  for (let i = 0; i < uuid.length && i < 6; i++) {
    const hexValue = uuid[i]
    number = number * 16 + (parseInt(hexValue, 16) || 0)
  }
  return number % 1000000
}

// 转换特殊字符
const convertStreamOutput = (output) => {
  return output
    .replace(/\n/g, '<br>')
    .replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')
    .replace(/&/g, '&amp;') // 新增转义，避免 HTML 注入
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const newChat = () => {
  console.log('开始新会话');

  // 如果有已存在的会话ID，先清除其记忆
  if (uuid.value) {
    axios.post(`${API_BASE}/api/memory/clear`, {
      session_id: String(uuid.value)
    }).catch(error => {
      console.error('清除记忆失败:', error);
    });
  }

  // 生成新的会话ID
  const newUUID = uuidToNumber(uuidv4());
  localStorage.setItem('user_uuid', newUUID);
  uuid.value = newUUID;

  // 清空消息列表
  messages.value = [];

  // 重新发送欢迎消息
  hello();
}

// 创建新会话
const createNewSession = () => {
  // 生成新的会话ID
  const newUUID = uuidToNumber(uuidv4())
  localStorage.setItem('user_uuid', newUUID)
  uuid.value = newUUID

  // 清空消息列表
  messages.value = []

  // 发送欢迎消息
  hello()
}

</script>
<style scoped>
/* ========================================
   整体布局
   ======================================== */
.app-layout {
  display: flex;
  height: 100vh;
  font-family: var(--font-family);
  background-color: var(--color-bg-page);
  color: var(--color-text-primary);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.6;

}

/* 品牌色文本选中 */
::selection {
  background: rgba(22, 119, 255, 0.15);
  color: var(--color-text-primary);
}

/* 键盘焦点可见 — 无障碍 */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: 2px;
}

/* 减弱动画 — 无障碍 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* ========================================
   左侧边栏
   ======================================== */
.sidebar {
  width: 200px;
  background-color: var(--color-sidebar-bg);
  padding: var(--space-xl);
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 1px 0 8px rgba(0, 0, 0, 0.04);
  transition: width var(--transition-normal);
  flex-shrink: 0;
  position: relative;
}

/* 侧边栏顶部品牌色装饰线 */
.sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-hover));
}

.logo-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
}

.logo-section img {
  border-radius: var(--radius-md);
  box-shadow: var(--color-shadow-md);
  transition: transform var(--transition-normal);
}

.logo-section img:hover {
  transform: scale(1.04);
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  margin-top: var(--space-md);
  color: var(--color-text-primary);
  text-align: center;
  letter-spacing: 0.5px;
}

.new-chat-button {
  width: 100%;
  margin-top: auto;
  background-color: var(--color-primary) !important;
  border: none !important;
  color: #FFFFFF !important;
  height: 44px;
  font-size: 15px;
  font-weight: 500;
  border-radius: var(--radius-sm) !important;
  box-shadow: var(--color-shadow-sm);
  transition: all var(--transition-fast) !important;
}

.new-chat-button:hover {
  background-color: var(--color-primary-hover) !important;
  box-shadow: var(--color-shadow-md);
  transform: translateY(-1px);
}

.new-chat-button:active {
  background-color: var(--color-primary-active) !important;
  transform: translateY(0);
}

/* ========================================
   右侧主内容区
   ======================================== */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--color-bg-page);
}

/* ========================================
   顶部标题栏
   ======================================== */
.chat-header {
  padding: var(--space-md) var(--space-xl);
  background-color: var(--color-bg-white);
  box-shadow: var(--color-shadow-sm);
  flex-shrink: 0;
  z-index: 10;
}

.chat-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: 0.5px;
}

.chat-description {
  display: inline-block;
  margin-top: 4px;
  color: var(--color-text-hint);
  font-size: 13px;
  font-weight: 400;
}

/* ========================================
   聊天容器
   ======================================== */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  max-width: 900px;
  width: 100%;
  margin: 0 auto;
}

/* ========================================
   消息列表
   ======================================== */
.message-list {
  flex: 1;
  padding: var(--space-lg) var(--space-xl);
  overflow-y: auto;
  scroll-behavior: smooth;
}

.message-list::-webkit-scrollbar {
  width: 5px;
}

.message-list::-webkit-scrollbar-track {
  background: transparent;
}

.message-list::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 10px;
}

.message-list::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.20);
}

/* ========================================
   单条消息
   ======================================== */
.message {
  display: flex;
  margin-bottom: var(--space-lg);
  max-width: 80%;
  align-items: flex-start;
  animation: messageIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========================================
   消息图标
   ======================================== */
.message-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-right: var(--space-sm);
  flex-shrink: 0;
  box-shadow: var(--color-shadow-sm);
}

/* ========================================
   消息内容区
   ======================================== */
.message-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.message-body {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  line-height: 1.65;
  font-size: 14px;
  font-weight: 400;
  position: relative;
  word-break: break-word;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.message:hover .message-body {
  transform: translateY(-1px);
}

/* ========================================
   用户消息（右侧）
   ======================================== */
.user-message {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.user-message .message-icon {
  margin-right: 0;
  margin-left: var(--space-sm);
  background-color: var(--color-primary-light);
  color: var(--color-primary);
}

.user-message .message-body {
  background-color: var(--color-primary);
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(22, 119, 255, 0.25);
  border-radius: var(--radius-md) 4px var(--radius-md) var(--radius-md);
}

.user-message:hover .message-body {
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.35);
}

/* ========================================
   机器人消息（左侧）
   ======================================== */
.bot-message {
  align-self: flex-start;
}

.bot-message .message-icon {
  background-color: var(--color-bg-gray);
  color: var(--color-text-secondary);
}

.bot-message .message-body {
  background-color: var(--color-bg-white);
  color: var(--color-text-primary);
  box-shadow: var(--color-shadow-sm);
  border-radius: 4px var(--radius-md) var(--radius-md) var(--radius-md);
}

.bot-message:hover .message-body {
  box-shadow: var(--color-shadow-md);
}

/* ========================================
   Loading 动画
   ======================================== */
.loading-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 4px;
  vertical-align: middle;
}

.loading-dots .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background-color: var(--color-text-hint);
  border-radius: 50%;
  animation: loadingBounce 1.4s ease-in-out infinite both;
}

.loading-dots .dot:nth-child(2) {
  animation-delay: 0.16s;
}

.loading-dots .dot:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes loadingBounce {
  0%, 80%, 100% {
    opacity: 0.2;
    transform: scale(0.75);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

/* ========================================
   底部输入区
   ======================================== */
.input-container {
  padding: var(--space-md) var(--space-xl);
  background-color: var(--color-bg-white);
  border-top: 1px solid rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-shrink: 0;
  position: relative;
  z-index: 5;
}

.input-container .el-input {
  flex: 1;
}

/* 输入框深度样式覆盖 */
:deep(.input-container .el-input__wrapper) {
  height: 44px;
  border-radius: var(--radius-sm);
  background-color: var(--color-bg-gray);
  box-shadow: none;
  border: 2px solid transparent;
  transition: all var(--transition-fast);
  padding: 0 var(--space-md);
}

:deep(.input-container .el-input__wrapper:hover) {
  background-color: #EBEDF0;
}

:deep(.input-container .el-input__wrapper.is-focus) {
  background-color: var(--color-bg-white);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.10);
}

:deep(.input-container .el-input__inner) {
  font-size: 14px;
  font-family: var(--font-family);
  color: var(--color-text-primary);
}

:deep(.input-container .el-input__inner::placeholder) {
  color: var(--color-text-hint);
}

/* 发送按钮深度样式覆盖 */
:deep(.input-container .el-button--primary) {
  height: 44px;
  min-width: 72px;
  font-size: 15px;
  font-weight: 500;
  background-color: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: var(--color-shadow-sm);
  transition: all var(--transition-fast);
}

:deep(.input-container .el-button--primary:hover) {
  background-color: var(--color-primary-hover);
  box-shadow: var(--color-shadow-md);
  transform: translateY(-1px);
}

:deep(.input-container .el-button--primary:active) {
  background-color: var(--color-primary-active);
  transform: translateY(0);
}

:deep(.input-container .el-button--primary.is-disabled) {
  background-color: #A0C4FF;
  box-shadow: none;
  transform: none;
}

/* ========================================
   图片和文档预览区
   ======================================== */
.preview-area {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
  align-items: center;
}

.image-preview-item {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.preview-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.doc-preview-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-bg-gray);
  border-radius: 20px;
  font-size: 13px;
  color: var(--color-text-primary);
  position: relative;
}

.doc-tag-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-remove {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 18px;
  height: 18px;
  background: rgba(0, 0, 0, 0.55);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.doc-preview-tag .preview-remove {
  position: relative;
  top: auto;
  right: auto;
  width: 16px;
  height: 16px;
  font-size: 9px;
  margin-left: 2px;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.3);
}

.preview-remove:hover {
  background: rgba(0, 0, 0, 0.8);
}

.doc-preview-tag .preview-remove:hover {
  background: rgba(0, 0, 0, 0.55);
}

/* ========================================
   消息中图片展示
   ======================================== */
.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.message-image-thumb {
  max-width: 200px;
  max-height: 160px;
  border-radius: 6px;
  cursor: pointer;
  object-fit: cover;
  transition: transform 0.2s;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.message-image-thumb:hover {
  transform: scale(1.03);
}

/* ========================================
   上传按钮
   ======================================== */
.upload-btn {
  width: 44px;
  height: 44px;
  padding: 0 !important;
  font-size: 18px;
  color: var(--color-text-hint);
  transition: color 0.2s;
}

.upload-btn:hover {
  color: var(--color-primary);
}

/* ========================================
   消息中文档展示
   ======================================== */
.message-documents {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.message-doc-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  font-size: 12px;
}

.bot-message .message-doc-card {
  background: var(--color-bg-gray);
}

.doc-filename {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========================================
   TTS 播放按钮
   ======================================== */
.tts-btn {
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
  cursor: pointer;
  color: var(--color-text-hint);
  font-size: 14px;
  transition: color 0.2s;
  vertical-align: middle;
}

.tts-btn:hover {
  color: var(--color-primary);
}

.tts-btn .tts-playing {
  color: var(--color-primary);
  animation: ttsPulse 0.8s ease-in-out infinite;
}

@keyframes ttsPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ========================================
   麦克风按钮
   ======================================== */
.mic-btn.mic-recording {
  color: #e74c3c !important;
  animation: micPulse 1.2s ease-in-out infinite;
}

@keyframes micPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.25); }
}

/* ========================================
   拖拽状态
   ======================================== */
.input-container.drag-over {
  background-color: rgba(22, 119, 255, 0.04);
  border-radius: var(--radius-sm);
  box-shadow: inset 0 0 0 2px var(--color-primary);
}

/* ========================================
   移动端响应式
   ======================================== */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-sm) var(--space-md);
    box-shadow: var(--color-shadow-sm);
  }

  .logo-section {
    flex-direction: row;
    align-items: center;
    margin-bottom: 0;
    gap: var(--space-sm);
  }

  .logo-section img {
    width: 36px;
    height: 36px;
  }

  .logo-text {
    font-size: 16px;
    margin-top: 0;
  }

  .new-chat-button {
    margin-top: 0;
    width: auto;
    padding: 0 var(--space-md);
  }

  .main-content {
    padding: 0;
  }

  .chat-header {
    padding: var(--space-sm) var(--space-md);
  }

  .chat-header h2 {
    font-size: 18px;
  }

  .message-list {
    padding: var(--space-md);
  }

  .message {
    max-width: 90%;
  }

  .input-container {
    padding: var(--space-sm) var(--space-md);
  }
}

/* 平板响应式 */
@media (min-width: 769px) and (max-width: 1024px) {
  .sidebar {
    width: 180px;
    padding: var(--space-md);
  }

  .message {
    max-width: 85%;
  }
}
</style>
