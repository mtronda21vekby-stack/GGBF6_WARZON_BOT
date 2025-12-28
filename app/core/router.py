# app/core/router.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main, kb_settings, kb_games, kb_platform, kb_input, kb_difficulty,
    kb_classes_bf6, kb_bf6_settings_menu, kb_bf6_class_settings
)

from app.worlds.bf6.presets import (
    bf6_class_text, bf6_aim_sens_text, bf6_controller_tuning_text, bf6_kbm_tuning_text
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

        if text in ("/start", "/menu", "📋 Меню", "Меню"):
            await self._send_main(chat_id, "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n\nЖми кнопки снизу 👇")
            return

        # MAIN
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return
        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Settings:", kb_settings())
            return
        if text == "🪖 Класс":
            await self._on_class(chat_id)
            return
        if text == "🧠 ИИ":
            await self._send_main(chat_id, "🧠 AI ON.\nНапиши проблему одной строкой: game | platform | input | class/role | death reason | distance")
            return
        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return
        if text == "📊 Статус":
            await self._on_status(chat_id)
            return
        if text == "🧹 Очистить память":
            await self._on_clear_memory(chat_id)
            return
        if text == "🧨 Сброс":
            await self._on_reset(chat_id)
            return
        if text == "⬅️ Назад":
            await self._send_main(chat_id, "↩️ OK. Menu below 👇")
            return

        # SETTINGS FLOW
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Choose game:", kb_games())
            return
        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._send(chat_id, f"✅ Game = {game}", kb_settings())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Choose platform:", kb_platform())
            return
        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._send(chat_id, f"✅ Platform = {platform}", kb_settings())
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Choose input:", kb_input())
            return
        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = "KBM" if "KBM" in text else "Controller"
            self._set_profile_field(chat_id, "input", inp)
            await self._send(chat_id, f"✅ Input = {inp}", kb_settings())
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Choose mode:", kb_difficulty())
            return
        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = "Normal" if "Normal" in text else ("Pro" if "Pro" in text else "Demon")
            self._set_profile_field(chat_id, "difficulty", diff)
            await self._send(chat_id, f"✅ Difficulty = {diff}", kb_settings())
            return

        # GAME SETTINGS (WORLD)
        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = prof.get("game") or "Warzone"
            if game == "BF6":
                await self._send(chat_id, "🧩 BF6 Settings (EN):", kb_bf6_settings_menu())
                return
            # Warzone/BO7 оставляем как было, не режем — позже расширим
            await self._send_main(chat_id, "🧩 Warzone/BO7 settings: next step. (Не режем, просто следующий блок работ.)")
            return

        # BF6 SETTINGS MENU
        if text == "🧩 BF6: Class Settings":
            await self._send(chat_id, "🪖 Pick class setup:", kb_bf6_class_settings())
            return

        if text in ("🟥 Assault Setup", "🟦 Recon Setup", "🟨 Engineer Setup", "🟩 Medic Setup"):
            cls = text.split(" ", 1)[-1].replace("Setup", "").strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, bf6_class_text(prof))
            return

        if text == "🎯 BF6: Aim/Sens":
            prof = self._get_profile(chat_id)
            await self._send_main(chat_id, bf6_aim_sens_text(prof))
            return

        if text == "🎮 BF6: Controller Tuning":
            await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text == "⌨️ BF6: KBM Tuning":
            await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            return

        # BF6 CLASS PICK (quick button)
        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, f"✅ BF6 Class = {cls}")
            return

        # fallback -> AI
        await self._chat_to_brain(chat_id, text)

    # ---------- SEND ----------
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
        return {"game": "Warzone", "platform": "PC", "input": "Controller", "difficulty": "Normal", "bf6_class": "Assault"}

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        if self.profiles:
            for name in ("set", "set_field", "set_value", "update", "update_profile"):
                if hasattr(self.profiles, name):
                    try:
                        fn = getattr(self.profiles, name)
                        # поддержка разных сигнатур
                        try:
                            fn(chat_id, key, val)
                        except TypeError:
                            fn(chat_id, {key: val})
                        return
                    except Exception:
                        pass

    # ---------- HANDLERS ----------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            f"🎮 Game: {prof.get('game')}\n"
            f"🖥 Platform: {prof.get('platform')}\n"
            f"⌨️ Input: {prof.get('input')}\n"
            f"😈 Difficulty: {prof.get('difficulty')}\n"
            f"🪖 BF6 Class: {prof.get('bf6_class')}\n"
        )

    async def _on_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        if (prof.get("game") or "Warzone") != "BF6":
            await self._send_main(chat_id, "🪖 Class is BF6 only.\nGo: ⚙️ Настройки → 🎮 Выбрать игру → 🪖 BF6")
            return
        await self._send(chat_id, "🪖 Pick BF6 class:", kb_classes_bf6())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        lines = "\n".join([f"• {k}: {v}" for k, v in prof.items()])
        await self._send_main(chat_id, "📌 Profile:\n" + lines)

    async def _on_status(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)

        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}

        # AI status (explicit)
        ai_key = (getattr(self.settings, "openai_api_key", "") or "").strip() if self.settings else ""
        ai_enabled = bool(getattr(self.settings, "ai_enabled", True)) if self.settings else False
        model = getattr(self.settings, "openai_model", "gpt-4.1-mini") if self.settings else "?"

        ai_state = "ON" if (ai_enabled and ai_key) else "OFF"
        why = "OK" if ai_state == "ON" else ("OPENAI_API_KEY missing" if not ai_key else "ai_enabled=False")

        await self._send_main(
            chat_id,
            "📊 Status: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n"
            f"🎮 Game={prof.get('game')} | 🪖 Class={prof.get('bf6_class')}"
        )

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Memory cleared ✅")

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
        await self._send_main(chat_id, "🧨 Reset done ✅")

    # ---------- AI CHAT ----------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        if not text:
            await self._send_main(chat_id, "Send text — I will analyze.")
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
            except Exception:
                reply = None

        if not reply:
            reply = "🧠 AI fallback. Check /status."

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
