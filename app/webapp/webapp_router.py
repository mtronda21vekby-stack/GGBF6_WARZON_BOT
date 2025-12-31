# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def _index() -> FileResponse:
    # HTML лучше отдавать без кэша, чтобы Telegram не залипал на старом UI
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/webapp", include_in_schema=False)
def webapp_index_redirect():
    # КЛЮЧЕВО: слэш в конце → правильная загрузка относительных ресурсов
    return RedirectResponse(url="/webapp/", status_code=307)


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
        # Статику можно кэшировать чуть-чуть, а HTML мы уже не кэшируем
        return FileResponse(
            file_path,
            headers={"Cache-Control": "public, max-age=300"},
        )

    # SPA fallback
    return _index()
