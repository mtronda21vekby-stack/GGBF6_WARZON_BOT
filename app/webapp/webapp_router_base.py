# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from app.webapp.security import verify_init_data

log = logging.getLogger("webapp")
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()
INDEX_FILE = (STATIC_DIR / "index.html").resolve()

_WEBAPP_MAX_BYTES = int(os.getenv("WEBAPP_MAX_BYTES", "16000") or "16000")
_WEBAPP_LOG_CHARS = int(os.getenv("WEBAPP_LOG_CHARS", "1200") or "1200")
_BUILD_CACHE_VALUE: str | None = None
_BUILD_CACHE_AT = 0.0
_BUILD_CACHE_TTL_SEC = 2.0

APP_BRAIN = None
APP_PROFILES = None
APP_STORE = None
APP_SETTINGS = None


def _truncate(value: Any, limit: int) -> str:
    try:
        text = str(value if value is not None else "")
    except Exception:
        text = ""
    if limit <= 0:
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _etag_for_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


def _etag_for_file(path: Path) -> str:
    try:
        st = path.stat()
        payload = f"{path.name}:{int(st.st_mtime)}:{st.st_size}".encode()
        return hashlib.sha1(payload).hexdigest()[:16]
    except Exception:
        return str(int(time.time()))


def _cache_headers(kind: str, *, etag: str | None = None) -> dict[str, str]:
    if kind == "html":
        headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    else:
        headers = {"Cache-Control": "public, max-age=0, must-revalidate"}
    if etag:
        headers["ETag"] = etag
    return headers


def _scan_static_mtime() -> int:
    newest = 0
    if not STATIC_DIR.exists():
        return int(time.time())
    try:
        for path in STATIC_DIR.rglob("*"):
            if path.is_file():
                newest = max(newest, int(path.stat().st_mtime))
    except Exception:
        return int(time.time())
    return newest or int(time.time())


def _build_id() -> str:
    global _BUILD_CACHE_VALUE, _BUILD_CACHE_AT
    now = time.time()
    if _BUILD_CACHE_VALUE and now - _BUILD_CACHE_AT < _BUILD_CACHE_TTL_SEC:
        return _BUILD_CACHE_VALUE
    value = (os.getenv("WEBAPP_BUILD_ID") or "").strip()
    if not value:
        value = (os.getenv("RENDER_GIT_COMMIT") or "").strip()
    if not value:
        value = str(_scan_static_mtime())
    _BUILD_CACHE_VALUE = value[:12]
    _BUILD_CACHE_AT = now
    return _BUILD_CACHE_VALUE


def _is_safe_rel_path(path: str) -> bool:
    value = (path or "").strip()
    if "\x00" in value or value.startswith(("/", "\\")) or "\\" in value:
        return False
    return all(part != ".." for part in value.split("/") if part)


def _render_index_html(request: Request | None = None) -> HTMLResponse:
    if not INDEX_FILE.exists():
        return HTMLResponse(
            "<h3>Mini App is not configured</h3><p>Missing app/webapp/static/index.html</p>",
            status_code=503,
            headers=_cache_headers("html"),
        )
    try:
        html = INDEX_FILE.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return HTMLResponse(
            "<h3>Mini App failed to load</h3>",
            status_code=500,
            headers=_cache_headers("html"),
        )

    build = _build_id()
    html = html.replace("__BUILD__", build).replace("%BUILD%", build)
    etag = _etag_for_bytes(html.encode("utf-8", errors="ignore"))
    if request is not None and (request.headers.get("if-none-match") or "").strip() == etag:
        return HTMLResponse(status_code=304, content="", headers=_cache_headers("html", etag=etag))
    return HTMLResponse(content=html, headers=_cache_headers("html", etag=etag))


