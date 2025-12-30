# app/webapp/routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ВАЖНО: мы не ломаем твою архитектуру.
# Просто добавляем API, которое вызывает твою brain.reply(text, profile, history)


def _s(v: Any, d: str = "") -> str:
    try:
        x = "" if v is None else str(v)
        x = x.strip()
        return x if x else d
    except Exception:
        return d


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def verify_telegram_init_data(init_data: str, bot_token: str, max_age_sec: int = 60 * 60) -> Dict[str, Any]:
    """
    Проверка Telegram WebApp initData (HMAC).
    Возвращает распарсенный словарь (включая user/chat) если валидно.
    """
    init_data = _s(init_data)
    bot_token = _s(bot_token)
    if not init_data or not bot_token:
        raise HTTPException(status_code=401, detail="initData/bot token missing")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_recv = pairs.get("hash")
    if not hash_recv:
        raise HTTPException(status_code=401, detail="hash missing")

    # check age if auth_date exists
    auth_date = int(pairs.get("auth_date", "0") or "0")
    now = int(time.time())
    if auth_date and abs(now - auth_date) > max_age_sec:
        raise HTTPException(status_code=401, detail="initData expired")

    # build data_check_string
    data_check_items = []
    for k in sorted(pairs.keys()):
        if k == "hash":
            continue
        data_check_items.append(f"{k}={pairs[k]}")
    data_check_string = "\n".join(data_check_items).encode("utf-8")

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    hash_calc = hmac.new(secret_key, data_check_string, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(hash_calc, hash_recv):
        raise HTTPException(status_code=401, detail="initData signature invalid")

    # parse JSON fields if present (user, chat, receiver)
    out: Dict[str, Any] = dict(pairs)
    for json_key in ("user", "chat", "receiver"):
        if json_key in out:
            try:
                import json
                out[json_key] = json.loads(out[json_key])
            except Exception:
                pass

    return out


class ChatIn(BaseModel):
    text: str
    initData: str = ""
    mode: str = "TEAMMATE"


class ChatOut(BaseModel):
    reply: str
    voice: str
    user_id: int


@dataclass
class MiniAppDeps:
    brain: Any = None
    store: Any = None
    profiles: Any = None


def build_webapp_router(deps: MiniAppDeps) -> APIRouter:
    r = APIRouter()

    base_dir = os.path.dirname(__file__)  # app/webapp
    bot_token = _s(os.getenv("TELEGRAM_BOT_TOKEN"), "")

    @r.get("/webapp")
    def webapp_index():
        return FileResponse(os.path.join(base_dir, "index.html"))

    @r.get("/webapp/styles.css")
    def webapp_css():
        return FileResponse(os.path.join(base_dir, "styles.css"))

    @r.get("/webapp/app.js")
    def webapp_js():
        return FileResponse(os.path.join(base_dir, "app.js"))

    @r.post("/webapp/api/chat", response_model=ChatOut)
    async def webapp_chat(payload: ChatIn):
        init_data = verify_telegram_init_data(payload.initData, bot_token)

        user = init_data.get("user") or {}
        user_id = int(user.get("id") or 0)
        if not user_id:
            raise HTTPException(status_code=401, detail="user id missing")

        text = _s(payload.text)
        if not text:
            raise HTTPException(status_code=400, detail="empty text")

        # берём профиль (как в твоём роутере)
        prof = {}
        if deps.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(deps.profiles, name):
                    try:
                        prof = getattr(deps.profiles, name)(user_id) or {}
                        if isinstance(prof, dict):
                            prof = dict(prof)
                    except Exception:
                        prof = {}
                    break

        # TEAMMATE дефолт, mode может переключать (не ломая твой voice)
        mode = _s(payload.mode, "TEAMMATE").upper()
        if mode not in ("TEAMMATE", "COACH"):
            mode = "TEAMMATE"

        prof.setdefault("voice", "TEAMMATE")
        prof["voice"] = mode  # MiniApp даёт быстрый переключатель, но можно и через клаву

        # история из стора (если есть)
        history = []
        if deps.store and hasattr(deps.store, "get"):
            try:
                history = deps.store.get(user_id) or []
            except Exception:
                history = []

        # сохраняем user message в память (если есть)
        if deps.store and hasattr(deps.store, "add"):
            try:
                deps.store.add(user_id, "user", text)
            except Exception:
                pass

        # вызываем твой brain.reply
        reply = None
        if deps.brain and hasattr(deps.brain, "reply"):
            out = deps.brain.reply(text=text, profile=prof, history=history)
            reply = await out if hasattr(out, "__await__") else out

        if not reply:
            reply = (
                "BCO онлайн.\n"
                "Кинь одной строкой:\n"
                "Игра | input | где ты сейчас | где должен быть\n"
                "И я включу контроль 😈"
            )

        # сохраняем assistant message
        if deps.store and hasattr(deps.store, "add"):
            try:
                deps.store.add(user_id, "assistant", str(reply))
            except Exception:
                pass

        return ChatOut(reply=str(reply), voice=mode, user_id=user_id)

    return r
