# app/web.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.config import get_settings
from app.observability.log import log

app = FastAPI(title="GGBF6 WARZON BOT")

# =========================================================
# MINI APP (Telegram WebApp) — PRODUCTION SAFE
# =========================================================
try:
    from app.webapp.webapp_router import router as webapp_router
    app.include_router(webapp_router)
except Exception as e:
    log.exception("Mini App router not loaded: %s", e)

    # Fallback покрывает /webapp, /webapp/ и всё внутри
    @app.get("/webapp", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/webapp/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/webapp/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    def webapp_missing(path: str = ""):
        return (
            "<h3>Mini App is not configured</h3>"
            "<p>Expected files:</p>"
            "<ul>"
            "<li><code>app/webapp/webapp_router.py</code></li>"
            "<li><code>app/webapp/static/index.html</code></li>"
            "</ul>"
            "<p>Fix the paths and redeploy.</p>"
        )

@app.get("/", include_in_schema=False)
def root():
    return {"ok": True, "service": "ggbf6-warzon-bot", "status": "alive"}

@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True, "status": "healthy"}

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

    try:
        from app.adapters.telegram.webhook import handle_update
        await handle_update(update)
    except Exception:
        log.exception("Telegram handle_update crashed")

    return {"ok": True}
