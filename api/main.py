"""
万象智识库 API 服务

这是一个精简的FastAPI接口，用于连接前端和后端服务。
提供聊天和会话管理功能。
"""
import os
import sys
import json
from typing import Dict, Optional, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 将项目根目录添加到Python路径中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入主服务模块
from output.main_service import get_response, clear_session_memory

# 创建FastAPI应用
app = FastAPI(
    title="万象智识库 API",
    description="企业知识库智能问答系统API",
    version="1.0.0"
)

# 添加CORS中间件，允许前端跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 图片大小限制: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024
# 文档大小限制: 20MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024
# 允许的文档格式
ALLOWED_DOC_TYPES = {'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'text/plain'}


def validate_images(images: list) -> None:
    """验证图片数据，超过大小限制抛出异常"""
    if not images:
        return
    for i, img in enumerate(images):
        if "base64" not in img:
            raise HTTPException(status_code=400, detail=f"第{i+1}张图片缺少 base64 字段")
        size_bytes = len(img["base64"]) * 3 / 4
        if size_bytes > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"第{i+1}张图片大小超过限制（最大10MB，当前{size_bytes/1024/1024:.1f}MB）"
            )


def validate_documents(documents: list) -> None:
    """验证文档数据"""
    if not documents:
        return
    for i, doc in enumerate(documents):
        if "base64" not in doc:
            raise HTTPException(status_code=400, detail=f"第{i+1}个文档缺少 base64 字段")
        if "filename" not in doc:
            raise HTTPException(status_code=400, detail=f"第{i+1}个文档缺少 filename 字段")
        mime = doc.get("mime_type", "")
        if mime not in ALLOWED_DOC_TYPES:
            raise HTTPException(status_code=400, detail=f"第{i+1}个文档格式不支持: {mime}，支持: pdf/docx/xlsx/txt")
        size_bytes = len(doc["base64"]) * 3 / 4
        if size_bytes > MAX_DOCUMENT_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"第{i+1}个文档大小超过限制（最大20MB，当前{size_bytes/1024/1024:.1f}MB）"
            )


# 请求模型
class ChatRequest(BaseModel):
    question: str
    session_id: str
    images: Optional[list] = None
    documents: Optional[list] = None

class ClearMemoryRequest(BaseModel):
    session_id: str

class SpeechRequest(BaseModel):
    text: str
    format: str = "mp3"

class TranscribeRequest(BaseModel):
    audio: str  # base64 编码的音频数据

# API路由
@app.get("/")
async def root():
    """API状态检查"""
    return {"status": "online", "message": "万象智识库API服务正常运行"}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """处理聊天请求，返回完整回答"""
    try:
        validate_images(request.images)
        validate_documents(request.documents)

        full_answer = ""
        metadata = {}

        async for chunk in get_response(request.question, request.session_id, request.images, request.documents):
            if chunk["type"] == "content":
                full_answer += chunk["data"]
            elif chunk["type"] == "metadata":
                metadata = chunk["data"]
            elif chunk["type"] == "end" and "metadata" in chunk["data"]:
                metadata.update(chunk["data"]["metadata"])

        return {
            "answer": full_answer,
            "metadata": metadata
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")

@app.get("/api/chat/stream")
async def chat_stream_get(question: str, session_id: str):
    """处理流式聊天请求(GET)，返回SSE流，支持纯文本（向后兼容）"""

    async def generate_stream():
        try:
            async for chunk in get_response(question, session_id):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )

@app.post("/api/chat/stream")
async def chat_stream_post(request: ChatRequest):
    """处理流式聊天请求(POST)，返回SSE流，支持图片和文档"""

    async def generate_stream():
        try:
            validate_images(request.images)
            validate_documents(request.documents)
            async for chunk in get_response(request.question, request.session_id, request.images, request.documents):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )

@app.post("/api/memory/clear")
async def clear_memory(request: ClearMemoryRequest):
    """清除指定会话的记忆"""
    try:
        clear_session_memory(request.session_id)
        return {"status": "success", "message": f"会话 {request.session_id} 的记忆已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除记忆时出错: {str(e)}")

@app.post("/api/speech/synthesize")
async def speech_synthesize(request: SpeechRequest):
    """文字转语音，调用 DashScope TTS API（OpenAI 兼容接口）"""
    if len(request.text) > 1000:
        raise HTTPException(status_code=400, detail="文本过长，最大1000字符")

    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_BASE_URL")

        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

        response = client.audio.speech.create(
            model="qwen-tts",
            voice="Cherry",
            input=request.text,
            response_format=request.format,
            extra_body={"enable_enhance": True}
        )

        return StreamingResponse(
            response.iter_bytes(),
            media_type=f"audio/{request.format}",
            headers={"Content-Disposition": "inline"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@app.post("/api/speech/transcribe")
async def speech_transcribe(request: TranscribeRequest):
    """语音转文字 — 同步短音频识别（浏览器不支持 Web Speech API 时的回退方案）"""
    try:
        import dashscope
        from dashscope.audio.asr import Recognition
        import io
        import base64 as b64

        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

        audio_bytes = b64.b64decode(request.audio)

        # 使用同步识别 API（适合 60 秒以内的短音频）
        response = Recognition.call(
            model="paraformer-realtime-v2",
            format="webm",
            sample_rate=16000,
            file=io.BytesIO(audio_bytes)
        )

        if response.status_code == 200:
            output = response.output
            if output and "sentence" in output:
                sentences = output["sentence"]
                if isinstance(sentences, list):
                    text = "".join(s.get("text", "") for s in sentences)
                elif isinstance(sentences, dict):
                    text = sentences.get("text", "")
                else:
                    text = str(sentences)
            elif output and "text" in output:
                text = output["text"]
            else:
                text = str(output) if output else ""
            return {"text": text.strip() if text else "[未识别到语音内容]", "status": "success"}
        else:
            return {"text": f"识别失败: {response.message}", "status": "error"}

    except ImportError:
        raise HTTPException(status_code=500, detail="语音识别服务未安装")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音识别失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 