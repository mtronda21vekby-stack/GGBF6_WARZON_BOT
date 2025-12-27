# app/web.py
from fastapi import FastAPI, Request, HTTPException
import httpx

from app.config import get_settings

app = FastAPI(title="GGBF6 WARZON BOT")


@app.get("/")
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot"}


async def tg_send_message(bot_token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        # если тут ошибка — Render логи покажут, почему
        r.raise_for_status()


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    s = get_settings()

    # защита webhook
    if secret != s.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")

    update = await request.json()

    # 1) достаём chat_id и текст (обычное сообщение)
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text")

    # 2) если это не текст (например стикер/фото) — просто 200 OK
    if not chat_id or not isinstance(text, str):
        return {"ok": True}

    # 3) минимальная логика ответа
    if text.strip().lower() in ("/start", "старт"):
        reply = "✅ Бот жив. Напиши любое сообщение — я отвечу."
    else:
        reply = f"✅ Получил: {text}"

    # 4) отправляем ответ
    await tg_send_message(s.BOT_TOKEN, int(chat_id), reply)

    return {"ok": True}
