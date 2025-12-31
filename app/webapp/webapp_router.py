# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import mimetypes
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]  # .../app
WEBAPP_DIR = BASE_DIR / "webapp"                # .../app/webapp  (если у тебя иначе — поправь)
STATIC_DIR = BASE_DIR / "static"                # .../app/static

def _no_cache_headers() -> dict:
    return {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }

def _safe_join(root: Path, rel: str) -> Path:
    rel = (rel or "").lstrip("/")
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        return root / "index.html"
    return p

@router.get("/webapp")
@router.get("/webapp/{path:path}")
async def webapp_spa(request: Request, path: str = "") -> Response:
    # сначала статик (css/js/img), потом SPA fallback -> index.html
    p = _safe_join(WEBAPP_DIR, path)

    if p.is_file():
        media_type, _ = mimetypes.guess_type(str(p))
        return FileResponse(
            str(p),
            media_type=media_type or "application/octet-stream",
            headers=_no_cache_headers(),
        )

    index = WEBAPP_DIR / "index.html"
    return FileResponse(str(index), media_type="text/html", headers=_no_cache_headers())
