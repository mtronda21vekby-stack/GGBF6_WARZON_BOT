# app/core/router.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.ui.quickbar import (
    kb_main,
    kb_settings,
    kb_games,
    kb_platform,
    kb_input,
    kb_difficulty,
    kb_bf6_classes,
    kb_game_settings_menu,
)

from app.worlds.bf6.presets import (
    bf6_class_text,
    bf6_aim_sens_text,
    bf6_controller_tuning_text,
    bf6_kbm_tuning_text,
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

        # ---------- commands ----------
        if text in ("/start", "/menu", "Меню", "📋 Меню"):
            await self._send_main(
                chat_id,
                "🧠 FPS Coach Bot | Warzone / BO7 / BF6\n"
                "Нижний UI закреплён. Жми кнопки снизу 👇\n\n"
                "Пиши ситуацию как в обычный чат — я отвечу как тиммейт.",
            )
            return

        if text in ("/status", "📊 Статус"):
            await self._on_status(chat_id)
            return

        # ---------- premium ----------
        if text in ("💎 Premium",):
            await self._send_main(
                chat_id,
                "💎 Premium активен: нижний UI закреплён.\n"
                "Дальше: подключаем настоящий AI (OpenAI ключ в ENV).",
            )
            return

        # ---------- AI ----------
        if text in ("/ai_start", "ai_start", "🧠 ИИ", "ИИ"):
            # ВАЖНО: не подменяем сообщение на шаблон — иначе “цикл”
            await self._send_main(
                chat_id,
                "🧠 AI режим: ON.\n"
                "Пиши проблему/смерть/ситуацию — отвечаю как элитный тиммейт.\n"
                "Качество зависит от режима Normal/Pro/Demon в профиле.",
            )
            return

        # ---------- MAIN ----------
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки:", kb_settings())
            return

        if text in ("🪖 BF6 Класс", "Класс"):
            await self._on_bf6_class(chat_id)
            return

        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return

        if text in ("🧹 Очистить память",):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс",):
            await self._on_reset(chat_id)
            return

        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

        # ---------- SETTINGS FLOW ----------
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", kb_games())
            return

        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._send(chat_id, f"✅ Игра = {game}", kb_settings())
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._send(chat_id, f"✅ Платформа = {platform}", kb_settings())
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
            await self._send(chat_id, f"✅ Режим = {diff}", kb_settings())
            return

        # ---------- GAME SETTINGS PER WORLD ----------
        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = prof.get("game") or "Warzone"
            await self._send(chat_id, f"🧩 {game} Settings:", kb_game_settings_menu(game))
            return

        # ---------- BF6 world settings ----------
        if text in ("🪖 BF6: Class Settings",):
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            return

        if text in ("🎯 BF6: Aim/Sens",):
            await self._send_main(chat_id, bf6_aim_sens_text(self._get_profile(chat_id)))
            return

        if text in ("🎮 BF6: Controller Tuning",):
            await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("⌨️ BF6: KBM Tuning",):
            await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            return

        # Warzone / BO7 placeholders (НЕ режем меню — просто отдаём текст)
        if text.startswith("🧩 Warzone:") or text.startswith("🧩 BO7:") or text.startswith("🧩 AUTO:"):
            await self._chat_to_brain(chat_id, text)
            return

        # ---------- default -> AI chat ----------
        await self._chat_to_brain(chat_id, text)

    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    def _get_profile(self, chat_id: int) -> dict:
        # 1) profiles service
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        prof = getattr(self.profiles, name)(chat_id)
                        if isinstance(prof, dict):
                            return prof
                    except Exception:
                        pass

        # 2) store fallback
        if self.store and hasattr(self.store, "get_profile"):
            try:
                prof = self.store.get_profile(chat_id)
                if isinstance(prof, dict) and prof:
                    return prof
            except Exception:
                pass

        return {"game": "Warzone", "platform": "PC", "input": "Controller", "difficulty": "Normal", "bf6_class": "Assault"}

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        # profiles service (любая сигнатура)
        if self.profiles:
            for name in ("set", "set_field", "set_value", "update", "update_profile"):
                if hasattr(self.profiles, name):
                    try:
                        fn = getattr(self.profiles, name)
                        try:
                            fn(chat_id, key, val)
                        except TypeError:
                            fn(chat_id, {key: val})
                        return
                    except Exception:
                        pass

        # store fallback
        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception:
                pass

    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            f"🎮 Game: {prof.get('game')}\n"
            f"🖥 Platform: {prof.get('platform')}\n"
            f"⌨️ Input: {prof.get('input')}\n"
            f"😈 Mode: {prof.get('difficulty')}\n"
            f"🪖 BF6 Class: {prof.get('bf6_class')}\n",
        )

    async def _on_bf6_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        if (prof.get("game") or "Warzone") != "BF6":
            await self._send_main(chat_id, "🪖 Класс доступен только в BF6.\n⚙️ Настройки → 🎮 Выбрать игру → 🪖 BF6")
            return
        await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        lines = "\n".join([f"• {k}: {v}" for k, v in prof.items()])
        await self._send_main(chat_id, "📌 Профиль:\n" + lines)

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                mem = {}

        ai_key = (getattr(self.settings, "openai_api_key", "") or "").strip() if self.settings else ""
        ai_enabled = bool(getattr(self.settings, "ai_enabled", True)) if self.settings else False
        model = getattr(self.settings, "openai_model", "gpt-4.1-mini") if self.settings else "?"

        ai_state = "ON" if (ai_enabled and ai_key) else "OFF"
        why = "OK" if ai_state == "ON" else ("OPENAI_API_KEY missing" if not ai_key else "AI_ENABLED=0")

        await self._send_main(
            chat_id,
            f"📊 Status: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n",
        )

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
        if self.brain and hasattr(self.brain, "reply"):
            try:
                fn = self.brain.reply
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    reply = await out if inspect.isawaitable(out) else out
            except Exception as e:
                reply = f"ИИ: ERROR\n{type(e).__name__}: {e}\n\nПроверь:\n• OPENAI_API_KEY\n• AI_ENABLED=1\n• openai>=1.40.0"

        if not reply:
            reply = "🧠 AI fallback.\n📊 Статус покажет причину. Напиши: игра | платформа | input | что болит — дам план."

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
