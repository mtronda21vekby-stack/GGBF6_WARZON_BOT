# app/services/profiles/service.py
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
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
    "tts_voice": "cedar",
}


@dataclass
class ProfileService:
    store: Any
    _context_secret: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)

    def _context_token(self, chat_id: int) -> str:
        return hmac.new(self._context_secret, str(int(chat_id)).encode("utf-8"), hashlib.sha256).hexdigest()

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

        # Internal context proof: generated server-side and never persisted.
        out["_chat_id"] = int(chat_id)
        out["_context_token"] = self._context_token(chat_id)
        return out

    def is_trusted_context(self, profile: Mapping[str, Any] | None) -> bool:
        profile = profile or {}
        try:
            chat_id = int(profile.get("_chat_id"))
            token = str(profile.get("_context_token") or "")
        except Exception:
            return False
        return bool(token) and hmac.compare_digest(token, self._context_token(chat_id))

    def get_intelligence(self, chat_id: int) -> PlayerIntelligence:
        data = self.get(chat_id)
        data.setdefault("voice_mode", data.get("voice"))
        data.setdefault("brain_mode", data.get("difficulty"))
        return PlayerIntelligence.from_mapping(data)

    @staticmethod
    def _with_aliases(patch: Mapping[str, Any]) -> dict[str, Any]:
        clean = {
            str(k): v for k, v in (patch or {}).items()
            if v is not None and not str(k).startswith("_")
        }
        # New Intelligence Core names and legacy Router names remain equivalent
        # during the incremental migration.
        if clean.get("brain_mode") is not None and clean.get("difficulty") is None:
            clean["difficulty"] = clean["brain_mode"]
        if clean.get("difficulty") is not None and clean.get("brain_mode") is None:
            clean["brain_mode"] = clean["difficulty"]
        if clean.get("voice_mode") is not None and clean.get("voice") is None:
            clean["voice"] = clean["voice_mode"]
        if clean.get("voice") is not None and clean.get("voice_mode") is None:
            clean["voice_mode"] = clean["voice"]
        return clean

    def patch(self, chat_id: int, patch: Mapping[str, Any]) -> None:
        clean = self._with_aliases(patch)
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
        if not self.store:
            return
        purge = getattr(self.store, "purge_player", None)
        if callable(purge):
            try:
                purge(chat_id)
                return
            except Exception:
                pass
        reset = getattr(self.store, "reset_profile", None)
        if callable(reset):
            try:
                reset(chat_id)
            except Exception:
                pass
