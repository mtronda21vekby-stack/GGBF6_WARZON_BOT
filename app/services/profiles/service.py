# app/services/profiles/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from app.services.profiles.models import PlayerIntelligence


DEFAULT_PROFILE: Dict[str, str] = {
    "game": "Warzone",
    "platform": "PC",
    "input": "Controller",
    "difficulty": "Normal",
    "voice": "TEAMMATE",
    "role": "Flex",
    "bf6_class": "Assault",
    "zombies_active": "0",
    "zombies_map": "ashes",
    "zombies_mode": "",
    "zombies_search_last": "",
}


@dataclass
class ProfileService:
    store: Any

    def get(self, chat_id: int) -> Dict[str, Any]:
        prof: Dict[str, Any] = {}
        if self.store and hasattr(self.store, "get_profile"):
            try:
                prof = self.store.get_profile(chat_id) or {}
            except Exception:
                prof = {}

        out: Dict[str, Any] = dict(DEFAULT_PROFILE)
        for key, value in (prof or {}).items():
            out[str(key)] = value
        for key, value in DEFAULT_PROFILE.items():
            out.setdefault(key, value)
        return out

    def get_intelligence(self, chat_id: int) -> PlayerIntelligence:
        data = self.get(chat_id)
        data.setdefault("voice_mode", data.get("voice"))
        data.setdefault("brain_mode", data.get("difficulty"))
        return PlayerIntelligence.from_mapping(data)

    def patch(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        clean = {str(k): v for k, v in (patch or {}).items() if v is not None}
        if not clean or not self.store:
            return
        if hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, clean)
            except Exception:
                pass

    def set_field(self, chat_id: int, key: str, val: Any) -> None:
        self.patch(chat_id, {key: val})

    def set_game(self, chat_id: int, game: str) -> None:
        self.set_field(chat_id, "game", game)

    def set_platform(self, chat_id: int, platform: str) -> None:
        self.set_field(chat_id, "platform", platform)

    def set_input(self, chat_id: int, input_name: str) -> None:
        self.set_field(chat_id, "input", input_name)

    def set_difficulty(self, chat_id: int, diff: str) -> None:
        self.set_field(chat_id, "difficulty", diff)

    def set_voice(self, chat_id: int, voice: str) -> None:
        self.set_field(chat_id, "voice", voice)

    def set_role(self, chat_id: int, role: str) -> None:
        self.set_field(chat_id, "role", role)

    def set_bf6_class(self, chat_id: int, cls: str) -> None:
        self.set_field(chat_id, "bf6_class", cls)

    def set_zombies_active(self, chat_id: int, active: bool) -> None:
        self.set_field(chat_id, "zombies_active", "1" if active else "0")

    def set_zombies_map(self, chat_id: int, map_name: str) -> None:
        self.set_field(chat_id, "zombies_map", str(map_name))

    def set_zombies_mode(self, chat_id: int, mode: str) -> None:
        self.set_field(chat_id, "zombies_mode", str(mode))

    def set_zombies_search_last(self, chat_id: int, query: str) -> None:
        self.set_field(chat_id, "zombies_search_last", str(query))

    def reset(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "reset_profile"):
            try:
                self.store.reset_profile(chat_id)
            except Exception:
                pass
