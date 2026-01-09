"""
config/settings.py
全区配置中心
负责读取环境变量 (.env) 并提供给各部门使用
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

class Settings:
    # --- 1. 基础开关 ---
    USE_LOCAL_NANOGPT: bool = False 

    # --- 2. 思考大脑 (LLM) ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL")
    
    # --- 3. 记忆向量 (Embedding) ---
    SILICON_KEY: str = os.getenv("SILICON_KEY")
    SILICON_BASE_URL: str = os.getenv("SILICON_BASE_URL", "https://api.siliconflow.cn/v1")
    
    # --- 4. 知识库 (Notion) ---
    NOTION_TOKEN: str = os.getenv("NOTION_TOKEN")
    
    # 核心修复：这里必须和你 .env 里的名字一模一样！
    _MAIN_DB_ID = os.getenv("NOTION_DATABASE_ID")
    
    # 1. 西语/主数据库 (如果没有专门设西班牙语库，就用主库)
    DB_SPANISH_ID: str = os.getenv("NOTION_DATABASE_ID_SPANISH") or _MAIN_DB_ID
    
    # 2. 社科数据库 (对应你的 NOTION_DATABASE_ID_HUMANITIES)
    DB_HUMANITIES_ID: str = os.getenv("NOTION_DATABASE_ID_HUMANITIES") or _MAIN_DB_ID
    
    # 3. 科技数据库 (对应你的 NOTION_DATABASE_ID_TECH)
    DB_TECH_ID: str = os.getenv("NOTION_DATABASE_ID_TECH") or _MAIN_DB_ID
    
    # --- 5. 文件路径 ---
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    AUDIO_DIR = os.path.join(PROJECT_ROOT, "generated_audio")
    TTS_RATE = "-10%"

# 实例化并导出
SETTINGS = Settings()

# 启动检查
if not SETTINGS.NOTION_TOKEN or not SETTINGS._MAIN_DB_ID:
    print("⚠️  Warning: Notion configuration missing in .env")