# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Mapping

from app.services.storage.canonical_read import CanonicalReadRouter
from app.services.storage.memory import InMemoryStore
from app.services.storage.resilient import ResilientStore
from app.services.storage.supabase import SupabaseStore


log = logging.getLogger("bco.storage")


class PersistentSupabaseStore(SupabaseStore):
    """Server-only Supabase adapter compatible with legacy and new API keys.

    New `sb_secret_...` keys are API keys, not JWTs, and therefore must not be
    copied into `Authorization: Bearer`. Legacy/older server keys keep the
    bearer header for backward compatibility.

    Canonical-first reads are controlled by a server-only database flag. Any
    missing flag, unresolved identity, conflict, ambiguous singleton, empty
    canonical result or query error fails closed to the existing legacy key.
    """

    def __init__(
        self,
        *,
        canonical_read_capability_enabled: bool = True,
        canonical_read_flag_cache_ttl_s: float = 15.0,
        canonical_read_identity_cache_ttl_s: float = 120.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._canonical_reads = CanonicalReadRouter(
            request=self._request,
            rows=self._rows,
            capability_enabled=canonical_read_capability_enabled,
            flag_cache_ttl_s=canonical_read_flag_cache_ttl_s,
            identity_cache_ttl_s=canonical_read_identity_cache_ttl_s,
        )

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
            "User-Agent": "BLACK-CROWN-OPS/storage-canonical-read-v1",
        }
        # Supabase's new sb_secret_* keys are not JWTs. Legacy/older server
        # keys remain bearer-compatible and existing integrations/tests depend
        # on that behavior.
        if not self.key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {self.key}"
        if extra:
            headers.update(dict(extra))
        return headers

    def resolve_telegram_identity(self, telegram_user_id: int) -> dict[str, Any]:
        identity = super().resolve_telegram_identity(int(telegram_user_id))
        self._canonical_reads.prime_telegram_identity(
            int(telegram_user_id),
            identity,
        )
        return identity

    def canonical_read_status(self) -> dict[str, Any]:
        return self._canonical_reads.snapshot(refresh_flag=True)

    def _count(self, table: str, chat_id: int) -> int:
        return self._canonical_reads.count(
            table,
            int(chat_id),
            select_column="id",
            legacy_column="chat_id",
        )

    def get(self, chat_id: int) -> list[dict]:
        rows = self._canonical_reads.select_rows(
            "bco_messages",
            int(chat_id),
            params={
                "select": "role,content,created_at",
                "order": "id.desc",
                "limit": str(self.memory_max_turns * 2),
            },
        )
        rows.reverse()
        return [
            {
                "role": str(row.get("role") or ""),
                "content": str(row.get("content") or ""),
            }
            for row in rows
        ]

    def get_profile(self, chat_id: int) -> dict[str, Any]:
        rows = self._canonical_reads.select_rows(
            "bco_players",
            int(chat_id),
            params={
                "select": "profile,chat_id,updated_at",
                "order": "updated_at.desc,chat_id.asc",
                "limit": "1",
            },
            singleton=True,
        )
        profile = rows[0].get("profile") if rows else {}
        return dict(profile) if isinstance(profile, dict) else {}

    def get_summary(self, chat_id: int) -> str:
        rows = self._canonical_reads.select_rows(
            "bco_players",
            int(chat_id),
            params={
                "select": "summary,chat_id,updated_at",
                "order": "updated_at.desc,chat_id.asc",
                "limit": "1",
            },
            singleton=True,
        )
        return str(rows[0].get("summary") or "") if rows else ""

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        rows = self._canonical_reads.select_rows(
            "bco_players",
            int(chat_id),
            params={
                "select": "derived,chat_id,updated_at",
                "order": "updated_at.desc,chat_id.asc",
                "limit": "1",
            },
            singleton=True,
        )
        value = rows[0].get("derived") if rows else {}
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _merge_mistake_rows(rows: list[dict]) -> list[dict]:
        merged: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("mistake_key") or "").strip()
            if not key:
                continue
            current = merged.setdefault(
                key,
                {
                    "mistake_key": key,
                    "label": "",
                    "count": 0,
                    "first_seen": "",
                    "last_seen": "",
                    "evidence": {},
                },
            )
            current["count"] = int(current.get("count") or 0) + max(
                0,
                int(row.get("count") or 0),
            )
            first_seen = str(row.get("first_seen") or "")
            last_seen = str(row.get("last_seen") or "")
            if first_seen and (
                not current["first_seen"] or first_seen < current["first_seen"]
            ):
                current["first_seen"] = first_seen
            if last_seen and last_seen >= str(current["last_seen"] or ""):
                current["last_seen"] = last_seen
                current["label"] = str(row.get("label") or current["label"])
            elif not current["label"]:
                current["label"] = str(row.get("label") or "")
            evidence = row.get("evidence")
            if isinstance(evidence, dict):
                current["evidence"] = {
                    **dict(current.get("evidence") or {}),
                    **evidence,
                }

        return sorted(
            merged.values(),
            key=lambda item: (
                -int(item.get("count") or 0),
                str(item.get("last_seen") or ""),
            ),
            reverse=False,
        )[:20]

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        rows = self._canonical_reads.select_rows(
            "bco_player_mistakes",
            int(chat_id),
            params={
                "select": (
                    "mistake_key,label,count,first_seen,last_seen,evidence"
                ),
                "order": "count.desc,last_seen.desc",
                "limit": "100",
            },
        )
        return self._merge_mistake_rows(rows)

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        rows = self._canonical_reads.select_rows(
            "bco_episodes",
            int(chat_id),
            params={
                "select": "kind,data,created_at",
                "order": "id.desc",
                "limit": str(max(1, min(int(limit), 100))),
            },
        )
        normalized: list[dict] = []
        for row in rows:
            data = row.get("data") if isinstance(row.get("data"), dict) else {}
            normalized.append(
                dict(
                    data,
                    kind=row.get("kind"),
                    created_at=row.get("created_at"),
                )
            )
        return normalized

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        rows = self._canonical_reads.select_rows(
            "bco_training_sessions",
            int(chat_id),
            params={
                "select": "data,created_at",
                "order": "id.desc",
                "limit": "50",
            },
        )
        return [
            dict(
                row.get("data") if isinstance(row.get("data"), dict) else {},
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    def list_progression_events(self, chat_id: int) -> list[dict]:
        rows = self._canonical_reads.select_rows(
            "bco_progression_events",
            int(chat_id),
            params={
                "select": "data,created_at",
                "order": "id.desc",
                "limit": "100",
            },
        )
        return [
            dict(
                row.get("data") if isinstance(row.get("data"), dict) else {},
                created_at=row.get("created_at"),
            )
            for row in rows
        ]

    def purge_player(self, chat_id: int, *, operation_id: str | None = None) -> None:
        # Destructive lifecycle behavior remains legacy-scoped in Phase 2C.
        self._request(
            "POST",
            "rpc/bco_purge_player",
            json={"p_chat_id": int(chat_id)},
            extra_headers={"Prefer": "return=minimal"},
        )


class PersistentResilientStore(ResilientStore):
    def purge_player(self, chat_id: int) -> None:
        self._write("purge_player", chat_id)

    def canonical_read_status(self) -> dict[str, Any]:
        status = getattr(self.primary, "canonical_read_status", None)
        if not callable(status):
            return {
                "schema_version": "bco-canonical-read-v1",
                "capability_enabled": False,
                "database_flag_enabled": False,
                "mode": "legacy",
                "last_control_error": "primary_status_unavailable",
            }
        try:
            return dict(status() or {})
        except Exception as exc:
            return {
                "schema_version": "bco-canonical-read-v1",
                "capability_enabled": True,
                "database_flag_enabled": False,
                "mode": "legacy",
                "last_control_error": type(exc).__name__,
            }


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

    # A browser/public key must never be accepted as the privileged backend key.
    if key.startswith("sb_publishable_"):
        log.error("storage backend=supabase rejected public credential; using memory")
        return memory

    try:
        canonical_read_capability = bool(
            getattr(settings, "canonical_read_capability_enabled", True)
        )
        primary = PersistentSupabaseStore(
            url=url,
            service_role_key=key,
            memory_max_turns=getattr(settings, "memory_max_turns", 20),
            schema=str(getattr(settings, "supabase_schema", "public") or "public"),
            timeout_s=float(getattr(settings, "storage_timeout_s", 8.0) or 8.0),
            canonical_read_capability_enabled=canonical_read_capability,
            canonical_read_flag_cache_ttl_s=float(
                getattr(settings, "canonical_read_flag_cache_ttl_s", 15.0)
                or 15.0
            ),
            canonical_read_identity_cache_ttl_s=float(
                getattr(settings, "canonical_read_identity_cache_ttl_s", 120.0)
                or 120.0
            ),
        )
        outbox_max = int(getattr(settings, "storage_outbox_max", 500) or 500)
        replay_batch = int(getattr(settings, "storage_replay_batch", 50) or 50)
        credential_kind = "secret" if key.startswith("sb_secret_") else "legacy_or_unknown"
        log.info(
            "storage backend=supabase credential=%s resilient_fallback=memory outbox_max=%d replay_batch=%d canonical_read_capability=%s",
            credential_kind,
            outbox_max,
            replay_batch,
            canonical_read_capability,
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
