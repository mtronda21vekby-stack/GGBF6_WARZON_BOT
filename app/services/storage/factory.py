# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


log = logging.getLogger("bco.storage")


def build_store(settings: Any):
    """Build the configured storage backend without making persistence mandatory.

    STORAGE_BACKEND:
      - memory: always in-process memory
      - supabase: use Supabase when configured, otherwise memory fallback
      - auto (default): Supabase when both URL/key exist, otherwise memory
    """
    memory = InMemoryStore(memory_max_turns=getattr(settings, "memory_max_turns", 20))
    backend = str(getattr(settings, "storage_backend", "auto") or "auto").strip().lower()
    url = str(getattr(settings, "supabase_url", "") or "").strip()
    key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()

    if backend == "memory":
        log.info("storage backend=memory")
        return memory

    wants_supabase = backend == "supabase" or (backend == "auto" and bool(url and key))
    if not wants_supabase:
        log.info("storage backend=memory reason=no_persistent_config")
        return memory

    if not url or not key:
        log.warning("storage backend=supabase requested but configuration is incomplete; using memory")
        return memory

    try:
        primary = SupabaseStore(
            url=url,
            service_role_key=key,
            memory_max_turns=getattr(settings, "memory_max_turns", 20),
            schema=str(getattr(settings, "supabase_schema", "public") or "public"),
            timeout_s=float(getattr(settings, "storage_timeout_s", 8.0) or 8.0),
        )
        log.info("storage backend=supabase resilient_fallback=memory")
        return ResilientStore(primary=primary, fallback=memory)
    except Exception as exc:
        log.warning("storage init failed backend=supabase error=%s; using memory", type(exc).__name__)
        return memory
