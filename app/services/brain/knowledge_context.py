# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol

from app.content.catalog import ContentCatalog
from app.domain.enums import Game, InputDevice, Mode, SkillTier
from app.services.brain.intents import Intent, IntentResult
from app.services.brain.knowledge import TOP_RULES
from app.services.brain.loadouts import ROLE_LOADOUTS


class KnowledgeConfidence(str, Enum):
    VERIFIED_CURRENT = "VERIFIED_CURRENT"
    VERIFIED_STATIC = "VERIFIED_STATIC"
    DATED_SOURCE = "DATED_SOURCE"
    MODEL_KNOWLEDGE = "MODEL_KNOWLEDGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class KnowledgeFact:
    text: str
    source: str = ""
    last_updated: str = ""
    confidence: KnowledgeConfidence = KnowledgeConfidence.UNKNOWN


@dataclass
class KnowledgeContext:
    facts: list[KnowledgeFact] = field(default_factory=list)
    source: str = ""
    last_updated: str = ""
    freshness: str = "unknown"
    confidence: KnowledgeConfidence = KnowledgeConfidence.UNKNOWN

    @property
    def is_verified_current(self) -> bool:
        return self.confidence == KnowledgeConfidence.VERIFIED_CURRENT

    @classmethod
    def unknown(cls) -> "KnowledgeContext":
        return cls()


@dataclass(frozen=True)
class KnowledgeRequest:
    intent: IntentResult
    text: str
    profile: Mapping[str, Any]


class KnowledgeProvider(Protocol):
    def query(self, request: KnowledgeRequest) -> KnowledgeContext:
        ...


def _game(profile: Mapping[str, Any]) -> Game | None:
    raw = str(profile.get("game") or "Warzone").lower().replace(" ", "")
    if raw in {"warzone", "wz", "warzone2"}:
        return Game.WARZONE
    if raw in {"bf6", "battlefield", "battlefield6"}:
        return Game.BF6
    if raw in {"bo7", "blackops7"}:
        return Game.BO7
    return None


def _mode(game: Game, profile: Mapping[str, Any]) -> Mode:
    raw = str(profile.get("mode") or "").lower().strip()
    if raw:
        for item in Mode:
            if item.value == raw:
                return item
    if game == Game.WARZONE:
        return Mode.WZ_BR
    if game == Game.BF6:
        return Mode.BF6_PVP
    return Mode.BO7_MP


def _tier(profile: Mapping[str, Any]) -> SkillTier:
    raw = str(profile.get("difficulty") or "Normal").lower()
    if "demon" in raw:
        return SkillTier.DEMON
    if "pro" in raw:
        return SkillTier.PRO
    return SkillTier.NORMAL


def _device(profile: Mapping[str, Any]) -> InputDevice | None:
    inp = str(profile.get("input") or "").upper()
    platform = str(profile.get("platform") or "").lower()
    if inp == "KBM":
        return InputDevice.KBM
    if "xbox" in platform:
        return InputDevice.XBOX
    if "play" in platform or platform.startswith("ps"):
        return InputDevice.PS
    return None


def _flatten(prefix: str, value: Any, out: list[str], limit: int = 16) -> None:
    if len(out) >= limit:
        return
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out, limit)
            if len(out) >= limit:
                break
    elif isinstance(value, list):
        for item in value:
            _flatten(prefix, item, out, limit)
            if len(out) >= limit:
                break
    else:
        out.append(f"{prefix}: {value}" if prefix else str(value))


