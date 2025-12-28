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

    app = FastAPI(title="GGBF6 WARZON BOT", version="1.0.0")

    tg = TelegramClient(settings.BOT_TOKEN)

    store = InMemoryStore(memory_max_turns=settings.memory_max_turns)
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    router = Router(tg=tg, brain=brain, settings=settings)

    @app.get("/")
    async def root():
        return {"ok": True, "service": "ggbf6-warzon-bot"}

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
        upd = Update.parse(raw)

        try:
            await router.handle_update(upd)
        except Exception:
            log.exception("Unhandled error in router")

        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def shutdown():
        await tg.close()

    return app


app = create_app()
