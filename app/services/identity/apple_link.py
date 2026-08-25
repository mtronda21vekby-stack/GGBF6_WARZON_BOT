from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx


_EXPECTED_SUPABASE_HOST = "wqriwhciqvrbhkkiuhxb.supabase.co"
_SAFE_BOT_USERNAME = re.compile(r"^[A-Za-z0-9_]{5,32}$")
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_ALLOWED_RPCS = {
    "black_crown_start_apple_telegram_link",
    "black_crown_get_apple_telegram_link_status",
    "black_crown_cancel_apple_telegram_link",
    "black_crown_complete_apple_telegram_link",
}


class AppleIdentityLinkRejected(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = str(reason or "account_link_rejected")[:80]
        super().__init__(self.reason)


@dataclass(frozen=True)
class AppleIdentityLinkChallenge:
    link_id: UUID
    verification_url: str
    expires_at: str
    ttl_seconds: int


@dataclass(frozen=True)
class AppleIdentityLinkStatus:
    status: str
    expires_at: str | None = None
    replayed: bool = False


class AppleIdentityLinkService:
    """Service-only Apple-to-canonical linking through verified Telegram proof."""

    def __init__(self, settings: Any, *, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = str(getattr(settings, "supabase_url", "") or "").strip().rstrip("/")
        self._service_key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()
        self._bot_username = str(
            getattr(settings, "telegram_bot_username", "") or "GGBF6_WARZON_BOT"
        ).strip().lstrip("@")
        self._ttl_seconds = max(
            60,
            min(int(getattr(settings, "apple_account_link_ttl_s", 600) or 600), 900),
        )
        timeout = max(
            2.0,
            min(float(getattr(settings, "apple_account_link_timeout_s", 8.0) or 8.0), 20.0),
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self._last_error = ""
        self._last_success_at: str | None = None

    @property
    def configured(self) -> bool:
        if not self._service_key or self._service_key.startswith("sb_publishable_"):
            return False
        try:
            parsed = urlsplit(self._base_url)
        except Exception:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == _EXPECTED_SUPABASE_HOST
            and _SAFE_BOT_USERNAME.fullmatch(self._bot_username) is not None
        )

    def readiness(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error[:64],
        }

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def start(self, apple_subject: str) -> AppleIdentityLinkChallenge:
        subject = self._subject(apple_subject)
        code = secrets.token_urlsafe(24)
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        raw = await self._rpc(
            "black_crown_start_apple_telegram_link",
            {
                "p_apple_subject": subject,
                "p_code_hash": code_hash,
                "p_ttl_seconds": self._ttl_seconds,
            },
        )
        if raw.get("status") == "linked":
            raise AppleIdentityLinkRejected("apple_identity_already_linked")
        try:
            link_id = UUID(str(raw.get("link_id") or ""))
        except ValueError as exc:
            raise RuntimeError("account_link_invalid_response") from exc
        expires_at = str(raw.get("expires_at") or "")
        if not expires_at:
            raise RuntimeError("account_link_invalid_response")
        ttl = max(60, min(int(raw.get("ttl_seconds") or self._ttl_seconds), 900))
        payload = quote(f"crownlink_{code}", safe="-_")
        return AppleIdentityLinkChallenge(
            link_id=link_id,
            verification_url=f"https://t.me/{self._bot_username}?start={payload}",
            expires_at=expires_at,
            ttl_seconds=ttl,
        )

    async def status(self, *, link_id: UUID, apple_subject: str) -> AppleIdentityLinkStatus:
        raw = await self._rpc(
            "black_crown_get_apple_telegram_link_status",
            {"p_link_id": str(link_id), "p_apple_subject": self._subject(apple_subject)},
        )
        status = self._status(raw.get("status"))
        return AppleIdentityLinkStatus(status=status, expires_at=str(raw.get("expires_at") or "") or None)

    async def cancel(self, *, link_id: UUID, apple_subject: str) -> AppleIdentityLinkStatus:
        raw = await self._rpc(
            "black_crown_cancel_apple_telegram_link",
            {"p_link_id": str(link_id), "p_apple_subject": self._subject(apple_subject)},
        )
        return AppleIdentityLinkStatus(status=self._status(raw.get("status")))

    async def complete_from_telegram(
        self,
        *,
        code: str,
        telegram_user_id: int,
    ) -> AppleIdentityLinkStatus:
        safe_code = str(code or "").strip()
        if _SAFE_CODE.fullmatch(safe_code) is None:
            raise AppleIdentityLinkRejected("invalid_or_expired_code")
        user_id = int(telegram_user_id)
        if user_id <= 0:
            raise AppleIdentityLinkRejected("invalid_telegram_identity")
        raw = await self._rpc(
            "black_crown_complete_apple_telegram_link",
            {"p_code": safe_code, "p_telegram_user_id": user_id},
        )
        return AppleIdentityLinkStatus(
            status=self._status(raw.get("status")),
            replayed=raw.get("replayed") is True,
        )

    async def _rpc(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in _ALLOWED_RPCS:
            raise ValueError("account_link_rpc_not_allowed")
        if not self.configured:
            raise RuntimeError("account_link_not_configured")
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "apikey": self._service_key,
            "user-agent": "BLACK-CROWN-OPS/apple-link-v1",
        }
        if not self._service_key.startswith("sb_secret_"):
            headers["authorization"] = f"Bearer {self._service_key}"
        try:
            response = await self._client.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict):
                raise RuntimeError("account_link_invalid_response")
            if raw.get("ok") is not True:
                raise AppleIdentityLinkRejected(str(raw.get("reason") or "account_link_rejected"))
            self._last_error = ""
            self._last_success_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return raw
        except AppleIdentityLinkRejected:
            self._last_error = "AppleIdentityLinkRejected"
            raise
        except Exception as exc:
            self._last_error = type(exc).__name__
            raise

    @staticmethod
    def _subject(value: str) -> str:
        try:
            return str(UUID(str(value or "")))
        except ValueError as exc:
            raise AppleIdentityLinkRejected("invalid_apple_identity") from exc

    @staticmethod
    def _status(value: Any) -> str:
        status = str(value or "")
        if status not in {"pending", "linked", "expired", "cancelled", "conflict"}:
            raise RuntimeError("account_link_invalid_response")
        return status
