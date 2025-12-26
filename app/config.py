import os
from dataclasses import dataclass
from typing import List


def _must(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _int_list(name: str) -> List[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    out: List[int] = []
    for p in raw.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            out.append(int(p))
        except ValueError:
            pass
    return out


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openai_api_key: str
    openai_model: str
    data_dir: str
    admin_ids: List[int]


def load_settings() -> Settings:
    return Settings(
        telegram_token=_must("TELEGRAM_BOT_TOKEN"),
        openai_api_key=_must("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
        data_dir=os.getenv("DATA_DIR", "./data").strip() or "./data",
        admin_ids=_int_list("ADMIN_IDS"),
    )