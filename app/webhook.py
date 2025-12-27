# app/webhook.py
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
    setup_logging(settings.log_level)

    app = FastAPI(title="GGBF6 Bot", version="1.0.0")

    # Telegram client
    tg = TelegramClient(settings.BOT_TOKEN)

    # Brain stack
    store = InMemoryStore(memory_max_turns=settings.memory_max_turns)
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    router = Router(tg=tg, brain=brain, settings=settings)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/tg/webhook")
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        if settings.WEBHOOK_SECRET:
            if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
                raise HTTPException(status_code=401, detail="bad secret")

        raw = await request.json()
        update = Update.parse(raw)

        try:
            await router.handle_update(update)
        except Exception:
            log.exception("Telegram update crashed")

        # Telegram ВСЕГДА должен получать 200
        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def shutdown():
        await tg.close()

    return app


# 🔴 ВАЖНО: ЭТО ОБЯЗАТЕЛЬНО
app = create_app()