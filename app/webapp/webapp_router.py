# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _file_response(path: Path, *, cache: str) -> FileResponse:
    # cache examples:
    # - "no-store, no-cache, must-revalidate, max-age=0"
    # - "public, max-age=31536000, immutable"
    return FileResponse(
        path,
        headers={
            "Cache-Control": cache,
            "Pragma": "no-cache" if "no-store" in cache else "",
        },
    )


def _index() -> FileResponse:
    # index.html всегда no-store — иначе Telegram/WebView будет показывать старое
    return _file_response(
        STATIC_DIR / "index.html",
        cache="no-store, no-cache, must-revalidate, max-age=0",
    )


@router.get("/webapp", include_in_schema=False)
@router.get("/webapp/", include_in_schema=False)
def webapp_index():
    return _index()


@router.get("/webapp/{path:path}", include_in_schema=False)
def webapp_static(path: str):
    if not path:
        return _index()

    file_path = (STATIC_DIR / path).resolve()

    # защита от ../
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        return _index()

    if file_path.exists() and file_path.is_file():
        # HTML тоже лучше не кешировать
        if file_path.suffix.lower() in {".html"}:
            return _file_response(file_path, cache="no-store, no-cache, must-revalidate, max-age=0")

        # css/js/img можно кешировать “долго”, потому что мы добавим ?v=...
        return _file_response(file_path, cache="public, max-age=31536000, immutable")

    # SPA fallback
    return _index()
