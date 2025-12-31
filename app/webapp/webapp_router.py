# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

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


def _cache_headers(kind: str) -> dict:
    """
    kind:
      - "html": отключаем кэш (Telegram iOS кэширует жёстко)
      - "asset": revalidate (пусть даже tg иногда игнорит)
    """
    if kind == "html":
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    return {
        "Cache-Control": "public, max-age=0, must-revalidate",
    }


def _file_response(path: Path, *, kind: str) -> FileResponse:
    return FileResponse(
        path=str(path),
        headers=_cache_headers(kind),
    )


def _scan_static_mtime() -> int:
    """
    Возвращает max mtime (секунды) по всем файлам в STATIC_DIR.
    Меняется при любом обновлении любого файла.
    """
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
    """
    Порядок приоритетов:
      1) WEBAPP_BUILD_ID (если руками задан)
      2) RENDER_GIT_COMMIT (Render обычно даёт сам)
      3) max mtime по static/*
    """
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

    return HTMLResponse(
        content=html,
        headers=_cache_headers("html"),
    )


# =========================================================
# ✅ КРИТИЧНО: /webapp -> /webapp/ (слэш фиксит резолв ./style.css в Telegram iOS)
# =========================================================
@router.get("/webapp", include_in_schema=False)
def webapp_redirect():
    return RedirectResponse(url="/webapp/", status_code=307)


# =========================================================
# ✅ Главная Mini App — всегда со слэшем
# =========================================================
@router.get("/webapp/", include_in_schema=False)
def webapp_root():
    return _render_index_html()


@router.get("/webapp/{req_path:path}", include_in_schema=False)
def webapp_files(req_path: str):
    """
    Раздаём статику и SPA fallback.

    ВАЖНО:
      - если путь имеет расширение и файла нет -> 404
        (иначе браузер получит HTML вместо CSS/JS и “дизайн пропадает”)
      - для SPA (без расширения) -> index.html
    """
    req_path = (req_path or "").strip()

    if not _is_safe_rel_path(req_path):
        raise HTTPException(status_code=400, detail="bad path")

    # SPA fallback: только для путей без расширения (settings, vod, etc.)
    has_ext = "." in Path(req_path).name
    if not has_ext:
        return _render_index_html()

    target = (STATIC_DIR / req_path).resolve()

    # блокируем выход из STATIC_DIR
    try:
        target.relative_to(STATIC_DIR)
    except Exception:
        raise HTTPException(status_code=400, detail="bad path")

    if target.exists() and target.is_file():
        return _file_response(target, kind="asset")

    return Response(status_code=404, content="Not Found")