def bind_runtime(*, brain=None, profiles=None, store=None, settings=None):
    global APP_BRAIN, APP_PROFILES, APP_STORE, APP_SETTINGS
    APP_BRAIN = brain
    APP_PROFILES = profiles
    APP_STORE = store
    APP_SETTINGS = settings
    log.info(
        "bind_runtime ok: brain=%s profiles=%s store=%s settings=%s",
        bool(brain), bool(profiles), bool(store), bool(settings),
    )


@router.get("/webapp")
def webapp_root(request: Request):
    return _render_index_html(request)


@router.get("/webapp/health")
def webapp_health():
    return JSONResponse({
        "ok": True,
        "build": _build_id(),
        "static_dir_exists": STATIC_DIR.exists(),
        "index_exists": INDEX_FILE.exists(),
    })


@router.get("/webapp/version.json")
def webapp_version():
    return JSONResponse({"bco_webapp": True, "build": _build_id(), "ts": int(time.time())})


@router.get("/webapp/{req_path:path}")
def webapp_files(req_path: str, request: Request):
    req_path = (req_path or "").strip()
    if not _is_safe_rel_path(req_path):
        raise HTTPException(status_code=400, detail="bad path")

    if "." not in Path(req_path).name:
        return _render_index_html(request)

    target = (STATIC_DIR / req_path).resolve()
    try:
        target.relative_to(STATIC_DIR)
    except Exception:
        raise HTTPException(status_code=400, detail="bad path")

    if not target.exists() or not target.is_file():
        return Response(status_code=404, content="Not Found")

    etag = _etag_for_file(target)
    if (request.headers.get("if-none-match") or "").strip() == etag:
        return Response(status_code=304, headers=_cache_headers("asset", etag=etag))
    return FileResponse(path=str(target), headers=_cache_headers("asset", etag=etag))


class AskBody(BaseModel):
    initData: str = ""
    text: str = Field(default="", max_length=6000)
    profile: dict = Field(default_factory=dict)
    history: list = Field(default_factory=list)


def _safe_profile(profile: Any) -> dict:
    if not isinstance(profile, dict):
        return {}
    allowed = {
        "game", "mode", "platform", "input", "difficulty", "voice", "role",
        "bf6_class", "zombies_active", "zombies_map", "rank", "kd",
        "playstyle", "current_goal", "training_focus", "weekly_focus",
    }
    return {str(k): v for k, v in profile.items() if k in allowed}


def _safe_history(history: Any) -> list[dict]:
    if not isinstance(history, list):
        return []
    out: list[dict] = []
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or item.get("text") or "").strip()
        if role in {"user", "assistant"} and content:
            row = {"role": role, "content": content[:2000]}
            if item.get("ts") is not None:
                row["ts"] = item.get("ts")
            out.append(row)
    return out


def _trusted_server_context(meta: dict) -> tuple[dict, list[dict], int | None]:
    identity = meta.get("chat_id") or meta.get("user_id")
    try:
        identity = int(identity) if identity is not None else None
    except Exception:
        identity = None

    profile: dict = {}
    history: list[dict] = []
    if identity is not None and APP_PROFILES is not None and hasattr(APP_PROFILES, "get"):
        try:
            profile = APP_PROFILES.get(identity) or {}
        except Exception:
            profile = {}
    if identity is not None and APP_STORE is not None and hasattr(APP_STORE, "get"):
        try:
            history = APP_STORE.get(identity) or []
        except Exception:
            history = []
    return profile, _safe_history(history), identity


