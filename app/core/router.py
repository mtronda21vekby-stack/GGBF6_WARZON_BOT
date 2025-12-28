# app/core/router.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import kb_main, kb_settings


def _safe_get(d: dict, path: list, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


@dataclass
class Router:
    """
    Единый роутер: все кнопки/команды идут сюда.
    Работает даже если brain/profiles у тебя реализованы по-разному.
    """

    tg: Any
    brain: Any = None
    profiles: Any = None
    store: Any = None
    settings: Any = None

    # --- PUBLIC API ---
    async def handle_update(self, update: Dict[str, Any]) -> None:
        """
        Telegram webhook update -> response via tg client
        """
        msg = update.get("message") or update.get("edited_message") or {}
        if not msg:
            # Можно расширить на callback_query позже
            return

        chat_id = _safe_get(msg, ["chat", "id"])
        text = (msg.get("text") or "").strip()

        if not chat_id:
            return

        # --- system commands ---
        if text in ("/start", "/menu", "📋 Меню", "Меню"):
            await self._send_welcome(chat_id)
            return

        # --- main quickbar buttons ---
        if text in ("🎮 Игра", "Игра"):
            await self._on_game(chat_id)
            return

        if text in ("⚙️ Настройки", "Настройки"):
            await self._on_settings(chat_id)
            return

        if text in ("📌 Профиль", "Профиль"):
            await self._on_profile(chat_id)
            return

        if text in ("🎯 Тренировка", "Тренировка"):
            await self._on_training(chat_id)
            return

        if text in ("🧠 ИИ", "ИИ"):
            await self._on_ai(chat_id)
            return

        if text in ("🧟 Zombies", "Zombies"):
            await self._on_zombies(chat_id)
            return

        if text in ("🎬 VOD", "VOD"):
            await self._on_vod(chat_id)
            return

        if text in ("🆘 Помощь", "Помощь"):
            await self._send(chat_id, "🆘 Помощь:\n/start — меню\nОпиши ситуацию/смерть одной строкой — дам разбор и план.")
            return

        if text in ("📡 Статус", "Статус", "/status"):
            await self._on_status(chat_id)
            return

        if text in ("🧹 Очистить память", "Очистить память"):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс", "Сброс"):
            await self._on_reset(chat_id)
            return

        # --- settings buttons (from kb_settings) ---
        if text.startswith("🎮 Игра:"):
            await self._set_game(chat_id, text.replace("🎮 Игра:", "").strip())
            await self._on_settings(chat_id, hint="✅ Игра сохранена.")
            return

        if text.startswith("🖥 Input:") or text.startswith("🎮 Input:") or text.startswith("🎮 Input"):
            # normalize
            raw = text.split(":", 1)[-1].strip() if ":" in text else text
            await self._set_input(chat_id, raw)
            await self._on_settings(chat_id, hint="✅ Input сохранён.")
            return

        if "Сложность:" in text:
            # "🧠 Сложность: Normal" / "🔥 Сложность: Pro" / "😈 Сложность: Demon"
            raw = text.split("Сложность:", 1)[-1].strip()
            await self._set_difficulty(chat_id, raw)
            await self._on_settings(chat_id, hint="✅ Сложность сохранена.")
            return

        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Возвращаю меню.")
            return

        # --- default: route to brain chat ---
        await self._chat_to_brain(chat_id, text)

    # --- INTERNAL: messaging helpers ---
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        # tg client у тебя уже принимает reply_markup как dict (важно!)
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, reply_markup=kb_main())

    async def _send_settings(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, reply_markup=kb_settings())

    async def _send_welcome(self, chat_id: int) -> None:
        title = "🧠 FPS Coach Bot | Warzone / BO7 / BF6"
        tip = "Напиши ситуацию/смерть одной строкой — я разберу и дам план.\nИли жми кнопки снизу 👇"
        await self._send_main(chat_id, f"{title}\n\n{tip}")

    # --- INTERNAL: button handlers ---
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = (prof.get("game") or "AUTO")
        await self._send_main(chat_id, f"🎮 Текущая игра: {game}\n\nОткрой ⚙️ Настройки чтобы выбрать Warzone/BF6/BO7.")

    async def _on_settings(self, chat_id: int, hint: str = "") -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "Warzone"
        input_ = prof.get("input") or "Controller"
        diff = prof.get("difficulty") or "Normal"

        head = "⚙️ Настройки — выбери ниже:"
        if hint:
            head = f"{hint}\n{head}"

        await self._send_settings(
            chat_id,
            f"{head}\n\n"
            f"🎮 Game: {game}\n"
            f"🎮 Input: {input_}\n"
            f"🧠 Difficulty: {diff}\n",
        )

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "AUTO"
        style = prof.get("style") or "coach"
        input_ = prof.get("input") or "Controller"
        diff = prof.get("difficulty") or "Normal"

        await self._send_main(
            chat_id,
            "📌 Профиль:\n"
            f"• Игра: {game}\n"
            f"• Input: {input_}\n"
            f"• Сложность: {diff}\n"
            f"• Стиль: {style}\n"
        )

    async def _on_training(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🎯 Тренировка:\n"
            "Напиши, что болит: аим / мувмент / позиционка.\n"
            "Пример: «Warzone, controller, мажу на средних, срываю контроль»"
        )

    async def _on_ai(self, chat_id: int) -> None:
        # пока: статус/заглушка, но НЕ тупая
        await self._send_main(
            chat_id,
            "🧠 ИИ: ON\n"
            "Дай вводные одной строкой:\n"
            "Игра | input | роль | проблема (аим/мувмент/позиционка) — соберу план."
        )

    async def _on_zombies(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🧟 Zombies:\n"
            "Скоро расширим карты и гайды. Сейчас напиши:\n"
            "Карта | раунд | от чего умираешь | что уже открыл — дам план."
        )

    async def _on_vod(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🎬 VOD:\n"
            "Пока режим в разработке.\n"
            "Если хочешь разбор — пришли 3 таймкода: 00:12 / 01:40 / 03:05 и что хочешь улучшить."
        )

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}
        await self._send_main(chat_id, f"📡 Статус: OK\n🧠 Memory: {mem or 'on'}")

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Память очищена ✅")

    async def _on_reset(self, chat_id: int) -> None:
        # сбрасываем профиль + память
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
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅\nВернул дефолтные настройки.")

    # --- INTERNAL: profile setters/getters (safe) ---
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
        return {"game": "AUTO", "input": "Controller", "difficulty": "Normal", "style": "coach"}

    async def _set_game(self, chat_id: int, game: str) -> None:
        if self.profiles:
            for name in ("set_game", "update_game"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, game)
                        return
                    except Exception:
                        pass

    async def _set_input(self, chat_id: int, input_name: str) -> None:
        if self.profiles:
            for name in ("set_input", "update_input"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, input_name)
                        return
                    except Exception:
                        pass

    async def _set_difficulty(self, chat_id: int, diff: str) -> None:
        if self.profiles:
            for name in ("set_difficulty", "update_difficulty"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, diff)
                        return
                    except Exception:
                        pass

    # --- INTERNAL: brain chat ---
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        # сохраняем память
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

        # brain может называться по-разному — ловим варианты
        if self.brain:
            for fn in ("reply", "chat", "handle", "run"):
                if hasattr(self.brain, fn):
                    try:
                        maybe = getattr(self.brain, fn)
                        # пробуем сигнатуры по очереди
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
            # фолбэк НЕ тупой (но без ИИ пока)
            reply = (
                "🧠 Принял.\n"
                "Дай вводные одной строкой:\n"
                "Игра (Warzone/BO7/BF6) | input (KBM/Controller) | где умираешь | почему думаешь.\n"
                "Я соберу план."
            )

        # сохраняем ответ в память
        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
