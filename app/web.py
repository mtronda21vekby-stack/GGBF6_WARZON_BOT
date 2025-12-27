# app/web.py
from fastapi import FastAPI, Request, HTTPException
from app.config import get_settings

app = FastAPI(title="GGBF6 WARZON BOT")

@app.get("/")
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot"}

@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    s = get_settings()
    if secret != s.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    update = await request.json()

    # TODO: сюда подключим твоего "brain + ai + ui premium"
    # пока просто чтобы Telegram видел 200 OK:
    return {"ok": True}
