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
DEFAULT_BLACKCROWN_ACCOUNT_URL = "https://blackcrown.work/account/telegram"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    telegram_max_update_bytes: int = int(os.getenv("TELEGRAM_MAX_UPDATE_BYTES", str(256 * 1024)))
    telegram_update_dedupe_ttl_s: int = int(os.getenv("TELEGRAM_UPDATE_DEDUPE_TTL_S", "900"))
    telegram_update_dedupe_max_entries: int = int(os.getenv("TELEGRAM_UPDATE_DEDUPE_MAX_ENTRIES", "20000"))
    telegram_aaa_console_enabled: bool = os.getenv("TELEGRAM_AAA_CONSOLE_ENABLED", "1") not in (
        "0",
        "false",
        "False",
        "off",
        "OFF",
        "",
    )

    # Abuse / cost guard. Limits are intentionally generous for legitimate use
    # but cap burst/flood cost at the actual expensive capability boundaries.
    usage_guard_enabled: bool = os.getenv("USAGE_GUARD_ENABLED", "1") not in ("0", "false", "False", "")
    usage_guard_max_buckets: int = int(os.getenv("USAGE_GUARD_MAX_BUCKETS", "10000"))
    ai_rate_limit_1m: int = int(os.getenv("AI_RATE_LIMIT_1M", "12"))
    ai_rate_limit_1h: int = int(os.getenv("AI_RATE_LIMIT_1H", "120"))
    ai_global_rate_limit_1m: int = int(os.getenv("AI_GLOBAL_RATE_LIMIT_1M", "180"))
    ai_global_rate_limit_1h: int = int(os.getenv("AI_GLOBAL_RATE_LIMIT_1H", "1800"))
    vod_rate_limit_10m: int = int(os.getenv("VOD_RATE_LIMIT_10M", "3"))
    vod_rate_limit_1h: int = int(os.getenv("VOD_RATE_LIMIT_1H", "12"))
    vod_global_rate_limit_10m: int = int(os.getenv("VOD_GLOBAL_RATE_LIMIT_10M", "30"))
    vod_global_rate_limit_1h: int = int(os.getenv("VOD_GLOBAL_RATE_LIMIT_1H", "120"))
    voice_rate_limit_1m: int = int(os.getenv("VOICE_RATE_LIMIT_1M", "10"))
    voice_rate_limit_1h: int = int(os.getenv("VOICE_RATE_LIMIT_1H", "60"))
    voice_global_rate_limit_1m: int = int(os.getenv("VOICE_GLOBAL_RATE_LIMIT_1M", "120"))
    voice_global_rate_limit_1h: int = int(os.getenv("VOICE_GLOBAL_RATE_LIMIT_1H", "1200"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory / persistence
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "20"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "auto")
    storage_timeout_s: float = float(os.getenv("STORAGE_TIMEOUT_S", "8"))
    storage_outbox_max: int = int(os.getenv("STORAGE_OUTBOX_MAX", "500"))
    storage_replay_batch: int = int(os.getenv("STORAGE_REPLAY_BATCH", "50"))
    supabase_url: str = os.getenv("SUPABASE_URL", DEFAULT_BCO_SUPABASE_URL)
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "public")

    # Shared BlackCrown identity / Premium entitlement authority.
    premium_link_enabled: bool = os.getenv("PREMIUM_LINK_ENABLED", "1") not in ("0", "false", "False", "")
    blackcrown_account_url: str = os.getenv("BLACKCROWN_ACCOUNT_URL", DEFAULT_BLACKCROWN_ACCOUNT_URL)
    premium_link_ttl_s: int = int(os.getenv("PREMIUM_LINK_TTL_S", "600"))
    entitlement_timeout_s: float = float(os.getenv("ENTITLEMENT_TIMEOUT_S", "8"))

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

    # Hybrid voice: steerable cloud TTS first, local Piper fallback always ready.
    # Legacy VOICE_PROVIDER=piper is treated as hybrid for a safe production
    # upgrade. Use VOICE_HIGH_FIDELITY_ENABLED=0 or VOICE_PROVIDER=piper-only
    # to force the fully local path.
    voice_enabled: bool = os.getenv("VOICE_ENABLED", "1") not in ("0", "false", "False", "")
    voice_provider: str = os.getenv("VOICE_PROVIDER", "auto")
    voice_high_fidelity_enabled: bool = os.getenv("VOICE_HIGH_FIDELITY_ENABLED", "1") not in (
        "0",
        "false",
        "False",
        "off",
        "OFF",
        "",
    )
    voice_local_fallback_enabled: bool = os.getenv("VOICE_LOCAL_FALLBACK_ENABLED", "1") not in (
        "0",
        "false",
        "False",
        "off",
        "OFF",
        "",
    )
    voice_model_name: str = os.getenv("VOICE_MODEL_NAME", "ru_RU-denis-medium")
    voice_model_dir: str = os.getenv("VOICE_MODEL_DIR", ".bco_voice")
    voice_model_timeout_s: float = float(os.getenv("VOICE_MODEL_TIMEOUT_S", "120"))
    voice_max_chars: int = int(os.getenv("VOICE_MAX_CHARS", "1800"))
    voice_opus_bitrate_kbps: int = int(os.getenv("VOICE_OPUS_BITRATE_KBPS", "48"))
    voice_openai_model: str = os.getenv("VOICE_OPENAI_MODEL", "gpt-4o-mini-tts")
    voice_openai_voice: str = os.getenv("VOICE_OPENAI_VOICE", "cedar")
    voice_openai_timeout_s: float = float(os.getenv("VOICE_OPENAI_TIMEOUT_S", "45"))
    voice_openai_max_bytes: int = int(os.getenv("VOICE_OPENAI_MAX_BYTES", str(20 * 1024 * 1024)))

    # AI
    ai_enabled: bool = os.getenv("AI_ENABLED", "1") not in ("0", "false", "False", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
