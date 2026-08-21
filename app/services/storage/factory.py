# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Mapping

from app.services.storage.canonical_shadow import CanonicalReadShadowStore
from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


log = logging.getLogger("bco.storage")


class PersistentSupabaseStore(SupabaseStore):
    """Server-only Supabase adapter compatible with legacy and new API keys.

    New `sb_secret_...` keys are API keys, not JWTs, and therefore must not be
    copied into `Authorization: Bearer`. Legacy/older server keys keep the
    bearer header for backward compatibility.
    """

    def _headers(
        self,
        extra: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
            "User-Agent": "BLACK-CROWN-OPS/storage-v12",
        }
        # Supabase's new sb_secret_* keys are not JWTs. Legacy/older server
        # keys remain bearer-compatible and existing integrations/tests depend
        # on that behavior.
        if not self.key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {self.key}"
        if extra:
            headers.update(dict(extra))
        return headers

    def purge_player(
        self,
        chat_id: int,
        *,
        operation_id: str | None = None,
    ) -> None:
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

    memory = InMemoryStore(
        memory_max_turns=getattr(settings, "memory_max_turns", 20)
    )
    backend = str(
        getattr(settings, "storage_backend", "auto") or "auto"
    ).strip().lower()
    url = str(getattr(settings, "supabase_url", "") or "").strip()
    key = str(
        getattr(settings, "supabase_service_role_key", "") or ""
    ).strip()

    if backend == "memory":
        log.info("storage backend=memory")
        return memory

    wants_supabase = backend == "supabase" or (
        backend == "auto" and bool(url and key)
    )
    if not wants_supabase:
        log.info("storage backend=memory reason=no_persistent_config")
        return memory

    if not url or not key:
        log.warning(
            "storage backend=supabase requested but configuration "
            "is incomplete; using memory"
        )
        return memory

    # A browser/public key must never be accepted as the privileged backend key.
    if key.startswith("sb_publishable_"):
        log.error(
            "storage backend=supabase rejected public credential; using memory"
        )
        return memory

    try:
        persistent = PersistentSupabaseStore(
            url=url,
            service_role_key=key,
            memory_max_turns=getattr(settings, "memory_max_turns", 20),
            schema=str(
                getattr(settings, "supabase_schema", "public") or "public"
            ),
            timeout_s=float(
                getattr(settings, "storage_timeout_s", 8.0) or 8.0
            ),
        )
        primary = CanonicalReadShadowStore(
            persistent,
            enabled=bool(
                getattr(settings, "canonical_read_shadow_enabled", True)
            ),
            sample_rate=float(
                getattr(
                    settings,
                    "canonical_read_shadow_sample_rate",
                    1.0,
                )
                or 0.0
            ),
            identity_cache_ttl_s=float(
                getattr(
                    settings,
                    "canonical_read_identity_cache_ttl_s",
                    120.0,
                )
                or 120.0
            ),
            identity_negative_cache_ttl_s=float(
                getattr(
                    settings,
                    "canonical_read_identity_negative_cache_ttl_s",
                    5.0,
                )
                or 5.0
            ),
            identity_cache_max_entries=int(
                getattr(
                    settings,
                    "canonical_read_identity_cache_max_entries",
                    10_000,
                )
                or 10_000
            ),
        )
        outbox_max = int(
            getattr(settings, "storage_outbox_max", 500) or 500
        )
        replay_batch = int(
            getattr(settings, "storage_replay_batch", 50) or 50
        )
        credential_kind = (
            "secret" if key.startswith("sb_secret_") else "legacy_or_unknown"
        )
        log.info(
            "storage backend=supabase credential=%s "
            "resilient_fallback=memory outbox_max=%d replay_batch=%d "
            "canonical_read_shadow=%s sample_rate=%.3f",
            credential_kind,
            outbox_max,
            replay_batch,
            primary.enabled,
            primary.sample_rate,
        )
        return PersistentResilientStore(
            primary=primary,
            fallback=memory,
            outbox_max=outbox_max,
            replay_batch=replay_batch,
        )
    except Exception as exc:
        log.warning(
            "storage init failed backend=supabase error=%s; using memory",
            type(exc).__name__,
        )
        return memory
