# app/webapp/__init__.py
# -*- coding: utf-8 -*-

# Register the privacy-safe v18 runtime capability endpoint before the main
# webapp router is imported by FastAPI.
from app.webapp import live_runtime_router as _live_runtime_router  # noqa: F401,E402
