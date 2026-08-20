# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qsl

from fastapi import HTTPException


log = logging.getLogger("bco.webapp.security")
Verifier = Callable[[str], tuple[bool, dict]]


@dataclass(frozen=True)
class TrustedTelegramContext:
    """Verified Mini App identity with no client-owned profile authority."""

    request_id: str
    identity: int
    meta: dict[str, Any]


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def safe_http_error(
    status_code: int,
    code: str,
    request_id: str,
    *,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> HTTPException:
    detail: dict[str, Any] = {
        "code": str(code or "request_failed")[:64],
        "request_id": str(request_id or new_request_id())[:32],
    }
    for key, value in extra.items():
        if value is not None:
            detail[str(key)[:64]] = value
    return HTTPException(status_code=int(status_code), detail=detail, headers=headers)


def bot_token() -> str:
    return (
        (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        or (os.getenv("BOT_TOKEN") or "").strip()
        or (os.getenv("TG_BOT_TOKEN") or "").strip()
    )


def verify_init_data(
    init_data: str,
    *,
    token: str | None = None,
    max_age_sec: int | None = 86400,
) -> tuple[bool, dict]:
    """Validate Telegram Mini App initData per Telegram Web Apps spec."""
    raw = (init_data or "").strip()
    token = (token or bot_token()).strip()
    if not raw or not token:
        return False, {}

    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    their_hash = pairs.pop("hash", None)
    if not their_hash:
        return False, {}

    data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, their_hash):
        return False, {}

    if max_age_sec is not None:
        try:
            auth_date = int(pairs.get("auth_date") or "0")
            if auth_date <= 0 or abs(int(time.time()) - auth_date) > int(max_age_sec):
                return False, {}
        except Exception:
            return False, {}

    user_id = None
    chat_id = None
    try:
        if pairs.get("user"):
            user_id = json.loads(pairs["user"]).get("id")
    except Exception:
        pass
    try:
        if pairs.get("chat"):
            chat_id = json.loads(pairs["chat"]).get("id")
    except Exception:
        pass

    return True, {
        "user_id": user_id,
        "chat_id": chat_id,
        "auth_date": pairs.get("auth_date"),
        "query_id": pairs.get("query_id"),
    }


def require_trusted_init_data(
    init_data: str,
    *,
    verifier: Verifier | None = None,
    request_id: str | None = None,
) -> TrustedTelegramContext:
    """Fail closed before any paid operation or server-owned context read.

    Raw initData is intentionally never included in logs or response details.
    A verified Telegram ``user_id`` is required; a browser-supplied identity,
    profile, history, Premium flag, or canonical account ID is never accepted.
    """

    rid = str(request_id or new_request_id())[:32]
    raw = str(init_data or "").strip()
    if not raw:
        raise safe_http_error(
            401,
            "telegram_auth_required",
            rid,
            legacy_code="trusted_telegram_context_required",
        )

    check = verifier or verify_init_data
    try:
        trusted, raw_meta = check(raw)
    except Exception as exc:
        log.exception(
            "telegram initData verification unavailable request_id=%s error=%s",
            rid,
            type(exc).__name__,
        )
        raise safe_http_error(503, "telegram_auth_unavailable", rid) from None

    if not trusted:
        raise safe_http_error(403, "telegram_auth_invalid", rid)

    meta = dict(raw_meta or {})
    try:
        identity = int(meta.get("user_id"))
    except Exception:
        raise safe_http_error(403, "telegram_identity_missing", rid) from None
    if identity <= 0:
        raise safe_http_error(403, "telegram_identity_missing", rid)

    # Retain only bounded verification metadata. Never retain or return raw
    # initData, Telegram username, or any client-submitted account authority.
    safe_meta = {
        "user_id": identity,
        "chat_id": meta.get("chat_id"),
        "auth_date": str(meta.get("auth_date") or "")[:24],
        "query_id": str(meta.get("query_id") or "")[:128],
    }
    return TrustedTelegramContext(request_id=rid, identity=identity, meta=safe_meta)


def enforce_usage_limit(
    usage_guard: Any,
    subject: Any,
    category: str,
    request_id: str,
) -> None:
    """Apply the shared process-wide subject and global cost guard."""

    rid = str(request_id or new_request_id())[:32]
    normalized = str(category or "").strip().lower()[:32] or "unknown"
    if usage_guard is None or not callable(getattr(usage_guard, "check", None)):
        log.error(
            "usage guard unavailable request_id=%s category=%s",
            rid,
            normalized,
        )
        raise safe_http_error(503, "usage_guard_unavailable", rid, category=normalized)

    try:
        decision = usage_guard.check(subject, normalized)
    except Exception as exc:
        log.exception(
            "usage guard failed request_id=%s category=%s error=%s",
            rid,
            normalized,
            type(exc).__name__,
        )
        raise safe_http_error(503, "usage_guard_unavailable", rid, category=normalized) from None

    if bool(getattr(decision, "allowed", True)):
        return

    retry_after = max(1, int(getattr(decision, "retry_after_s", 1) or 1))
    raise safe_http_error(
        429,
        "rate_limited",
        rid,
        headers={"Retry-After": str(retry_after)},
        category=normalized,
        retry_after_s=retry_after,
    )