@router.post("/webapp/api/conversation-history")
async def webapp_conversation_history(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    init_data = str(x_telegram_init_data or "").strip()
    trusted, meta = verify_init_data(init_data)
    if not trusted:
        raise HTTPException(status_code=401, detail="trusted_telegram_context_required")
    _, history, identity = _trusted_server_context(dict(meta or {}))
    if identity is None:
        raise HTTPException(status_code=401, detail="telegram_identity_missing")
    return JSONResponse(
        {
            "ok": True,
            "trusted": True,
            "authority": "shared_server_conversation_store",
            "history": history[-20:],
            "count": len(history[-20:]),
            "build": _build_id(),
        },
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.post("/webapp/api/ask")
async def webapp_api_ask(
    body: AskBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_bco_version: str | None = Header(default=None, alias="X-BCO-Version"),
):
    text = (body.text or "").strip()
    if not text:
        return {"ok": False, "error": "empty_text", "build": _build_id()}

    init_data = (x_telegram_init_data or body.initData or "").strip()
    trusted, meta = verify_init_data(init_data)
    meta = dict(meta or {})

    if trusted:
        profile, history, identity = _trusted_server_context(meta)
        meta["trusted"] = True
        meta["identity"] = identity
    else:
        profile = _safe_profile(body.profile)
        history = _safe_history(body.history)
        meta = {"untrusted": True, "trusted": False}

    log.info(
        "webapp_api_ask build=%s v=%s trusted=%s text_len=%d",
        _build_id(), _truncate(x_bco_version or "", 64), trusted, len(text),
    )

    reply_text = None
    try:
        brain = APP_BRAIN
        settings = APP_SETTINGS
        ai_key = (getattr(settings, "openai_api_key", "") or "").strip() if settings else ""
        ai_enabled = bool(getattr(settings, "ai_enabled", True)) if settings else True
        ai_on = bool(ai_enabled and ai_key and brain and hasattr(brain, "reply"))

        if ai_on:
            fn = brain.reply
            if inspect.iscoroutinefunction(fn):
                reply_text = await fn(text=text, profile=profile, history=history)
            else:
                output = fn(text=text, profile=profile, history=history)
                reply_text = await output if inspect.isawaitable(output) else output
        else:
            meta["ai"] = {
                "enabled": ai_enabled,
                "has_key": bool(ai_key),
                "has_brain": bool(brain),
                "reason": "ai_off",
            }
    except Exception as exc:
        log.exception("webapp_api_ask failed: %s", type(exc).__name__)
        reply_text = "🧠 AI временно недоступен. Повтори запрос через несколько секунд."

    if not reply_text:
        reply_text = (
            "🤝 BLACK CROWN OPS: AI сейчас выключен.\n"
            "Проверь OPENAI_API_KEY, AI_ENABLED и OPENAI_MODEL."
        )

    return {
        "ok": True,
        "reply": str(reply_text),
        "meta": {
            **meta,
            "bco_version": x_bco_version or "",
            "webapp_build": _build_id(),
        },
        "build": _build_id(),
    }


class GameEventBody(BaseModel):
    initData: str = ""
    event: str = Field(default="", max_length=64)
    payload: dict = Field(default_factory=dict)


@router.post("/webapp/api/game/event")
async def webapp_game_event(
    body: GameEventBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    init_data = (x_telegram_init_data or body.initData or "").strip()
    trusted, meta = verify_init_data(init_data)
    meta = dict(meta or {})

    event = (body.event or "").strip()[:64]
    payload = body.payload if isinstance(body.payload, dict) else {}
    try:
        raw = json.dumps(payload, ensure_ascii=False)
        if len(raw.encode("utf-8", errors="ignore")) > _WEBAPP_MAX_BYTES:
            payload = {"truncated": True, "keys": list(payload.keys())[:40]}
    except Exception:
        payload = {}

    log.info(
        "webapp_game_event event=%s trusted=%s payload_keys=%s",
        event, trusted, list(payload.keys())[:20],
    )

    stored = False
    if trusted and APP_STORE is not None and hasattr(APP_STORE, "add_progression_event"):
        identity = meta.get("chat_id") or meta.get("user_id")
        try:
            if identity is not None:
                APP_STORE.add_progression_event(int(identity), {"event": event, "payload": payload})
                stored = True
        except Exception:
            stored = False

    if not trusted:
        meta = {"untrusted": True, "trusted": False}
    else:
        meta["trusted"] = True

    return {"ok": True, "stored": stored, "build": _build_id(), "meta": meta}
