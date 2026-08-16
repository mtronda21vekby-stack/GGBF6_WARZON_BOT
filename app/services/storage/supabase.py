# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from typing import Any, Mapping

import httpx


class SupabaseStore:
    """Persistent Storage implementation backed by Supabase/PostgREST.

    Secrets are supplied only through runtime configuration. The adapter does not
    create schema automatically; see migrations/001_player_intelligence.sql.
    """

    def __init__(
        self,
        *,
        url: str,
        service_role_key: str,
        memory_max_turns: int = 20,
        schema: str = "public",
        timeout_s: float = 8.0,
    ) -> None:
        self.url = (url or "").strip().rstrip("/")
        self.key = (service_role_key or "").strip()
        if not self.url or not self.key:
            raise ValueError("Supabase URL and service-role key are required")
        self.rest_url = f"{self.url}/rest/v1"
        self.schema = (schema or "public").strip() or "public"
        self.memory_max_turns = max(4, int(memory_max_turns or 20))
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_s))

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
        }
        if extra:
            headers.update(dict(extra))
        return headers

    def _request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json: Any = None,
                 extra_headers: Mapping[str, str] | None = None) -> httpx.Response:
        response = self._client.request(
            method,
            f"{self.rest_url}/{path.lstrip('/')}",
            params=dict(params or {}),
            json=json,
            headers=self._headers(extra_headers),
        )
        response.raise_for_status()
        return response

    def _rows(self, response: httpx.Response) -> list[dict]:
        if not response.content:
            return []
        data = response.json()
        return data if isinstance(data, list) else []

    def _count(self, table: str, chat_id: int) -> int:
        response = self._request(
            "GET",
            table,
            params={"chat_id": f"eq.{int(chat_id)}", "select": "id", "limit": "1"},
            extra_headers={"Prefer": "count=exact"},
        )
        content_range = response.headers.get("content-range", "")
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[-1]
            if tail.isdigit():
                return int(tail)
        return len(self._rows(response))

    # Working memory -------------------------------------------------
    def add(self, chat_id: int, role: str, content: Any) -> None:
        self._request("POST", "bco_messages", json={
            "chat_id": int(chat_id),
            "role": str(role),
            "content": str(content),
        }, extra_headers={"Prefer": "return=minimal"})

    def get(self, chat_id: int) -> list[dict]:
        limit = self.memory_max_turns * 2
        rows = self._rows(self._request("GET", "bco_messages", params={
            "chat_id": f"eq.{int(chat_id)}",
            "select": "role,content,created_at",
            "order": "id.desc",
            "limit": str(limit),
        }))
        rows.reverse()
        return [{"role": str(x.get("role") or ""), "content": str(x.get("content") or "")} for x in rows]

    def clear(self, chat_id: int) -> None:
        self._request("DELETE", "bco_messages", params={"chat_id": f"eq.{int(chat_id)}"},
                      extra_headers={"Prefer": "return=minimal"})

    # Player profile -------------------------------------------------
    def get_profile(self, chat_id: int) -> dict[str, Any]:
        rows = self._rows(self._request("GET", "bco_players", params={
            "chat_id": f"eq.{int(chat_id)}",
            "select": "profile",
            "limit": "1",
        }))
        profile = rows[0].get("profile") if rows else {}
        return dict(profile) if isinstance(profile, dict) else {}

    def set_profile(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        clean = {str(k): v for k, v in dict(patch or {}).items() if v is not None}
        if not clean:
            return
        self._request("POST", "rpc/bco_patch_profile", json={
            "p_chat_id": int(chat_id),
            "p_patch": clean,
        }, extra_headers={"Prefer": "return=minimal"})

    def reset_profile(self, chat_id: int) -> None:
        self._request("DELETE", "bco_players", params={"chat_id": f"eq.{int(chat_id)}"},
                      extra_headers={"Prefer": "return=minimal"})

    # Long-term summary / derived intelligence ----------------------
    def get_summary(self, chat_id: int) -> str:
        rows = self._rows(self._request("GET", "bco_players", params={
            "chat_id": f"eq.{int(chat_id)}", "select": "summary", "limit": "1"
        }))
        return str(rows[0].get("summary") or "") if rows else ""

    def set_summary(self, chat_id: int, summary: str) -> None:
        self._request("POST", "bco_players", params={"on_conflict": "chat_id"}, json={
            "chat_id": int(chat_id), "summary": str(summary or "").strip()
        }, extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def get_derived_intelligence(self, chat_id: int) -> dict[str, Any]:
        rows = self._rows(self._request("GET", "bco_players", params={
            "chat_id": f"eq.{int(chat_id)}", "select": "derived", "limit": "1"
        }))
        value = rows[0].get("derived") if rows else {}
        return dict(value) if isinstance(value, dict) else {}

    def set_derived_intelligence(self, chat_id: int, data: Mapping[str, Any]) -> None:
        self._request("POST", "bco_players", params={"on_conflict": "chat_id"}, json={
            "chat_id": int(chat_id), "derived": dict(data or {})
        }, extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    # Recurring mistakes --------------------------------------------
    @staticmethod
    def _mistake_key(mistake: str) -> str:
        normalized = " ".join(str(mistake or "").lower().split())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]

    def add_recurring_mistake(self, chat_id: int, mistake: str) -> None:
        label = str(mistake or "").strip()
        if not label:
            return
        self._request("POST", "rpc/bco_record_mistake", json={
            "p_chat_id": int(chat_id),
            "p_mistake_key": self._mistake_key(label),
            "p_label": label,
            "p_evidence": {},
        }, extra_headers={"Prefer": "return=minimal"})

    def list_recurring_mistakes(self, chat_id: int) -> list[str]:
        return [str(x.get("label") or "") for x in self.list_mistake_stats(chat_id) if x.get("label")]

    def list_mistake_stats(self, chat_id: int) -> list[dict]:
        return self._rows(self._request("GET", "bco_player_mistakes", params={
            "chat_id": f"eq.{int(chat_id)}",
            "select": "mistake_key,label,count,first_seen,last_seen,evidence",
            "order": "count.desc,last_seen.desc",
            "limit": "20",
        }))

    # Episodic/training/progression events --------------------------
    def add_episode(self, chat_id: int, event: Mapping[str, Any]) -> None:
        payload = dict(event or {})
        self._request("POST", "bco_episodes", json={
            "chat_id": int(chat_id),
            "kind": str(payload.pop("kind", "event"))[:64],
            "data": payload,
        }, extra_headers={"Prefer": "return=minimal"})

    def list_episodes(self, chat_id: int, limit: int = 20) -> list[dict]:
        rows = self._rows(self._request("GET", "bco_episodes", params={
            "chat_id": f"eq.{int(chat_id)}",
            "select": "kind,data,created_at",
            "order": "id.desc",
            "limit": str(max(1, min(int(limit), 100))),
        }))
        return rows

    def add_training_session(self, chat_id: int, event: Mapping[str, Any]) -> None:
        self._request("POST", "bco_training_sessions", json={"chat_id": int(chat_id), "data": dict(event or {})},
                      extra_headers={"Prefer": "return=minimal"})

    def list_training_sessions(self, chat_id: int) -> list[dict]:
        rows = self._rows(self._request("GET", "bco_training_sessions", params={
            "chat_id": f"eq.{int(chat_id)}", "select": "data,created_at", "order": "id.desc", "limit": "50"
        }))
        return [dict(x.get("data") or {}, created_at=x.get("created_at")) for x in rows]

    def add_progression_event(self, chat_id: int, event: Mapping[str, Any]) -> None:
        self._request("POST", "bco_progression_events", json={"chat_id": int(chat_id), "data": dict(event or {})},
                      extra_headers={"Prefer": "return=minimal"})

    def list_progression_events(self, chat_id: int) -> list[dict]:
        rows = self._rows(self._request("GET", "bco_progression_events", params={
            "chat_id": f"eq.{int(chat_id)}", "select": "data,created_at", "order": "id.desc", "limit": "100"
        }))
        return [dict(x.get("data") or {}, created_at=x.get("created_at")) for x in rows]

    def stats(self, chat_id: int) -> dict:
        cid = int(chat_id)
        return {
            "backend": "supabase",
            "turns": self._count("bco_messages", cid),
            "has_profile": bool(self.get_profile(cid)),
            "has_summary": bool(self.get_summary(cid)),
            "recurring_mistakes": self._count("bco_player_mistakes", cid),
            "training_sessions": self._count("bco_training_sessions", cid),
            "progression_events": self._count("bco_progression_events", cid),
            "episodes": self._count("bco_episodes", cid),
            "max_turns": self.memory_max_turns,
        }

    def close(self) -> None:
        self._client.close()
