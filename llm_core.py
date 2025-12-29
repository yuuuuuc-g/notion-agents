import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    """
    返回配置好的 LLM 实例
    建议使用 DeepSeek-V3 (deepseek-chat) 或 GPT-4o 以获得最佳的 Tool Calling 体验
    """
    return ChatOpenAI(
        model="deepseek-chat", # 或 gpt-4o
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"), # 如果是 DeepSeek 需要配置这个
        temperature=0.1, # 低温度保证工具调用准确
        streaming=True
    )