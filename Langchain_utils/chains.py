"""
处理链模块

提供不同类型的处理链：
1. 知识库查询链 - 使用知识库回答问题
2. 一般对话链 - 使用模型直接回答问题
"""

from typing import Dict, Any, Callable,AsyncGenerator
import os
import sys
import logging
import base64
from dotenv import load_dotenv
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# 导入RAGFlow_mcp模块
from RAGFlow_mcp.chat import RAGFlow_chat

# 导入查询增强模块
from RAGFlow_utils.query_enhancer import enhance_query

# 导入文档解析模块
from .document_parser import parse_document

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

async def call_llm(question: str, prompt: str) -> AsyncGenerator[str, None]:
    """
    调用大模型进行回答

    Args:
        question: 用户问题
        prompt: 完整提示词

    Returns:
        str: 模型回答的字符串内容
    """
    logger.info(f"调用LLM处理问题: {question[:50]}...")

    try:
        #模型信息配置
        api_key = os.getenv("DASHSCOPE_API_KEY")
        model = os.getenv("LLM_QWEN2.5")
        base_url = os.getenv("DASHSCOPE_BASE_URL")

        #创建LanChain的ChatOpenAI模型
        llm = ChatOpenAI(
            model = model,
            base_url = base_url,
            api_key = api_key,
            streaming = True  #启动流失输出
        )

        #创建提示词模板
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ('system',prompt),
                ('human',question)
            ]
        )

        #构建链
        chain = chat_prompt | llm

        #使用astream进行异步流失调用
        async for chunk in chain.astream({}):
            if hasattr(chunk,'content') and chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"调用LLM出错：{str(e)}")
        yield f"回答生成失败：{str(e)}"


async def call_multimodal_llm(question: str, prompt: str, images: list = None) -> AsyncGenerator[str, None]:
    """
    调用多模态大模型进行回答，支持图片输入

    当有图片时使用 AsyncOpenAI 原生客户端构建多模态消息，
    因为 LangChain 的 ChatPromptTemplate 对 HumanMessage(content=[...]) 列表格式兼容性不足。

    Args:
        question: 用户问题
        prompt: 完整提示词
        images: 图片列表，每项为 {"base64": "...", "mime_type": "image/png"}

    Returns:
        AsyncGenerator: 流式输出的字符串内容
    """
    logger.info(f"调用多模态LLM处理问题: {question[:50]}..., 图片数量: {len(images) if images else 0}")

    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        model = os.getenv("LLM_QWEN2.5")
        base_url = os.getenv("DASHSCOPE_BASE_URL")

        if images and len(images) > 0:
            # 多模态请求使用视觉模型（qwen-vl-plus），纯文本模型不支持图片
            vision_model = os.getenv("LLM_VISION", "qwen-vl-plus")
            logger.info(f"使用视觉模型: {vision_model}")

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)

            user_content = [{"type": "text", "text": question}]
            for img in images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img['mime_type']};base64,{img['base64']}"}
                })

            stream = await client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                stream=True
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        else:
            # 无图片时复用 LangChain 的标准链
            llm = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                streaming=True
            )
            chat_prompt = ChatPromptTemplate.from_messages([
                ('system', prompt),
                ('human', question)
            ])
            chain = chat_prompt | llm
            async for chunk in chain.astream({}):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content

    except Exception as e:
        logger.error(f"调用多模态LLM出错：{str(e)}")
        yield f"回答生成失败：{str(e)}"



