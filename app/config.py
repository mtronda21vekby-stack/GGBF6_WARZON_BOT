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


def _env_on(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().casefold() not in {
        "0",
        "false",
        "off",
        "no",
        "",
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Telegram
    bot_token: str = os.getenv("BOT_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    telegram_max_update_bytes: int = int(
        os.getenv("TELEGRAM_MAX_UPDATE_BYTES", str(256 * 1024))
    )
    telegram_update_dedupe_ttl_s: int = int(
        os.getenv("TELEGRAM_UPDATE_DEDUPE_TTL_S", "900")
    )
    telegram_update_dedupe_max_entries: int = int(
        os.getenv("TELEGRAM_UPDATE_DEDUPE_MAX_ENTRIES", "20000")
    )
    telegram_aaa_console_enabled: bool = _env_on(
        "TELEGRAM_AAA_CONSOLE_ENABLED"
    )
    telegram_live_drafts_enabled: bool = _env_on(
        "TELEGRAM_LIVE_DRAFTS_ENABLED"
    )

    # Mini App presentation / streaming.
    webapp_live_stream_enabled: bool = _env_on(
        "WEBAPP_LIVE_STREAM_ENABLED"
    )
    webapp_cinematic_ui_enabled: bool = _env_on(
        "WEBAPP_CINEMATIC_UI_ENABLED"
    )

    # Operator Twin / adaptive mission intelligence.
    operator_intelligence_enabled: bool = _env_on(
        "OPERATOR_INTELLIGENCE_ENABLED"
    )
    adaptive_mission_control_enabled: bool = _env_on(
        "ADAPTIVE_MISSION_CONTROL_ENABLED"
    )
    mission_vod_evidence_fusion_enabled: bool = _env_on(
        "MISSION_VOD_EVIDENCE_FUSION_ENABLED"
    )

    # Abuse / cost guard.
    usage_guard_enabled: bool = _env_on("USAGE_GUARD_ENABLED")
    usage_guard_max_buckets: int = int(
        os.getenv("USAGE_GUARD_MAX_BUCKETS", "10000")
    )
    ai_rate_limit_1m: int = int(os.getenv("AI_RATE_LIMIT_1M", "12"))
    ai_rate_limit_1h: int = int(os.getenv("AI_RATE_LIMIT_1H", "120"))
    ai_global_rate_limit_1m: int = int(
        os.getenv("AI_GLOBAL_RATE_LIMIT_1M", "180")
    )
    ai_global_rate_limit_1h: int = int(
        os.getenv("AI_GLOBAL_RATE_LIMIT_1H", "1800")
    )
    vod_rate_limit_10m: int = int(os.getenv("VOD_RATE_LIMIT_10M", "3"))
    vod_rate_limit_1h: int = int(os.getenv("VOD_RATE_LIMIT_1H", "12"))
    vod_global_rate_limit_10m: int = int(
        os.getenv("VOD_GLOBAL_RATE_LIMIT_10M", "30")
    )
    vod_global_rate_limit_1h: int = int(
        os.getenv("VOD_GLOBAL_RATE_LIMIT_1H", "120")
    )
    # STT and TTS are distinct paid capability boundaries. A voice→voice turn
    # consumes one STT event and, when spoken output is enabled, one TTS event.
    stt_rate_limit_1m: int = int(os.getenv("STT_RATE_LIMIT_1M", "12"))
    stt_rate_limit_1h: int = int(os.getenv("STT_RATE_LIMIT_1H", "90"))
    stt_global_rate_limit_1m: int = int(
        os.getenv("STT_GLOBAL_RATE_LIMIT_1M", "150")
    )
    stt_global_rate_limit_1h: int = int(
        os.getenv("STT_GLOBAL_RATE_LIMIT_1H", "1200")
    )
    voice_rate_limit_1m: int = int(os.getenv("VOICE_RATE_LIMIT_1M", "10"))
    voice_rate_limit_1h: int = int(os.getenv("VOICE_RATE_LIMIT_1H", "60"))
    voice_global_rate_limit_1m: int = int(
        os.getenv("VOICE_GLOBAL_RATE_LIMIT_1M", "120")
    )
    voice_global_rate_limit_1h: int = int(
        os.getenv("VOICE_GLOBAL_RATE_LIMIT_1H", "1200")
    )

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory / persistence
    memory_max_turns: int = int(os.getenv("MEMORY_MAX_TURNS", "20"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "auto")
    storage_timeout_s: float = float(os.getenv("STORAGE_TIMEOUT_S", "8"))
    storage_outbox_max: int = int(
        os.getenv("STORAGE_OUTBOX_MAX", "500")
    )
    storage_replay_batch: int = int(
        os.getenv("STORAGE_REPLAY_BATCH", "50")
    )
    supabase_url: str = os.getenv(
        "SUPABASE_URL",
        DEFAULT_BCO_SUPABASE_URL,
    )
    supabase_service_role_key: str = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        "",
    )
    supabase_schema: str = os.getenv("SUPABASE_SCHEMA", "public")

    # Phase 2C1 canonical-read parity probe. This is read-only and always
    # returns the legacy result. Set the enabled flag to false for immediate
    # rollback without a schema or deploy rollback.
    canonical_read_shadow_enabled: bool = _env_on(
        "CANONICAL_READ_SHADOW_ENABLED"
    )
    canonical_read_shadow_sample_rate: float = float(
        os.getenv("CANONICAL_READ_SHADOW_SAMPLE_RATE", "1.0")
    )
    canonical_read_identity_cache_ttl_s: float = float(
        os.getenv("CANONICAL_READ_IDENTITY_CACHE_TTL_S", "120")
    )
    canonical_read_identity_negative_cache_ttl_s: float = float(
        os.getenv("CANONICAL_READ_IDENTITY_NEGATIVE_CACHE_TTL_S", "5")
    )
    canonical_read_identity_cache_max_entries: int = int(
        os.getenv("CANONICAL_READ_IDENTITY_CACHE_MAX_ENTRIES", "10000")
    )

    # Shared BlackCrown identity / Premium entitlement authority.
    premium_link_enabled: bool = _env_on("PREMIUM_LINK_ENABLED")
    blackcrown_account_url: str = os.getenv(
        "BLACKCROWN_ACCOUNT_URL",
        DEFAULT_BLACKCROWN_ACCOUNT_URL,
    )
    premium_link_ttl_s: int = int(
        os.getenv("PREMIUM_LINK_TTL_S", "600")
    )
    entitlement_timeout_s: float = float(
        os.getenv("ENTITLEMENT_TIMEOUT_S", "8")
    )
    telegram_bot_username: str = os.getenv(
        "TELEGRAM_BOT_USERNAME", "GGBF6_WARZON_BOT"
    )
    apple_account_link_ttl_s: int = int(
        os.getenv("APPLE_ACCOUNT_LINK_TTL_S", "600")
    )
    apple_account_link_timeout_s: float = float(
        os.getenv("APPLE_ACCOUNT_LINK_TIMEOUT_S", "8")
    )

    # Live official game intelligence
    live_knowledge_enabled: bool = _env_on("LIVE_KNOWLEDGE_ENABLED")
    live_knowledge_ttl_s: int = int(
        os.getenv("LIVE_KNOWLEDGE_TTL_S", "900")
    )
    live_knowledge_timeout_s: float = float(
        os.getenv("LIVE_KNOWLEDGE_TIMEOUT_S", "6")
    )

    # Real VOD intelligence
    vod_enabled: bool = _env_on("VOD_ENABLED")
    vod_max_bytes: int = int(
        os.getenv("VOD_MAX_BYTES", str(20 * 1024 * 1024))
    )
    vod_max_frames: int = int(os.getenv("VOD_MAX_FRAMES", "8"))
    vod_frame_width: int = int(os.getenv("VOD_FRAME_WIDTH", "1280"))
    vod_download_timeout_s: float = float(
        os.getenv("VOD_DOWNLOAD_TIMEOUT_S", "60")
    )
    vod_vision_model: str = os.getenv(
        "VOD_VISION_MODEL",
        os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )

    # Duplex voice input: Telegram voice/audio/video-note ->
    # confidence-aware STT -> same Intelligence Core.
    voice_input_enabled: bool = _env_on("VOICE_INPUT_ENABLED")
    voice_transcription_model: str = os.getenv(
        "VOICE_TRANSCRIPTION_MODEL",
        "gpt-4o-transcribe",
    )
    voice_transcription_fallback_model: str = os.getenv(
        "VOICE_TRANSCRIPTION_FALLBACK_MODEL",
        "gpt-4o-mini-transcribe",
    )
    voice_transcription_language: str = os.getenv(
        "VOICE_TRANSCRIPTION_LANGUAGE",
        "ru",
    )
    voice_transcription_timeout_s: float = float(
        os.getenv("VOICE_TRANSCRIPTION_TIMEOUT_S", "45")
    )
    voice_transcription_confidence_threshold: float = float(
        os.getenv("VOICE_TRANSCRIPTION_CONFIDENCE_THRESHOLD", "0.58")
    )
    voice_input_max_bytes: int = int(
        os.getenv("VOICE_INPUT_MAX_BYTES", str(12 * 1024 * 1024))
    )
    voice_input_max_duration_s: int = int(
        os.getenv("VOICE_INPUT_MAX_DURATION_S", "300")
    )
    voice_transcript_confirmation_ttl_s: int = int(
        os.getenv("VOICE_TRANSCRIPT_CONFIRMATION_TTL_S", "120")
    )

    # Hybrid output: natural OpenAI speech first, local Piper fallback ready.
    voice_enabled: bool = _env_on("VOICE_ENABLED")
    voice_follow_input_enabled: bool = _env_on(
        "VOICE_FOLLOW_INPUT_ENABLED"
    )
    voice_provider: str = os.getenv("VOICE_PROVIDER", "auto")
    voice_high_fidelity_enabled: bool = _env_on(
        "VOICE_HIGH_FIDELITY_ENABLED"
    )
    voice_local_fallback_enabled: bool = _env_on(
        "VOICE_LOCAL_FALLBACK_ENABLED"
    )
    voice_model_name: str = os.getenv(
        "VOICE_MODEL_NAME",
        "ru_RU-denis-medium",
    )
    voice_model_dir: str = os.getenv("VOICE_MODEL_DIR", ".bco_voice")
    voice_model_timeout_s: float = float(
        os.getenv("VOICE_MODEL_TIMEOUT_S", "120")
    )
    voice_max_chars: int = int(os.getenv("VOICE_MAX_CHARS", "3200"))
    voice_duplex_max_chars: int = int(
        os.getenv("VOICE_DUPLEX_MAX_CHARS", "1800")
    )
    voice_opus_bitrate_kbps: int = int(
        os.getenv("VOICE_OPUS_BITRATE_KBPS", "72")
    )
    voice_openai_model: str = os.getenv(
        "VOICE_OPENAI_MODEL",
        "gpt-4o-mini-tts",
    )
    voice_openai_voice: str = os.getenv("VOICE_OPENAI_VOICE", "marin")
    voice_openai_timeout_s: float = float(
        os.getenv("VOICE_OPENAI_TIMEOUT_S", "45")
    )
    voice_openai_max_bytes: int = int(
        os.getenv("VOICE_OPENAI_MAX_BYTES", str(20 * 1024 * 1024))
    )

    # AI
    ai_enabled: bool = _env_on("AI_ENABLED")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
