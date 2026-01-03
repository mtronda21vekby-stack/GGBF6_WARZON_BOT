# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response, JSONResponse
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

# Пара лимитов/защит (НЕ ломают, только защищают)
_WEBAPP_MAX_BYTES = int(os.getenv("WEBAPP_MAX_BYTES", "16000") or "16000")
_WEBAPP_LOG_CHARS = int(os.getenv("WEBAPP_LOG_CHARS", "1200") or "1200")

# ==========================================
# SECURITY: Telegram initData verify
# ==========================================
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

    # пробуем достать user id / chat id
    user_id = None
    chat_id = None
    try:
        if "user" in pairs:
            u = json.loads(pairs["user"])
            user_id = u.get("id")
    except Exception:
        pass

    try:
        if "chat" in pairs:
            c = json.loads(pairs["chat"])
            chat_id = c.get("id")
    except Exception:
        pass

    return ok, {"user_id": user_id, "chat_id": chat_id, "raw": pairs}


# ==========================================
# Small utils (safe log / etag)
# ==========================================
def _truncate(s: Any, n: int) -> str:
    try:
        x = str(s if s is not None else "")
    except Exception:
        x = ""
    if n <= 0:
        return ""
    return x if len(x) <= n else (x[: n - 1] + "…")


def _etag_for_bytes(b: bytes) -> str:
    # слабый ETag достаточно для iOS WebView кеша
    try:
        return hashlib.sha1(b).hexdigest()[:16]
    except Exception:
        return str(int(time.time()))


def _etag_for_file(p: Path) -> str:
    try:
        st = p.stat()
        payload = f"{p.name}:{int(st.st_mtime)}:{int(st.st_size)}".encode("utf-8", errors="ignore")
        return hashlib.sha1(payload).hexdigest()[:16]
    except Exception:
        return str(int(time.time()))


# ==========================================
# Cache / static helpers
# ==========================================
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


