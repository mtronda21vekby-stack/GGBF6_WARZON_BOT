# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import inspect
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.services.voice.service import TTSMode
from app.webapp.security import (
    enforce_usage_limit,
    new_request_id,
    require_trusted_init_data,
    safe_http_error,
    verify_init_data,
)

log = logging.getLogger("bco.webapp.voice")
router = APIRouter()

APP_BRAIN: Any = None
APP_PROFILES: Any = None
APP_STORE: Any = None
APP_TRANSCRIPTION: Any = None
APP_VOICE: Any = None
APP_USAGE_GUARD: Any = None


def bind_runtime(
    *,
    brain=None,
    profiles=None,
    store=None,
    transcription=None,
    voice=None,
    usage_guard=None,
) -> None:
    global APP_BRAIN, APP_PROFILES, APP_STORE, APP_TRANSCRIPTION, APP_VOICE, APP_USAGE_GUARD
    APP_BRAIN = brain
    APP_PROFILES = profiles
    APP_STORE = store
    APP_TRANSCRIPTION = transcription
    APP_VOICE = voice
    # ConversationService is the canonical AI boundary and owns the process-wide
    # UsageGuard. Resolve that exact instance rather than creating a Mini App
    # limiter with divergent counters.
    APP_USAGE_GUARD = usage_guard or getattr(brain, "usage_guard", None)
    log.info(
        "Mini App voice bind brain=%s profiles=%s store=%s stt=%s tts=%s guard=%s",
        bool(brain),
        bool(profiles),
        bool(store),
        bool(transcription),
        bool(voice),
        bool(APP_USAGE_GUARD),
    )


def _usage_guard() -> Any:
    return APP_USAGE_GUARD or getattr(APP_BRAIN, "usage_guard", None)


def _trusted_context(
    init_data: str,
    request_id: str,
) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    # Compatibility marker retained for existing clients/tests:
    # trusted_telegram_context_required
    context = require_trusted_init_data(
        str(init_data or "").strip(),
        verifier=verify_init_data,
        request_id=request_id,
    )
    chat_id = context.identity
    if APP_BRAIN is None or APP_PROFILES is None or APP_STORE is None:
        raise safe_http_error(503, "voice_runtime_unavailable", request_id)
    try:
        profile = dict(APP_PROFILES.get(chat_id) or {})
    except Exception:
        profile = {}
    try:
        history = list(APP_STORE.get(chat_id) or [])[-20:]
    except Exception:
        history = []
    return chat_id, profile, history


def _require_transcription_runtime(request_id: str) -> None:
    if APP_TRANSCRIPTION is None or not bool(getattr(APP_TRANSCRIPTION, "configured", False)):
        raise safe_http_error(503, "transcription_unavailable", request_id)


def _safe_suffix(filename: str | None, content_type: str | None) -> str:
    suffix = Path(str(filename or "")).suffix.casefold()
    if suffix in {".webm", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".mp3", ".mp4", ".flac"}:
        return suffix
    ctype = str(content_type or "").casefold()
    if "ogg" in ctype or "opus" in ctype:
        return ".ogg"
    if "wav" in ctype:
        return ".wav"
    if "mp4" in ctype or "m4a" in ctype:
        return ".m4a"
    return ".webm"


async def _transcribe_upload(
    audio: UploadFile,
    profile: dict[str, Any],
    request_id: str,
) -> tuple[Any, int]:
    _require_transcription_runtime(request_id)
    max_bytes = int(getattr(APP_TRANSCRIPTION, "max_bytes", 12 * 1024 * 1024) or 12 * 1024 * 1024)
    max_bytes = max(256 * 1024, min(max_bytes, 12 * 1024 * 1024))
    raw = await audio.read(max_bytes + 1)
    if not raw:
        raise safe_http_error(422, "audio_empty", request_id)
    if len(raw) > max_bytes:
        raise safe_http_error(413, "audio_too_large", request_id)

    temp_dir = Path(tempfile.mkdtemp(prefix="bco-mini-voice-"))
    source = temp_dir / ("input" + _safe_suffix(audio.filename, audio.content_type))
    try:
        source.write_bytes(raw)
        started = time.perf_counter()
        result = await APP_TRANSCRIPTION.transcribe_result(source, profile=profile)
        return result, int((time.perf_counter() - started) * 1000)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _reply(text: str, profile: dict[str, Any], history: list[dict[str, Any]]) -> str:
    fn = getattr(APP_BRAIN, "reply", None)
    if not callable(fn):
        raise RuntimeError("conversation_runtime_unavailable")
    kwargs = {"text": text, "profile": profile, "history": history}
    if inspect.iscoroutinefunction(fn):
        return str(await fn(**kwargs))
    return str(await asyncio.to_thread(fn, **kwargs))


