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

log = logging.getLogger("bco.webapp.voice")
router = APIRouter()

APP_BRAIN: Any = None
APP_PROFILES: Any = None
APP_STORE: Any = None
APP_TRANSCRIPTION: Any = None
APP_VOICE: Any = None


def bind_runtime(*, brain=None, profiles=None, store=None, transcription=None, voice=None) -> None:
    global APP_BRAIN, APP_PROFILES, APP_STORE, APP_TRANSCRIPTION, APP_VOICE
    APP_BRAIN = brain
    APP_PROFILES = profiles
    APP_STORE = store
    APP_TRANSCRIPTION = transcription
    APP_VOICE = voice
    log.info(
        "Mini App voice bind brain=%s profiles=%s store=%s stt=%s tts=%s",
        bool(brain), bool(profiles), bool(store), bool(transcription), bool(voice),
    )


def _trusted_context(init_data: str) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    trusted, raw_meta = verify_init_data(str(init_data or "").strip())
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")
    meta = dict(raw_meta or {})
    identity = meta.get("chat_id") or meta.get("user_id")
    try:
        chat_id = int(identity)
    except Exception:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    if APP_BRAIN is None or APP_PROFILES is None or APP_STORE is None:
        raise HTTPException(status_code=503, detail="voice_runtime_unavailable")
    try:
        profile = dict(APP_PROFILES.get(chat_id) or {})
    except Exception:
        profile = {}
    try:
        history = list(APP_STORE.get(chat_id) or [])[-20:]
    except Exception:
        history = []
    return chat_id, profile, history


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


async def _transcribe_upload(audio: UploadFile, profile: dict[str, Any]) -> tuple[Any, int]:
    if APP_TRANSCRIPTION is None or not bool(getattr(APP_TRANSCRIPTION, "configured", False)):
        raise HTTPException(status_code=503, detail="transcription_unavailable")
    max_bytes = int(getattr(APP_TRANSCRIPTION, "max_bytes", 12 * 1024 * 1024) or 12 * 1024 * 1024)
    max_bytes = max(256 * 1024, min(max_bytes, 12 * 1024 * 1024))
    raw = await audio.read(max_bytes + 1)
    if not raw:
        raise HTTPException(status_code=422, detail="audio_empty")
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="audio_too_large")

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
        raise HTTPException(status_code=503, detail="conversation_runtime_unavailable")
    kwargs = {"text": text, "profile": profile, "history": history}
    if inspect.iscoroutinefunction(fn):
        return str(await fn(**kwargs))
    return str(await asyncio.to_thread(fn, **kwargs))


@router.post("/webapp/api/voice-transcribe")
async def voice_transcribe(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    _, profile, _ = _trusted_context(x_telegram_init_data or "")
    result, stt_ms = await _transcribe_upload(audio, profile)
    transcript = str(getattr(result, "text", "") or "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcription_empty")
    mode = APP_VOICE.mode_for(profile) if APP_VOICE is not None else TTSMode.OFF
    return JSONResponse(
        {
            "ok": True,
            "trusted": True,
            "authority": "stt_only_shared_voice_runtime",
            "transcript": transcript,
            "latency": {"stt_ms": stt_ms},
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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.post("/webapp/api/voice-turn")
async def voice_turn(
    audio: UploadFile = File(...),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    request_started = time.perf_counter()
    _, profile, history = _trusted_context(x_telegram_init_data or "")
    result, stt_ms = await _transcribe_upload(audio, profile)
    transcript = str(getattr(result, "text", "") or "").strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="transcription_empty")
    think_started = time.perf_counter()
    reply = await _reply(transcript, profile, history)
    think_ms = int((time.perf_counter() - think_started) * 1000)
    mode = APP_VOICE.mode_for(profile) if APP_VOICE is not None else TTSMode.OFF
    total_ms = int((time.perf_counter() - request_started) * 1000)
    return JSONResponse(
        {
            "ok": True,
            "trusted": True,
            "authority": "shared_conversation_and_voice_runtime",
            "transcript": transcript,
            "reply": reply,
            "latency": {"stt_ms": stt_ms, "think_ms": think_ms, "turn_ms": total_ms},
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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


class SpeakBody(BaseModel):
    text: str = Field(default="", min_length=1, max_length=6000)


@router.post("/webapp/api/voice-speak")
async def voice_speak(
    body: SpeakBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    _, profile, _ = _trusted_context(x_telegram_init_data or "")
    if APP_VOICE is None or not bool(getattr(APP_VOICE, "enabled", False)):
        raise HTTPException(status_code=503, detail="tts_unavailable")
    if APP_VOICE.mode_for(profile) == TTSMode.OFF:
        raise HTTPException(status_code=409, detail="tts_disabled_in_profile")
    started = time.perf_counter()
    artifact = await APP_VOICE.synthesize(str(body.text or "").strip(), profile)
    try:
        audio_bytes = artifact.path.read_bytes()
        if not audio_bytes:
            raise HTTPException(status_code=503, detail="tts_empty")
        tts_ms = int((time.perf_counter() - started) * 1000)
        return Response(
            content=audio_bytes,
            media_type="audio/ogg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-BCO-Voice": str(artifact.voice_name or "")[:80],
                "X-BCO-Provider": str(artifact.provider or "")[:40],
                "X-BCO-TTS-MS": str(tts_ms),
            },
        )
    finally:
        artifact.cleanup()
