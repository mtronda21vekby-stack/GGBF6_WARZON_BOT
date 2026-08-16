# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from app.services.brain.intents import Intent
from app.services.brain.knowledge_context import (
    KnowledgeConfidence,
    KnowledgeContext,
    KnowledgeFact,
    KnowledgeRequest,
)


_ALLOWED_OFFICIAL_HOSTS = {
    "www.callofduty.com",
    "callofduty.com",
    "forums.ea.com",
    "www.ea.com",
    "ea.com",
    "news.ea.com",
}
_CURRENT_INTENTS = {Intent.META_CURRENT, Intent.PATCH_CURRENT}


def _parse_dt(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _official_url(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() in _ALLOWED_OFFICIAL_HOSTS
    except Exception:
        return False


def _game_key(request: KnowledgeRequest) -> str:
    text = str(request.text or "").lower()
    if any(x in text for x in ("bo7", "black ops 7", "blackops7")):
        return "bo7"
    if any(x in text for x in ("bf6", "battlefield 6", "battlefield6")):
        return "bf6"
    if any(x in text for x in ("warzone", "варзон", "wz")):
        return "warzone"

    raw = str(request.profile.get("game") or "warzone").lower().replace(" ", "")
    if raw in {"bo7", "blackops7"}:
        return "bo7"
    if raw in {"bf6", "battlefield6", "battlefield"}:
        return "bf6"
    return "warzone"


def _fact_selected(item: dict[str, Any], intent: Intent) -> bool:
    tags = {str(x).lower() for x in (item.get("tags") or [])}
    if not tags:
        return True
    if intent == Intent.META_CURRENT:
        return bool(tags & {"meta_context", "weapon_balance", "weapon", "ranked", "loadout"})
    return True


@dataclass
class OfficialSnapshotProvider:
    """Curated official-source snapshots with a hard freshness TTL.

    The provider deliberately does not scrape publisher pages at request time.
    A snapshot is VERIFIED_CURRENT only when:
      * its source URL is on an approved first-party domain;
      * it has an explicit verified_at timestamp;
      * verified_at is not in the future;
      * its age is within LIVE_KNOWLEDGE_MAX_AGE_HOURS.

    Once the TTL expires, the same data degrades to DATED_SOURCE and the v1
    currentness gate blocks silent claims about "today/latest/current meta".
    """

    base_dir: Path | str = Path("app/content/live")
    max_age_hours: float | None = None
    now_fn: Callable[[], datetime] | None = None

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir)
        if self.max_age_hours is None:
            try:
                self.max_age_hours = float(os.getenv("LIVE_KNOWLEDGE_MAX_AGE_HOURS", "168"))
            except ValueError:
                self.max_age_hours = 168.0
        self.max_age_hours = max(1.0, float(self.max_age_hours))
        if self.now_fn is None:
            self.now_fn = lambda: datetime.now(timezone.utc)

    def _load(self, game: str) -> dict[str, Any] | None:
        path = self.base_dir / f"{game}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(raw, dict) or str(raw.get("game") or "").lower() != game:
            return None
        return raw

    def query(self, request: KnowledgeRequest) -> KnowledgeContext:
        if request.intent.intent not in _CURRENT_INTENTS:
            return KnowledgeContext.unknown()

        game = _game_key(request)
        snapshot = self._load(game)
        if not snapshot:
            return KnowledgeContext.unknown()

        source_url = str(snapshot.get("source_url") or "").strip()
        source_kind = str(snapshot.get("source_kind") or "").strip()
        publisher = str(snapshot.get("publisher") or "").strip()
        title = str(snapshot.get("title") or "").strip()
        verified_at = _parse_dt(str(snapshot.get("verified_at") or ""))
        published_at = _parse_dt(str(snapshot.get("published_at") or ""))
        now = (self.now_fn or (lambda: datetime.now(timezone.utc)))().astimezone(timezone.utc)

        age_hours: float | None = None
        current = False
        if verified_at is not None and _official_url(source_url):
            age_hours = (now - verified_at).total_seconds() / 3600.0
            current = 0.0 <= age_hours <= float(self.max_age_hours)

        confidence = (
            KnowledgeConfidence.VERIFIED_CURRENT
            if current
            else KnowledgeConfidence.DATED_SOURCE
            if source_url and (verified_at or published_at)
            else KnowledgeConfidence.UNKNOWN
        )

        facts: list[KnowledgeFact] = []
        for item in snapshot.get("facts") or []:
            if not isinstance(item, dict) or not _fact_selected(item, request.intent.intent):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            facts.append(
                KnowledgeFact(
                    text=text,
                    source=source_url,
                    last_updated=(published_at.date().isoformat() if published_at else ""),
                    confidence=confidence,
                )
            )
            if len(facts) >= 14:
                break

        if request.intent.intent == Intent.META_CURRENT:
            facts.append(
                KnowledgeFact(
                    text=(
                        "Scope rule: official patch notes verify balance/content changes, "
                        "not a definitive weapon meta ranking. Any 'best/meta' conclusion "
                        "must be labeled as a patch-informed recommendation or inference."
                    ),
                    source=source_url,
                    last_updated=(published_at.date().isoformat() if published_at else ""),
                    confidence=confidence,
                )
            )

        source_label = " | ".join(x for x in (publisher, title, source_url) if x)
        freshness = (
            f"current; verified_at={verified_at.isoformat()}; age_hours={age_hours:.1f}; ttl_hours={self.max_age_hours:g}"
            if current and verified_at is not None and age_hours is not None
            else f"stale_or_unverified; verified_at={verified_at.isoformat() if verified_at else 'none'}; ttl_hours={self.max_age_hours:g}"
        )
        if source_kind:
            freshness += f"; source_kind={source_kind}"

        return KnowledgeContext(
            facts=facts,
            source=source_label,
            last_updated=(published_at.date().isoformat() if published_at else ""),
            freshness=freshness,
            confidence=confidence,
        )
