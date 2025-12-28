# app/core/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main,
    kb_settings,
    kb_games,
    kb_platform,
    kb_input,
    kb_difficulty,
)


def _safe_get(d: dict, path: list, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def kb_roles() -> dict:
    return {
        "keyboard": [
            [{"text": "⚔️ Slayer"}, {"text": "🚪 Entry"}],
            [{"text": "🧠 IGL"}, {"text": "🛡 Support"}],
            [{"text": "🌀 Flex"}],
            [{"text": "⬅️ Назад"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
        "one_time_keyboard": False,
    }


@dataclass
class Router:
    tg: Any
    brain: Any = None
    profiles: Any = None
    store: Any = None
    settings: Any = None

    async def handle_update(self, update: Dict[str, Any]) -> None:
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            return

        chat_id = _safe_get(msg, ["chat", "id"])
        text = (msg.get("text") or "").strip()
        if not chat_id:
            return

        # -------- /start /menu --------
        if text in ("/start", "/menu", "📋 Меню", "Меню"):
            await self._send_welcome(chat_id)
            return

        # -------- MAIN QUICKBAR --------
        if text in ("🎮 Игра",):
            await self._on_game(chat_id)
            return

        if text in ("⚙️ Настройки",):
            await self._on_settings(chat_id)
            return

        if text in ("🎭 Роль",):
            await self._on_role(chat_id)
            return

        if text in ("🧠 ИИ",):
            await self._on_ai(chat_id)
            return

        if text in ("🎯 Тренировка",):
            await self._on_training(chat_id)
            return

        if text in ("🎬 VOD",):
            await self._on_vod(chat_id)
            return

        if text in ("🧟 Zombies",):
            await self._on_zombies(chat_id)
            return

        if text in ("📌 Профиль",):
            await self._on_profile(chat_id)
            return

        if text in ("📊 Статус", "/status"):
            await self._on_status(chat_id)
            return

        if text in ("💎 Premium",):
            await self._send_main(chat_id, "💎 Premium скоро будет (баннер/анимации/память/ультра-режимы). Сейчас допиливаем мозг и настройки.")
            return

        if text in ("🧹 Очистить память",):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс",):
            await self._on_reset(chat_id)
            return

        # -------- SETTINGS CONTAINER --------
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", reply_markup=kb_games())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", reply_markup=kb_platform())
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Выбери input:", reply_markup=kb_input())
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Выбери режим мышления:", reply_markup=kb_difficulty())
            return

        if text == "🧩 Настройки игры":
            # пока заглушка — но не тупая
            prof = self._get_profile(chat_id)
            g = prof.get("game") or "Warzone"
            if str(g).upper() == "BF6":
                await self._send_main(chat_id, "🧩 BF6 Settings: type “settings” in chat and I’ll generate EN settings for your platform/input.")
            else:
                await self._send_main(chat_id, "🧩 Настройки игры: напиши «настройки» — и я дам полный сет под твою платформу и input.")
            return

        # -------- BACK --------
        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        # -------- GAME SELECTION --------
        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = text.replace("🔥", "").replace("💣", "").replace("🪖", "").strip()
            await self._set_profile(chat_id, {"game": game})
            await self._on_settings(chat_id, hint=f"✅ Игра: {game}")
            return

        # -------- PLATFORM SELECTION --------
        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            plat = text.replace("🖥", "").replace("🎮", "").strip()
            await self._set_profile(chat_id, {"platform": plat})
            await self._on_settings(chat_id, hint=f"✅ Платформа: {plat}")
            return

        # -------- INPUT SELECTION --------
        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = text.replace("⌨️", "").replace("🎮", "").strip()
            await self._set_profile(chat_id, {"input": inp})
            await self._on_settings(chat_id, hint=f"✅ Input: {inp}")
            return

        # -------- DIFFICULTY SELECTION --------
        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = text.replace("🧠", "").replace("🔥", "").replace("😈", "").strip()
            await self._set_profile(chat_id, {"difficulty": diff})
            await self._on_settings(chat_id, hint=f"✅ Режим: {diff}")
            return

        # -------- ROLE SELECTION --------
        if text in ("⚔️ Slayer", "🚪 Entry", "🧠 IGL", "🛡 Support", "🌀 Flex"):
            role = text.replace("⚔️", "").replace("🚪", "").replace("🧠", "").replace("🛡", "").replace("🌀", "").strip()
            await self._set_profile(chat_id, {"role": role})
            await self._send_main(chat_id, f"✅ Роль: {role}")
            return

        # -------- DEFAULT: CHAT TO BRAIN --------
        await self._chat_to_brain(chat_id, text)

    # ---------------- SEND HELPERS ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, reply_markup=kb_main())

    async def _send_settings(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, reply_markup=kb_settings())

    async def _send_welcome(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n\n"
            "Нажимай кнопки снизу 👇 или напиши ситуацию одной строкой:\n"
            "игра | input | роль | что болит (аим/мувмент/позиционка)"
        )

    # ---------------- BUTTON HANDLERS ----------------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        g = prof.get("game") or "Warzone"
        await self._send(chat_id, f"🎮 Текущая игра: {g}\nВыбери другую:", reply_markup=kb_games())

    async def _on_settings(self, chat_id: int, hint: str = "") -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "Warzone"
        platform = prof.get("platform") or "PC"
        input_ = prof.get("input") or "Controller"
        diff = prof.get("difficulty") or "Normal"
        role = prof.get("role") or "Flex"

        head = "⚙️ Настройки — выбери:"
        if hint:
            head = f"{hint}\n{head}"

        await self._send_settings(
            chat_id,
            f"{head}\n\n"
            f"🎮 Game: {game}\n"
            f"🖥 Platform: {platform}\n"
            f"⌨️ Input: {input_}\n"
            f"😈 Mind: {diff}\n"
            f"🎭 Role: {role}\n"
        )

    async def _on_role(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        role = prof.get("role") or "Flex"
        await self._send(chat_id, f"🎭 Текущая роль: {role}\nВыбери:", reply_markup=kb_roles())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            "📌 Профиль:\n"
            f"• Game: {prof.get('game')}\n"
            f"• Platform: {prof.get('platform')}\n"
            f"• Input: {prof.get('input')}\n"
            f"• Mind: {prof.get('difficulty')}\n"
            f"• Role: {prof.get('role')}\n"
        )

    async def _on_training(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🎯 Тренировка:\nНапиши: «план тренировки» или опиши что болит (аим/мувмент/позиционка).")

    async def _on_ai(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🧠 ИИ: ON\n"
            "Пиши одной строкой:\n"
            "игра | input | роль | от чего умер | дистанция (close/mid/long)\n"
            "Я дам «СЕЙЧАС / ДАЛЬШЕ» как тиммейт."
        )

    async def _on_zombies(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🧟 Zombies пока не трогаем (как ты сказал). Позже расширим Ashes/Astra.")

    async def _on_vod(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🎬 VOD: пришли 3 таймкода + что хочешь улучшить. Позже сделаем полноценный режим.")

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}
        await self._send_main(chat_id, f"📊 Статус: OK\n🧠 Memory: {mem or 'on'}")

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Память очищена ✅")

    async def _on_reset(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._set_profile(chat_id, {"game": "Warzone", "platform": "PC", "input": "Controller", "difficulty": "Normal", "role": "Flex"})
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅")

    # ---------------- PROFILE STORAGE (НЕ ЛОМАЕТ profiles service) ----------------
    def _get_profile(self, chat_id: int) -> dict:
        base = {"game": "Warzone", "platform": "PC", "input": "Controller", "difficulty": "Normal", "role": "Flex"}

        # 1) профили из твоего ProfileService (если умеет)
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        p = getattr(self.profiles, name)(chat_id)
                        if isinstance(p, dict):
                            base.update(p)
                    except Exception:
                        pass

        # 2) meta из store (надежно и всегда есть)
        if self.store and hasattr(self.store, "get_meta"):
            try:
                base.update(self.store.get_meta(chat_id))
            except Exception:
                pass

        return base

    async def _set_profile(self, chat_id: int, patch: dict) -> None:
        # store meta
        if self.store and hasattr(self.store, "update_meta"):
            try:
                self.store.update_meta(chat_id, patch)
            except Exception:
                pass

        # profiles service (если умеет)
        if self.profiles:
            for fn in ("update", "set", "set_profile", "patch"):
                if hasattr(self.profiles, fn):
                    try:
                        getattr(self.profiles, fn)(chat_id, patch)
                        break
                    except Exception:
                        pass

    # ---------------- BRAIN CHAT ----------------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "user", text)
            except Exception:
                pass

        prof = self._get_profile(chat_id)

        history = []
        if self.store and hasattr(self.store, "get"):
            try:
                history = self.store.get(chat_id)
            except Exception:
                history = []

        reply = None
        if self.brain:
            for fn in ("reply", "chat", "handle", "run"):
                if hasattr(self.brain, fn):
                    try:
                        maybe = getattr(self.brain, fn)
                        try:
                            reply = maybe(text=text, profile=prof, history=history)
                        except TypeError:
                            try:
                                reply = maybe(chat_id=chat_id, text=text, profile=prof, history=history)
                            except TypeError:
                                reply = maybe(text)
                        break
                    except Exception:
                        reply = None

        if not reply:
            reply = "ИИ временно недоступен. Напиши: игра | input | роль | что болит — и я отвечу."

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
