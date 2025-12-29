# app/services/profiles/service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_PROFILE: Dict[str, str] = {
    "game": "Warzone",          # Warzone / BO7 / BF6
    "platform": "PC",           # PC / PlayStation / Xbox
    "input": "Controller",      # Controller / KBM
    "difficulty": "Normal",     # Normal / Pro / Demon
    "voice": "TEAMMATE",        # TEAMMATE / COACH
    "role": "Flex",             # Slayer / Entry / IGL / Support / Flex
    "bf6_class": "Assault",     # Assault / Recon / Engineer / Medic
}


@dataclass
class ProfileService:
    store: Any

    def get(self, chat_id: int) -> Dict[str, str]:
        # store may or may not have get_profile
        prof = {}
        if self.store and hasattr(self.store, "get_profile"):
            try:
                prof = self.store.get_profile(chat_id) or {}
            except Exception:
                prof = {}
        out = dict(DEFAULT_PROFILE)
        for k, v in (prof or {}).items():
            out[str(k)] = str(v)
        return out

    # universal setter used by router
    def set_field(self, chat_id: int, key: str, val: str) -> None:
        if not self.store:
            return
        if hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception:
                pass

    # optional convenience setters (router supports both styles)
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

    def reset(self, chat_id: int) -> None:
        # reset profile in store if possible
        if self.store and hasattr(self.store, "reset_profile"):
            try:
                self.store.reset_profile(chat_id)
            except Exception:
                pass
