# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Header
from fastapi.responses import StreamingResponse

from app.webapp import webapp_router_base as _base
from app.webapp import voice_router as _voice


log = logging.getLogger("webapp.live")

# Preserve established static/chat routes and compose voice as an isolated
# surface on the same APIRouter. The base router remains independently stable.
router = _base.router
router.include_router(_voice.router)
AskBody = _base.AskBody
webapp_root = _base.webapp_root
webapp_health = _base.webapp_health
webapp_version = _base.webapp_version
webapp_files = _base.webapp_files
webapp_api_ask = _base.webapp_api_ask
webapp_game_event = _base.webapp_game_event


def bind_runtime(
    *,
    brain=None,
    profiles=None,
    store=None,
    settings=None,
    transcription=None,
    voice=None,
):
    _base.bind_runtime(brain=brain, profiles=profiles, store=store, settings=settings)
    _voice.bind_runtime(
        brain=brain,
        profiles=profiles,
        store=store,
        transcription=transcription,
        voice=voice,
    )


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
    """Stream one verified Intelligence Core answer as newline-delimited JSON.

    Authentication is completed before the StreamingResponse is created, so an
    anonymous/forged request cannot start a model task or enter Player Brain.
    The final event is authoritative; partial events are presentation-only and
    may be coalesced by the client.
    """
    request_id = _base.new_request_id()
    text = str(body.text or "").strip()
    build = _base._build_id()
    if not text:
        async def empty_stream() -> AsyncIterator[bytes]:
            yield _ndjson({
                "type": "error",
                "error": "empty_text",
                "request_id": request_id,
                "build": build,
            })
        return StreamingResponse(
            empty_stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            status_code=400,
        )

    init_data = str(x_telegram_init_data or body.initData or "").strip()
    context = _base.require_trusted_init_data(
        init_data,
        verifier=_base.verify_init_data,
        request_id=request_id,
    )
    profile, history, identity = _base._trusted_server_context(context.meta)
    if identity is None:
        raise _base.safe_http_error(403, "telegram_identity_missing", request_id)
    meta = {
        "trusted": True,
        "authority": "verified_telegram_server_context",
    }

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
            raise RuntimeError("ai_unavailable")

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
                "trusted": True,
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
                    "trusted": True,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "build": build,
                    "meta": meta,
                }
            )
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:
            log.exception(
                "webapp live generation failed request_id=%s error=%s",
                request_id,
                type(exc).__name__,
            )
            yield _ndjson(
                {
                    "type": "error",
                    "ok": False,
                    "request_id": request_id,
                    "error": "generation_unavailable",
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
            "X-Request-ID": request_id,
        },
    )
