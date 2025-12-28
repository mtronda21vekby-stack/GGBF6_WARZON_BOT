# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.observability.log import setup_logging, get_logger

from app.adapters.telegram.types import Update
from app.adapters.telegram.client import TelegramClient

from app.core.router import Router

from app.services.brain.engine import BrainEngine
from app.services.brain.memory import InMemoryStore
from app.services.profiles.service import ProfileService


log = get_logger("webhook")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(getattr(settings, "log_level", "INFO"))

    app = FastAPI(title="GGBF6 Bot Webhook", version="1.0.0")

    tg = TelegramClient(settings.bot_token)

    store = InMemoryStore(memory_max_turns=getattr(settings, "memory_max_turns", 12))
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    router = Router(tg=tg, brain=brain, settings=settings, profiles=profiles)

    @app.get("/health")
    async def health():
        return {"ok": True, "status": "alive"}

    @app.post("/tg/webhook")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        if getattr(settings, "webhook_secret", None):
            if x_telegram_bot_api_secret_token != settings.webhook_secret:
                raise HTTPException(status_code=401, detail="bad secret token")

        raw = await request.json()
        upd = Update.parse(raw)

        try:
            await router.handle_update(upd)
        except Exception as e:
            log.exception("Unhandled error: %s", e)

        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()

    return app
