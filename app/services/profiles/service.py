# app/services/profiles/service.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_PROFILE: Dict[str, str] = {
    # worlds
    "game": "Warzone",          # Warzone / BO7 / BF6
    # device
    "platform": "PC",           # PC / PlayStation / Xbox
    "input": "Controller",      # Controller / KBM
    # brain
    "difficulty": "Normal",     # Normal / Pro / Demon
    "voice": "TEAMMATE",        # TEAMMATE / COACH
    # roles/classes
    "role": "Flex",             # Slayer / Entry / IGL / Support / Flex (Warzone/BO7)
    "bf6_class": "Assault",     # Assault / Recon / Engineer / Medic (BF6)
}


def _norm_game(v: str) -> str:
    s = (v or "").strip()
    sl = s.lower()
    if sl in ("bf6", "battlefield", "battlefield 6", "battlefield6"):
        return "BF6"
    if sl in ("bo7", "black ops 7", "blackops7"):
        return "BO7"
    if sl in ("warzone", "wz"):
        return "Warzone"
    # unknown -> keep default
    return "Warzone"


def _norm_platform(v: str) -> str:
    s = (v or "").strip().lower()
    if "play" in s or "ps" in s:
        return "PlayStation"
    if "xbox" in s or "xb" in s:
        return "Xbox"
    return "PC"


def _norm_input(v: str) -> str:
    s = (v or "").strip().lower()
    if "kbm" in s or "mouse" in s or "key" in s:
        return "KBM"
    return "Controller"


def _norm_difficulty(v: str) -> str:
    s = (v or "").strip().lower()
    if "demon" in s:
        return "Demon"
    if "pro" in s:
        return "Pro"
    return "Normal"


def _norm_voice(v: str) -> str:
    s = (v or "").strip().lower()
    if "coach" in s or "коуч" in s:
        return "COACH"
    return "TEAMMATE"


def _norm_role(v: str) -> str:
    # internal role values EN, UI labels RU
    s = (v or "").strip().lower()
    if "slay" in s or "слэй" in s:
        return "Slayer"
    if "entry" in s or "энтри" in s:
        return "Entry"
    if "igl" in s:
        return "IGL"
    if "support" in s or "саппорт" in s:
        return "Support"
    return "Flex"


def _norm_bf6_class(v: str) -> str:
    s = (v or "").strip().lower()
    if "recon" in s:
        return "Recon"
    if "engineer" in s:
        return "Engineer"
    if "medic" in s:
        return "Medic"
    return "Assault"


def _merge(base: Dict[str, str], patch: Dict[str, str]) -> Dict[str, str]:
    out = dict(base)
    out.update({k: v for k, v in (patch or {}).items() if v is not None})
    return out


