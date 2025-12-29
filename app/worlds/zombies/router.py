# app/worlds/zombies/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional, List

from app.ui.quickbar import kb_zombies_home, kb_zombies_maps, kb_zombies_sections

from app.worlds.zombies.ashes_of_damned import (
    MAP_ID as ASHES_ID,
    MAP_NAME as ASHES_NAME,
    get_section as ashes_get_section,
    search_sections as ashes_search,
)
from app.worlds.zombies.astra_malorum import (
    MAP_ID as ASTRA_ID,
    MAP_NAME as ASTRA_NAME,
    get_section as astra_get_section,
    search_sections as astra_search,
)


def _norm_map_name(text: str) -> str:
    t = (text or "").lower()
    if "ashes" in t:
        return ASHES_ID
    if "astra" in t:
        return ASTRA_ID
    return ""


def _map_title(map_id: str) -> str:
    if map_id == ASHES_ID:
        return ASHES_NAME
    if map_id == ASTRA_ID:
        return ASTRA_NAME
    return "Unknown"


def _get_section(map_id: str, section_key: str) -> Optional[dict]:
    if map_id == ASHES_ID:
        return ashes_get_section(section_key)
    if map_id == ASTRA_ID:
        return astra_get_section(section_key)
    return None


def _search(map_id: str, query: str) -> List[dict]:
    if map_id == ASHES_ID:
        return ashes_search(query)
    if map_id == ASTRA_ID:
        return astra_search(query)
    return []


def _default_map(profile: Dict[str, Any]) -> str:
    m = (profile or {}).get("zombies_map") or ASHES_ID
    m = str(m).strip().lower()
    if m not in (ASHES_ID, ASTRA_ID):
        return ASHES_ID
    return m


