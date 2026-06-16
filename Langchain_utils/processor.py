"""
统一处理器模块

集成记忆、意图识别和处理链，提供完整的处理流程
"""

import logging
from typing import Callable, Dict, Any, Optional,AsyncGenerator
from .memory import create_memory, format_chat_history
from .intent import detect_intent
from .chains import create_knowledge_chain, create_general_chain
from RAGFlow_utils.query_enhancer import enhance_query
from .config import DEFAULT_SESSION_ID
from langchain.schema import AIMessage, HumanMessage


def create_unified_processor(
    system_prompt: str = "你是一个智能助手，可以根据需要查询知识库或直接回答用户问题。",
    session_id: str = DEFAULT_SESSION_ID
) -> Callable[[str], AsyncGenerator[Dict[str, Any], None]]:
    """
    创建统一处理器
    
    Args:
        system_prompt: 系统提示词
        session_id: 会话ID，用于MongoDB存储
        
    Returns:
        Callable: 处理函数，接受问题并返回包含回答和元数据的字典
    """
    # 创建记忆对象，使用指定的会话ID
    memory = create_memory(session_id=session_id)

    # 创建处理链
    knowledge_chain = create_knowledge_chain(system_prompt)
    general_chain = create_general_chain(system_prompt)

    # 处理统计
    stats = {
        "total_queries": 0,
        "knowledge_base_queries": 0,
        "general_chat_queries": 0
    }

    async def processor(question: str, images: list = None, documents: list = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户问题，支持图片和文档输入

        Args:
            question: 用户问题
            images: 图片列表
            documents: 文档列表，每项为 {"base64": "...", "filename": "...", "mime_type": "..."}

        Returns:
            Dict: 包含回答和元信息的字典
        """
        stats["total_queries"] += 1

        has_images = images is not None and len(images) > 0
        has_documents = documents is not None and len(documents) > 0

        memory_variables = memory.load_memory_variables({})
        chat_history = memory_variables.get("chat_history", [])
        formatted_history = format_chat_history(chat_history)

        intent = detect_intent(question, formatted_history, has_images=has_images, has_documents=has_documents)

        metadata = {
            "intent": intent,
            "original_query": question,
            "session_id": session_id,
            "has_images": has_images,
            "has_documents": has_documents
        }

        if has_images:
            metadata["image_count"] = len(images)
        if has_documents:
            metadata["document_count"] = len(documents)
            metadata["document_names"] = [doc.get("filename", "未知文件") for doc in documents]

        if intent == "knowledge_base":
            enhanced_query = enhance_query(question, formatted_history)
            metadata["enhanced_query"] = enhanced_query
            metadata["query_enhanced"] = enhanced_query != question

        yield {
            "type": "metadata",
            "data": metadata
        }

        full_answer = ""
        if intent == "knowledge_base":
            stats["knowledge_base_queries"] += 1
            metadata["processor"] = "knowledge_base"
            chain = knowledge_chain
        else:
            stats["general_chat_queries"] += 1
            metadata["processor"] = "general_chat"
            chain = general_chain

        async for chunk in chain(question, formatted_history, images, documents):
            full_answer += chunk
            yield {
                "type": "content",
                "data": chunk
            }
        # 保存完整对话到记忆
        input_message = HumanMessage(content=question)
        output_message = AIMessage(content=full_answer)

        try:
            memory.chat_memory.add_messages([input_message, output_message])
        except Exception as e:
            logging.error(f"将会话历史保存到MongoDB时出错: {e}")

        # 记录查询统计
        logging.info(
            f"处理统计 | 会话ID: {session_id} | 总查询: {stats['total_queries']} | "
            f"知识库查询: {stats['knowledge_base_queries']} | "
            f"一般查询: {stats['general_chat_queries']}"
        )

        # 发送结束标记
        yield {
            "type": "end",
            "data": {
                "full_answer": full_answer,
                "metadata": metadata
            }
        }

    # 添加实用函数
    def get_stats() -> Dict[str, int]:
        """获取处理统计信息"""
        return stats.copy()

    def clear_memory() -> None:
        """清除对话记忆"""
        memory.clear()
        logging.info(f"会话 {session_id} 的对话记忆已清除")

    # 将实用函数附加到处理器函数
    processor.get_stats = get_stats
    processor.clear_memory = clear_memory

    return processor




    
