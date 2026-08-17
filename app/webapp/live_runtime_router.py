# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi.responses import JSONResponse

from app.webapp import webapp_router_base as _base


@_base.router.post("/webapp/api/runtime", include_in_schema=False)
def webapp_live_runtime():
    """Public capability flags only; never expose configuration values or secrets."""
    settings = _base.APP_SETTINGS
    live_stream = bool(getattr(settings, "webapp_live_stream_enabled", True)) if settings else True
    cinematic = bool(getattr(settings, "webapp_cinematic_ui_enabled", True)) if settings else True
    return JSONResponse(
        {
            "ok": True,
            "build": _base._build_id(),
            "release": "bco-live-intelligence-v18",
            "webapp": {
                "live_stream": live_stream,
                "cinematic_ui": cinematic,
                "v18_overlay": live_stream and cinematic,
                "transport": "ndjson" if live_stream else "json",
            },
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "X-Content-Type-Options": "nosniff",
        },
    )
