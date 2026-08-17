# app/webhook.py
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.adapters.telegram.client import TelegramClient
from app.adapters.telegram.types import Update
from app.config import get_settings
from app.core.router import Router
from app.observability.log import get_logger, setup_logging
from app.observability.readiness import readiness_snapshot
from app.release import APP_VERSION, RELEASE_CONTRACT
from app.security.usage_guard import UpdateReplayGuard, UsageGuard
from app.services.brain.engine import BrainEngine
from app.services.conversation.service import ConversationService
from app.services.entitlements.service import PremiumEntitlementService
from app.services.entitlements.site_bridge import SiteEntitlementBridgeAPI
from app.services.entitlements.telegram import EntitlementTelegramController
from app.services.profiles.service import ProfileService
from app.services.storage.factory import build_store
from app.services.telegram.command_console import CommandConsoleController
from app.services.vod.service import VODAnalysisService
from app.services.vod.telegram import VODTelegramIngress
from app.services.voice.ingress import TelegramVoiceIngress
from app.services.voice.service import VoiceService
from app.services.voice.telegram import VoiceTelegramController
from app.services.voice.transcription import OpenAITranscriptionBackend

log = get_logger("webhook")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    tg = TelegramClient(settings.bot_token)
    store = build_store(settings)
    profiles = ProfileService(store=store)
    entitlement_service = PremiumEntitlementService(settings)
    entitlement_controller = EntitlementTelegramController(tg=tg, service=entitlement_service)
    site_entitlement_bridge = SiteEntitlementBridgeAPI(settings=settings, entitlements=entitlement_service)
    usage_guard = UsageGuard.from_settings(settings)
    replay_guard = UpdateReplayGuard(
        ttl_s=settings.telegram_update_dedupe_ttl_s,
        max_entries=settings.telegram_update_dedupe_max_entries,
    )
    command_console: CommandConsoleController | None = None

    transcription_backend = OpenAITranscriptionBackend(
        api_key=settings.openai_api_key,
        model=settings.voice_transcription_model,
        fallback_model=settings.voice_transcription_fallback_model,
        language=settings.voice_transcription_language,
        timeout_s=settings.voice_transcription_timeout_s,
        max_bytes=settings.voice_input_max_bytes,
    )
    voice_ingress = TelegramVoiceIngress(
        tg=tg,
        transcription=transcription_backend,
        profiles=profiles,
        usage_guard=usage_guard,
        enabled=settings.voice_input_enabled,
        max_bytes=settings.voice_input_max_bytes,
        max_duration_s=settings.voice_input_max_duration_s,
        confidence_threshold=settings.voice_transcription_confidence_threshold,
        confirmation_ttl_s=settings.voice_transcript_confirmation_ttl_s,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        probe = getattr(store, "probe_primary", None)
        if callable(probe):
            try:
                ok = await asyncio.to_thread(probe)
                log.info("storage startup probe result=%s adapter=%s", "ok" if ok else "failed", type(store).__name__)
            except Exception as exc:
                log.warning("storage startup probe crashed error=%s", type(exc).__name__)
        else:
            log.info("storage startup probe skipped adapter=%s", type(store).__name__)

        if command_console is not None:
            try:
                await asyncio.wait_for(command_console.configure_bot_surface(), timeout=8.0)
                log.info("AAA Telegram command surface configured")
            except Exception as exc:
                log.warning("AAA Telegram command surface setup failed: %s", type(exc).__name__)

        try:
            yield
        finally:
            try:
                await transcription_backend.close()
            except Exception as exc:
                log.warning("voice transcription shutdown failed: %s", type(exc).__name__)
            try:
                await site_entitlement_bridge.close()
            except Exception as exc:
                log.warning("site entitlement bridge shutdown failed: %s", type(exc).__name__)
            try:
                await entitlement_service.close()
            except Exception as exc:
                log.warning("entitlement service shutdown failed: %s", type(exc).__name__)
            await tg.close()
            close_store = getattr(store, "close", None)
            if callable(close_store):
                try:
                    close_store()
                except Exception as exc:
                    log.warning("storage shutdown failed: %s", type(exc).__name__)

    app = FastAPI(title="GGBF6 WARZON BOT", version=APP_VERSION, lifespan=lifespan)
    app.include_router(site_entitlement_bridge.router)

    core_brain = BrainEngine(store=store, profiles=profiles, settings=settings)
    conversation = ConversationService(brain=core_brain, store=store, profiles=profiles, usage_guard=usage_guard)
    command_console = CommandConsoleController(
        tg=tg, profiles=profiles, store=store, entitlements=entitlement_service, settings=settings
    )

    voice_service = VoiceService(settings=settings)
    voice_controller = VoiceTelegramController(
        tg=tg, profiles=profiles, store=store, voice=voice_service, usage_guard=usage_guard
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
        usage_guard=usage_guard,
        enabled=settings.vod_enabled,
        max_bytes=settings.vod_max_bytes,
        download_timeout_s=settings.vod_download_timeout_s,
    )

    router = Router(tg=tg, brain=conversation, profiles=profiles, store=store, settings=settings)

    try:
        from app.webapp.command_center_router import bind_runtime as command_center_bind_runtime
        from app.webapp.command_center_router import router as command_center_router
        app.include_router(command_center_router)
        command_center_bind_runtime(store=store, profiles=profiles, entitlements=entitlement_service)
        log.info("Command Center runtime bind: OK")
    except Exception as exc:
        log.exception("Command Center runtime bind FAILED: %s", type(exc).__name__)

    try:
        from app.webapp.quality_router import bind_runtime as quality_bind_runtime
        from app.webapp.quality_router import router as quality_router
        app.include_router(quality_router)
        quality_bind_runtime(store=store)
        log.info("Quality feedback runtime bind: OK")
    except Exception as exc:
        log.exception("Quality feedback runtime bind FAILED: %s", type(exc).__name__)

    try:
        from app.webapp.webapp_router import bind_runtime as webapp_bind_runtime
        from app.webapp.webapp_router import router as webapp_router
        app.include_router(webapp_router)
        try:
            webapp_bind_runtime(brain=conversation, profiles=profiles, store=store, settings=settings)
            log.info("Mini App runtime bind: OK")
        except Exception as exc:
            log.exception("Mini App runtime bind FAILED: %s", exc)
        log.info("Mini App router loaded")
    except Exception as exc:
        log.exception("Mini App router NOT loaded: %s", exc)

        @app.get("/webapp", response_class=HTMLResponse, include_in_schema=False)
        async def webapp_missing():
            return (
                "<h3>Mini App is not configured</h3><p>Expected:</p><ul>"
                "<li>app/webapp/webapp_router.py</li><li>app/webapp/static/index.html</li></ul>"
            )

    @app.get("/", include_in_schema=False)
    async def root():
        return {"ok": True, "service": "ggbf6-warzon-bot"}

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"ok": True, "status": "alive"}

    @app.get("/health/details", include_in_schema=False)
    async def health_details():
        return readiness_snapshot(
            settings,
            store,
            app_version=APP_VERSION,
            release_contract=RELEASE_CONTRACT,
            usage_guard=usage_guard,
            replay_guard=replay_guard,
            entitlement_service=entitlement_service,
        )

    @app.post("/tg/webhook", include_in_schema=False)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ):
        if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
            raise HTTPException(status_code=401, detail="bad secret token")

        max_bytes = max(1024, int(settings.telegram_max_update_bytes or 256 * 1024))
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    raise HTTPException(status_code=413, detail="telegram update too large")
            except ValueError:
                pass

        body = await request.body()
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="telegram update too large")
        try:
            raw = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            raise HTTPException(status_code=400, detail="invalid telegram update")
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="invalid telegram update")

        update_id = raw.get("update_id")
        if update_id is not None and not replay_guard.accept(update_id):
            return JSONResponse({"ok": True, "duplicate": True})

        upd = Update.parse(raw)
        input_mode = "text"

        try:
            transformed, voice_handled = await voice_ingress.transform(upd)
            if voice_handled:
                upd = transformed
                msg = (upd.get("message") or upd.get("edited_message") or {}) if isinstance(upd, dict) else {}
                input_mode = str(msg.get("_bco_input_mode") or "") if isinstance(msg, dict) else ""
                if not input_mode.startswith("voice"):
                    return JSONResponse({"ok": True, "voice_consumed": True})
        except Exception as exc:
            log.exception("voice ingress pre-handler crashed: %s", type(exc).__name__)

        try:
            if await command_console.maybe_handle(upd):
                return JSONResponse({"ok": True})
        except Exception as exc:
            log.exception("AAA command console pre-handler crashed: %s", type(exc).__name__)

        try:
            callback = upd.get("callback_query") if isinstance(upd, dict) else None
            if isinstance(callback, dict):
                callback_id = str(callback.get("id") or "").strip()
                if callback_id:
                    await tg.answer_callback_query(callback_id)
        except Exception as exc:
            log.warning("legacy callback acknowledgement failed: %s", type(exc).__name__)

        try:
            if await entitlement_controller.maybe_handle_command(upd):
                return JSONResponse({"ok": True})
        except Exception as exc:
            log.exception("Premium account bridge pre-handler crashed: %s", type(exc).__name__)

        try:
            if await voice_controller.maybe_handle_command(upd):
                return JSONResponse({"ok": True})
        except Exception as exc:
            log.exception("voice command pre-handler crashed: %s", type(exc).__name__)

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

        try:
            await voice_controller.maybe_auto(chat_id, before_voice_signature, input_mode=input_mode)
        except Exception as exc:
            log.warning("voice auto post-handler failed: %s", type(exc).__name__)

        return JSONResponse({"ok": True})

    return app


app = create_app()
