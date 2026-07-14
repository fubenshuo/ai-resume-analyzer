"""
应用配置管理

通过环境变量或 .env 文件配置，兼容阿里云函数计算 FC 的环境变量注入。
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 查找 .env 文件：优先当前目录，其次上级目录（项目根目录）
_ENV_FILE = ".env"
if not Path(_ENV_FILE).exists():
    _PARENT_ENV = Path(__file__).parent.parent / ".env"
    if _PARENT_ENV.exists():
        _ENV_FILE = str(_PARENT_ENV)


class Settings(BaseSettings):
    # --- AI 模型配置 ---
    # 兼容 OpenAI 接口的 API 地址（如通义千问、DeepSeek、OpenAI 等）
    ai_api_base_url: str = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
    ai_api_key: str = os.getenv("AI_API_KEY", "sk-your-api-key")
    ai_model: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    # 请求超时（秒）
    ai_request_timeout: int = int(os.getenv("AI_REQUEST_TIMEOUT", "60"))
    # AI 分析文本最大长度（字符）
    text_max_chars: int = int(os.getenv("TEXT_MAX_CHARS", "8000"))

    # --- 缓存配置 ---
    cache_type: str = os.getenv("CACHE_TYPE", "memory")  # "memory" 或 "redis"
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl: int = int(os.getenv("CACHE_TTL", "3600"))  # 缓存过期时间（秒）

    # --- 上传配置 ---
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

    # --- 服务配置 ---
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    model_config = {"env_file": _ENV_FILE, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