def _cache_headers(kind: str, *, etag: str | None = None) -> dict:
    """
    kind:
      - "html": отключаем кэш (Telegram iOS кэширует жёстко)
      - "asset": короткий кэш, но с revalidate
      - "json": revalidate
    """
    headers = {}
    if kind == "html":
        headers.update(
            {
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    elif kind == "asset":
        headers.update({"Cache-Control": "public, max-age=0, must-revalidate"})
    else:
        headers.update({"Cache-Control": "public, max-age=0, must-revalidate"})

    if etag:
        headers["ETag"] = etag
    return headers


def _file_response(path: Path, *, kind: str) -> FileResponse:
    # FileResponse сам стримит файл, добавляем заголовки (кэш + ETag)
    et = _etag_for_file(path)
    return FileResponse(path=str(path), headers=_cache_headers(kind, etag=et))


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


def _fallback_index_html(reason: str) -> HTMLResponse:
    """
    Если index.html реально отсутствует в деплое — не даём белый экран.
    Даём понятную страницу + подсказки.
    (Это не меняет поведение при наличии index.html)
    """
    b = _build_id()
    body = f"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no" />
  <title>Mini App not configured</title>
  <style>
    html,body{{height:100%;margin:0;background:#0b0b10;color:#fff;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;}}
    .wrap{{max-width:860px;margin:0 auto;padding:24px;}}
    h1{{margin:0 0 10px 0;font-size:20px;}}
    .muted{{opacity:.75;line-height:1.5}}
    .box{{margin-top:14px;padding:14px;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(255,255,255,.06)}}
    code{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}}
    ul{{margin:10px 0 0 20px}}
    .pill{{display:inline-block;margin-top:10px;padding:8px 10px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-weight:700}}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Mini App is not configured</h1>
    <div class="muted">
      Причина: <b>{reason}</b><br/>
      Build: <code>{b}</code>
    </div>

    <div class="box">
      Expected:
      <ul>
        <li><code>app/webapp/webapp_router.py</code></li>
        <li><code>app/webapp/static/index.html</code></li>
      </ul>
      <div class="pill">Проверь деплой: файл index.html должен быть в репе и попасть на Render</div>
    </div>

    <div class="box muted">
      Быстрый тест: открой в Safari (вне Telegram) <code>/webapp</code> и <code>/webapp/version.json</code> — если тут же ошибка, значит проблема в деплое/файлах, а не в кнопках.
    </div>
  </div>
</body>
</html>
""".strip()

    et = _etag_for_bytes(body.encode("utf-8", errors="ignore"))
    return HTMLResponse(content=body, headers=_cache_headers("html", etag=et))


def _render_index_html(request: Request | None = None) -> HTMLResponse:
    if not INDEX_FILE.exists():
        # ВАЖНО: раньше было 500. Теперь вместо белого экрана — понятный fallback.
        try:
            log.error("index.html not found at %s", INDEX_FILE)
        except Exception:
            pass
        return _fallback_index_html("index.html missing in deploy")

    try:
        html = INDEX_FILE.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        try:
            log.exception("index read failed: %s", e)
        except Exception:
            pass
        return _fallback_index_html("index read failed")

    b = _build_id()
    html = html.replace("__BUILD__", b).replace("%BUILD%", b)

    # ETag помогает Telegram iOS понять, что это другой контент
    et = _etag_for_bytes(html.encode("utf-8", errors="ignore"))

    # If-None-Match -> 304 (ускоряет, но html всё равно no-store)
    if request is not None:
        inm = (request.headers.get("if-none-match") or "").strip()
        if inm and inm == et:
            return HTMLResponse(status_code=304, content="", headers=_cache_headers("html", etag=et))

    return HTMLResponse(content=html, headers=_cache_headers("html", etag=et))


# ==========================================
# ROUTES (static)
# ==========================================
@router.get("/webapp")
def webapp_root(request: Request):
    return _render_index_html(request)


@router.get("/webapp/health")
def webapp_health():
    # быстрый sanity-check без статик-файлов
    return JSONResponse(
        {
            "ok": True,
            "build": _build_id(),
            "static_dir_exists": bool(STATIC_DIR.exists()),
            "index_exists": bool(INDEX_FILE.exists()),
        },
        headers=_cache_headers("json"),
    )


@router.get("/webapp/version.json")
def webapp_version():
    # удобно дебажить “у меня старый деплой в TG”
    return JSONResponse(
        {
            "bco_webapp": True,
            "build": _build_id(),
            "ts": int(time.time()),
        },
        headers=_cache_headers("json"),
    )


@router.get("/webapp/{req_path:path}")
def webapp_files(req_path: str, request: Request):
    req_path = (req_path or "").strip()

    if not _is_safe_rel_path(req_path):
        raise HTTPException(status_code=400, detail="bad path")

    # SPA fallback: если запрос без расширения — отдаём index.html
    has_ext = "." in Path(req_path).name
    if not has_ext:
        return _render_index_html(request)

    target = (STATIC_DIR / req_path).resolve()

    try:
        target.relative_to(STATIC_DIR)
    except Exception:
        raise HTTPException(status_code=400, detail="bad path")

    if target.exists() and target.is_file():
        # If-None-Match -> 304
        et = _etag_for_file(target)
        inm = (request.headers.get("if-none-match") or "").strip()
        if inm and inm == et:
            return Response(status_code=304, headers=_cache_headers("asset", etag=et))
        return _file_response(target, kind="asset")

    return Response(status_code=404, content="Not Found")


# ==========================================
# API: "бот отвечает в мини-аппе"
# ==========================================
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

    # безопасный лог (чтобы не словить гигантский payload)
    try:
        log.info(
            "webapp_api_ask build=%s v=%s text=%s",
            _build_id(),
            _truncate(x_bco_version or "", 64),
            _truncate(text, _WEBAPP_LOG_CHARS),
        )
    except Exception:
        pass

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

    return {
        "ok": True,
        "reply": str(reply_text),
        "meta": {
            **(meta or {}),
            "bco_version": x_bco_version or "",
            "webapp_build": _build_id(),
        },
        "build": _build_id(),
    }


# ==========================================
# 3D/ИГРА — запас на будущее (НЕ ломает текущее)
# ==========================================
class GameEventBody(BaseModel):
    initData: str = ""
    event: str = ""
    payload: dict = {}


@router.post("/webapp/api/game/event")
async def webapp_game_event(
    body: GameEventBody,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    """
    Ничего не ломает. Можно слать из 2D/3D движка:
      { event: "game_result" | "telemetry" | "error", payload: {...} }
    Сервер:
      - валидирует initData (если есть)
      - безопасно логирует
      - (если есть store) может сохранить
    """
    init_data = (x_telegram_init_data or body.initData or "").strip()
    ok, meta = _verify_init_data(init_data)
    if not ok:
        meta = meta or {}
        meta["untrusted"] = True

    ev = (body.event or "").strip()[:64]
    pl = body.payload if isinstance(body.payload, dict) else {}

    # защита от гигантских payload
    try:
        raw = json.dumps(pl, ensure_ascii=False)
        if len(raw.encode("utf-8", errors="ignore")) > _WEBAPP_MAX_BYTES:
            pl = {"truncated": True, "keys": list(pl.keys())[:40]}
    except Exception:
        pass

    try:
        log.info("webapp_game_event ev=%s meta=%s payload=%s", ev, _truncate(meta, 300), _truncate(pl, _WEBAPP_LOG_CHARS))
    except Exception:
        pass

    # если есть store — сохраним (не обязательно)
    if APP_STORE is not None and hasattr(APP_STORE, "add"):
        try:
            # user_id/chat_id могут быть None — это ок
            key = f"webapp:{ev or 'event'}"
            APP_STORE.add(int(meta.get("chat_id") or meta.get("user_id") or 0), key, {"event": ev, "payload": pl, "meta": meta})
        except Exception:
            pass

    return {"ok": True, "build": _build_id(), "meta": meta}
