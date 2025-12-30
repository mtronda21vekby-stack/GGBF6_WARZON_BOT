# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


@router.get("/webapp", include_in_schema=False)
def webapp_index():
    return FileResponse(INDEX_FILE)


@router.get("/webapp/{path:path}", include_in_schema=False)
def webapp_static(path: str):
    file_path = (STATIC_DIR / path).resolve()

    # защита от ../
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        return FileResponse(INDEX_FILE)

    # отдаём файл если есть, иначе SPA fallback
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return FileResponse(INDEX_FILE)
