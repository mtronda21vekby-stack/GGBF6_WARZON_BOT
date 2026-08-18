from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CrownIdentity:
    black_crown_user_id: str
    provider: str
    status: str
    account_status: str

    @property
    def provisional(self) -> bool:
        return self.status == "provisional" or self.account_status == "provisional"


class CrownIdentityCore:
    """Canonical account resolver.

    Telegram is an identity provider, never the permanent product primary key.
    Resolution is server-side through the shared Supabase GAME authority.
    """

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    def resolve_telegram(self, telegram_user_id: int) -> CrownIdentity | None:
        resolver = getattr(self.storage, "resolve_telegram_identity", None)
        if not callable(resolver):
            return None
        raw = resolver(int(telegram_user_id))
        if not isinstance(raw, dict) or not raw.get("black_crown_user_id"):
            return None
        return CrownIdentity(
            black_crown_user_id=str(raw["black_crown_user_id"]),
            provider="telegram",
            status=str(raw.get("identity_status") or "provisional"),
            account_status=str(raw.get("account_status") or "provisional"),
        )
