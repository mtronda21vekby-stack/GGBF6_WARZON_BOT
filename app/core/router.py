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
    kb_role,
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

        # --- system commands ---
        if text in ("/start", "/menu", "📋 Меню", "Меню"):
            await self._send_welcome(chat_id)
            return

        # --- MAIN QUICKBAR ---
        if text in ("🎮 Игра", "Игра"):
            await self._on_game(chat_id)
            return

        if text in ("⚙️ Настройки", "Настройки"):
            await self._open_settings(chat_id)
            return

        if text in ("🎭 Роль", "Роль"):
            await self._open_role(chat_id)
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

        if text in ("📊 Статус", "Статус", "/status"):
            await self._on_status(chat_id)
            return

        if text in ("🧹 Очистить память", "Очистить память"):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс", "Сброс"):
            await self._on_reset(chat_id)
            return

        if text in ("💎 Premium", "Premium"):
            await self._send_main(chat_id, "💎 Premium UI активен ✅\n(всё управление — снизу кнопками)")
            return

        # --- SETTINGS SUBMENU (premium reply keyboard) ---
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
            # позже подключим “миры” (Warzone/BO7 на RU, BF6 settings EN)
            await self._send(
                chat_id,
                "🧩 Настройки игры:\nСкоро подключим полный мир настроек под выбранную игру.\nПока выбери игру/платформу/input/режим мышления.",
                reply_markup=kb_settings(),
            )
            return

        # --- GAME PICK ---
        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = text.replace("🔥", "").replace("💣", "").replace("🪖", "").strip()
            await self._set_game(chat_id, game)
            await self._open_settings(chat_id, hint=f"✅ Игра сохранена: {game}")
            return

        # --- PLATFORM PICK ---
        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = text.replace("🖥", "").replace("🎮", "").strip()
            await self._set_platform(chat_id, platform)
            await self._open_settings(chat_id, hint=f"✅ Платформа: {platform}")
            return

        # --- INPUT PICK ---
        if text in ("⌨️ KBM", "🎮 Controller"):
            input_ = text.replace("⌨️", "").replace("🎮", "").strip()
            await self._set_input(chat_id, input_)
            await self._open_settings(chat_id, hint=f"✅ Input: {input_}")
            return

        # --- DIFFICULTY PICK ---
        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = text.replace("🧠", "").replace("🔥", "").replace("😈", "").strip()
            await self._set_difficulty(chat_id, diff)
            await self._open_settings(chat_id, hint=f"✅ Режим мышления: {diff}")
            return

        # --- ROLE PICK (Assault/Recon/Engineer/Medic) ---
        if text in ("🗡 Assault", "🎯 Recon", "🛠 Engineer", "🩺 Medic"):
            role = text.replace("🗡", "").replace("🎯", "").replace("🛠", "").replace("🩺", "").strip()
            await self._set_role(chat_id, role)
            await self._send(chat_id, f"✅ Роль: {role}", reply_markup=kb_role())
            return

        # --- BACK ---
        if text in ("⬅️ Назад", "Назад", "↩️ Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        # --- default: route to brain chat ---
        await self._chat_to_brain(chat_id, text)

    # -------------------------
    # SEND HELPERS
    # -------------------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, reply_markup=kb_main())

    async def _send_welcome(self, chat_id: int) -> None:
        title = "🧠 FPS Coach Bot | Warzone / BO7 / BF6"
        tip = "Пиши: игра | input | роль | от чего умер | дистанция (close/mid/long)\nЯ дам «СЕЙЧАС / ДАЛЬШЕ» как тиммейт."
        await self._send_main(chat_id, f"{title}\n\n{tip}")

    # -------------------------
    # MENUS
    # -------------------------
    async def _open_settings(self, chat_id: int, hint: str = "") -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "AUTO"
        platform = prof.get("platform") or "PC"
        input_ = prof.get("input") or "Controller"
        diff = prof.get("difficulty") or "Normal"
        role = prof.get("role") or "Assault"

        head = "⚙️ Настройки — выбери:"
        if hint:
            head = f"{hint}\n{head}"

        await self._send(
            chat_id,
            f"{head}\n\n"
            f"🎮 Game: {game}\n"
            f"🖥 Platform: {platform}\n"
            f"⌨️ Input: {input_}\n"
            f"😈 Brain: {diff}\n"
            f"🎭 Role: {role}\n",
            reply_markup=kb_settings(),
        )

    async def _open_role(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        role = prof.get("role") or "Assault"
        await self._send(chat_id, f"🎭 Текущая роль: {role}\nВыбери:", reply_markup=kb_role())

    # -------------------------
    # BUTTON HANDLERS
    # -------------------------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "AUTO"
        await self._send_main(chat_id, f"🎮 Текущая игра: {game}\nНажми ⚙️ Настройки → «🎮 Выбрать игру»")

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            "📌 Профиль:\n"
            f"• Game: {prof.get('game','AUTO')}\n"
            f"• Platform: {prof.get('platform','PC')}\n"
            f"• Input: {prof.get('input','Controller')}\n"
            f"• Brain: {prof.get('difficulty','Normal')}\n"
            f"• Role: {prof.get('role','Assault')}\n"
        )

    async def _on_training(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🎯 Тренировка:\nНапиши: что болит (aim/movement/positioning) + коротко ситуацию.")

    async def _on_ai(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🧠 ИИ: ON\nПиши одной строкой:\nигра | input | роль | от чего умер | дистанция — дам «СЕЙЧАС/ДАЛЬШЕ».")

    async def _on_zombies(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🧟 Zombies:\nСкоро расширим карты. Пиши: карта | раунд | от чего умираешь | что открыл.")

    async def _on_vod(self, chat_id: int) -> None:
        await self._send_main(chat_id, "🎬 VOD:\nПришли 3 таймкода и цель — сделаю разбор.")

    async def _on_status(self, chat_id: int) -> None:
        await self._send_main(chat_id, "📊 Статус: OK ✅")

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

    # -------------------------
    # PROFILE SAFE GET/SET
    # -------------------------
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
        return {
            "game": "AUTO",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Normal",
            "role": "Assault",
        }

    async def _set_game(self, chat_id: int, game: str) -> None:
        if self.profiles:
            for name in ("set_game", "update_game"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, game)
                        return
                    except Exception:
                        pass
        # fallback in store (если profiles нет)
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, "game", game)
            except Exception:
                pass

    async def _set_platform(self, chat_id: int, platform: str) -> None:
        if self.profiles:
            for name in ("set_platform", "update_platform"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, platform)
                        return
                    except Exception:
                        pass
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, "platform", platform)
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
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, "input", input_name)
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
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, "difficulty", diff)
            except Exception:
                pass

    async def _set_role(self, chat_id: int, role: str) -> None:
        if self.profiles:
            for name in ("set_role", "update_role"):
                if hasattr(self.profiles, name):
                    try:
                        getattr(self.profiles, name)(chat_id, role)
                        return
                    except Exception:
                        pass
        if self.store and hasattr(self.store, "set_profile_field"):
            try:
                self.store.set_profile_field(chat_id, "role", role)
            except Exception:
                pass

    # -------------------------
    # BRAIN CHAT (оставляем как было — без урезания)
    # -------------------------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        # если brain молчит — всё равно отвечаем “умным” фолбеком
        reply = None
        if self.brain:
            for fn in ("reply", "chat", "handle", "run"):
                if hasattr(self.brain, fn):
                    try:
                        maybe = getattr(self.brain, fn)
                        try:
                            reply = maybe(text=text, profile=self._get_profile(chat_id), history=[])
                        except TypeError:
                            reply = maybe(text)
                        break
                    except Exception:
                        reply = None

        if not reply:
            reply = (
                "🧠 Принял.\n"
                "Пиши одной строкой:\n"
                "игра | input | роль | от чего умер | дистанция (close/mid/long)\n"
                "Я дам «СЕЙЧАС / ДАЛЬШЕ» как тиммейт."
            )

        await self._send_main(chat_id, str(reply))
