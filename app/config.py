# app/config.py
from __future__ import annotations

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except Exception:
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore


DEFAULT_BCO_SUPABASE_URL = "https://wqriwhciqvrbhkkiuhxb.supabase.co"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory / persistence
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "20"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "auto")
    storage_timeout_s: float = float(os.getenv("STORAGE_TIMEOUT_S", "8"))
    supabase_url: str = os.getenv("SUPABASE_URL", DEFAULT_BCO_SUPABASE_URL)
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "public")

    # Live official game intelligence
    live_knowledge_enabled: bool = os.getenv("LIVE_KNOWLEDGE_ENABLED", "1") not in ("0", "false", "False", "")
    live_knowledge_ttl_s: int = int(os.getenv("LIVE_KNOWLEDGE_TTL_S", "900"))
    live_knowledge_timeout_s: float = float(os.getenv("LIVE_KNOWLEDGE_TIMEOUT_S", "6"))

    # Real VOD intelligence
    vod_enabled: bool = os.getenv("VOD_ENABLED", "1") not in ("0", "false", "False", "")
    vod_max_bytes: int = int(os.getenv("VOD_MAX_BYTES", str(20 * 1024 * 1024)))
    vod_max_frames: int = int(os.getenv("VOD_MAX_FRAMES", "8"))
    vod_frame_width: int = int(os.getenv("VOD_FRAME_WIDTH", "1280"))
    vod_download_timeout_s: float = float(os.getenv("VOD_DOWNLOAD_TIMEOUT_S", "60"))
    vod_vision_model: str = os.getenv("VOD_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

    # Free/self-hosted Telegram voice. No paid TTS API is required.
    voice_enabled: bool = os.getenv("VOICE_ENABLED", "1") not in ("0", "false", "False", "")
    voice_provider: str = os.getenv("VOICE_PROVIDER", "piper")
    voice_model_name: str = os.getenv("VOICE_MODEL_NAME", "ru_RU-denis-medium")
    voice_model_dir: str = os.getenv("VOICE_MODEL_DIR", ".bco_voice")
    voice_model_timeout_s: float = float(os.getenv("VOICE_MODEL_TIMEOUT_S", "120"))
    voice_max_chars: int = int(os.getenv("VOICE_MAX_CHARS", "1600"))

    # AI
    ai_enabled: bool = os.getenv("AI_ENABLED", "1") not in ("0", "false", "False", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
