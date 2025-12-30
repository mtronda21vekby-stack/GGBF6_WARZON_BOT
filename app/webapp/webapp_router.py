# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _safe_file(path: str | None):
    # index.html по умолчанию
    if not path:
        file_path = (STATIC_DIR / "index.html").resolve()
        return file_path

    file_path = (STATIC_DIR / path).resolve()

    # защита от ../
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        return (STATIC_DIR / "index.html").resolve()

    # если файл существует — отдаём
    if file_path.exists() and file_path.is_file():
        return file_path

    # SPA fallback
    return (STATIC_DIR / "index.html").resolve()


@router.get("/webapp", include_in_schema=False)
def webapp_index():
    return FileResponse(_safe_file("index.html"))


# ВОТ ЭТО ГЛАВНОЕ: поддержка /webapp/
@router.get("/webapp/", include_in_schema=False)
def webapp_index_slash():
    return FileResponse(_safe_file("index.html"))


@router.get("/webapp/{path:path}", include_in_schema=False)
def webapp_static(path: str):
    return FileResponse(_safe_file(path))