@router.post("/webapp/api/voice-transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    try:
        chat_id, profile, _ = _trusted_context(x_telegram_init_data or "", request_id)
        _require_transcription_runtime(request_id)
        enforce_usage_limit(_usage_guard(), chat_id, "stt", request_id)
        result, stt_ms = await _transcribe_upload(audio, profile, request_id)
        transcript = str(getattr(result, "text", "") or "").strip()
        if not transcript:
            raise safe_http_error(422, "transcription_empty", request_id)
        mode = APP_VOICE.mode_for(profile) if APP_VOICE is not None else TTSMode.OFF
        return JSONResponse(
            {
                "ok": True,
                "trusted": True,
                "request_id": request_id,
                "authority": "stt_only_shared_voice_runtime",
                "transcript": transcript,
                "latency": {"stt_ms": stt_ms},
                "transcription": {
                    "model": str(getattr(result, "model", "") or "")[:64],
                    "language": str(getattr(result, "language", "") or "")[:16],
                    "confidence": getattr(result, "confidence", None),
                    "fallback_used": bool(getattr(result, "fallback_used", False)),
                },
                "voice": {
                    "identity": str(profile.get("voice_identity") or "female"),
                    "mode": mode.value,
                    "available": bool(APP_VOICE is not None and getattr(APP_VOICE, "enabled", False)),
                },
            },
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Request-ID": request_id,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception(
            "Mini App STT failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_error(503, "transcription_unavailable", request_id) from None


@router.post("/webapp/api/voice-turn")
async def voice_turn(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    request_started = time.perf_counter()
    try:
        chat_id, profile, history = _trusted_context(x_telegram_init_data or "", request_id)
        _require_transcription_runtime(request_id)
        # STT is guarded here. AI is guarded once, at ConversationService.reply,
        # using the same UsageGuard instance; do not double-charge one turn.
        enforce_usage_limit(_usage_guard(), chat_id, "stt", request_id)
        result, stt_ms = await _transcribe_upload(audio, profile, request_id)
        transcript = str(getattr(result, "text", "") or "").strip()
        if not transcript:
            raise safe_http_error(422, "transcription_empty", request_id)
        think_started = time.perf_counter()
        reply = await _reply(transcript, profile, history)
        think_ms = int((time.perf_counter() - think_started) * 1000)
        mode = APP_VOICE.mode_for(profile) if APP_VOICE is not None else TTSMode.OFF
        total_ms = int((time.perf_counter() - request_started) * 1000)
        return JSONResponse(
            {
                "ok": True,
                "trusted": True,
                "request_id": request_id,
                "authority": "shared_conversation_and_voice_runtime",
                "transcript": transcript,
                "reply": reply,
                "latency": {"stt_ms": stt_ms, "think_ms": think_ms, "turn_ms": total_ms},
                "transcription": {
                    "model": str(getattr(result, "model", "") or "")[:64],
                    "language": str(getattr(result, "language", "") or "")[:16],
                    "confidence": getattr(result, "confidence", None),
                    "fallback_used": bool(getattr(result, "fallback_used", False)),
                },
                "voice": {
                    "identity": str(profile.get("voice_identity") or "female"),
                    "mode": mode.value,
                    "available": bool(APP_VOICE is not None and getattr(APP_VOICE, "enabled", False)),
                },
            },
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Request-ID": request_id,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception(
            "Mini App voice turn failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_error(503, "voice_turn_unavailable", request_id) from None


class SpeakBody(BaseModel):
    text: str = Field(default="", min_length=1, max_length=6000)


@router.post("/webapp/api/voice-speak")
async def voice_speak(
    body: SpeakBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    try:
        chat_id, profile, _ = _trusted_context(x_telegram_init_data or "", request_id)
        if APP_VOICE is None or not bool(getattr(APP_VOICE, "enabled", False)):
            raise safe_http_error(503, "tts_unavailable", request_id)
        if APP_VOICE.mode_for(profile) == TTSMode.OFF:
            raise safe_http_error(409, "tts_disabled_in_profile", request_id)

        enforce_usage_limit(_usage_guard(), chat_id, "voice", request_id)
        started = time.perf_counter()
        artifact = await APP_VOICE.synthesize(str(body.text or "").strip(), profile)
        try:
            audio_bytes = artifact.path.read_bytes()
            if not audio_bytes:
                raise safe_http_error(503, "tts_empty", request_id)
            tts_ms = int((time.perf_counter() - started) * 1000)
            return Response(
                content=audio_bytes,
                media_type="audio/ogg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "X-BCO-Voice": str(artifact.voice_name or "")[:80],
                    "X-BCO-Provider": str(artifact.provider or "")[:40],
                    "X-BCO-TTS-MS": str(tts_ms),
                    "X-Request-ID": request_id,
                },
            )
        finally:
            artifact.cleanup()
    except HTTPException:
        raise
    except Exception as exc:
        log.exception(
            "Mini App TTS failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_error(503, "tts_unavailable", request_id) from None
