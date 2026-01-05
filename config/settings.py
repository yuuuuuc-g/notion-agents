"""
config/settings.py
统一配置管理：负责读取 .env 并提供全局常量
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件 (全局只做这一次)
load_dotenv()

class Settings:
    # --- 1. LLM (思考大脑) ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
    
    # --- 2. SiliconFlow (向量记忆) ---
    SILICON_KEY = os.getenv("SILICON_KEY")
    SILICON_BASE_URL = os.getenv("SILICON_BASE_URL")
    
    # --- 3. Notion (知识库) ---
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    # 默认数据库 ID
    DB_SPANISH_ID = os.getenv("NOTION_DATABASE_ID")
    # 如果有特定分类数据库，优先读特定 ID，否则回退到默认 ID
    DB_HUMANITIES_ID = os.getenv("NOTION_DATABASE_ID_HUMANITIES", DB_SPANISH_ID)
    DB_TECH_ID = os.getenv("NOTION_DATABASE_ID_TECH", DB_SPANISH_ID)

    # --- 4. 本地路径配置 ---
    # 音频文件存放目录 (Server 和 AudioOps 都要用，必须统一)
    AUDIO_DIR = "generated_audio"
    
    # --- 5. 业务参数配置 ---
    # 语速配置 (-10% 表示慢 10%)
    TTS_RATE = "-10%" 

# 实例化单例，方便外部直接 import SETTINGS 使用
SETTINGS = Settings()

# 简单的启动检查
if not SETTINGS.OPENAI_API_KEY:
    print("⚠️ Warning: OPENAI_API_KEY is missing in .env")