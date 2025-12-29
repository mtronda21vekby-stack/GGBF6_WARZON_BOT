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
    kb_roles,
    kb_game_settings_menu,
)

from app.worlds.bf6.presets import (
    bf6_class_text,
    bf6_aim_sens_text,
    bf6_controller_tuning_text,
    bf6_kbm_tuning_text,
)

from app.worlds.warzone.presets import (
    wz_role_text,
    wz_aim_sens_text,
    wz_controller_tuning_text,
    wz_kbm_tuning_text,
    wz_movement_positioning_text,
    wz_audio_visual_text,
)

from app.worlds.bo7.presets import (
    bo7_role_text,
    bo7_aim_sens_text,
    bo7_controller_tuning_text,
    bo7_kbm_tuning_text,
    bo7_movement_positioning_text,
    bo7_audio_visual_text,
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
                "Напиши ситуацию одной строкой — дам разбор как элитный тиммейт.",
            )
            return

        if text in ("/status",):
            await self._on_status(chat_id)
            return

        # ---------- MAIN quickbar ----------
        if text in ("🎮 Игра", "Игра"):
            await self._on_game(chat_id)
            return

        if text in ("⚙️ Настройки", "Настройки"):
            await self._send(chat_id, "⚙️ Настройки:", kb_settings())
            return

        # Класс (BF6) / Роль (Warzone/BO7)
        if text in ("🪖 Класс", "Класс"):
            await self._on_class_or_role(chat_id)
            return

        if text in ("🧠 ИИ", "ИИ", "/ai_start", "ai_start"):
            await self._send_main(
                chat_id,
                "🧠 AI режим: ON.\n"
                "Пиши как в чат: что случилось / где умер / что не получается.\n"
                "Я отвечу как живой сильный тиммейт (Normal/Pro/Demon зависит от профиля).",
            )
            return

        if text in ("🎯 Тренировка", "Тренировка"):
            await self._send_main(
                chat_id,
                "🎯 Тренировка:\n"
                "Напиши, что болит: aim / movement / positioning.\n"
                "Пример: «BF6, controller, мажу на миде, умираю при репике»"
            )
            return

        if text in ("🎬 VOD", "VOD"):
            await self._send_main(
                chat_id,
                "🎬 VOD:\n"
                "Пришли 3 таймкода (00:12 / 01:40 / 03:05) + что хочешь улучшить.\n"
                "Я дам разбор “ошибка → фикс → тренировка”."
            )
            return

        if text in ("🧟 Zombies", "Zombies"):
            await self._send_main(
                chat_id,
                "🧟 Zombies:\n"
                "Напиши: карта | раунд | от чего умираешь | что уже открыл.\n"
                "Дам план + приоритеты."
            )
            return

        if text in ("📌 Профиль", "Профиль"):
            await self._on_profile(chat_id)
            return

        if text in ("📊 Статус", "Статус"):
            await self._on_status(chat_id)
            return

        if text in ("💎 Premium",):
            await self._send_main(
                chat_id,
                "💎 Premium активен: нижний UI закреплён ✅\n"
                "Дальше добавим баннер/анимации в стиле DEMON."
            )
            return

        if text in ("🧹 Очистить память", "Очистить память"):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс", "Сброс"):
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

        # ----- BF6 settings -----
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

        # ----- Warzone settings -----
        if text in ("🎭 Warzone: Role Setup",):
            await self._send(chat_id, "🎭 Выбери роль:", kb_roles())
            return

        if text in ("⚔️ Slayer", "🚪 Entry", "🧠 IGL", "🛡 Support", "🌀 Flex"):
            role = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "role", role)
            prof = self._get_profile(chat_id)
            if (prof.get("game") or "Warzone") == "BO7":
                await self._send_main(chat_id, bo7_role_text(prof))
            else:
                await self._send_main(chat_id, wz_role_text(prof))
            return

        if text in ("🎯 Warzone: Aim/Sens",):
            await self._send_main(chat_id, wz_aim_sens_text(self._get_profile(chat_id)))
            return

        if text in ("🎮 Warzone: Controller Tuning",):
            await self._send_main(chat_id, wz_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("⌨️ Warzone: KBM Tuning",):
            await self._send_main(chat_id, wz_kbm_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("🧠 Warzone: Movement/Positioning",):
            await self._send_main(chat_id, wz_movement_positioning_text(self._get_profile(chat_id)))
            return

        if text in ("🎧 Warzone: Audio/Visual",):
            await self._send_main(chat_id, wz_audio_visual_text(self._get_profile(chat_id)))
            return

        # ----- BO7 settings -----
        if text in ("🎭 BO7: Role Setup",):
            await self._send(chat_id, "🎭 Выбери роль:", kb_roles())
            return

        if text in ("🎯 BO7: Aim/Sens",):
            await self._send_main(chat_id, bo7_aim_sens_text(self._get_profile(chat_id)))
            return

        if text in ("🎮 BO7: Controller Tuning",):
            await self._send_main(chat_id, bo7_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("⌨️ BO7: KBM Tuning",):
            await self._send_main(chat_id, bo7_kbm_tuning_text(self._get_profile(chat_id)))
            return

        if text in ("🧠 BO7: Movement/Positioning",):
            await self._send_main(chat_id, bo7_movement_positioning_text(self._get_profile(chat_id)))
            return

        if text in ("🎧 BO7: Audio/Visual",):
            await self._send_main(chat_id, bo7_audio_visual_text(self._get_profile(chat_id)))
            return

        # ---------- default -> AI chat ----------
        await self._chat_to_brain(chat_id, text)

    # ---------------- messaging helpers ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------------- profile ----------------
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
            "game": "Warzone",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Normal",
            "bf6_class": "Assault",
            "role": "Flex",
        }

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
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

        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception:
                pass

    # ---------------- UI handlers ----------------
    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            f"🎮 Game: {prof.get('game')}\n"
            f"🖥 Platform: {prof.get('platform')}\n"
            f"⌨️ Input: {prof.get('input')}\n"
            f"😈 Mode: {prof.get('difficulty')}\n"
            f"🪖 BF6 Class: {prof.get('bf6_class')}\n"
            f"🎭 Role: {prof.get('role')}\n",
        )

    async def _on_class_or_role(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = (prof.get("game") or "Warzone").strip()
        if game == "BF6":
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
        else:
            await self._send(chat_id, "🎭 Выбери роль:", kb_roles())

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

    # ---------------- AI chat ----------------
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
                    reply = (await out) if inspect.isawaitable(out) else out
            except Exception:
                reply = None

        if not reply:
            reply = (
                "🧠 AI fallback.\n"
                "📊 Статус покажет причину (OPENAI_API_KEY / AI_ENABLED).\n"
                "Напиши: игра | платформа | input | где умер | почему — дам план."
            )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
