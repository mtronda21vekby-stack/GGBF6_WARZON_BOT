# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Config
from app.tg_api import TelegramAPI
from app.ai import AIEngine
from app.handlers import BotHandlers


cfg = Config.from_env()

api = TelegramAPI(
    token=cfg.TELEGRAM_BOT_TOKEN,
    http_timeout=cfg.HTTP_TIMEOUT,
    user_agent=cfg.USER_AGENT,
    log=cfg.log,
)

ai = AIEngine(
    openai_key=cfg.OPENAI_API_KEY,
    base_url=cfg.OPENAI_BASE_URL,
    model=cfg.OPENAI_MODEL,
    log=cfg.log,
)

handlers = BotHandlers(api=api, ai_engine=ai, config=cfg, log=cfg.log)

app = FastAPI(title="GGBF6_WARZON_BOT Webhook")

@app.get("/")
def root():
    return PlainTextResponse("OK")

@app.get("/health")
def health():
    return {"ok": True, "ai": bool(ai.enabled), "mode": "webhook"}

@app.post("/tg/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    # защита от чужих запросов
    if cfg.WEBHOOK_SECRET and secret != cfg.WEBHOOK_SECRET:
        return JSONResponse({"ok": False, "error": "bad secret"}, status_code=403)

    try:
        upd = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "bad json"}, status_code=400)

    try:
        handlers.handle_update(upd)
    except Exception as e:
        cfg.log.exception("handle_update failed: %r", e)

    return {"ok": True}
