# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response

log = logging.getLogger("webapp")
if not log.handlers:
    logging.basicConfig(level=logging.INFO)

router = APIRouter()

# папка рядом с этим файлом: app/webapp/static/*
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()
INDEX_FILE = (STATIC_DIR / "index.html").resolve()

# дефолтные mime (на всякий)
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("application/octet-stream", ".bin")

SEC_HEADERS = {
    # Telegram WebApp живёт внутри webview — держим безопасно, но без “жёсткого CSP”, чтобы не сломать web-app js
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "SAMEORIGIN",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def _is_inside(base: Path, target: Path) -> bool:
    try:
        target.relative_to(base)
        return True
    except Exception:
        return False


def _cache_headers_for(path: Path) -> dict:
    """
    SPA:
      - index.html: всегда no-cache (чтобы обновления сразу прилетали)
      - ассеты: можно кешировать (но у тебя есть ?v=... — идеально)
    """
    name = path.name.lower()
    if name == "index.html":
        return {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    # ассеты: кешируем, обновление — через ?v=...
    return {"Cache-Control": "public, max-age=86400"}  # 1 день


def _file_response(file_path: Path) -> FileResponse:
    guessed_type, _ = mimetypes.guess_type(str(file_path))
    headers = {}
    headers.update(SEC_HEADERS)
    headers.update(_cache_headers_for(file_path))

    return FileResponse(
        path=str(file_path),
        media_type=guessed_type or "application/octet-stream",
        headers=headers,
    )


def _index_response() -> Response:
    if not INDEX_FILE.exists():
        # вместо 500 — понятная ошибка
        raise HTTPException(
            status_code=404,
            detail=f"index.html not found at {INDEX_FILE}. Put files into {STATIC_DIR}",
        )
    return _file_response(INDEX_FILE)


@router.get("/webapp/health", include_in_schema=False)
async def webapp_health() -> Response:
    ok = STATIC_DIR.exists() and INDEX_FILE.exists()
    txt = "OK" if ok else "MISSING_FILES"
    headers = {}
    headers.update(SEC_HEADERS)
    headers["Cache-Control"] = "no-store"
    return PlainTextResponse(txt, status_code=200 if ok else 503, headers=headers)


@router.get("/webapp", include_in_schema=False)
async def webapp_root() -> Response:
    # SPA entry
    return _index_response()


@router.get("/webapp/{req_path:path}", include_in_schema=False)
async def webapp_any(req_path: str, request: Request) -> Response:
    """
    SPA fallback:
      - если файл существует в static — отдаём файл
      - иначе отдаём index.html
    Защита от ../ и любого обхода путей.
    """
    # нормализуем
    raw = (req_path or "").strip().lstrip("/")
    if not raw:
        return _index_response()

    # режем query — FastAPI сюда его не передаёт, но на всякий
    raw = raw.split("?", 1)[0].split("#", 1)[0]

    # candidate
    candidate = (STATIC_DIR / raw).resolve()

    # защита от ../
    if not _is_inside(STATIC_DIR, candidate):
        log.warning("Blocked path traversal: %s", raw)
        raise HTTPException(status_code=403, detail="Forbidden")

    # если папка — пробуем index.html внутри
    if candidate.exists() and candidate.is_dir():
        idx = (candidate / "index.html").resolve()
        if idx.exists() and _is_inside(STATIC_DIR, idx):
            return _file_response(idx)
        return _index_response()

    # если файл существует — отдать
    if candidate.exists() and candidate.is_file():
        return _file_response(candidate)

    # SPA fallback
    return _index_response()
