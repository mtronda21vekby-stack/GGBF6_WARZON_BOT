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
from app.webapp.security import verify_init_data
from app.webapp.security_boundary import (
    enforce_usage,
    mark_usage_reserved,
    new_request_id,
    resolve_trusted_telegram_context,
    safe_http_exception,
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
    global APP_BRAIN, APP_PROFILES, APP_STORE
    global APP_TRANSCRIPTION, APP_VOICE, APP_USAGE_GUARD
    APP_BRAIN = brain
    APP_PROFILES = profiles
    APP_STORE = store
    APP_TRANSCRIPTION = transcription
    APP_VOICE = voice
    APP_USAGE_GUARD = usage_guard
    log.info(
        "Mini App voice bind brain=%s profiles=%s store=%s stt=%s tts=%s usage_guard=%s",
        bool(brain),
        bool(profiles),
        bool(store),
        bool(transcription),
        bool(voice),
        bool(usage_guard),
    )


async def _trusted_context(init_data: str, request_id: str):
    return await asyncio.to_thread(
        resolve_trusted_telegram_context,
        init_data=str(init_data or "").strip(),
        verifier=verify_init_data,
        profiles=APP_PROFILES,
        store=APP_STORE,
        request_id=request_id,
    )


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
    if APP_TRANSCRIPTION is None or not bool(getattr(APP_TRANSCRIPTION, "configured", False)):
        raise safe_http_exception(503, "transcription_unavailable", request_id)

    max_bytes = int(
        getattr(APP_TRANSCRIPTION, "max_bytes", 12 * 1024 * 1024)
        or 12 * 1024 * 1024
    )
    max_bytes = max(256 * 1024, min(max_bytes, 12 * 1024 * 1024))
    raw = await audio.read(max_bytes + 1)
    if not raw:
        raise safe_http_exception(422, "audio_empty", request_id)
    if len(raw) > max_bytes:
        raise safe_http_exception(413, "audio_too_large", request_id)

    temp_dir = Path(tempfile.mkdtemp(prefix="bco-mini-voice-"))
    source = temp_dir / ("input" + _safe_suffix(audio.filename, audio.content_type))
    try:
        source.write_bytes(raw)
        started = time.perf_counter()
        result = await APP_TRANSCRIPTION.transcribe_result(source, profile=profile)
        return result, int((time.perf_counter() - started) * 1000)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "Mini App transcription failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(503, "transcription_unavailable", request_id)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _reply(
    text: str,
    profile: dict[str, Any],
    history: list[dict[str, Any]],
    request_id: str,
) -> str:
    fn = getattr(APP_BRAIN, "reply", None)
    if not callable(fn):
        raise safe_http_exception(503, "conversation_runtime_unavailable", request_id)
    kwargs = {"text": text, "profile": profile, "history": history}
    try:
        if inspect.iscoroutinefunction(fn):
            return str(await fn(**kwargs))
        output = await asyncio.to_thread(fn, **kwargs)
        return str(await output) if inspect.isawaitable(output) else str(output)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "Mini App voice generation failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(503, "generation_unavailable", request_id)


@router.post("/webapp/api/voice-transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    context = await _trusted_context(x_telegram_init_data or "", request_id)
    enforce_usage(APP_USAGE_GUARD, context.chat_id, "stt", request_id)

    result, stt_ms = await _transcribe_upload(audio, context.profile, request_id)
    transcript = str(getattr(result, "text", "") or "").strip()
    if not transcript:
        raise safe_http_exception(422, "transcription_empty", request_id)

    mode = APP_VOICE.mode_for(context.profile) if APP_VOICE is not None else TTSMode.OFF
    return JSONResponse(
        {
            "ok": True,
            "trusted": True,
            "authority": "stt_only_shared_voice_runtime",
            "request_id": request_id,
            "transcript": transcript,
            "latency": {"stt_ms": stt_ms},
            "transcription": {
                "model": str(getattr(result, "model", "") or ""),
                "language": str(getattr(result, "language", "") or ""),
                "confidence": getattr(result, "confidence", None),
                "fallback_used": bool(getattr(result, "fallback_used", False)),
            },
            "voice": {
                "identity": str(context.profile.get("voice_identity") or "female"),
                "mode": mode.value,
                "available": bool(APP_VOICE is not None and getattr(APP_VOICE, "enabled", False)),
            },
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Request-ID": request_id,
        },
    )


@router.post("/webapp/api/voice-turn")
async def voice_turn(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    request_started = time.perf_counter()
    context = await _trusted_context(x_telegram_init_data or "", request_id)
    if not callable(getattr(APP_BRAIN, "reply", None)):
        raise safe_http_exception(503, "conversation_runtime_unavailable", request_id)

    enforce_usage(APP_USAGE_GUARD, context.chat_id, "stt", request_id)
    enforce_usage(APP_USAGE_GUARD, context.chat_id, "ai", request_id)

    profile = dict(context.profile)
    if getattr(APP_BRAIN, "usage_guard", None) is APP_USAGE_GUARD:
        profile = mark_usage_reserved(profile, "ai")
    result, stt_ms = await _transcribe_upload(audio, profile, request_id)
    transcript = str(getattr(result, "text", "") or "").strip()
    if not transcript:
        raise safe_http_exception(422, "transcription_empty", request_id)

    think_started = time.perf_counter()
    reply = await _reply(transcript, profile, context.history, request_id)
    think_ms = int((time.perf_counter() - think_started) * 1000)
    if not reply.strip():
        raise safe_http_exception(503, "generation_unavailable", request_id)

    mode = APP_VOICE.mode_for(profile) if APP_VOICE is not None else TTSMode.OFF
    total_ms = int((time.perf_counter() - request_started) * 1000)
    return JSONResponse(
        {
            "ok": True,
            "trusted": True,
            "authority": "shared_conversation_and_voice_runtime",
            "request_id": request_id,
            "transcript": transcript,
            "reply": reply,
            "latency": {
                "stt_ms": stt_ms,
                "think_ms": think_ms,
                "turn_ms": total_ms,
            },
            "transcription": {
                "model": str(getattr(result, "model", "") or ""),
                "language": str(getattr(result, "language", "") or ""),
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


class SpeakBody(BaseModel):
    text: str = Field(default="", min_length=1, max_length=6000)


@router.post("/webapp/api/voice-speak")
async def voice_speak(
    body: SpeakBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_id = new_request_id()
    context = await _trusted_context(x_telegram_init_data or "", request_id)
    enforce_usage(APP_USAGE_GUARD, context.chat_id, "voice", request_id)

    if APP_VOICE is None or not bool(getattr(APP_VOICE, "enabled", False)):
        raise safe_http_exception(503, "tts_unavailable", request_id)
    if APP_VOICE.mode_for(context.profile) == TTSMode.OFF:
        raise safe_http_exception(409, "tts_disabled_in_profile", request_id)

    artifact = None
    started = time.perf_counter()
    try:
        artifact = await APP_VOICE.synthesize(
            str(body.text or "").strip(),
            context.profile,
        )
        audio_bytes = artifact.path.read_bytes()
        if not audio_bytes:
            raise safe_http_exception(503, "tts_empty", request_id)
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
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "Mini App TTS failed request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        raise safe_http_exception(503, "tts_unavailable", request_id)
    finally:
        if artifact is not None:
            try:
                artifact.cleanup()
            except Exception as exc:
                log.warning(
                    "Mini App TTS cleanup failed request_id=%s error=%s",
                    request_id,
                    type(exc).__name__,
                )
