# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Header
from fastapi.responses import StreamingResponse

from app.webapp import webapp_router_base as _base


log = logging.getLogger("webapp.live")

# Preserve the established static routes and runtime binding. This module only
# adds the v18 live-intelligence transport to the same APIRouter instance.
router = _base.router
bind_runtime = _base.bind_runtime
AskBody = _base.AskBody
webapp_root = _base.webapp_root
webapp_health = _base.webapp_health
webapp_version = _base.webapp_version
webapp_files = _base.webapp_files
webapp_api_ask = _base.webapp_api_ask
webapp_game_event = _base.webapp_game_event


def __getattr__(name: str) -> Any:
    return getattr(_base, name)


def _ndjson(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _queue_latest_partial(
    queue: asyncio.Queue[dict[str, Any]],
    payload: dict[str, Any],
) -> None:
    """Bound partial-state pressure without dropping final/control events."""
    if not queue.full():
        queue.put_nowait(payload)
        return

    buffered: list[dict[str, Any]] = []
    removed = False
    try:
        while True:
            item = queue.get_nowait()
            queue.task_done()
            if not removed and item.get("type") == "partial":
                removed = True
                continue
            buffered.append(item)
    except asyncio.QueueEmpty:
        pass

    for item in buffered[-30:]:
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            break
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


@router.post("/webapp/api/ask/stream")
async def webapp_api_ask_stream(
    body: AskBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_bco_version: str | None = Header(default=None, alias="X-BCO-Version"),
):
    """Stream one Intelligence Core answer as newline-delimited JSON.

    The trusted identity/profile boundary is identical to `/webapp/api/ask`.
    The final event is authoritative; partial events are presentation-only and
    may be coalesced by the client.
    """
    text = str(body.text or "").strip()
    build = _base._build_id()
    if not text:
        async def empty_stream() -> AsyncIterator[bytes]:
            yield _ndjson({"type": "error", "error": "empty_text", "build": build})
        return StreamingResponse(
            empty_stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            status_code=400,
        )

    init_data = str(x_telegram_init_data or body.initData or "").strip()
    trusted, raw_meta = _base.verify_init_data(init_data)
    meta = dict(raw_meta or {})
    if trusted:
        profile, history, identity = _base._trusted_server_context(meta)
        meta["trusted"] = True
        meta["identity"] = identity
    else:
        profile = _base._safe_profile(body.profile)
        history = _base._safe_history(body.history)
        meta = {"untrusted": True, "trusted": False}

    request_id = uuid.uuid4().hex[:12]
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
    loop = asyncio.get_running_loop()
    sequence = 0

    def on_partial(partial_text: str, partial_meta: dict[str, Any] | None = None) -> None:
        nonlocal sequence
        sequence += 1
        payload = {
            "type": "partial",
            "seq": sequence,
            "text": str(partial_text or ""),
            "phase": str((partial_meta or {}).get("phase") or "generating")[:32],
            "reset": bool((partial_meta or {}).get("reset")),
            "attempt": max(1, int((partial_meta or {}).get("attempt") or 1)),
        }
        try:
            loop.call_soon_threadsafe(_queue_latest_partial, queue, payload)
        except RuntimeError:
            pass

    async def generate() -> str:
        brain = _base.APP_BRAIN
        settings = _base.APP_SETTINGS
        ai_key = str(getattr(settings, "openai_api_key", "") or "").strip() if settings else ""
        ai_enabled = bool(getattr(settings, "ai_enabled", True)) if settings else True
        stream_enabled = bool(getattr(settings, "webapp_live_stream_enabled", True)) if settings else True
        ai_on = bool(ai_enabled and ai_key and brain and hasattr(brain, "reply"))
        if not ai_on:
            return (
                "🧠 AI сейчас недоступен. Проверь серверную конфигурацию "
                "OPENAI_API_KEY, AI_ENABLED и OPENAI_MODEL."
            )

        fn = brain.reply
        kwargs: dict[str, Any] = {
            "text": text,
            "profile": profile,
            "history": history,
        }
        if stream_enabled:
            kwargs["on_partial"] = on_partial

        if inspect.iscoroutinefunction(fn):
            try:
                return str(await fn(**kwargs))
            except TypeError as exc:
                if "on_partial" not in str(exc):
                    raise
                kwargs.pop("on_partial", None)
                return str(await fn(**kwargs))

        try:
            return str(await asyncio.to_thread(fn, **kwargs))
        except TypeError as exc:
            if "on_partial" not in str(exc):
                raise
            kwargs.pop("on_partial", None)
            return str(await asyncio.to_thread(fn, **kwargs))

    async def event_stream() -> AsyncIterator[bytes]:
        started = time.monotonic()
        yield _ndjson(
            {
                "type": "meta",
                "ok": True,
                "request_id": request_id,
                "trusted": bool(trusted),
                "build": build,
                "bco_version": str(x_bco_version or "")[:64],
            }
        )

        task = asyncio.create_task(generate(), name=f"bco-webapp-stream-{request_id}")
        try:
            while not task.done():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.35)
                except asyncio.TimeoutError:
                    yield _ndjson(
                        {
                            "type": "pulse",
                            "request_id": request_id,
                            "elapsed_ms": int((time.monotonic() - started) * 1000),
                        }
                    )
                    continue
                try:
                    yield _ndjson(event)
                finally:
                    queue.task_done()

            while not queue.empty():
                event = queue.get_nowait()
                try:
                    yield _ndjson(event)
                finally:
                    queue.task_done()

            reply = await task
            yield _ndjson(
                {
                    "type": "final",
                    "ok": True,
                    "request_id": request_id,
                    "reply": str(reply),
                    "trusted": bool(trusted),
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "build": build,
                    "meta": meta,
                }
            )
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:
            log.exception("webapp live generation failed request_id=%s error=%s", request_id, type(exc).__name__)
            yield _ndjson(
                {
                    "type": "error",
                    "ok": False,
                    "request_id": request_id,
                    "error": "generation_unavailable",
                    "error_class": type(exc).__name__,
                    "build": build,
                }
            )
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
            "X-BCO-Stream": "live-intelligence-v18",
        },
    )
