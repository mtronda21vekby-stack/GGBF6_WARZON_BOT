# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

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
    # простая защита от ../ и ./../
    parts = [x for x in p.split("/") if x]
    if any(x in ("..",) for x in parts):
        return False
    return True


def _cache_headers(kind: str) -> dict:
    """
    kind:
      - "html": отключаем кэш (Telegram iOS реально кэширует жёстко)
      - "asset": можно кэшировать, но безопасно коротко
    """
    if kind == "html":
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        }
    # assets
    return {
        "Cache-Control": "public, max-age=300",  # 5 минут, без боли
    }


def _file_response(path: Path, *, kind: str) -> FileResponse:
    return FileResponse(
        path=str(path),
        headers=_cache_headers(kind),
    )


@router.get("/webapp")
def webapp_root():
    # Главная Mini App
    if not INDEX_FILE.exists():
        log.error("index.html not found at %s", INDEX_FILE)
        raise HTTPException(status_code=500, detail="webapp index missing")
    return _file_response(INDEX_FILE, kind="html")


@router.get("/webapp/{req_path:path}")
def webapp_files(req_path: str):
    """
    Раздаём:
      /webapp/style.css
      /webapp/app.js
      /webapp/assets/...
    SPA fallback:
      /webapp (handled above)
      /webapp/settings -> index.html
    ВАЖНО:
      - если путь имеет расширение (.css/.js/.png) и файла нет -> 404 (а не index.html),
        иначе браузер будет получать HTML вместо CSS/JS и “дизайн пропадает”.
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

    # файл существует -> отдаём как asset
    if target.exists() and target.is_file():
        # html тоже можем отдавать, но лучше считать это asset, кроме index
        kind = "html" if target.name.lower() == "index.html" else "asset"
        return _file_response(target, kind=kind)

    # SPA fallback: только для путей БЕЗ расширения
    has_ext = "." in Path(req_path).name
    if not has_ext:
        if not INDEX_FILE.exists():
            log.error("index.html not found at %s", INDEX_FILE)
            raise HTTPException(status_code=500, detail="webapp index missing")
        return _file_response(INDEX_FILE, kind="html")

    # если расширение есть, но файла нет -> 404 (иначе ломаем css/js)
    return Response(status_code=404, content="Not Found")
