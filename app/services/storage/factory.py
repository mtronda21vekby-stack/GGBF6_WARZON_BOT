# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


log = logging.getLogger("bco.storage")


class PersistentSupabaseStore(SupabaseStore):
    def purge_player(self, chat_id: int, *, operation_id: str | None = None) -> None:
        self._request(
            "POST",
            "rpc/bco_purge_player",
            json={"p_chat_id": int(chat_id)},
            extra_headers={"Prefer": "return=minimal"},
        )


class PersistentResilientStore(ResilientStore):
    def purge_player(self, chat_id: int) -> None:
        self._write("purge_player", chat_id)


def build_store(settings: Any):
    """Build optional persistent storage with in-process recovery fallback."""
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
        primary = PersistentSupabaseStore(
            url=url,
            service_role_key=key,
            memory_max_turns=getattr(settings, "memory_max_turns", 20),
            schema=str(getattr(settings, "supabase_schema", "public") or "public"),
            timeout_s=float(getattr(settings, "storage_timeout_s", 8.0) or 8.0),
        )
        outbox_max = int(getattr(settings, "storage_outbox_max", 500) or 500)
        replay_batch = int(getattr(settings, "storage_replay_batch", 50) or 50)
        log.info(
            "storage backend=supabase resilient_fallback=memory outbox_max=%d replay_batch=%d",
            outbox_max, replay_batch,
        )
        return PersistentResilientStore(
            primary=primary,
            fallback=memory,
            outbox_max=outbox_max,
            replay_batch=replay_batch,
        )
    except Exception as exc:
        log.warning("storage init failed backend=supabase error=%s; using memory", type(exc).__name__)
        return memory
