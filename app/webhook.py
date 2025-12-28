# app/webhook.py  (ЗАМЕНИ ЦЕЛИКОМ)
from __future__ import annotations

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.adapters.telegram.client import TelegramClient
from app.adapters.telegram.types import Update
from app.core.router import Router

# если у тебя уже есть BrainEngine — оставь импорт/инициализацию как было
# тут ставим временную заглушку, чтобы ВСЁ ЗАПУСТИЛОСЬ
class _BrainStub:
    async def handle_text(self, *args, **kwargs):
        return None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="GGBF6 Bot Webhook", version="1.0.0")

    tg = TelegramClient(settings.bot_token)
    brain = _BrainStub()
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
        if getattr(settings, "webhook_secret", None):
            if x_telegram_bot_api_secret_token != settings.webhook_secret:
                raise HTTPException(status_code=401, detail="bad secret token")

        raw = await request.json()
        upd = Update.parse(raw)

        try:
            await router.handle_update(upd)
        except Exception:
            # всегда 200, чтобы телега не ретраила бесконечно
            pass

        return JSONResponse({"ok": True})

    return app


app = create_app()
