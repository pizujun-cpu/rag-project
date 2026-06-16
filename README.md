# 万象智识库

企业级 RAG 多模态知识库智能问答系统。基于 LangChain + RAGFlow 架构，支持文本、图片、文档混合输入，提供流式对话体验。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python / FastAPI / Uvicorn |
| LLM 编排 | LangChain / LangChain-OpenAI |
| 知识库引擎 | RAGFlow SDK（多助手动态调度） |
| LLM 模型 | 阿里云 DashScope（Qwen-Plus 文本 + Qwen-VL-Plus 视觉） |
| 多模态 | 图片理解、文档解析（PDF/Word/Excel/TXT）、语音输入/输出 |
| 数据库 | MongoDB（会话记忆持久化） |
| 前端 | Vue 3 + Element Plus + Vite |
| API 设计 | REST + SSE 流式响应 |

## 项目结构

```
├── api/                  # FastAPI 接口层
│   ├── main.py           # 路由定义（聊天、会话管理）
│   └── run_api.py        # 启动入口
├── output/               # 核心业务逻辑
│   └── main_service.py   # 会话管理、流式响应调度
├── Langchain_utils/      # LangChain 处理模块
│   ├── chains.py         # LLM 调用链（文本 + 视觉）
│   ├── intent.py         # 意图分类（知识库查询 / 一般对话）
│   ├── document_parser.py# 文档解析与 RAGFlow 检索
│   ├── memory.py         # MongoDB 会话记忆
│   ├── processor.py      # 流水线整合
│   └── config.py         # 配置管理
├── RAGFlow_mcp/          # RAGFlow MCP 集成
├── RAGFlow_utils/        # RAGFlow 工具函数
├── ui/                   # Vue 3 前端
│   ├── src/
│   │   ├── App.vue
│   │   └── components/
│   └── package.json
├── requirements.txt
└── resume_prompt.txt
```

## 问答管线

```
用户输入（文本/图片/文档）
  → 意图识别（知识库查询 / 一般对话）
  → 查询增强
  → RAGFlow 知识库检索
  → LLM 生成（文本模型 / 视觉模型）
  → SSE 流式输出
```

## 快速开始

### 环境要求

- Python 3.10+
- MongoDB（会话记忆）
- Node.js 18+（前端）

### 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制 .env 并填入实际密钥）
cp .env.example .env

# 启动 API 服务
cd api
python run_api.py
```

服务运行在 `http://localhost:8000`

### 前端

```bash
cd ui
npm install
npm run dev
```

### 环境变量

参考 `.env.example` 创建 `.env`：

```ini
# RAGFlow 服务
RAGFLOW_API_URL=<your-ragflow-url>
RAGFLOW_API_KEY=<your-ragflow-key>

# DashScope LLM
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=<your-dashscope-key>
LLM_QWEN2.5=qwen-plus
LLM_VISION=qwen-vl-plus
```