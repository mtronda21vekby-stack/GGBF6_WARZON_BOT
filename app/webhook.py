# app/webhook.py
from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.observability.log import setup_logging, get_logger
from app.adapters.telegram.types import Update
from app.adapters.telegram.client import TelegramClient
from app.core.router import Router
from app.services.brain.engine import BrainEngine
from app.services.profiles.service import ProfileService

log = get_logger("webhook")


# ================= SAFE MEMORY (INLINE) =================
class InMemoryStore:
    def __init__(self, *args, **kwargs):
        limit = None

        if "memory_max_turns" in kwargs:
            limit = kwargs["memory_max_turns"]
        elif "max_turns" in kwargs:
            limit = kwargs["max_turns"]
        elif len(args) > 0:
            limit = args[0]

        try:
            self.max_turns = int(limit) if limit is not None else 20
        except Exception:
            self.max_turns = 20

        if self.max_turns < 4:
            self.max_turns = 4

        self.data = {}

    def add(self, chat_id, role, content):
        chat_id = int(chat_id)
        self.data.setdefault(chat_id, [])
        self.data[chat_id].append({"role": role, "content": content})
        if len(self.data[chat_id]) > self.max_turns:
            self.data[chat_id] = self.data[chat_id][-self.max_turns:]

    def get(self, chat_id):
        return self.data.get(int(chat_id), [])

    def clear(self, chat_id):
        self.data.pop(int(chat_id), None)
# ================= END SAFE MEMORY =================


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(title="GGBF6 WARZON BOT", version="3.0.0")

    tg = TelegramClient(settings.bot_token)

    store = InMemoryStore(memory_max_turns=settings.memory_max_turns)
    profiles = ProfileService(store=store)
    brain = BrainEngine(store=store, profiles=profiles, settings=settings)

    router = Router(tg=tg, brain=brain, profiles=profiles, settings=settings)

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
        # Защита от левых запросов
        if settings.webhook_secret:
            if x_telegram_bot_api_secret_token != settings.webhook_secret:
                raise HTTPException(status_code=401, detail="bad secret token")

        raw = await request.json()
        upd = Update.parse(raw)

        try:
            await router.handle_update(upd)
        except Exception as e:
            log.exception("Unhandled error: %s", e)

        # Telegram всегда 200
        return JSONResponse({"ok": True})

    @app.on_event("shutdown")
    async def _shutdown():
        await tg.close()

    return app


# Render/uvicorn entrypoint:
app = create_app()
