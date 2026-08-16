# app/webhook.py
from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.adapters.telegram.client import TelegramClient
from app.adapters.telegram.types import Update
from app.config import get_settings
from app.core.router import Router
from app.observability.log import get_logger, setup_logging
from app.services.brain.engine import BrainEngine
from app.services.brain.memory import InMemoryStore
from app.services.conversation.service import ConversationService
from app.services.profiles.service import ProfileService

log = get_logger("webhook")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="GGBF6 WARZON BOT", version="4.0.0")

    tg = TelegramClient(settings.bot_token)
    store = InMemoryStore(memory_max_turns=settings.memory_max_turns)
    profiles = ProfileService(store=store)
    core_brain = BrainEngine(store=store, profiles=profiles, settings=settings)
    conversation = ConversationService(brain=core_brain)

    router = Router(
        tg=tg,
        brain=conversation,
        profiles=profiles,
        store=store,
        settings=settings,
    )

    try:
        from app.webapp.webapp_router import bind_runtime as webapp_bind_runtime
        from app.webapp.webapp_router import router as webapp_router

        app.include_router(webapp_router)
        try:
            webapp_bind_runtime(
                brain=conversation,
                profiles=profiles,
                store=store,
                settings=settings,
            )
            log.info("Mini App runtime bind: OK")
        except Exception as exc:
            log.exception("Mini App runtime bind FAILED: %s", exc)

        log.info("Mini App router loaded")
    except Exception as exc:
        log.exception("Mini App router NOT loaded: %s", exc)

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

    @app.get("/", include_in_schema=False)
    async def root():
        return {"ok": True, "service": "ggbf6-warzon-bot"}

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"ok": True, "status": "alive"}

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
            msg = getattr(upd, "message", None)
            web_app_data = getattr(msg, "web_app_data", None) if msg else None

            data_raw = None
            if web_app_data:
                if isinstance(web_app_data, dict):
                    data_raw = web_app_data.get("data")
                else:
                    data_raw = getattr(web_app_data, "data", None)

            if data_raw:
                handler = getattr(router, "handle_webapp_data", None)
                if callable(handler):
                    try:
                        await handler(upd, data_raw)
                        return JSONResponse({"ok": True})
                    except Exception as exc:
                        log.exception("handle_webapp_data crashed: %s", exc)
                else:
                    log.warning("Router has no handle_webapp_data() yet")
        except Exception as exc:
            log.exception("web_app_data pre-handler crashed: %s", exc)

        try:
            await router.handle_update(upd)
        except Exception as exc:
            log.exception("Unhandled error: %s", exc)

        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()

    return app


app = create_app()
