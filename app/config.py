import os

def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} is required")
    return v

def _opt(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

class Settings:
    BOT_TOKEN: str
    WEBHOOK_SECRET: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str
    ADMIN_IDS: set[int]
    TZ: str

def get_settings() -> Settings:
    s = Settings()
    s.BOT_TOKEN = _req("BOT_TOKEN")
    s.WEBHOOK_SECRET = _req("WEBHOOK_SECRET")

    s.OPENAI_API_KEY = _opt("OPENAI_API_KEY", "")
    s.OPENAI_MODEL = _opt("OPENAI_MODEL", "gpt-4o-mini")

    raw_admins = _opt("ADMIN_IDS", "")
    s.ADMIN_IDS = set()
    for x in raw_admins.replace(" ", "").split(","):
        if x.isdigit():
            s.ADMIN_IDS.add(int(x))

    s.TZ = _opt("TZ", "UTC")
    return s
