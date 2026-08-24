# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from typing import Any, Mapping

import httpx


class SupabaseStore:
    """Persistent Storage implementation backed by Supabase/PostgREST."""

    def __init__(self, *, url: str, service_role_key: str, memory_max_turns: int = 20,
                 schema: str = "public", timeout_s: float = 8.0) -> None:
        self.url = (url or "").strip().rstrip("/")
        self.key = (service_role_key or "").strip()
        if not self.url or not self.key:
            raise ValueError("Supabase URL and service-role key are required")
        self.rest_url = f"{self.url}/rest/v1"
        self.schema = (schema or "public").strip() or "public"
        self.memory_max_turns = max(4, int(memory_max_turns or 20))
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_s))

    def _headers(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        headers = {"apikey": self.key,"Authorization": f"Bearer {self.key}","Accept": "application/json","Content-Type": "application/json","Accept-Profile": self.schema,"Content-Profile": self.schema,"User-Agent": "BLACK-CROWN-OPS/storage-v39"}
        if extra: headers.update(dict(extra))
        return headers

    def _request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json: Any = None, extra_headers: Mapping[str, str] | None = None) -> httpx.Response:
        response = self._client.request(method, f"{self.rest_url}/{path.lstrip('/')}", params=dict(params or {}), json=json, headers=self._headers(extra_headers)); response.raise_for_status(); return response

    def _rows(self, response: httpx.Response) -> list[dict]:
        if not response.content: return []
        data = response.json(); return data if isinstance(data, list) else []

    def resolve_telegram_identity(self, telegram_user_id: int) -> dict[str, Any]:
        """Resolve/create the canonical BLACK CROWN account for a Telegram identity.

        This is additive: legacy chat_id keyed storage remains authoritative during the
        migration window. No player data is moved or deleted here.
        """
        rows = self._rows(self._request("POST", "rpc/black_crown_resolve_telegram_identity", json={"p_telegram_user_id": int(telegram_user_id)}))
        result = dict(rows[0]) if rows else {}
        if result:
            result["legacy_owner_id"] = int(telegram_user_id)
        return result

    def resolve_canonical_identity(self, provider: str, provider_subject: str) -> dict[str, Any]:
        """Resolve an authenticated provider identity to the legacy-compatible owner.

        The canonical UUID is authoritative. The Telegram subject is selected only
        as the compatibility key for existing bco_* tables during the additive
        ownership migration. No identity or account is created by this read path.
        """
        name = str(provider or "").strip().lower()
        subject = str(provider_subject or "").strip()
        if name not in {"apple", "website_auth", "telegram"} or not subject:
            return {}
        identities = self._rows(self._request(
            "GET",
            "black_crown_identities",
            params={
                "provider": f"eq.{name}",
                "provider_subject": f"eq.{subject}",
                "status": "eq.active",
                "select": "black_crown_user_id,status",
                "limit": "2",
            },
        ))
        if len(identities) != 1:
            return {}
        canonical = str(identities[0].get("black_crown_user_id") or "")
        accounts = self._rows(self._request(
            "GET",
            "black_crown_accounts",
            params={
                "black_crown_user_id": f"eq.{canonical}",
                "select": "account_status",
                "limit": "1",
            },
        ))
        telegram = self._rows(self._request(
            "GET",
            "black_crown_identities",
            params={
                "black_crown_user_id": f"eq.{canonical}",
                "provider": "eq.telegram",
                "status": "eq.active",
                "select": "provider_subject",
                "limit": "2",
            },
        ))
        if len(accounts) != 1 or len(telegram) != 1:
            return {}
        try:
            owner = int(str(telegram[0].get("provider_subject") or ""))
        except ValueError:
            return {}
        return {
            "black_crown_user_id": canonical,
            "identity_status": str(identities[0].get("status") or ""),
            "account_status": str(accounts[0].get("account_status") or ""),
            "legacy_owner_id": owner,
        }

    def list_canonical_entitlements(self, black_crown_user_id: str) -> list[dict[str, Any]]:
        return self._rows(self._request(
            "GET",
            "blackcrown_entitlements",
            params={
                "black_crown_user_id": f"eq.{str(black_crown_user_id)}",
                "status": "eq.active",
                "select": "entitlement_key,status,source,valid_until",
                "order": "updated_at.asc",
                "limit": "100",
            },
        ))

    def _count(self, table: str, chat_id: int) -> int:
        response = self._request("GET", table, params={"chat_id": f"eq.{int(chat_id)}", "select": "id", "limit": "1"}, extra_headers={"Prefer": "count=exact"})
        content_range = response.headers.get("content-range", "")
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[-1]
            if tail.isdigit(): return int(tail)
        return len(self._rows(response))

    def ping(self) -> bool:
        self._request("HEAD", "bco_players", params={"select": "chat_id", "limit": "1"}, extra_headers={"X-BCO-Storage-Probe": "startup-v39"}); return True

    def _append(self, table: str, payload: dict[str, Any], operation_id: str | None = None) -> None:
        body = dict(payload); op = str(operation_id or "").strip()
        if op:
            body["operation_id"] = op; self._request("POST", table, params={"on_conflict": "operation_id"}, json=body, extra_headers={"Prefer": "resolution=ignore-duplicates,return=minimal"}); return
        self._request("POST", table, json=body, extra_headers={"Prefer": "return=minimal"})

    def add(self, chat_id: int, role: str, content: Any, *, operation_id: str | None = None) -> None: self._append("bco_messages", {"chat_id": int(chat_id), "role": str(role), "content": str(content)}, operation_id)
    def get(self, chat_id: int) -> list[dict]:
        rows=self._rows(self._request("GET","bco_messages",params={"chat_id":f"eq.{int(chat_id)}","select":"role,content,created_at","order":"id.desc","limit":str(self.memory_max_turns*2)})); rows.reverse(); return [{"role":str(x.get("role") or ""),"content":str(x.get("content") or "")} for x in rows]
    def clear(self, chat_id:int,*,operation_id:str|None=None)->None:self._request("DELETE","bco_messages",params={"chat_id":f"eq.{int(chat_id)}"},extra_headers={"Prefer":"return=minimal"})
    def get_profile(self,chat_id:int)->dict[str,Any]:
        rows=self._rows(self._request("GET","bco_players",params={"chat_id":f"eq.{int(chat_id)}","select":"profile","limit":"1"})); p=rows[0].get("profile") if rows else {}; return dict(p) if isinstance(p,dict) else {}
    def set_profile(self,chat_id:int,patch:Mapping[str,Any],*,operation_id:str|None=None)->None:
        clean={str(k):v for k,v in dict(patch or {}).items() if v is not None};
        if clean:self._request("POST","rpc/bco_patch_profile",json={"p_chat_id":int(chat_id),"p_patch":clean},extra_headers={"Prefer":"return=minimal"})
    def reset_profile(self,chat_id:int,*,operation_id:str|None=None)->None:self._request("DELETE","bco_players",params={"chat_id":f"eq.{int(chat_id)}"},extra_headers={"Prefer":"return=minimal"})
    def get_summary(self,chat_id:int)->str:
        rows=self._rows(self._request("GET","bco_players",params={"chat_id":f"eq.{int(chat_id)}","select":"summary","limit":"1"})); return str(rows[0].get("summary") or "") if rows else ""
    def set_summary(self,chat_id:int,summary:str,*,operation_id:str|None=None)->None:self._request("POST","bco_players",params={"on_conflict":"chat_id"},json={"chat_id":int(chat_id),"summary":str(summary or "").strip()},extra_headers={"Prefer":"resolution=merge-duplicates,return=minimal"})
    def get_derived_intelligence(self,chat_id:int)->dict[str,Any]:
        rows=self._rows(self._request("GET","bco_players",params={"chat_id":f"eq.{int(chat_id)}","select":"derived","limit":"1"})); v=rows[0].get("derived") if rows else {}; return dict(v) if isinstance(v,dict) else {}
    def set_derived_intelligence(self,chat_id:int,data:Mapping[str,Any],*,operation_id:str|None=None)->None:self._request("POST","bco_players",params={"on_conflict":"chat_id"},json={"chat_id":int(chat_id),"derived":dict(data or {})},extra_headers={"Prefer":"resolution=merge-duplicates,return=minimal"})
    @staticmethod
    def _mistake_key(mistake:str)->str:return hashlib.sha1(" ".join(str(mistake or "").lower().split()).encode("utf-8")).hexdigest()[:20]
    def add_recurring_mistake(self,chat_id:int,mistake:str,*,operation_id:str|None=None)->None:
        label=str(mistake or "").strip();
        if not label:return
        op=str(operation_id or "").strip()
        if op:self._request("POST","rpc/bco_record_mistake_once",json={"p_operation_id":op,"p_chat_id":int(chat_id),"p_mistake_key":self._mistake_key(label),"p_label":label,"p_evidence":{}},extra_headers={"Prefer":"return=minimal"});return
        self._request("POST","rpc/bco_record_mistake",json={"p_chat_id":int(chat_id),"p_mistake_key":self._mistake_key(label),"p_label":label,"p_evidence":{}},extra_headers={"Prefer":"return=minimal"})
    def list_recurring_mistakes(self,chat_id:int)->list[str]:return [str(x.get("label") or "") for x in self.list_mistake_stats(chat_id) if x.get("label")]
    def list_mistake_stats(self,chat_id:int)->list[dict]:return self._rows(self._request("GET","bco_player_mistakes",params={"chat_id":f"eq.{int(chat_id)}","select":"mistake_key,label,count,first_seen,last_seen,evidence","order":"count.desc,last_seen.desc","limit":"20"}))
    def add_episode(self,chat_id:int,event:Mapping[str,Any],*,operation_id:str|None=None)->None:
        payload=dict(event or {});self._append("bco_episodes",{"chat_id":int(chat_id),"kind":str(payload.pop("kind","event"))[:64],"data":payload},operation_id)
    def list_episodes(self,chat_id:int,limit:int=20)->list[dict]:
        rows=self._rows(self._request("GET","bco_episodes",params={"chat_id":f"eq.{int(chat_id)}","select":"kind,data,created_at","order":"id.desc","limit":str(max(1,min(int(limit),100)))}));return [dict((r.get("data") if isinstance(r.get("data"),dict) else {}),kind=r.get("kind"),created_at=r.get("created_at")) for r in rows]
    def add_training_session(self,chat_id:int,event:Mapping[str,Any],*,operation_id:str|None=None)->None:self._append("bco_training_sessions",{"chat_id":int(chat_id),"data":dict(event or {})},operation_id)
    def list_training_sessions(self,chat_id:int)->list[dict]:
        rows=self._rows(self._request("GET","bco_training_sessions",params={"chat_id":f"eq.{int(chat_id)}","select":"data,created_at","order":"id.desc","limit":"50"}));return [dict(x.get("data") or {},created_at=x.get("created_at")) for x in rows]
    def add_progression_event(self,chat_id:int,event:Mapping[str,Any],*,operation_id:str|None=None)->None:self._append("bco_progression_events",{"chat_id":int(chat_id),"data":dict(event or {})},operation_id)
    def list_progression_events(self,chat_id:int)->list[dict]:
        rows=self._rows(self._request("GET","bco_progression_events",params={"chat_id":f"eq.{int(chat_id)}","select":"data,created_at","order":"id.desc","limit":"100"}));return [dict(x.get("data") or {},created_at=x.get("created_at")) for x in rows]
    def stats(self,chat_id:int)->dict:
        cid=int(chat_id);return {"backend":"supabase","turns":self._count("bco_messages",cid),"has_profile":bool(self.get_profile(cid)),"has_summary":bool(self.get_summary(cid)),"recurring_mistakes":self._count("bco_player_mistakes",cid),"training_sessions":self._count("bco_training_sessions",cid),"progression_events":self._count("bco_progression_events",cid),"episodes":self._count("bco_episodes",cid),"max_turns":self.memory_max_turns}
    def close(self)->None:self._client.close()
