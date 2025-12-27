# app/web.py
from fastapi import FastAPI, Request, HTTPException
from app.config import get_settings
from app.observability.log import log

app = FastAPI(title="GGBF6 WARZON BOT")


@app.get("/")
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot"}


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    s = get_settings()
    if secret != s.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        update = await request.json()
    except Exception:
        log.exception("Failed to parse JSON body")
        raise HTTPException(status_code=400, detail="bad json")

    # ВАЖНО: webhook должен ВСЕГДА быстро отвечать 200,
    # поэтому любые ошибки ловим и возвращаем {"ok": True}
    try:
        # Точка интеграции: один-единственный обработчик Telegram
        from app.adapters.telegram.webhook import handle_update
        await handle_update(update)
    except Exception:
        log.exception("Telegram handle_update crashed")

    return {"ok": True}