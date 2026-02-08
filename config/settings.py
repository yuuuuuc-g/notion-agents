"""
settings.py
集中化配置管理 - 修复版 v3
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. 先在外部计算出根目录 (作为私有变量)
_PROJECT_ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # === 0. 核心路径配置 ===
    # 必须显式定义为字段，外部才能通过 SETTINGS.PROJECT_ROOT 访问
    PROJECT_ROOT: str = _PROJECT_ROOT_PATH

    # === 1. 基础应用配置 ===
    APP_NAME: str = "BioBrain API"
    ENVIRONMENT: str = "development"  # development / production
    DEBUG: bool = True

    # 🔥 安全核心: API_SECRET
    API_SECRET: str

    # === 2. 思考大脑 (LLM) ===
    MOONSHOT_API_KEY: Optional[str] = None
    MOONSHOT_BASE_URL: str = "https://api.moonshot.cn/v1"
    LLM_MODEL_NAME: str = "kimi-k2.5"

    # === 3. 记忆向量 (Embedding - 硅基流动) ===
    SILICON_KEY: Optional[str] = None
    SILICON_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # === 4. 知识库 (Notion) ===
    NOTION_TOKEN: str

    # 数据库 IDs
    DB_SPANISH_ID: str
    DB_TECH_ID: Optional[str] = None
    DB_HUMANITIES_ID: Optional[str] = None

    # === 5. Redis (安全配置) ===
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False
    REDIS_MAX_CONNECTIONS: int = 50

    # === 6. 文件路径与音频 ===
    # 使用上面计算好的 _PROJECT_ROOT_PATH
    UPLOAD_DIR: str = os.path.join(_PROJECT_ROOT_PATH, "uploads")
    AUDIO_DIR: str = os.path.join(_PROJECT_ROOT_PATH, "generated_audio")
    TTS_RATE: str = "-10%"

    # === 7. CORS与网络 ===
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # === 8. 模型内存优化配置 ===
    # 控制是否启用稀疏模型以节省内存
    ENABLE_SPARSE_MODEL: bool = True
    # 控制是否启用重排序模型以节省内存
    ENABLE_RERANKER: bool = True
    # 最大内存使用限制（MB），超过则卸载非核心模型
    MAX_MEMORY_MB: int = 2048
    # 稀疏模型选择（默认使用相对轻量级的模型）
    SPARSE_MODEL_NAME: str = "prithivida/Splade_PP_en_v1"
    # 重排序模型选择（large=精度高但内存大，base=内存小但精度略低）
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-large"

    # === Pydantic 配置 ===
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings():
    """单例模式获取配置"""
    return Settings()


# 导出全局实例
SETTINGS = get_settings()

if SETTINGS.DEBUG:
    print(f"🔧 Config loaded. Project root: {SETTINGS.PROJECT_ROOT}")
