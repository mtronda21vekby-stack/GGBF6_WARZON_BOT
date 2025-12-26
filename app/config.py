import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_MODEL: str

    DATA_DIR: str
    STATE_PATH: str
    OFFSET_PATH: str

    HTTP_TIMEOUT: float
    TG_LONGPOLL_TIMEOUT: int
    TG_RETRIES: int

    CONFLICT_BACKOFF_MIN: int
    CONFLICT_BACKOFF_MAX: int

    MIN_SECONDS_BETWEEN_MSG: float
    MEMORY_MAX_TURNS: int
    MAX_TEXT_LEN: int


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        # не падаем сразу — логика polling сама будет ждать, но лучше явно
        raise RuntimeError("Missing ENV: TELEGRAM_BOT_TOKEN")

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    data_dir = os.getenv("DATA_DIR", "/tmp").strip() or "/tmp"

    http_timeout = float(os.getenv("HTTP_TIMEOUT", "25"))
    longpoll_timeout = int(os.getenv("TG_LONGPOLL_TIMEOUT", "50"))
    retries = int(os.getenv("TG_RETRIES", "6"))

    conflict_min = int(os.getenv("CONFLICT_BACKOFF_MIN", "12"))
    conflict_max = int(os.getenv("CONFLICT_BACKOFF_MAX", "30"))

    min_between = float(os.getenv("MIN_SECONDS_BETWEEN_MSG", "0.25"))
    mem_turns = int(os.getenv("MEMORY_MAX_TURNS", "10"))

    max_text = int(os.getenv("MAX_TEXT_LEN", "3900"))

    state_path = os.path.join(data_dir, "fps_coach_state.json")
    offset_path = os.path.join(data_dir, "tg_offset.txt")

    return Settings(
        TELEGRAM_BOT_TOKEN=token,
        OPENAI_API_KEY=openai_key,
        OPENAI_BASE_URL=base_url,
        OPENAI_MODEL=model,

        DATA_DIR=data_dir,
        STATE_PATH=state_path,
        OFFSET_PATH=offset_path,

        HTTP_TIMEOUT=http_timeout,
        TG_LONGPOLL_TIMEOUT=longpoll_timeout,
        TG_RETRIES=retries,

        CONFLICT_BACKOFF_MIN=conflict_min,
        CONFLICT_BACKOFF_MAX=conflict_max,

        MIN_SECONDS_BETWEEN_MSG=min_between,
        MEMORY_MAX_TURNS=mem_turns,
        MAX_TEXT_LEN=max_text,
    )