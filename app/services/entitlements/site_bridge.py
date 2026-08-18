# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.services.entitlements.service import EntitlementStatus, PremiumEntitlementService

log = logging.getLogger("bco.entitlements.site_bridge")

_DEFAULT_VERIFY_URL = "https://blackcrown.work/api/me"
_ALLOWED_VERIFY_HOSTS = {"blackcrown.work", "www.blackcrown.work"}
_MAX_BODY_BYTES = 2_048
_ASSERTION_VERSION = "v1"
_ASSERTION_MAX_SKEW_S = 90


def _json(body: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def _safe_site_user(value: Any) -> str:
    text = str(value or "").strip()
    if not 1 <= len(text) <= 160:
        return ""
    if not all(ch.isalnum() or ch in "_.:@-" for ch in text):
        return ""
    return text


def _safe_session_token(value: Any) -> str:
    token = str(value or "").strip()
    if not 24 <= len(token) <= 4096:
        return ""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return ""
    if not all(part and all(ch.isalnum() or ch in "-_" for ch in part) for part in parts[1:]):
        return ""
    return token


def _safe_code(value: Any) -> str:
    code = str(value or "").strip()
    if not 32 <= len(code) <= 128:
        return ""
    if not all(ch.isalnum() or ch in "-_" for ch in code):
        return ""
    return code


def _safe_nonce(value: Any) -> str:
    nonce = str(value or "").strip()
    if not 16 <= len(nonce) <= 96:
        return ""
    return nonce if all(ch.isalnum() or ch in "-_" for ch in nonce) else ""


def _status_payload(status: EntitlementStatus) -> dict[str, Any]:
    return {
        "ok": True,
        "linked": status.linked,
        "premium": status.premium,
        "entitlements": list(status.entitlements),
        "linkedAt": status.linked_at,
    }


class SiteIdentityAssertionVerifier:
    """Verifies a short-lived assertion issued only after Pages validates bc_session."""

    def __init__(self, secret: str | None = None):
        self._secret = str(secret if secret is not None else os.getenv("BLACKCROWN_SITE_BRIDGE_SECRET", "")).strip()

    @property
    def configured(self) -> bool:
        return len(self._secret) >= 32

    def verify(self, *, assertion: str, site_user: str, method: str, path: str) -> str:
        if not self.configured:
            raise RuntimeError("site_assertion_not_configured")
        safe_user = _safe_site_user(site_user)
        parts = str(assertion or "").strip().split(".")
        if len(parts) != 4 or parts[0] != _ASSERTION_VERSION or not safe_user:
            raise PermissionError("auth_required")
        _, raw_ts, nonce, signature = parts
        safe_nonce = _safe_nonce(nonce)
        try:
            issued_at = int(raw_ts)
        except (TypeError, ValueError):
            raise PermissionError("auth_required") from None
        now = int(time.time())
        if abs(now - issued_at) > _ASSERTION_MAX_SKEW_S or not safe_nonce:
            raise PermissionError("auth_required")
        normalized_method = str(method or "").strip().upper()
        normalized_path = str(path or "").strip()
        payload = f"blackcrown:site-bridge:{_ASSERTION_VERSION}:{issued_at}:{safe_nonce}:{normalized_method}:{normalized_path}:{safe_user}"
        expected = hmac.new(self._secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PermissionError("auth_required")
        return safe_user


class SiteSessionVerifier:
    """Legacy fallback: independently asks blackcrown.work to verify its signed session cookie."""

    def __init__(self, settings: Any, *, client: httpx.AsyncClient | None = None):
        raw_url = str(getattr(settings, "blackcrown_session_verify_url", "") or _DEFAULT_VERIFY_URL).strip()
        parsed = urlsplit(raw_url)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_VERIFY_HOSTS or parsed.path != "/api/me":
            raise ValueError("blackcrown_verify_url_invalid")
        timeout_s = max(2.0, min(float(getattr(settings, "site_session_verify_timeout_s", 10.0) or 10.0), 20.0))
        self._url = raw_url
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def verify(self, *, token: str, expected_user_id: str) -> str:
        safe_token = _safe_session_token(token)
        expected = _safe_site_user(expected_user_id)
        if not safe_token or not expected:
            raise PermissionError("auth_required")
        response = await self._client.get(
            self._url,
            headers={
                "accept": "application/json",
                "cookie": f"bc_session={safe_token}",
                "user-agent": "BLACK-CROWN-OPS/site-session-verifier-v13",
            },
        )
        if response.status_code != 200:
            raise PermissionError("auth_required")
        try:
            payload = response.json()
        except Exception as exc:
            raise PermissionError("auth_required") from exc
        profile = payload.get("profile") if isinstance(payload, dict) else None
        verified = _safe_site_user(profile.get("id") if isinstance(profile, dict) else "")
        if not verified:
            raise PermissionError("auth_required")
        if verified != expected:
            raise PermissionError("site_session_mismatch")
        return verified


class SiteEntitlementBridgeAPI:
    def __init__(
        self,
        *,
        settings: Any,
        entitlements: PremiumEntitlementService,
        verifier: SiteSessionVerifier | None = None,
        assertion_verifier: SiteIdentityAssertionVerifier | None = None,
    ):
        self.entitlements = entitlements
        self.verifier = verifier or SiteSessionVerifier(settings)
        self.assertion_verifier = assertion_verifier or SiteIdentityAssertionVerifier()
        self.router = APIRouter()
        self._bind_routes()

    async def close(self) -> None:
        await self.verifier.close()

    async def _identity(
        self,
        *,
        token: str | None,
        site_user: str | None,
        assertion: str | None,
        method: str,
        path: str,
    ) -> str:
        if assertion and self.assertion_verifier.configured:
            return self.assertion_verifier.verify(
                assertion=str(assertion),
                site_user=str(site_user or ""),
                method=method,
                path=path,
            )
        return await self.verifier.verify(token=str(token or ""), expected_user_id=str(site_user or ""))

    def _bind_routes(self) -> None:
        @self.router.post("/integrations/site/telegram/link", include_in_schema=False)
        async def complete_link(
            request: Request,
            x_bc_session_token: str | None = Header(default=None),
            x_bc_site_user: str | None = Header(default=None),
            x_bc_site_assertion: str | None = Header(default=None),
        ):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > _MAX_BODY_BYTES:
                        return _json({"ok": False, "reason": "payload_too_large"}, 413)
                except ValueError:
                    pass
            body_bytes = await request.body()
            if len(body_bytes) > _MAX_BODY_BYTES:
                return _json({"ok": False, "reason": "payload_too_large"}, 413)
            try:
                import json
                raw = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                return _json({"ok": False, "reason": "invalid_json"}, 400)
            if not isinstance(raw, dict):
                return _json({"ok": False, "reason": "invalid_json"}, 400)
            code = _safe_code(raw.get("code"))
            if not code:
                return _json({"ok": False, "reason": "invalid_or_expired_code"}, 400)
            try:
                site_user_id = await self._identity(
                    token=x_bc_session_token,
                    site_user=x_bc_site_user,
                    assertion=x_bc_site_assertion,
                    method="POST",
                    path="/integrations/site/telegram/link",
                )
            except PermissionError as exc:
                reason = str(exc) if str(exc) in {"auth_required", "site_session_mismatch"} else "auth_required"
                return _json({"ok": False, "reason": reason}, 401)
            except Exception as exc:
                log.warning("site identity verification failed error=%s", type(exc).__name__)
                return _json({"ok": False, "reason": "site_identity_unavailable"}, 503)
            try:
                status = await self.entitlements.complete_site_link(code=code, site_user_id=site_user_id)
                return _json(_status_payload(status))
            except (ValueError, RuntimeError) as exc:
                reason = str(exc)[:80] or "link_failed"
                code_status = 409 if reason in {"site_already_linked", "telegram_already_linked", "link_conflict"} else 400
                return _json({"ok": False, "reason": reason}, code_status)
            except Exception as exc:
                log.warning("site link completion failed error=%s", type(exc).__name__)
                return _json({"ok": False, "reason": "link_service_unavailable"}, 503)

        @self.router.get("/integrations/site/telegram/status", include_in_schema=False)
        async def site_status(
            x_bc_session_token: str | None = Header(default=None),
            x_bc_site_user: str | None = Header(default=None),
            x_bc_site_assertion: str | None = Header(default=None),
        ):
            try:
                site_user_id = await self._identity(
                    token=x_bc_session_token,
                    site_user=x_bc_site_user,
                    assertion=x_bc_site_assertion,
                    method="GET",
                    path="/integrations/site/telegram/status",
                )
            except PermissionError as exc:
                reason = str(exc) if str(exc) in {"auth_required", "site_session_mismatch"} else "auth_required"
                return _json({"ok": False, "reason": reason}, 401)
            except Exception as exc:
                log.warning("site identity verification failed error=%s", type(exc).__name__)
                return _json({"ok": False, "reason": "site_identity_unavailable"}, 503)
            try:
                status = await self.entitlements.get_site_status(site_user_id)
                return _json(_status_payload(status))
            except Exception as exc:
                log.warning("site entitlement status failed error=%s", type(exc).__name__)
                return _json({"ok": False, "reason": "link_service_unavailable"}, 503)
