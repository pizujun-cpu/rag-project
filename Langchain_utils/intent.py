"""
意图识别模块

使用MCP的Function Call功能判断用户意图，确定是否需要调用知识库
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# 导入get_assistants函数
from RAGFlow_mcp.chat import get_assistants

# 获取项目根目录的绝对路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')

# 确保日志目录存在
os.makedirs(LOGS_DIR, exist_ok=True)

# 配置日志记录
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, 'intent_detection.log'),
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 使用@tool装饰器注册两个意图工具
@tool("knowledge_base")
def knowledge_base_tool(question: str, chat_history: str = "") -> str:
    """当用户问题需要查询知识库时调用此工具。适用于涉及公司信息、规章制度、专业领域知识、特定人物或事件等需要查询知识库的内容。"""
    return "knowledge_base"

@tool("general_chat")
def general_chat_tool(question: str, chat_history: str = "") -> str:
    """当用户问题是日常问候、常识性问题、数学计算、个人意见等无需特殊知识库时调用此工具。"""
    return "general_chat"

# 意图分类器工具定义
INTENT_CLASSIFIER_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "classify_intent",
            "description": "根据用户问题判断需要使用哪种处理方式",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "意图分类结果",
                        "enum": ["knowledge_base", "general_chat"]
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "分类理由"
                    }
                },
                "required": ["intent", "reasoning"]
            }
        }
    }
]

# 存储最近的意图历史
_intent_history = []

def get_last_intent() -> Optional[str]:
    """获取最近一次的意图"""
    if _intent_history:
        return _intent_history[-1]
    return None


def detect_intent(question: str, chat_history: str = "", has_images: bool = False, has_documents: bool = False) -> str:
    """
    使用MCP的Function Call功能进行意图分类

    Args:
        question: 用户问题
        chat_history: 对话历史文本
        has_images: 是否包含图片
        has_documents: 是否包含文档

    Returns:
        str: 意图类型，"knowledge_base"或"general_chat"
    """
    global _intent_history

    #加载环境变量
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY")
    model = os.getenv("LLM_QWEN2.5")
    base_url = os.getenv("DASHSCOPE_BASE_URL")

    #获取助手列表信息
    try:
        assistants_info = get_assistants()
        logging.info(f"成功获取助手列表，共有 {assistants_info.count('助手名称')} 个助手")
    except Exception as e:
        logging.error(f"获取列表助手出错：{str(e)}")
        assistans_info = "获取列表失败，无法提供助手信息"

    #获取上一个意图
    last_intent = get_last_intent()
    # 三元表达式: 值1 if 条件 else 值2
    # 如条件有值,则执行第一个条件,否则执行第二个
    last_intent_info = f"上一个问题的意图是: {last_intent}" if last_intent else "这是对话的第一个问题"

    # 创建OpenAI兼容客户端
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url
    )
    # bind_tools将工具绑定至模型,传入工具列表
    llm_with_tools = llm.bind_tools([knowledge_base_tool, general_chat_tool])

    # 构建系统提示词
    system_prompt = """分析用户问题，判断是否需要查询专业知识库来回答。

    以下是当前系统中所有可用的知识助手及其掌握的知识内容：
    {assistants_info}

    {last_intent_info}

    根据以上助手信息、对话历史和用户问题的内容，判断：
    1. 如果问题涉及到以上任何助手掌握的知识领域，或涉及具体的公司信息、规章制度、专业领域知识、特定人物或事件等需要查询知识库的内容，应返回intent=knowledge_base。
    2. 如果是日常问候、常识性问题、数学计算、个人意见等无需特殊知识库的问题，应返回intent=general_chat。
    3. 特别注意对话历史上下文，判断当前问题是否是对前文的跟进：
       - 如果当前问题是对前一个知识库问题的跟进（例如"他是谁？"、"这是什么？"、"还有呢？"等），应该沿用前一个问题的意图，即knowledge_base。
       - 如果当前问题虽然简短，但明显是在询问前文提到的知识库内容的相关信息，应该返回knowledge_base。
       - 如代词（他、她、它、这个、那个等）指代前文中通过知识库查询获得的信息，应该返回knowledge_base。

    请特别注意：
    1. 如果用户使用"查询"、"找找"、"检索"等词语，或明确提到某个助手名称，这通常是强烈的知识库需求信号。
    2. 如果当前问题是简短的跟进问题（如"为什么？"、"然后呢？"、"详细说说"等），应该考虑前一个问题的意图。
    3. 如果用户问题包含代词（他、她、它、这个、那个等），很可能是对前文的跟进，需要结合对话历史判断。
    """

    # 当用户上传图片时，追加多模态意图判断规则
    if has_images:
        multimodal_rules = """

    ## 多模态场景判断规则
    用户本次提问包含图片，请在判断意图时额外考虑：
    1. 如果图片内容涉及公司业务、产品、技术文档、内部系统、合同、报表等 → 应返回 knowledge_base，结合知识库回答
    2. 如果图片是通用内容（风景照、日常物品、网络表情等）→ 应返回 general_chat，直接基于视觉理解回答
    3. 如果用户仅上传图片未提出明确文字问题 → 返回 general_chat，描述图片内容
    4. 如果图片中包含可识别的文字、数据、图表，且可能涉及专业知识领域 → 倾向返回 knowledge_base
    """
        system_prompt += multimodal_rules

    # 当用户上传文档时，追加文档意图判断规则
    if has_documents:
        doc_rules = """

    ## 文档场景判断规则
    用户本次提问包含文档（PDF/Word/Excel/TXT），请在判断意图时额外考虑：
    1. 如果文档内容涉及专业知识、公司业务、技术规范、合同条款等 → 应返回 knowledge_base，结合知识库深度分析
    2. 如果文档是个人笔记、通用资料等非专业内容 → 可返回 general_chat，直接基于文档内容回答
    3. 如果用户要求对比文档内容与知识库信息 → 必须返回 knowledge_base
    4. 文档通常包含需要专业知识才能准确解读的内容，如无特殊理由应倾向返回 knowledge_base
    """
        system_prompt += doc_rules

    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt}
    ]

    # 添加对话历史（如果有）
    if chat_history:
        messages.append({"role": "system", "content": f"对话历史:\n{chat_history}"})

    # 添加用户问题
    messages.append({"role": "user", "content": question})

    # 记录用户问题
    logging.info(f"用户问题: {question}")
    if chat_history:
        logging.info(f"对话历史: {chat_history}")
    logging.info(f"上一个意图: {last_intent}")

    try:
        # 调用LLM，让它选择工具
        response = llm_with_tools.invoke(messages)

        # hasattr用于检查一个对象是否具有指定的属性或方法
        # 这里是检测其是否调用了工具
        if hasattr(response, 'tool_calls') and response.tool_calls:
            # 获取第一个工具调用
            # 通常在工具返回的时候只会返回一个工具,但tool_calls是列表格式,所以返回该列表的第一个元素
            tool_call = response.tool_calls[0]
            tool_name = tool_call["name"]

            # 根据工具名称确定意图
            if tool_name == "knowledge_base":
                intent = "knowledge_base"
            else:
                intent = "general_chat"

            # 输出详细的意图分类信息，方便调试
            print(f"意图检测结果: {intent}")
            print(f"调用的工具: {tool_name}")

            # 记录意图检测结果
            log_message = (
                f"意图检测结果 | 问题: {question} | "
                f"意图: {intent} | "
                f"调用的工具: {tool_name}"
            )
            logging.info(log_message)

            # 更新意图历史
            # 这里的下划线表示是一个私有变量/内部变量,不应从外部访问。
            # 是一种命名约定,并不强制,但开发的时候要遵守这个约定
            _intent_history.append(intent)
            # 只保留最近5个意图
            if len(_intent_history) > 5:
                _intent_history = _intent_history[-5:]

            return intent

        logging.warning(f"模型未返回工具调用结果，默认使用general_chat")
        _intent_history.append("general_chat")
        return "general_chat"  # 默认类型

    except Exception as e:
        error_msg = f"意图分类错误: {str(e)}"
        print(error_msg)
        logging.error(error_msg)
        _intent_history.append("general_chat")
        return "general_chat"  # 发生错误时默认为一般对话









if __name__ == "__main__":
    import os
    import sys
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, PROJECT_ROOT)

    print("[测试] 意图识别功能...")
    
    # 测试用例1：明确的知识库查询
    print("\n=== 测试1：明确的知识库查询 ===")
    question1 = "请帮我查询一下公司的请假制度"
    history1 = ""
    result1 = detect_intent(question1, history1)
    print(f"问题: {question1}")
    print(f"结果: {result1}\n")
    
    # 测试用例2：一般性对话
    print("=== 测试2：一般性对话 ===")
    question2 = "今天天气真不错啊"
    history2 = ""
    result2 = detect_intent(question2, history2)
    print(f"问题: {question2}")
    print(f"结果: {result2}\n")

    # 测试用例3：上下文跟进问题
    print("=== 测试3：上下文跟进问题 ===")
    question3 = "明天是周几呢？"
    history3 = "用户: 今天是周几？\n助手: 今天是周一。"
    result3 = detect_intent(question3, history3)
    print(f"问题: {question3}")
    print(f"历史: {history3}")
    print(f"结果: {result3}\n")

    # 测试用例4：模糊的跟进问题
    print("=== 测试4：模糊的跟进问题 ===")
    question4 = "还有什么其他的吗？"
    history4 = "用户: 公司有哪些福利政策？\n助手: 公司提供五险一金、年终奖等福利。"
    result4 = detect_intent(question4, history4)
    print(f"问题: {question4}")
    print(f"历史: {history4}")
    print(f"结果: {result4}\n")