class StaticKnowledgeProvider:
    """Trusted local repository knowledge.

    This provider never labels its data as *current*. Even dated data with a
    source remains DATED_SOURCE until a future live provider verifies it.
    """

    def __init__(self, catalog: ContentCatalog | None = None):
        self.catalog = catalog or ContentCatalog()

    def query(self, request: KnowledgeRequest) -> KnowledgeContext:
        intent = request.intent.intent
        profile = request.profile
        game = _game(profile)

        if intent in {Intent.META_CURRENT, Intent.PATCH_CURRENT}:
            return KnowledgeContext.unknown()

        if game and intent == Intent.GAME_SETTINGS:
            device = _device(profile)
            if device is not None:
                try:
                    pack = self.catalog.load_settings_pack(game, _mode(game, profile), device, _tier(profile))
                    flat: list[str] = []
                    _flatten("", pack.settings, flat)
                    facts = [
                        KnowledgeFact(
                            text=x,
                            source=pack.source,
                            last_updated=pack.last_updated,
                            confidence=KnowledgeConfidence.DATED_SOURCE,
                        )
                        for x in flat
                    ]
                    return KnowledgeContext(
                        facts=facts,
                        source=pack.source,
                        last_updated=pack.last_updated,
                        freshness="dated",
                        confidence=KnowledgeConfidence.DATED_SOURCE,
                    )
                except (FileNotFoundError, KeyError, ValueError):
                    pass

        if game and intent == Intent.TRAINING:
            try:
                plan = self.catalog.load_training_plan(game, _mode(game, profile), _tier(profile))
                flat: list[str] = []
                _flatten("", plan, flat)
                source = str(plan.get("source") or "app/content/data")
                updated = str(plan.get("last_updated") or "")
                facts = [
                    KnowledgeFact(x, source, updated, KnowledgeConfidence.DATED_SOURCE)
                    for x in flat[:16]
                ]
                return KnowledgeContext(
                    facts=facts, source=source, last_updated=updated,
                    freshness="dated" if updated else "static",
                    confidence=KnowledgeConfidence.DATED_SOURCE if updated else KnowledgeConfidence.VERIFIED_STATIC,
                )
            except (FileNotFoundError, KeyError, ValueError):
                pass

        game_key = game.value if game else str(profile.get("game") or "").lower()

        if intent == Intent.LOADOUT:
            role = str(profile.get("role") or "").lower()
            data = ROLE_LOADOUTS.get(game_key, {}).get(role)
            if data:
                facts = [
                    KnowledgeFact(f"Role: {data.get('role', role)}", "app/services/brain/loadouts.py", "", KnowledgeConfidence.VERIFIED_STATIC),
                    KnowledgeFact(f"Weapon classes: {', '.join(data.get('weapons', []))}", "app/services/brain/loadouts.py", "", KnowledgeConfidence.VERIFIED_STATIC),
                    KnowledgeFact(f"Focus: {data.get('focus', '')}", "app/services/brain/loadouts.py", "", KnowledgeConfidence.VERIFIED_STATIC),
                ]
                return KnowledgeContext(
                    facts=facts,
                    source="app/services/brain/loadouts.py",
                    freshness="static",
                    confidence=KnowledgeConfidence.VERIFIED_STATIC,
                )

        rules = TOP_RULES.get(game_key)
        if rules and intent in {
            Intent.GAME_TACTICS, Intent.DEATH_ANALYSIS, Intent.POSITIONING,
            Intent.AIM, Intent.MOVEMENT, Intent.UNKNOWN,
        }:
            facts = [
                KnowledgeFact(f"ALWAYS: {x}", "app/services/brain/knowledge.py", "", KnowledgeConfidence.VERIFIED_STATIC)
                for x in rules.get("always", [])
            ]
            facts.extend(
                KnowledgeFact(f"NEVER: {x}", "app/services/brain/knowledge.py", "", KnowledgeConfidence.VERIFIED_STATIC)
                for x in rules.get("never", [])
            )
            return KnowledgeContext(
                facts=facts,
                source="app/services/brain/knowledge.py",
                freshness="static",
                confidence=KnowledgeConfidence.VERIFIED_STATIC,
            )

        return KnowledgeContext.unknown()


class CompositeKnowledgeProvider:
    def __init__(self, providers: list[KnowledgeProvider] | None = None):
        self.providers = providers or [StaticKnowledgeProvider()]

    def query(self, request: KnowledgeRequest) -> KnowledgeContext:
        best = KnowledgeContext.unknown()
        rank = {
            KnowledgeConfidence.UNKNOWN: 0,
            KnowledgeConfidence.MODEL_KNOWLEDGE: 1,
            KnowledgeConfidence.VERIFIED_STATIC: 2,
            KnowledgeConfidence.DATED_SOURCE: 3,
            KnowledgeConfidence.VERIFIED_CURRENT: 4,
        }
        for provider in self.providers:
            try:
                ctx = provider.query(request)
            except Exception:
                continue
            if rank[ctx.confidence] > rank[best.confidence]:
                best = ctx
            if ctx.confidence == KnowledgeConfidence.VERIFIED_CURRENT:
                break
        return best