@dataclass
class ProfileService:
    """
    Хранилище профилей поверх store.
    Требование: НЕ ЛОМАТЬСЯ, если store другой.
    Поддерживаем разные методы store:
      - get_profile(chat_id) / set_profile(chat_id, dict)
      - get(chat_id) / set(chat_id, dict)
      - read_profile / write_profile
    """
    store: Any

    # -------- public API --------
    def get(self, chat_id: int) -> Dict[str, str]:
        prof = self._read(chat_id)
        if not isinstance(prof, dict):
            prof = {}
        # гарантируем ключи
        merged = _merge(DEFAULT_PROFILE, {k: str(v) for k, v in prof.items()})
        # нормализуем
        return self._normalize(merged)

    def get_profile(self, chat_id: int) -> Dict[str, str]:
        return self.get(chat_id)

    def read(self, chat_id: int) -> Dict[str, str]:
        return self.get(chat_id)

    def reset(self, chat_id: int) -> None:
        self._write(chat_id, dict(DEFAULT_PROFILE))

    # универсальная запись (router вызывает set_field/set/update_profile и т.п.)
    def set(self, chat_id: int, key: str, val: str) -> None:
        prof = self.get(chat_id)
        prof[key] = val
        self._write(chat_id, self._normalize(prof))

    def set_field(self, chat_id: int, key: str, val: str) -> None:
        self.set(chat_id, key, val)

    def set_value(self, chat_id: int, key: str, val: str) -> None:
        self.set(chat_id, key, val)

    def update(self, chat_id: int, patch: Dict[str, str]) -> None:
        prof = self.get(chat_id)
        prof = _merge(prof, {k: str(v) for k, v in (patch or {}).items()})
        self._write(chat_id, self._normalize(prof))

    def update_profile(self, chat_id: int, patch: Dict[str, str]) -> None:
        self.update(chat_id, patch)

    # удобные методы (не обязательно, но полезно)
    def set_game(self, chat_id: int, game: str) -> None:
        self.set(chat_id, "game", game)

    def set_input(self, chat_id: int, input_name: str) -> None:
        self.set(chat_id, "input", input_name)

    def set_difficulty(self, chat_id: int, diff: str) -> None:
        self.set(chat_id, "difficulty", diff)

    def set_platform(self, chat_id: int, platform: str) -> None:
        self.set(chat_id, "platform", platform)

    def set_voice(self, chat_id: int, voice: str) -> None:
        self.set(chat_id, "voice", voice)

    def set_role(self, chat_id: int, role: str) -> None:
        self.set(chat_id, "role", role)

    def set_bf6_class(self, chat_id: int, bf6_class: str) -> None:
        self.set(chat_id, "bf6_class", bf6_class)

    # -------- internals --------
    def _normalize(self, prof: Dict[str, str]) -> Dict[str, str]:
        out = dict(prof)

        out["game"] = _norm_game(out.get("game", DEFAULT_PROFILE["game"]))
        out["platform"] = _norm_platform(out.get("platform", DEFAULT_PROFILE["platform"]))
        out["input"] = _norm_input(out.get("input", DEFAULT_PROFILE["input"]))
        out["difficulty"] = _norm_difficulty(out.get("difficulty", DEFAULT_PROFILE["difficulty"]))
        out["voice"] = _norm_voice(out.get("voice", DEFAULT_PROFILE["voice"]))
        out["role"] = _norm_role(out.get("role", DEFAULT_PROFILE["role"]))
        out["bf6_class"] = _norm_bf6_class(out.get("bf6_class", DEFAULT_PROFILE["bf6_class"]))

        # маленькая логика: если BF6, роль не критична, но не трогаем (НЕ режем)
        # если Warzone/BO7, bf6_class не критичен, но тоже не трогаем
        return out

    def _read(self, chat_id: int) -> Dict[str, Any]:
        s = self.store

        # 1) store.get_profile(chat_id)
        for name in ("get_profile", "read_profile"):
            if hasattr(s, name):
                try:
                    data = getattr(s, name)(chat_id)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass

        # 2) store.get(chat_id) (если store универсальный)
        if hasattr(s, "get"):
            try:
                data = s.get(chat_id)
                # ВНИМАНИЕ: InMemoryStore.get(chat_id) у тебя возвращает историю сообщений.
                # Поэтому здесь проверяем, что это именно профиль (dict), а не list.
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        # 3) store.profile(chat_id)
        if hasattr(s, "profile"):
            try:
                data = s.profile(chat_id)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass

        # 4) если store умеет set_profile/get_profile отдельно — но get не нашли
        # тогда профиля нет
        return {}

    def _write(self, chat_id: int, prof: Dict[str, Any]) -> None:
        s = self.store

        # 1) store.set_profile(chat_id, dict)
        if hasattr(s, "set_profile"):
            try:
                s.set_profile(chat_id, prof)
                return
            except Exception:
                pass

        # 2) store.write_profile(chat_id, dict)
        if hasattr(s, "write_profile"):
            try:
                s.write_profile(chat_id, prof)
                return
            except Exception:
                pass

        # 3) store.set(chat_id, dict) (НО осторожно: set может означать другое)
        if hasattr(s, "set"):
            try:
                s.set(chat_id, prof)
                return
            except Exception:
                pass

        # 4) store.profile_set(chat_id, dict)
        if hasattr(s, "profile_set"):
            try:
                s.profile_set(chat_id, prof)
                return
            except Exception:
                pass

        # если вообще некуда писать — молча (не падаем)
        return
