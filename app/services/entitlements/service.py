# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

log = logging.getLogger("bco.entitlements")

_EXPECTED_SUPABASE_HOST = "wqriwhciqvrbhkkiuhxb.supabase.co"
_EXPECTED_SITE_HOSTS = {"blackcrown.work", "www.blackcrown.work"}
_RPC_CREATE_LINK = "blackcrown_create_telegram_link_challenge"
_RPC_COMPLETE_LINK = "blackcrown_complete_telegram_link"
_RPC_TELEGRAM_STATUS = "blackcrown_get_telegram_entitlement_status"
_RPC_SITE_STATUS = "blackcrown_get_site_telegram_status"
_RPC_UNLINK = "blackcrown_unlink_telegram"
_ALLOWED_RPCS = {
    _RPC_CREATE_LINK,
    _RPC_COMPLETE_LINK,
    _RPC_TELEGRAM_STATUS,
    _RPC_SITE_STATUS,
    _RPC_UNLINK,
}


@dataclass(frozen=True)
class LinkChallenge:
    code: str
    url: str
    expires_at: str | None
    ttl_seconds: int


@dataclass(frozen=True)
class EntitlementStatus:
    linked: bool = False
    premium: bool = False
    entitlements: tuple[str, ...] = ()
    site_user_id: str | None = None
    linked_at: str | None = None


