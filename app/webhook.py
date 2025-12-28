# app/webhook.py
from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.observability.log import setup_logging, get_logger
from app.adapters.telegram.client import TelegramClient
from app.core.router import Router
from app.services.brain.engine import BrainEngine
from app.services.brain.memory import InMemoryStore
from app.services.profiles.service import ProfileService

log = get_logger("webhook")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="GGBF6 WARZON BOT", version="3.0.0")

    tg = TelegramClient(settings.bot_token)

    # IMPORTANT: Store должен принимать разные имена аргументов (мы это починим в memory.py)
    store = InMemoryStore(memory_max_turns=getattr(settings, "memory_max_turns", 20))
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    # IMPORTANT: передаём store в Router (иначе память/статус/очистка не работают)
    router = Router(tg=tg, brain=brain, profiles=profiles, store=store, settings=settings)

    @app.get("/")
    async def root():
        return {"ok": True, "service": "ggbf6-warzon-bot"}

    @app.get("/health")
    async def health():
        return {"ok": True, "status": "alive"}

    @app.post("/tg/webhook")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        # защита от левых запросов
        if getattr(settings, "webhook_secret", ""):
            if x_telegram_bot_api_secret_token != settings.webhook_secret:
                raise HTTPException(status_code=401, detail="bad secret token")

        raw = await request.json()

        try:
            # IMPORTANT: в роутер отдаём СЫРОЙ dict (100% совместимо)
            await router.handle_update(raw)
        except Exception as e:
            log.exception("Unhandled error: %s", e)

        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()

    return app


app = create_app()
