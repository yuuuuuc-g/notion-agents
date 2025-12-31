import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    """
    OpenRouter 配置
    """
    return ChatOpenAI(
        # 🚨 关键修改：OpenRouter 的模型 ID 必须带厂商前缀
        model="deepseek/deepseek-chat", 
        
        # 备选：如果 DeepSeek 比较慢，也可以换成便宜且极快的
        # model="google/gemini-2.0-flash-exp:free", 
        
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        temperature=0.1,
        streaming=True
    )