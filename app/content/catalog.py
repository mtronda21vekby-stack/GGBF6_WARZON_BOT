from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.enums import Game, InputDevice, SkillTier, Mode


@dataclass
class SettingsPack:
    game: Game
    mode: Mode
    device: InputDevice
    tier: SkillTier
    title: str
    last_updated: str
    source: str
    settings: dict[str, Any]


class ContentCatalog:
    def __init__(self, base_dir: str = "app/content/data"):
        self.base = Path(base_dir)

    def _load_json(self, name: str) -> dict[str, Any]:
        p = self.base / name
        return json.loads(p.read_text(encoding="utf-8"))

    def list_games(self) -> list[Game]:
        return [Game.WARZONE, Game.BF6, Game.BO7]

    def modes_for_game(self, game: Game) -> list[Mode]:
        if game == Game.WARZONE:
            return [Mode.WZ_BR, Mode.WZ_RESURGENCE, Mode.WZ_RANKED]
        if game == Game.BF6:
            return [Mode.BF6_PVP]
        if game == Game.BO7:
            return [Mode.BO7_MP, Mode.BO7_ZOMBIES, Mode.BO7_ZOMBIES_ZOMBIE]
        return []

    def load_settings_pack(self, game: Game, mode: Mode, device: InputDevice, tier: SkillTier) -> SettingsPack:
        # file naming convention
        fname = f"{game.value}__{mode.value}__{device.value}__{tier.value}.json"
        raw = self._load_json(fname)
        return SettingsPack(
            game=game,
            mode=mode,
            device=device,
            tier=tier,
            title=raw["title"],
            last_updated=raw["last_updated"],
            source=raw["source"],
            settings=raw["settings"],
        )

    def load_training_plan(self, game: Game, mode: Mode, tier: SkillTier) -> dict[str, Any]:
        fname = f"training__{game.value}__{mode.value}__{tier.value}.json"
        return self._load_json(fname)

    def load_classes(self, game: Game) -> dict[str, Any]:
        fname = f"classes__{game.value}.json"
        return self._load_json(fname)
