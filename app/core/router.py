# app/core/router.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main, kb_settings, kb_games, kb_platform, kb_input, kb_difficulty, kb_classes_bf6
)


def _safe_get(d: dict, path: list, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


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

        # команды
        if text in ("/start", "/menu", "📋 Меню", "Меню"):
            await self._send_main(chat_id, "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n\nЖми кнопки снизу 👇")
            return

        # --- MAIN QUICKBAR ---
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return
        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки — выбери раздел:", kb_settings())
            return
        if text == "🪖 Класс":
            await self._on_class(chat_id)
            return
        if text == "🧠 ИИ":
            await self._on_ai(chat_id)
            return
        if text == "🎯 Тренировка":
            await self._send_main(chat_id, "🎯 Напиши: что болит (aim/movement/positioning) + игра + input. Я соберу план.")
            return
        if text == "🎬 VOD":
            await self._send_main(chat_id, "🎬 Пришли 3 таймкода и цель разбора. Я дам конкретные правки.")
            return
        if text == "🧟 Zombies":
            await self._send_main(chat_id, "🧟 Zombies: пока не трогаем, позже расширим карты.\nНапиши: карта | раунд | от чего умираешь | что открыл.")
            return
        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return
        if text == "📊 Статус":
            await self._on_status(chat_id)
            return
        if text == "💎 Premium":
            await self._send_main(chat_id, "💎 Premium активен: нижний UI закреплён.\nСкоро добавим баннер/анимации в стиле DEMON.")
            return
        if text == "🧹 Очистить память":
            await self._on_clear_memory(chat_id)
            return
        if text == "🧨 Сброс":
            await self._on_reset(chat_id)
            return

        # --- SETTINGS FLOW ---
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", kb_games())
            return
        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._send(chat_id, f"✅ Game = {game}\nВыбери следующий шаг:", kb_settings())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", kb_platform())
            return
        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._send(chat_id, f"✅ Platform = {platform}", kb_settings())
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Выбери input:", kb_input())
            return
        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = "KBM" if "KBM" in text else "Controller"
            self._set_profile_field(chat_id, "input", inp)
            await self._send(chat_id, f"✅ Input = {inp}", kb_settings())
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Выбери режим:", kb_difficulty())
            return
        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = "Normal" if "Normal" in text else ("Pro" if "Pro" in text else "Demon")
            self._set_profile_field(chat_id, "difficulty", diff)
            await self._send(chat_id, f"✅ Difficulty = {diff}", kb_settings())
            return

        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = prof.get("game") or "Warzone"
            # заглушка-навигатор под “миры” (позже расширим)
            if game == "BF6":
                await self._send_main(chat_id, "🧩 BF6 Settings: coming next (classes/loadouts/sens).\n(Сейчас главное: AI и UI стабильно.)")
            else:
                await self._send_main(chat_id, "🧩 Warzone/BO7 настройки: coming next (демон/про/норм пресеты).\n(Сейчас главное: AI и UI стабильно.)")
            return

        if text == "⬅️ Назад":
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        # --- CLASS PICK (BF6) ---
        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, f"✅ BF6 Class = {cls}")
            return

        # --- DEFAULT: CHAT TO AI ---
        await self._chat_to_brain(chat_id, text)

    # ---------- SEND HELPERS ----------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------- PROFILE ----------
    def _get_profile(self, chat_id: int) -> dict:
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        prof = getattr(self.profiles, name)(chat_id)
                        if isinstance(prof, dict):
                            return prof
                    except Exception:
                        pass
        # дефолт
        return {"game": "Warzone", "platform": "PC", "input": "Controller", "difficulty": "Normal", "bf6_class": ""}

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        if self.profiles:
            for name in ("set", "update", "set_field", "set_value"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, key, val)
                        return
                    except Exception:
                        pass
            # fallback: если нет сеттера — попробуем update_profile(dict)
            if hasattr(self.profiles, "update_profile"):
                try:
                    self.profiles.update_profile(chat_id, {key: val})
                    return
                except Exception:
                    pass

    # ---------- HANDLERS ----------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            f"🎮 Game: {prof.get('game','Warzone')}\n"
            f"🖥 Platform: {prof.get('platform','PC')}\n"
            f"⌨️ Input: {prof.get('input','Controller')}\n"
            f"😈 Difficulty: {prof.get('difficulty','Normal')}\n"
            f"🪖 BF6 Class: {prof.get('bf6_class','')}\n"
            "\nОткрой ⚙️ Настройки чтобы поменять."
        )

    async def _on_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "Warzone"
        if game != "BF6":
            await self._send_main(chat_id, "🪖 Класс доступен для BF6.\nСначала выбери игру: ⚙️ Настройки → 🎮 Выбрать игру → 🪖 BF6")
            return
        current = prof.get("bf6_class") or "—"
        await self._send(chat_id, f"🪖 BF6 Class сейчас: {current}\nВыбери:", kb_classes_bf6())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(chat_id, "📌 Профиль:\n" + "\n".join([f"• {k}: {v}" for k, v in prof.items()]))

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}
        await self._send_main(chat_id, f"📊 Status: OK\n🧠 Memory: {mem or 'on'}")

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
        if self.profiles and hasattr(self.profiles, "reset"):
            try:
                self.profiles.reset(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅")

    async def _on_ai(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "Warzone"
        if game == "BF6":
            await self._send_main(chat_id, "🧠 AI ON.\nFormat: game | platform | input | class | problem | distance (close/mid/long)")
        else:
            await self._send_main(chat_id, "🧠 ИИ ON.\nФормат: игра | платформа | input | роль | от чего умер | дистанция (close/mid/long)")

    # ---------- AI CHAT ----------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        if not text:
            await self._send_main(chat_id, "Напиши текстом, что случилось — я разберу.")
            return

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
        if self.brain and hasattr(self.brain, "reply"):
            try:
                reply = self.brain.reply(text=text, profile=prof, history=history)
            except TypeError:
                # на всякий
                reply = self.brain.reply(text=text, profile=prof, history=history)
            except Exception:
                reply = None

        if not reply:
            reply = "🧠 Принял. Дай вводные одной строкой: игра | платформа | input | от чего умер | дистанция."

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
