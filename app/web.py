# app/web.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.config import get_settings
from app.observability.log import log

app = FastAPI(title="GGBF6 WARZON BOT")


# =========================
# MINI APP (Telegram WebApp)
# =========================
WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

if WEBAPP_DIR.exists() and WEBAPP_DIR.is_dir():
    # /webapp -> index.html
    # /webapp/assets/... -> статика
    app.mount("/webapp", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
else:
    # Чтобы сервис не падал, если папки нет
    @app.get("/webapp", response_class=HTMLResponse)
    def webapp_missing():
        return (
            "<h3>Mini App is not configured</h3>"
            "<p>Create folder <b>app/webapp</b> and add <b>index.html</b>.</p>"
            "<p>Example path: <code>app/webapp/index.html</code></p>"
        )


@app.get("/")
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot", "status": "alive"}


@app.get("/health")
def health():
    return {"ok": True, "status": "healthy"}


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

    # ВАЖНО: webhook должен ВСЕГДА быстро отвечать 200
    # поэтому любые ошибки ловим и всё равно возвращаем {"ok": True}
    try:
        from app.adapters.telegram.webhook import handle_update
        await handle_update(update)
    except Exception:
        log.exception("Telegram handle_update crashed")

    return {"ok": True}
