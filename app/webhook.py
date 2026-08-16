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
from app.services.conversation.service import ConversationService
from app.services.profiles.service import ProfileService
from app.services.storage.factory import build_store
from app.services.vod.service import VODAnalysisService
from app.services.vod.telegram import VODTelegramIngress
from app.services.voice.service import VoiceService
from app.services.voice.telegram import VoiceTelegramController

log = get_logger("webhook")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="GGBF6 WARZON BOT", version="5.0.0")

    tg = TelegramClient(settings.bot_token)
    store = build_store(settings)
    profiles = ProfileService(store=store)
    core_brain = BrainEngine(store=store, profiles=profiles, settings=settings)
    conversation = ConversationService(brain=core_brain, store=store, profiles=profiles)

    voice_service = VoiceService(settings=settings)
    voice_controller = VoiceTelegramController(
        tg=tg,
        profiles=profiles,
        store=store,
        voice=voice_service,
    )

    vod_service = VODAnalysisService(
        api_key=settings.openai_api_key,
        model=settings.vod_vision_model,
        max_frames=settings.vod_max_frames,
        max_width=settings.vod_frame_width,
    )
    vod_ingress = VODTelegramIngress(
        tg=tg,
        vod=vod_service,
        profiles=profiles,
        store=store,
        player_memory=conversation.player_memory,
        enabled=settings.vod_enabled,
        max_bytes=settings.vod_max_bytes,
        download_timeout_s=settings.vod_download_timeout_s,
    )

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

        # Voice controls are a narrow pre-handler. Existing persona buttons
        # (TEAMMATE/COACH) still fall through to the legacy Router.
        try:
            if await voice_controller.maybe_handle_command(upd):
                return JSONResponse({"ok": True})
        except Exception as exc:
            log.exception("voice command pre-handler crashed: %s", type(exc).__name__)

        # Media/VOD gets a dedicated capability boundary before the legacy
        # text router. This keeps the large existing Router stable.
        try:
            if await vod_ingress.maybe_handle(upd):
                return JSONResponse({"ok": True})
        except Exception as exc:
            log.exception("VOD pre-handler crashed: %s", type(exc).__name__)

        try:
            msg = (upd.get("message") or upd.get("edited_message") or {}) if isinstance(upd, dict) else {}
            web_app_data = msg.get("web_app_data") if isinstance(msg, dict) else None
            data_raw = web_app_data.get("data") if isinstance(web_app_data, dict) else None

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

        chat_id = voice_controller.extract_chat_id(upd) if isinstance(upd, dict) else None
        before_voice_signature = voice_controller.history_signature(chat_id)

        try:
            await router.handle_update(upd)
        except Exception as exc:
            log.exception("Unhandled error: %s", exc)

        # AUTO speaks only when Router/ConversationService actually appended a
        # new assistant turn. Menu responses do not mutate working memory and
        # therefore do not trigger TTS.
        try:
            await voice_controller.maybe_auto(chat_id, before_voice_signature)
        except Exception as exc:
            log.warning("voice auto post-handler failed: %s", type(exc).__name__)

        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()
        close_store = getattr(store, "close", None)
        if callable(close_store):
            try:
                close_store()
            except Exception as exc:
                log.warning("storage shutdown failed: %s", type(exc).__name__)

    return app


app = create_app()
