# app/web.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.config import get_settings
from app.observability.log import log

app = FastAPI(title="GGBF6 WARZON BOT")

# =========================================================
# MINI APP (Telegram WebApp) — MAX / PRODUCTION-SAFE
# ВАЖНО:
# - У тебя структура: app/webapp/static/index.html + app/webapp/webapp_router.py
# - Значит НУЖНО include_router, а не mount на папку app/webapp (иначе будет 404)
# =========================================================
try:
    # app/webapp/webapp_router.py (у тебя уже есть)
    from app.webapp.webapp_router import router as webapp_router

    # /webapp и /webapp/* будет отдавать index.html + статику из app/webapp/static
    app.include_router(webapp_router)

except Exception as e:
    log.exception("Mini App router not loaded: %s", e)

    @app.get("/webapp", response_class=HTMLResponse, include_in_schema=False)
    def webapp_missing():
        return (
            "<h3>Mini App is not configured</h3>"
            "<p>Expected files:</p>"
            "<ul>"
            "<li><code>app/webapp/webapp_router.py</code></li>"
            "<li><code>app/webapp/static/index.html</code></li>"
            "</ul>"
            "<p>Fix the paths and redeploy.</p>"
        )


# =========================================================
# ROOT / HEALTH
# =========================================================
@app.get("/", include_in_schema=False)
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot", "status": "alive"}


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True, "status": "healthy"}


# =========================================================
# TELEGRAM WEBHOOK (FAST + SAFE)
# =========================================================
@app.post("/telegram/webhook/{secret}", include_in_schema=False)
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