class ZombiesWorld:
    """
    Отдельный «мир» Zombies.
    Router (core) просто делегирует сюда кнопки/текст, когда пользователь в Zombies.
    """

    def __init__(self, *, tg: Any, profiles: Any):
        self.tg = tg
        self.profiles = profiles

    def _get_profile(self, chat_id: int) -> Dict[str, Any]:
        if self.profiles and hasattr(self.profiles, "get"):
            try:
                p = self.profiles.get(chat_id)
                if isinstance(p, dict):
                    return p
            except Exception:
                pass
        return {"zombies_map": ASHES_ID}

    def _set(self, chat_id: int, key: str, val: str) -> None:
        if self.profiles and hasattr(self.profiles, "set_field"):
            try:
                self.profiles.set_field(chat_id, key, val)
            except Exception:
                pass

    async def show_home(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        m = _default_map(prof)
        title = _map_title(m)

        txt = (
            "🧟 Zombies (MAX)\n\n"
            f"Текущая карта: {title}\n\n"
            "Как пользоваться:\n"
            "• Выбери карту (🗺 Карта)\n"
            "• Затем секцию (⚡/🔫/🧩/🧠)\n"
            "• Или напиши одной строкой:\n"
            "  карта | раунд | от чего падаешь | что открыл | соло/кооп\n\n"
            "Юмор:\n"
            "• Если ты умираешь в одном и том же месте — это не карта, это твоя привычка 😄"
        )
        await self.tg.send_message(chat_id=chat_id, text=txt, reply_markup=kb_zombies_home())

    async def handle(self, chat_id: int, text: str) -> bool:
        """
        Возвращает True если обработали (и core-router не должен дальше обрабатывать).
        False если не похоже на zombies-команду.
        """
        t = (text or "").strip()

        # входы
        if t == "🧟 Zombies":
            await self.show_home(chat_id)
            return True

        # zombies ui
        if t == "🗺 Карта":
            await self.tg.send_message(chat_id=chat_id, text="🗺 Выбери карту:", reply_markup=kb_zombies_maps())
            return True

        if t in ("🔥 Ashes of the Damned", "🌙 Astra Malorum"):
            map_id = _norm_map_name(t)
            if map_id:
                self._set(chat_id, "zombies_map", map_id)
                await self.tg.send_message(
                    chat_id=chat_id,
                    text=f"✅ Карта выбрана: {_map_title(map_id)}\nВыбирай секции ниже 👇",
                    reply_markup=kb_zombies_sections(),
                )
                return True

        if t in ("⚡ Перки", "🔫 Оружие", "🧩 Пасхалки", "🧠 Тактика по раундам", "💀 Ошибки/вайпы"):
            # это “хабы”, ведём в секции (универсально)
            await self.tg.send_message(
                chat_id=chat_id,
                text="Ок, выбирай конкретную секцию ниже 👇",
                reply_markup=kb_zombies_sections(),
            )
            return True

        if t in ("🔎 Поиск по гайду",):
            await self.tg.send_message(
                chat_id=chat_id,
                text="🔎 Напиши слово/фразу для поиска (пример: pap, перки, босс, антенны).",
                reply_markup=kb_zombies_home(),
            )
            # пометим состояние “ждём поисковый запрос”
            self._set(chat_id, "zombies_mode", "SEARCH")
            return True

        if t in ("🆘 Я застрял",):
            prof = self._get_profile(chat_id)
            map_id = _default_map(prof)
            sec = _get_section(map_id, "stuck")
            await self.tg.send_message(
                chat_id=chat_id,
                text=(sec["text"] if sec else "Напиши: карта | раунд | от чего падаешь | что открыл | соло/кооп"),
                reply_markup=kb_zombies_home(),
            )
            return True

        if t == "⬅️ Назад":
            # в zombies это возвращает в zombies-home
            await self.show_home(chat_id)
            return True

        # секции (унифицированные названия)
        section_map = {
            "🚀 Старт/маршрут": "start",
            "⚡ Pack-a-Punch": "pap",
            "🔫 Чудо-оружие": "wonder",
            "⚡ Перки (порядок)": "perks",
            "🔫 Оружие (2 слота)": "weapons",
            "🧠 Ротации/позиции": "rotation",
            "👹 Спец-зомби/боссы": "specials",
            "🧩 Пасхалка (основная)": "ee_main",
            "🎁 Мини-пасхалки": "ee_mini",
            "💀 Ошибки/вайпы": "mistakes",
            "🧾 Чек-лист раунда": "checklist",
        }
        if t in section_map:
            prof = self._get_profile(chat_id)
            map_id = _default_map(prof)
            key = section_map[t]
            sec = _get_section(map_id, key)

            # если на Ashes нет ee_main/ee_mini в “точном” виде — покажем intro/логическую секцию
            if not sec and key in ("ee_main", "ee_mini"):
                sec = _get_section(map_id, "ee_main") or _get_section(map_id, "intro")

            if sec:
                await self.tg.send_message(chat_id=chat_id, text=sec["text"], reply_markup=kb_zombies_sections())
            else:
                await self.tg.send_message(
                    chat_id=chat_id,
                    text="Секция пока не найдена. Нажми 🗺 Карта или 🔎 Поиск по гайду.",
                    reply_markup=kb_zombies_home(),
                )
            return True

        # обработка режима поиска
        prof = self._get_profile(chat_id)
        if str(prof.get("zombies_mode", "")).upper() == "SEARCH":
            map_id = _default_map(prof)
            hits = _search(map_id, t)
            self._set(chat_id, "zombies_mode", "")  # сброс режима

            if not hits:
                await self.tg.send_message(
                    chat_id=chat_id,
                    text="🔎 Ничего не нашёл. Попробуй другое слово (пример: пап, перки, босс, антенны).",
                    reply_markup=kb_zombies_home(),
                )
                return True

            # покажем до 3 лучших совпадений
            out = ["🔎 Нашёл вот что:\n"]
            for i, s in enumerate(hits[:3], 1):
                out.append(f"{i}) {s['title']}")
            out.append("\nНапиши номер (1-3), чтобы открыть, или повтори поиск другим словом.")

            # сохраним hits в профиль, чтобы открыть по номеру
            self._set(chat_id, "zombies_search_last", ",".join([h["id"] for h in hits[:3]]))

            await self.tg.send_message(chat_id=chat_id, text="\n".join(out), reply_markup=kb_zombies_home())
            return True

        # если юзер написал "1/2/3" после поиска
        if t in ("1", "2", "3"):
            ids = str(prof.get("zombies_search_last", "")).split(",")
            idx = int(t) - 1
            if 0 <= idx < len(ids) and ids[idx]:
                map_id = _default_map(prof)
                sec = _get_section(map_id, ids[idx])
                if sec:
                    await self.tg.send_message(chat_id=chat_id, text=sec["text"], reply_markup=kb_zombies_sections())
                    return True

        # не обработали
        return False
