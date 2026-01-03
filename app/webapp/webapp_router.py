# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

log = logging.getLogger("webapp")
router = APIRouter()

# Папка со статикой: app/webapp/static/*
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()
INDEX_FILE = (STATIC_DIR / "index.html").resolve()

# Небольшой кэш build-id (чтобы не сканировать файлы на каждый запрос)
_BUILD_CACHE_VALUE: str | None = None
_BUILD_CACHE_AT: float = 0.0
_BUILD_CACHE_TTL_SEC = 2.0


# =========================
# SECURITY: Telegram initData verify
# =========================
def _bot_token() -> str:
    return (
        (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        or (os.getenv("BOT_TOKEN") or "").strip()
        or (os.getenv("TG_BOT_TOKEN") or "").strip()
    )


def _verify_init_data(init_data: str) -> tuple[bool, dict]:
    """
    Проверка Telegram WebApp initData:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app

    Возвращаем: (ok, parsed_dict)
    parsed_dict содержит user_id/chat_id если есть.
    """
    init_data = (init_data or "").strip()
    if not init_data:
        return False, {}

    token = _bot_token()
    if not token:
        # без токена не можем проверить — но не роняем, просто не доверяем
        return False, {}

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    their_hash = pairs.pop("hash", None)
    if not their_hash:
        return False, {}

    # формируем data_check_string
    data_check_string = "\n".join([f"{k}={pairs[k]}" for k in sorted(pairs.keys())])

    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    ok = hmac.compare_digest(calc_hash, their_hash)

    # пробуем достать user id / chat id (в initDataUnsafe это есть, но тут мы парсим строку)
    user_id = None
    chat_id = None
    try:
        if "user" in pairs:
            import json as _json

            u = _json.loads(pairs["user"])
            user_id = u.get("id")
    except Exception:
        pass

    try:
        if "chat" in pairs:
            import json as _json

            c = _json.loads(pairs["chat"])
            chat_id = c.get("id")
    except Exception:
        pass

    return ok, {"user_id": user_id, "chat_id": chat_id, "raw": pairs}


# =========================
# Cache / static helpers
# =========================
def _is_safe_rel_path(p: str) -> bool:
    if not p:
        return True
    if "\x00" in p:
        return False
    if p.startswith(("/", "\\")):
        return False
    if "\\" in p:
        return False
    parts = [x for x in p.split("/") if x]
    if any(x in ("..",) for x in parts):
        return False
    return True


def _scan_static_mtime() -> int:
    if not STATIC_DIR.exists():
        return int(time.time())

    newest = 0
    try:
        for p in STATIC_DIR.rglob("*"):
            if p.is_file():
                try:
                    mt = int(p.stat().st_mtime)
                    if mt > newest:
                        newest = mt
                except Exception:
                    continue
    except Exception:
        return int(time.time())

    return newest or int(time.time())


def _build_id() -> str:
    global _BUILD_CACHE_VALUE, _BUILD_CACHE_AT

    now = time.time()
    if _BUILD_CACHE_VALUE and (now - _BUILD_CACHE_AT) < _BUILD_CACHE_TTL_SEC:
        return _BUILD_CACHE_VALUE

    v = (os.getenv("WEBAPP_BUILD_ID") or "").strip()
    if not v:
        v = (os.getenv("RENDER_GIT_COMMIT") or "").strip()

    if not v:
        v = str(_scan_static_mtime())

    v = v[:12] if len(v) > 12 else v

    _BUILD_CACHE_VALUE = v
    _BUILD_CACHE_AT = now
    return v


def _cache_headers(kind: str) -> dict:
    """
    kind:
      - "html": отключаем кэш (Telegram iOS кэширует жёстко)
      - "asset": короткий кэш, но с revalidate
      - "nocache_asset": жёстко no-store для js/css/json (анти-залипание iOS)
    """
    b = _build_id()
    base = {
        "X-BCO-Build": b,
        "Vary": "Accept-Encoding",
    }

    if kind == "html":
        base.update(
            {
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Surrogate-Control": "no-store",
            }
        )
        return base

    if kind == "nocache_asset":
        base.update(
            {
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Surrogate-Control": "no-store",
            }
        )
        return base

    base.update({"Cache-Control": "public, max-age=0, must-revalidate"})
    return base


def _guess_asset_kind(path: Path) -> str:
    ext = (path.suffix or "").lower()
    if ext in (".js", ".mjs", ".css", ".json", ".map", ".txt"):
        return "nocache_asset"
    return "asset"


def _etag_for_file(path: Path) -> str:
    """
    ETag для стабильного 304.
    Делается так, чтобы смена build тоже меняла etag.
    """
    b = _build_id()
    try:
        st = path.stat()
        raw = f"{b}:{path.name}:{int(st.st_mtime)}:{int(st.st_size)}".encode("utf-8", errors="ignore")
    except Exception:
        raw = f"{b}:{path.name}:{time.time_ns()}".encode("utf-8", errors="ignore")
    return '"' + hashlib.sha256(raw).hexdigest()[:32] + '"'


def _file_response(path: Path, *, kind: str, if_none_match: str | None = None) -> Response:
    headers = _cache_headers(kind)
    etag = _etag_for_file(path)
    headers["ETag"] = etag

    inm = (if_none_match or "").strip()
    if inm and inm == etag:
        # 304 — быстрее и надёжнее на iOS
        return Response(status_code=304, headers=headers)

    return FileResponse(path=str(path), headers=headers)


def _render_index_html() -> HTMLResponse:
    if not INDEX_FILE.exists():
        log.error("index.html not found at %s", INDEX_FILE)
        raise HTTPException(status_code=500, detail="webapp index missing")

    try:
        html = INDEX_FILE.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        log.exception("index read failed: %s", e)
        raise HTTPException(status_code=500, detail="webapp index read failed")

    b = _build_id()
    html = html.replace("__BUILD__", b).replace("%BUILD%", b)

    headers = _cache_headers("html")
    headers["ETag"] = _etag_for_file(INDEX_FILE)

    return HTMLResponse(content=html, headers=headers)


# =========================
# DIAGNOSTIC (must-have)
# =========================
@router.get("/webapp/version.json")
def webapp_version():
    b = _build_id()
    return Response(
        content=(
            "{"
            f"\"build\":\"{b}\","
            f"\"ts\":{int(time.time())},"
            f"\"static\":\"{str(STATIC_DIR).replace('\\\\', '/')}\""
            "}"
        ),
        media_type="application/json; charset=utf-8",
        headers=_cache_headers("nocache_asset"),
    )


@router.get("/webapp")
def webapp_root():
    # ОСТАВЛЕНО КАК БЫЛО: ничего не ломаем.
    return _render_index_html()


@router.get("/webapp/{req_path:path}")
def webapp_files(
    req_path: str,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
    req_path = (req_path or "").strip()

    if not _is_safe_rel_path(req_path):
        raise HTTPException(status_code=400, detail="bad path")

    has_ext = "." in Path(req_path).name
    if not has_ext:
        return _render_index_html()

    target = (STATIC_DIR / req_path).resolve()

    try:
        target.relative_to(STATIC_DIR)
    except Exception:
        raise HTTPException(status_code=400, detail="bad path")

    if target.exists() and target.is_file():
        kind = _guess_asset_kind(target)
        return _file_response(target, kind=kind, if_none_match=if_none_match)

    return Response(status_code=404, content="Not Found")


# =========================
# API: "бот отвечает в мини-аппе"
# =========================
class AskBody(BaseModel):
    # ✅ поддержка и body.initData (если кто-то шлёт так), и header X-Telegram-Init-Data (как у тебя в app.js)
    initData: str = ""
    text: str = ""
    profile: dict = {}
    history: list = []


# Эти переменные заполняются из webhook.py
APP_BRAIN = None
APP_PROFILES = None
APP_STORE = None
APP_SETTINGS = None


def bind_runtime(*, brain=None, profiles=None, store=None, settings=None):
    global APP_BRAIN, APP_PROFILES, APP_STORE, APP_SETTINGS
    APP_BRAIN = brain
    APP_PROFILES = profiles
    APP_STORE = store
    APP_SETTINGS = settings
    try:
        log.info(
            "bind_runtime ok: brain=%s profiles=%s store=%s settings=%s",
            bool(brain),
            bool(profiles),
            bool(store),
            bool(settings),
        )
    except Exception:
        pass


def _safe_profile(p: dict) -> dict:
    return dict(p) if isinstance(p, dict) else {}


def _safe_history(h: Any) -> list:
    if isinstance(h, list):
        out = []
        for x in h[-50:]:
            if isinstance(x, dict):
                out.append(x)
            else:
                out.append({"role": "user", "content": str(x)})
        return out
    return []


@router.post("/webapp/api/ask")
async def webapp_api_ask(
    body: AskBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_bco_version: str | None = Header(default=None, alias="X-BCO-Version"),
):
    text = (body.text or "").strip()
    if not text:
        return {"ok": False, "error": "empty_text", "build": _build_id()}

    # ✅ initData берём приоритетно из заголовка (как у тебя в JS),
    # а если его нет — из body.initData
    init_data = (x_telegram_init_data or body.initData or "").strip()

    ok, meta = _verify_init_data(init_data)
    if not ok:
        # не валим UX: просто помечаем как untrusted
        meta = meta or {}
        meta["untrusted"] = True

    profile = _safe_profile(body.profile)
    history = _safe_history(body.history)

    # Ответ через brain.reply (как бот)
    reply_text = None

    try:
        brain = APP_BRAIN
        settings = APP_SETTINGS

        ai_key = (getattr(settings, "openai_api_key", "") or "").strip() if settings else ""
        ai_enabled = bool(getattr(settings, "ai_enabled", True)) if settings else True
        ai_on = bool(ai_enabled and ai_key and brain and hasattr(brain, "reply"))

        if ai_on:
            fn = brain.reply
            import inspect as _inspect

            if _inspect.iscoroutinefunction(fn):
                reply_text = await fn(text=text, profile=profile, history=history)
            else:
                out = fn(text=text, profile=profile, history=history)
                reply_text = await out if _inspect.isawaitable(out) else out
        else:
            # честная инфа в мету (но UX не ломаем)
            meta = meta or {}
            meta["ai"] = {
                "enabled": bool(ai_enabled),
                "has_key": bool(ai_key),
                "has_brain": bool(brain),
                "reason": "ai_off",
            }
    except Exception as e:
        reply_text = f"🧠 AI ERROR: {type(e).__name__}: {e}"

    if not reply_text:
        # fallback: чтобы мини-апп не был “пустой”
        reply_text = (
            "🤝 Тиммейт (Mini App):\n"
            "Я тебя понял. Но AI сейчас выключен.\n\n"
            "Включение:\n"
            "• Render ENV: OPENAI_API_KEY\n"
            "• AI_ENABLED=1\n"
            "• OPENAI_MODEL\n\n"
            "И да — без паники. Сейчас добьём 😈"
        )

    b = _build_id()
    return {
        "ok": True,
        "reply": str(reply_text),
        "meta": {
            **(meta or {}),
            "bco_version": x_bco_version or "",
            "webapp_build": b,
        },
        "build": b,
    }
