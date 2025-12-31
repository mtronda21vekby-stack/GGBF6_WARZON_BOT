# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

log = logging.getLogger("webapp")
router = APIRouter()

# Папка со статикой: app/webapp/static/*
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()
INDEX_FILE = (STATIC_DIR / "index.html").resolve()


def _is_safe_rel_path(p: str) -> bool:
    # запрет: абсолютные пути, backslash, нулевой байт, path traversal
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


def _build_id() -> str:
    """
    Build-id для cache-bust.
    Приоритет:
      1) WEBAPP_BUILD_ID (если выставишь руками)
      2) RENDER_GIT_COMMIT (обычно есть на Render)
      3) mtime index.html (последняя линия обороны)
    """
    bid = (os.getenv("WEBAPP_BUILD_ID") or "").strip()
    if bid:
        return bid

    bid = (os.getenv("RENDER_GIT_COMMIT") or "").strip()
    if bid:
        return bid[:12]

    try:
        return str(int(INDEX_FILE.stat().st_mtime))
    except Exception:
        return "dev"


def _cache_headers(kind: str) -> dict:
    """
    kind:
      - "html": no-store (Telegram iOS кэширует жёстко)
      - "asset": можно кэшировать, т.к. у нас cache-bust через ?v=BUILD
    """
    if kind == "html":
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }

    # assets
    return {
        # можно жёстко кэшировать, потому что URL меняется (?v=BUILD)
        "Cache-Control": "public, max-age=31536000, immutable",
    }


def _file_response(path: Path, *, kind: str) -> FileResponse:
    return FileResponse(
        path=str(path),
        headers=_cache_headers(kind),
    )


def _render_index_html() -> HTMLResponse:
    if not INDEX_FILE.exists():
        log.error("index.html not found at %s", INDEX_FILE)
        raise HTTPException(status_code=500, detail="webapp index missing")

    try:
        html = INDEX_FILE.read_text(encoding="utf-8")
    except Exception as e:
        log.exception("Failed to read index.html: %s", e)
        raise HTTPException(status_code=500, detail="webapp index read failed")

    bid = _build_id()

    # ВАЖНО:
    # index.html должен содержать ?v=__BUILD__
    # Мы заменяем __BUILD__ на актуальный build-id.
    html = html.replace("__BUILD__", bid)

    return HTMLResponse(content=html, headers=_cache_headers("html"))


@router.get("/webapp")
def webapp_root():
    # Главная Mini App (HTML с динамическим build-id)
    return _render_index_html()


@router.get("/webapp/{req_path:path}")
def webapp_files(req_path: str):
    """
    Раздаём:
      /webapp/style.css
      /webapp/app.js
      /webapp/assets/...
    SPA fallback:
      /webapp/settings -> index.html

    ВАЖНО:
      - если путь имеет расширение и файла нет -> 404 (а не index.html),
        иначе браузер получает HTML вместо CSS/JS и “дизайн пропадает”.
    """
    req_path = (req_path or "").strip()

    if not _is_safe_rel_path(req_path):
        raise HTTPException(status_code=400, detail="bad path")

    target = (STATIC_DIR / req_path).resolve()

    # блокируем выход из STATIC_DIR
    try:
        target.relative_to(STATIC_DIR)
    except Exception:
        raise HTTPException(status_code=400, detail="bad path")

    # файл существует -> отдаём как asset (кэшируем сильно, URL у нас меняется через ?v=BUILD)
    if target.exists() and target.is_file():
        name = target.name.lower()
        if name == "index.html":
            # index всегда через render (no-store + build-id)
            return _render_index_html()
        return _file_response(target, kind="asset")

    # SPA fallback: только для путей БЕЗ расширения
    has_ext = "." in Path(req_path).name
    if not has_ext:
        return _render_index_html()

    # если расширение есть, но файла нет -> 404
    return Response(status_code=404, content="Not Found")
