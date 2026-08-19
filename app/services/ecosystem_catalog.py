# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EcosystemModule:
    id: str
    title: str
    short_title: str
    icon: str
    group: str
    description: str
    bot_callback: str | None = None
    mini_target: str | None = None
    premium: bool = False
    surfaces: tuple[str, ...] = ("telegram_bot", "telegram_mini_app")

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["surfaces"] = list(self.surfaces)
        return data


MODULES: tuple[EcosystemModule, ...] = (
    EcosystemModule("ai_brief", "AI Combat Brief", "CROWN", "✦", "crown", "Ask BLACK CROWN about a fight, decision, build or tactical problem.", "bco:ai", "crown"),
    EcosystemModule("training", "Training Protocol", "Training", "◎", "crown", "Personal drills and measurable session focus from Player Intelligence.", "bco:training", "training"),
    EcosystemModule("world", "World & Loadout", "World", "◈", "more", "Shared game, platform and input context used by AI, VOD and missions.", "bco:world", "world"),
    EcosystemModule("vod", "VOD Intelligence", "VOD", "▣", "vod", "Sampled-frame review, engagement intelligence and mission evidence.", "bco:vod", "vod"),
    EcosystemModule("zombies", "Zombies HQ", "Zombies", "⬡", "more", "Zombies world, strategy, loadout and game launcher.", "bco:zombies", "zombies"),
    EcosystemModule("operator", "Operator Dossier", "Operator", "◇", "operator", "Canonical account, Operator Twin, Personal Meta, history and missions.", "bco:profile", "operator"),
    EcosystemModule("premium", "CROWN Premium", "Premium", "◆", "more", "Server-owned entitlement and premium intelligence access.", "bco:premium", "premium", premium=False),
    EcosystemModule("system", "System Control", "System", "⚙", "more", "Brain mode, voice behavior, world context and account diagnostics.", "bco:system", "system"),
)


def ecosystem_modules() -> list[dict[str, Any]]:
    return [module.public() for module in MODULES]


def module_by_id(module_id: str) -> EcosystemModule | None:
    wanted = str(module_id or "").strip().casefold()
    return next((item for item in MODULES if item.id == wanted), None)


def modules_for_group(group: str) -> tuple[EcosystemModule, ...]:
    wanted = str(group or "").strip().casefold()
    return tuple(item for item in MODULES if item.group == wanted)


def telegram_home_rows(module_ids: Iterable[str] | None = None) -> list[list[EcosystemModule]]:
    wanted = set(module_ids or ("ai_brief", "training", "world", "vod", "zombies", "operator", "premium", "system"))
    selected = [item for item in MODULES if item.id in wanted]
    return [selected[index:index + 2] for index in range(0, len(selected), 2)]
