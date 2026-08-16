# app/services/brain/memory.py
"""Backward-compatible import for the production webhook.

New storage implementations live under app.services.storage.
"""
from app.services.storage.memory import InMemoryStore

__all__ = ["InMemoryStore"]
