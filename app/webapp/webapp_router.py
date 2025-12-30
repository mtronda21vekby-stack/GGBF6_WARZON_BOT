# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@router.get("/webapp", include_in_schema=False)
def webapp_index():
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/webapp/{path:path}", include_in_schema=False)
def webapp_static(path: str):
    file_path = (STATIC_DIR / path).resolve()
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        # защита от ../
        return FileResponse(STATIC_DIR / "index.html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")
