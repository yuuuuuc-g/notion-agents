from langchain_openai import ChatOpenAI
from config.settings import SETTINGS

def get_llm():
    """
    OpenRouter 配置
    """
    return ChatOpenAI(
        model="deepseek/deepseek-chat", 
        # 👇 直接从 SETTINGS 取值
        api_key=SETTINGS.OPENAI_API_KEY,
        base_url=SETTINGS.OPENAI_BASE_URL,
        temperature=0.1,
        streaming=True
    )