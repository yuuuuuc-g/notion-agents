"""
人工智能
人工智障
"""

from config.settings import SETTINGS


def get_llm():
    if SETTINGS.USE_LOCAL_NANOGPT:
        # 使用适配器
        from .local_model import LocalNanoGPT

        return LocalNanoGPT()
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=SETTINGS.LLM_MODEL_NAME,
            # 👇 直接从 SETTINGS 取值
            api_key=SETTINGS.OPENAI_API_KEY,
            base_url=SETTINGS.OPENAI_BASE_URL,
            temperature=0.1,
            streaming=True,
        )