class PremiumEntitlementService:
    """Server-only bridge between Telegram identity and Supabase GAME.

    The bot creates the one-time token and stores only its SHA-256 hash through
    a service-role-only RPC. Account linking never creates Premium ownership;
    `bco_premium` must already exist as an authoritative entitlement row.
    """

    def __init__(self, settings: Any, *, client: httpx.AsyncClient | None = None):
        self._enabled = bool(getattr(settings, "premium_link_enabled", True))
        self._base_url = str(getattr(settings, "supabase_url", "") or "").strip().rstrip("/")
        self._service_key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()
        self._account_url = str(
            getattr(settings, "blackcrown_account_url", "")
            or "https://blackcrown.work/account/telegram"
        ).strip()
        self._ttl_seconds = max(60, min(int(getattr(settings, "premium_link_ttl_s", 600) or 600), 900))
        timeout_s = max(2.0, min(float(getattr(settings, "entitlement_timeout_s", 8.0) or 8.0), 20.0))
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))
        self._last_error = ""
        self._last_success_at: str | None = None

    @property
    def configured(self) -> bool:
        if not self._enabled:
            return False
        if not self._service_key or self._service_key.startswith("sb_publishable_"):
            return False
        try:
            parsed = urlsplit(self._base_url)
            site = urlsplit(self._account_url)
        except Exception:
            return False
        return (
            parsed.scheme == "https"
            and parsed.hostname == _EXPECTED_SUPABASE_HOST
            and site.scheme == "https"
            and site.hostname in _EXPECTED_SITE_HOSTS
        )

    def readiness(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "configured": self.configured,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error[:64],
        }

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise RuntimeError("premium_link_not_configured")
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "apikey": self._service_key,
            "user-agent": "BLACK-CROWN-OPS/premium-link-v13",
        }
        # Modern sb_secret_* keys are opaque API keys and must not be sent as
        # JWT Bearer tokens. Legacy service-role JWTs retain compatibility.
        if not self._service_key.startswith("sb_secret_"):
            headers["authorization"] = f"Bearer {self._service_key}"
        return headers

    async def _rpc(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name not in _ALLOWED_RPCS:
            raise ValueError("premium_rpc_not_allowed")
        try:
            response = await self._client.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()
            if not isinstance(raw, dict):
                raise RuntimeError("premium_rpc_invalid_response")
            if raw.get("ok") is not True:
                reason = str(raw.get("reason") or "premium_rpc_rejected")[:80]
                raise RuntimeError(reason)
            self._last_error = ""
            self._last_success_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return raw
        except Exception as exc:
            self._last_error = type(exc).__name__
            raise

    @staticmethod
    def _safe_username(value: str | None) -> str | None:
        text = "".join(ch for ch in str(value or "") if ch.isalnum() or ch == "_")[:64]
        return text or None

    @staticmethod
    def _safe_site_user_id(value: Any) -> str:
        text = str(value or "").strip()
        if not 1 <= len(text) <= 160:
            return ""
        if not all(ch.isalnum() or ch in "_.:@-" for ch in text):
            return ""
        return text

    @staticmethod
    def _safe_code(value: Any) -> str:
        text = str(value or "").strip()
        if not 32 <= len(text) <= 128:
            return ""
        if not all(ch.isalnum() or ch in "-_" for ch in text):
            return ""
        return text

    @staticmethod
    def _normalize_entitlements(value: Any) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        result: list[str] = []
        seen: set[str] = set()
        for item in value[:100]:
            key = str(item or "").strip()
            if not key or len(key) > 80:
                continue
            if not all(ch.islower() or ch.isdigit() or ch in "_.:-" for ch in key):
                continue
            if key not in seen:
                seen.add(key)
                result.append(key)
        return tuple(result)

    @classmethod
    def _status_from_raw(cls, raw: dict[str, Any]) -> EntitlementStatus:
        entitlements = cls._normalize_entitlements(raw.get("entitlements"))
        site_user_id = cls._safe_site_user_id(raw.get("site_user_id")) or None
        return EntitlementStatus(
            linked=raw.get("linked") is True,
            premium=raw.get("premium") is True and "bco_premium" in entitlements,
            entitlements=entitlements,
            site_user_id=site_user_id,
            linked_at=(str(raw.get("linked_at") or "")[:64] or None),
        )

    async def create_link_challenge(
        self,
        *,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_username: str | None = None,
    ) -> LinkChallenge:
        user_id = int(telegram_user_id)
        chat_id = int(telegram_chat_id)
        if user_id <= 0:
            raise ValueError("invalid_telegram_identity")

        code = secrets.token_urlsafe(24)  # 192 bits, normally 32 URL-safe chars.
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        raw = await self._rpc(
            _RPC_CREATE_LINK,
            {
                "p_code_hash": code_hash,
                "p_telegram_user_id": user_id,
                "p_telegram_chat_id": chat_id,
                "p_telegram_username": self._safe_username(telegram_username),
                "p_ttl_seconds": self._ttl_seconds,
            },
        )
        ttl = max(60, min(int(raw.get("ttl_seconds") or self._ttl_seconds), 900))
        base = self._account_url.split("#", 1)[0]
        url = f"{base}#telegram-link={quote(code, safe='-_')}"
        return LinkChallenge(
            code=code,
            url=url,
            expires_at=str(raw.get("expires_at") or "") or None,
            ttl_seconds=ttl,
        )

    async def get_status(self, telegram_user_id: int) -> EntitlementStatus:
        user_id = int(telegram_user_id)
        if user_id <= 0:
            raise ValueError("invalid_telegram_identity")
        raw = await self._rpc(_RPC_TELEGRAM_STATUS, {"p_telegram_user_id": user_id})
        return self._status_from_raw(raw)

    async def complete_site_link(self, *, code: str, site_user_id: str) -> EntitlementStatus:
        safe_code = self._safe_code(code)
        safe_user = self._safe_site_user_id(site_user_id)
        if not safe_code:
            raise ValueError("invalid_or_expired_code")
        if not safe_user:
            raise ValueError("invalid_site_user")
        raw = await self._rpc(
            _RPC_COMPLETE_LINK,
            {"p_code": safe_code, "p_site_user_id": safe_user},
        )
        return self._status_from_raw({**raw, "site_user_id": safe_user})

    async def get_site_status(self, site_user_id: str) -> EntitlementStatus:
        safe_user = self._safe_site_user_id(site_user_id)
        if not safe_user:
            raise ValueError("invalid_site_user")
        raw = await self._rpc(_RPC_SITE_STATUS, {"p_site_user_id": safe_user})
        return self._status_from_raw({**raw, "site_user_id": safe_user})

    async def unlink(self, telegram_user_id: int) -> bool:
        user_id = int(telegram_user_id)
        if user_id <= 0:
            raise ValueError("invalid_telegram_identity")
        raw = await self._rpc(_RPC_UNLINK, {"p_telegram_user_id": user_id})
        return raw.get("unlinked") is True
