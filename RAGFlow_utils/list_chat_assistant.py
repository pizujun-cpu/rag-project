import os
from ragflow_sdk import RAGFlow
from dotenv import load_dotenv

def get_assistant_list():
    """
    获取RAGFlow中的所有聊天助手信息，并返回组合后的字符串
    
    Returns:
        str: 包含所有助手信息的字符串，每个助手一行
    """
    # 加载环境变量
    load_dotenv()
    
    # 获取环境变量
    url = str(os.getenv("RAGFLOW_API_URL"))
    apikey = str(os.getenv("RAGFLOW_API_KEY"))
    
    # 初始化结果字符串
    result = ""
    
    try:
        # 创建RAGFlow实例
        rag_object = RAGFlow(api_key=apikey, base_url=url)
        
        # 获取所有助手信息并组合成字符串
        for assistant in rag_object.list_chats():
            # 提取知识库名称
            kb_names = []
            if assistant.datasets and isinstance(assistant.datasets, list):
                for dataset in assistant.datasets:
                    if isinstance(dataset, dict) and 'name' in dataset:
                        kb_names.append(dataset['name'])
            
            # 格式化知识库名称列表
            kb_names_str = "、".join(kb_names) if kb_names else "无"
            
            # 添加到结果字符串
            result += f"助手名称：{assistant.name}； 功能介绍：{assistant.description}； 知识库：{kb_names_str}\n"
        
        # 移除最后一个换行符（如果结果不为空）
        if result:
            result = result.rstrip("\n")
    except Exception as e:
        # 发生错误时，返回错误信息
        result = f"获取助手列表时出错: {str(e)}"
    
    return result

# 如果直接运行此脚本，则打印结果
if __name__ == "__main__":
    assistants_info = get_assistant_list()
    print(assistants_info)