from fastapi import FastAPI, Request, HTTPException
from telegram import Update

from app.config import get_settings
from app.log import setup_logger
from app.telegram_bot import build_application

logger = setup_logger()
settings = get_settings()

fastapi_app = FastAPI()
tg_app = build_application()

@fastapi_app.get("/healthz")
async def healthz():
    return {"ok": True}

@fastapi_app.post("/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")

    data = await request.json()
    update = Update.de_json(data, tg_app.bot)

    # Важно: PTB должен быть “инициализирован”
    await tg_app.initialize()
    await tg_app.process_update(update)
    return {"ok": True}

app = fastapi_app
