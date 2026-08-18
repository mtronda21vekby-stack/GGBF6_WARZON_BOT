# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


_CATEGORY_TERMS = {
    "weapons": ("weapon", "weapons", "rifle", "smg", "lmg", "shotgun", "pistol", "damage", "recoil", "range", "attachment"),
    "movement": ("movement", "slide", "sprint", "mantle", "vault", "jump"),
    "maps": ("map", "maps", "poi", "location"),
    "modes": ("mode", "modes", "battle royale", "resurgence", "multiplayer"),
    "ranked": ("ranked", "sr", "competitive"),
    "zombies": ("zombies", "zombie"),
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _content_hash(document: Any) -> str:
    body = {
        "game": str(getattr(document, "game", "")),
        "title": _norm(getattr(document, "title", "")),
        "published": str(getattr(document, "published", "") or ""),
        "blocks": [_norm(x) for x in getattr(document, "blocks", ()) if _norm(x)],
    }
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _categories(blocks: list[str]) -> list[str]:
    haystack = "\n".join(blocks).lower()
    return [name for name, terms in _CATEGORY_TERMS.items() if any(term in haystack for term in terms)]


@dataclass(frozen=True)
class PersonalImpact:
    relevant: bool
    score: int
    categories: tuple[str, ...]
    reasons: tuple[str, ...]
    alert: str


class CrownIntelLedger:
    """Server-only Supabase ledger for official snapshots and deterministic diffs."""

    def __init__(self, *, url: str, service_role_key: str, schema: str = "public", timeout_s: float = 6.0) -> None:
        self.url = str(url or "").strip().rstrip("/")
        self.key = str(service_role_key or "").strip()
        if not self.url or not self.key:
            raise ValueError("Supabase ledger requires URL and service-role key")
        self.schema = str(schema or "public").strip() or "public"
        self.client = httpx.Client(timeout=httpx.Timeout(max(1.0, min(float(timeout_s), 20.0))))

    def _headers(self, prefer: str = "") -> dict[str, str]:
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "Accept": "application/json", "Accept-Profile": self.schema, "Content-Profile": self.schema, "User-Agent": "BLACK-CROWN-OPS/crown-intel-v43"}
        if prefer:
            h["Prefer"] = prefer
        return h

    def _rows(self, method: str, table: str, *, params: Mapping[str, Any] | None = None, payload: Any = None, prefer: str = "") -> list[dict[str, Any]]:
        r = self.client.request(method, f"{self.url}/rest/v1/{table}", params=dict(params or {}), json=payload, headers=self._headers(prefer))
        r.raise_for_status()
        if not r.content:
            return []
        data = r.json()
        return data if isinstance(data, list) else []

    def latest_snapshot(self, game: str) -> dict[str, Any]:
        rows = self._rows("GET", "bco_game_intel_snapshots", params={"game": f"eq.{game}", "select": "game,source_url,title,published,content_hash,blocks,fetched_at,created_at", "order": "created_at.desc", "limit": "1"})
        return dict(rows[0]) if rows else {}

    def latest_change(self, game: str) -> dict[str, Any]:
        rows = self._rows("GET", "bco_game_intel_changes", params={"game": f"eq.{game}", "select": "id,game,from_hash,to_hash,source_url,published,added_blocks,removed_blocks,categories,created_at", "order": "created_at.desc", "limit": "1"})
        return dict(rows[0]) if rows else {}

    def record_document(self, document: Any) -> dict[str, Any]:
        game = str(getattr(document, "game", "") or "")
        digest = _content_hash(document)
        previous = self.latest_snapshot(game)
        if previous.get("content_hash") == digest:
            return {"changed": False, "content_hash": digest, "game": game}

        blocks = [_norm(x) for x in getattr(document, "blocks", ()) if _norm(x)]
        old_blocks = [_norm(x) for x in (previous.get("blocks") or []) if _norm(x)]
        old_set, new_set = set(old_blocks), set(blocks)
        added = [x for x in blocks if x not in old_set][:120]
        removed = [x for x in old_blocks if x not in new_set][:120]
        cats = _categories(added + removed)

        snapshot = {
            "game": game,
            "source_url": str(getattr(document, "url", "") or ""),
            "title": _norm(getattr(document, "title", ""))[:500],
            "published": str(getattr(document, "published", "") or ""),
            "content_hash": digest,
            "blocks": blocks[:1200],
            "fetched_at": str(getattr(document, "fetched_at", "") or "") or None,
        }
        self._rows("POST", "bco_game_intel_snapshots", params={"on_conflict": "game,content_hash"}, payload=snapshot, prefer="resolution=ignore-duplicates,return=minimal")

        change = {
            "game": game,
            "from_hash": str(previous.get("content_hash") or ""),
            "to_hash": digest,
            "source_url": snapshot["source_url"],
            "published": snapshot["published"],
            "added_blocks": added,
            "removed_blocks": removed,
            "categories": cats,
        }
        self._rows("POST", "bco_game_intel_changes", params={"on_conflict": "game,to_hash"}, payload=change, prefer="resolution=ignore-duplicates,return=minimal")
        return {"changed": True, **change}

    def personalize(self, change: Mapping[str, Any], profile: Mapping[str, Any], *, query_text: str = "") -> PersonalImpact:
        categories = tuple(str(x) for x in (change.get("categories") or []) if x)
        mode = str(profile.get("mode") or "").lower()
        role = str(profile.get("role") or "").lower()
        text = str(query_text or "").lower()
        score = 0
        reasons: list[str] = []

        if "weapons" in categories:
            score += 3; reasons.append("weapon balance changed")
        if "movement" in categories:
            score += 2; reasons.append("movement rules changed")
        if "ranked" in categories and ("rank" in mode or "rank" in text):
            score += 3; reasons.append("ranked rules are relevant")
        if "zombies" in categories and ("zomb" in mode or "zomb" in text):
            score += 4; reasons.append("zombies context matches")
        if "modes" in categories and any(x in f"{mode} {text}" for x in ("resurgence", "battle royale", "multiplayer")):
            score += 2; reasons.append("active mode is affected")
        if role and "weapons" in categories:
            score += 1; reasons.append(f"loadout role={role}")

        added = [str(x) for x in (change.get("added_blocks") or []) if x]
        query_tokens = {x for x in re.findall(r"[a-zа-я0-9-]{3,}", text) if x not in {"что", "какой", "какая", "мета", "сейчас", "current", "meta"}}
        if query_tokens and any(any(t in block.lower() for t in query_tokens) for block in added[:60]):
            score += 3; reasons.append("official change matches the current question")

        relevant = score >= 3
        alert = ""
        if relevant and added:
            alert = _norm(added[0])[:420]
        return PersonalImpact(relevant=relevant, score=score, categories=categories, reasons=tuple(reasons[:6]), alert=alert)

    def close(self) -> None:
        self.client.close()


def build_crown_intel_ledger(settings: Any) -> CrownIntelLedger | None:
    url = str(getattr(settings, "supabase_url", "") or "").strip()
    key = str(getattr(settings, "supabase_service_role_key", "") or "").strip()
    if not url or not key:
        return None
    try:
        return CrownIntelLedger(url=url, service_role_key=key, schema=getattr(settings, "supabase_schema", "public"), timeout_s=getattr(settings, "live_knowledge_timeout_s", 6.0))
    except Exception:
        return None