def create_knowledge_chain(system_prompt: str = "你是一个有用的助手，能够利用知识库回答用户问题。") -> Callable:
    """
    创建知识库查询链
    Args:
        system_prompt: 系统提示词

    Returns:
        Callable: 处理函数，接受问题、历史记录和图片，返回回答字符串
    """
    async def process_with_knowledge(question: str, history: str, images: list = None, documents: list = None) -> AsyncGenerator[str,None]:
        """使用知识库处理问题，支持图片和文档输入"""
        has_images = images and len(images) > 0
        has_docs = documents and len(documents) > 0
        logger.info(f"使用知识库处理问题: {question[:50]}..., 图片:{len(images) if has_images else 0}, 文档:{len(documents) if has_docs else 0}")

        # 解析文档
        doc_texts = ""
        if has_docs:
            doc_parts = []
            for doc in documents:
                try:
                    file_bytes = base64.b64decode(doc["base64"])
                    text = parse_document(file_bytes, doc.get("filename", "unknown"))
                    doc_parts.append(f"【{doc.get('filename', '文档')}】\n{text}")
                except Exception as e:
                    doc_parts.append(f"【{doc.get('filename', '文档')}】解析失败: {str(e)}")
            doc_texts = "\n\n".join(doc_parts)
            logger.info(f"文档解析完成，总长度: {len(doc_texts)} 字符")

        # 图片理解
        image_description = ""
        if has_images:
            img_extract_prompt = "你是一个信息提取助手。请分析用户提供的图片，提取出可用于知识库检索的关键信息。\n要求：\n1. 提取图片中的关键实体名称、术语、编号、产品名等\n2. 描述图片的核心内容（1-2句话）\n3. 直接输出提取结果，不要添加额外解释"
            img_desc_parts = []
            async for chunk in call_multimodal_llm("请分析这张图片中的关键信息。", img_extract_prompt, images):
                img_desc_parts.append(chunk)
            image_description = "".join(img_desc_parts)
            logger.info(f"图片关键信息提取: {image_description[:100]}...")

        # 查询增强，融合图片描述和文档内容
        enhanced_question = enhance_query(question, history)
        if image_description:
            enhanced_question = f"{enhanced_question}\n图片相关信息: {image_description}"
        if doc_texts:
            # 截取文档关键词部分用于检索增强
            doc_keywords = doc_texts[:500]
            enhanced_question = f"{enhanced_question}\n文档关键内容: {doc_keywords}"
        logger.info(f"查询增强: '{question}' -> '{enhanced_question[:100]}...'")

        # 调用RAGFlow
        rag_answer = RAGFlow_chat(enhanced_question)
        logger.info(f"RAGFlow返回结果长度: {len(rag_answer)}")

        # 构建完整提示
        prompt = system_prompt + "\n\n"

        if history:
            prompt += f"以下是你和用户之前的对话记录，请参考这些记录：\n{history}\n\n"

        if image_description:
            prompt += f"用户上传了图片，图片内容分析: {image_description}\n\n"

        if doc_texts:
            prompt += f"以下是从用户上传文档中提取的内容：\n{doc_texts}\n\n"

        prompt += f"用户问题: {question}\n\n"

        prompt += f"以下是从知识库中检索到的相关信息：\n{rag_answer}\n\n"
        prompt += "请基于上述知识库信息、文档内容、图片内容和对话历史回答用户问题。如果知识库中没有相关信息，请说明并尽可能用你自己的知识回答。\n\n"
        prompt += f"用户问题: {question}"

        # 有图片时用多模态LLM
        if has_images:
            async for chunk in call_multimodal_llm(question, prompt, images):
                yield chunk
        else:
            async for chunk in call_llm(question, prompt):
                yield chunk


    return process_with_knowledge



def create_general_chain(system_prompt: str = "你是一个有用的助手，能够回答各种问题。") -> Callable:
    """
    创建一般对话链

    Args:
        system_prompt: 系统提示词

    Returns:
        Callable: 处理函数，接受问题、历史记录和图片，返回回答字符串
    """
    async def process_general_chat(question:str, history:str, images: list = None, documents: list = None) -> AsyncGenerator[str,None]:
        """一般对话处理问题，支持图片和文档输入"""
        has_images = images and len(images) > 0
        has_docs = documents and len(documents) > 0
        logger.info(f"使用一般对话处理问题：{question[:50]}..., 图片:{len(images) if has_images else 0}, 文档:{len(documents) if has_docs else 0}")

        # 解析文档
        doc_texts = ""
        if has_docs:
            doc_parts = []
            for doc in documents:
                try:
                    file_bytes = base64.b64decode(doc["base64"])
                    text = parse_document(file_bytes, doc.get("filename", "unknown"))
                    doc_parts.append(f"【{doc.get('filename', '文档')}】\n{text}")
                except Exception as e:
                    doc_parts.append(f"【{doc.get('filename', '文档')}】解析失败: {str(e)}")
            doc_texts = "\n\n".join(doc_parts)

        prompt = system_prompt + "\n\n"

        if history:
            prompt += f"以下是你和用户之前的对话记录，请参考这些记录：\n{history}\n\n"

        if has_images:
            prompt += "用户上传了图片，请结合图片内容回答用户问题。\n\n"

        if doc_texts:
            prompt += f"以下是从用户上传文档中提取的内容：\n{doc_texts}\n\n"

        prompt += f"用户问题: {question}"

        if has_images:
            async for chunk in call_multimodal_llm(question, prompt, images):
                yield chunk
        else:
            async for chunk in call_llm(question, prompt):
                yield chunk

    return process_general_chat









if __name__ == "__main__":
    import asyncio
    import os
    import sys
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, PROJECT_ROOT)

    async def streaming():
        """测试流式输出效果"""
        print("[测试] 知识库查询链流式功能...")
        knowledge_chain = create_knowledge_chain()
        question1 = "那它的风景怎么样？"
        history1 = "用户: 瓦尔登湖在哪里\n助手: 瓦尔登湖在美国。"
        
        print(f"问题: {question1}")
        print(f"历史: {history1}")
        print("流式回答: ", end="", flush=True)
        
        full_answer = ""
        async for chunk in knowledge_chain(question1, history1):
            print(chunk, end="", flush=True)  # 实时打印每个片段
            full_answer += chunk
        
        print(f"\n完整回答: {full_answer}\n")

        print("[测试] 一般对话链流式功能...")
        general_chain = create_general_chain()
        question2 = "那你如何看待它？"
        history2 = "用户: 你了解人工智能吗？\n助手: 当然，人工智能是我工作的基础。"
        
        print(f"问题: {question2}")
        print(f"历史: {history2}")
        print("流式回答: ", end="", flush=True)
        
        full_answer = ""
        async for chunk in general_chain(question2, history2):
            print(chunk, end="", flush=True)  # 实时打印每个片段
            full_answer += chunk
        
        print(f"\n完整回答: {full_answer}\n")

    # 运行异步测试
    asyncio.run(streaming())