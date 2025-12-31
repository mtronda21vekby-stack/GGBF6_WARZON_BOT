# app/webapp/webapp_router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = (BASE_DIR / "static").resolve()


def _file(path: Path, *, is_html: bool = False) -> FileResponse:
    """
    Возвращает файл со здравыми заголовками:
    - index.html не кэшируем (иначе на iOS/Safari/Telegram часто липнет старая версия)
    - ассеты (css/js/png/svg/woff2/...) можно кэшировать агрессивно
    """
    headers = {}

    if is_html:
        # Важно для Mini App: чтобы правки UI/JS гарантированно подтягивались
        headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        headers["Pragma"] = "no-cache"
    else:
        # Для ассетов: быстро и “дорого” по ощущению
        headers["Cache-Control"] = "public, max-age=31536000, immutable"

    return FileResponse(path, headers=headers)


def _index() -> FileResponse:
    # index.html — SPA entrypoint
    return _file(STATIC_DIR / "index.html", is_html=True)


@router.get("/webapp", include_in_schema=False)
@router.get("/webapp/", include_in_schema=False)
def webapp_index():
    return _index()


@router.get("/webapp/{path:path}", include_in_schema=False)
def webapp_static(path: str):
    # Если запросили /webapp/ (пустой path) — тоже отдаём index
    if not path:
        return _index()

    # Собираем путь и нормализуем
    file_path = (STATIC_DIR / path).resolve()

    # ✅ Защита от ../ (надёжнее, чем startswith)
    try:
        file_path.relative_to(STATIC_DIR)
    except ValueError:
        return _index()

    # Если существует файл — отдаём его
    if file_path.exists() and file_path.is_file():
        # HTML файлы тоже лучше не кэшировать (на случай роутов типа /webapp/some.html)
        is_html = (file_path.suffix.lower() in {".html", ".htm"})
        return _file(file_path, is_html=is_html)

    # SPA fallback
    return _index()
