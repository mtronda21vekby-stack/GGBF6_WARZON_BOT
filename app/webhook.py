# app/webhook.py
from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

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

    app = FastAPI(title="GGBF6 WARZON BOT", version="3.0.0")

    # =========================================================
    # CORE SERVICES (НЕ ТРОГАЕМ)
    # =========================================================
    tg = TelegramClient(settings.bot_token)

    store = InMemoryStore(memory_max_turns=settings.memory_max_turns)
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    router = Router(
        tg=tg,
        brain=brain,
        profiles=profiles,
        store=store,
        settings=settings,
    )

    # =========================================================
    # MINI APP (Telegram WebApp) — SAFE + FUTURE-PROOF
    # Структура:
    # app/webapp/webapp_router.py
    # app/webapp/static/index.html
    # =========================================================
    try:
        from app.webapp.webapp_router import router as webapp_router
        app.include_router(webapp_router)
        log.info("Mini App router loaded")
    except Exception as e:
        log.exception("Mini App router NOT loaded: %s", e)

        @app.get("/webapp", response_class=HTMLResponse, include_in_schema=False)
        async def webapp_missing():
            return (
                "<h3>Mini App is not configured</h3>"
                "<p>Expected:</p>"
                "<ul>"
                "<li>app/webapp/webapp_router.py</li>"
                "<li>app/webapp/static/index.html</li>"
                "</ul>"
            )

    # =========================================================
    # HEALTH / ROOT
    # =========================================================
    @app.get("/", include_in_schema=False)
    async def root():
        return {"ok": True, "service": "ggbf6-warzon-bot"}

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"ok": True, "status": "alive"}

    # =========================================================
    # TELEGRAM WEBHOOK (НЕ ТРОГАЕМ)
    # =========================================================
    @app.post("/tg/webhook", include_in_schema=False)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        if settings.webhook_secret:
            if x_telegram_bot_api_secret_token != settings.webhook_secret:
                raise HTTPException(status_code=401, detail="bad secret token")

        raw = await request.json()
        upd = Update.parse(raw)

        try:
            await router.handle_update(upd)
        except Exception as e:
            log.exception("Unhandled error: %s", e)

        return JSONResponse({"ok": True})

    # =========================================================
    # SHUTDOWN
    # =========================================================
    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()

    return app


# =========================================================
# Render / uvicorn ENTRYPOINT (НЕ ТРОГАЕМ)
# =========================================================
app = create_app()
