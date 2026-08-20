# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException


log = logging.getLogger("bco.webapp.security_boundary")


@dataclass(frozen=True)
class TrustedWebAppContext:
    """Server-resolved Mini App identity and product context."""

    chat_id: int
    profile: dict[str, Any]
    history: list[dict[str, Any]]
    meta: dict[str, Any]


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def safe_http_exception(
    status_code: int,
    error: str,
    request_id: str,
    *,
    retry_after_s: int = 0,
) -> HTTPException:
    headers = {
        "Cache-Control": "no-store",
        "X-Request-ID": str(request_id),
    }
    if retry_after_s > 0:
        headers["Retry-After"] = str(max(1, int(retry_after_s)))
    return HTTPException(
        status_code=int(status_code),
        detail={
            "error": str(error or "request_failed")[:80],
            "request_id": str(request_id),
        },
        headers=headers,
    )


def _safe_history(history: Any) -> list[dict[str, Any]]:
    if not isinstance(history, list):
        return []
    out: list[dict[str, Any]] = []
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or item.get("text") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        row: dict[str, Any] = {"role": role, "content": content[:2000]}
        if item.get("ts") is not None:
            row["ts"] = item.get("ts")
        out.append(row)
    return out


def resolve_trusted_telegram_context(
    *,
    init_data: str,
    verifier: Callable[[str], tuple[bool, dict]],
    profiles: Any,
    store: Any,
    request_id: str,
) -> TrustedWebAppContext:
    """Resolve trusted Telegram identity without accepting browser authority."""

    raw = str(init_data or "").strip()
    if not raw:
        raise safe_http_exception(401, "telegram_auth_required", request_id)

    try:
        trusted, raw_meta = verifier(raw)
    except Exception as exc:
        log.warning(
            "telegram initData verification failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(403, "telegram_auth_invalid", request_id)

    if not trusted:
        raise safe_http_exception(403, "telegram_auth_invalid", request_id)

    meta = dict(raw_meta or {})
    identity = meta.get("chat_id") or meta.get("user_id")
    try:
        chat_id = int(identity)
    except Exception:
        raise safe_http_exception(403, "telegram_identity_missing", request_id)

    if profiles is None or store is None:
        raise safe_http_exception(503, "trusted_context_unavailable", request_id)

    try:
        profile = dict(profiles.get(chat_id) or {})
    except Exception as exc:
        log.warning(
            "server profile resolution failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(503, "trusted_context_unavailable", request_id)

    try:
        history = _safe_history(list(store.get(chat_id) or []))
    except Exception as exc:
        log.warning(
            "server history resolution failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(503, "trusted_context_unavailable", request_id)

    return TrustedWebAppContext(
        chat_id=chat_id,
        profile=profile,
        history=history,
        meta={
            "trusted": True,
            "authority": "verified_telegram_server_context",
        },
    )


def enforce_usage(
    usage_guard: Any,
    subject: Any,
    category: str,
    request_id: str,
) -> None:
    """Fail closed before an expensive operation when cost protection is absent."""

    normalized = str(category or "").strip().lower()
    if usage_guard is None:
        log.error(
            "usage guard unavailable request_id=%s category=%s",
            request_id,
            normalized or "unknown",
        )
        raise safe_http_exception(503, "usage_guard_unavailable", request_id)

    try:
        decision = usage_guard.check(subject, normalized)
    except Exception as exc:
        log.error(
            "usage guard failed request_id=%s category=%s error=%s",
            request_id,
            normalized or "unknown",
            type(exc).__name__,
        )
        raise safe_http_exception(503, "usage_guard_unavailable", request_id)

    if bool(getattr(decision, "allowed", False)):
        return

    retry_after_s = max(1, int(getattr(decision, "retry_after_s", 1) or 1))
    log.info(
        "expensive operation limited request_id=%s category=%s scope=%s retry_after_s=%s",
        request_id,
        normalized or "unknown",
        str(getattr(decision, "scope", "subject") or "subject")[:16],
        retry_after_s,
    )
    raise safe_http_exception(
        429,
        "rate_limited",
        request_id,
        retry_after_s=retry_after_s,
    )


def mark_usage_reserved(profile: dict[str, Any], category: str) -> dict[str, Any]:
    """Attach an internal, non-persistent reservation marker to server context."""

    out = dict(profile or {})
    raw_reserved = out.get("_usage_guard_reserved")
    items = raw_reserved if isinstance(raw_reserved, (list, tuple, set)) else ()
    reserved = {
        str(item).strip().lower()
        for item in items
        if str(item).strip()
    }
    reserved.add(str(category or "").strip().lower())
    out["_usage_guard_reserved"] = sorted(reserved)
    return out
