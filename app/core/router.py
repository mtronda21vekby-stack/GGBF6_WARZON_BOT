# app/core/router.py
# -*- coding: utf-8 -*-
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
    kb_premium,
    kb_voice,
)

from app.worlds.bf6.presets import (
    bf6_class_text,
    bf6_aim_sens_text,
    bf6_controller_tuning_text,
    bf6_kbm_tuning_text,
)

from app.worlds.warzone.presets import (
    wz_role_setup_text,
    wz_aim_sens_text,
    wz_controller_tuning_text,
    wz_kbm_tuning_text,
    wz_movement_positioning_text,
    wz_audio_visual_text,
)

from app.worlds.bo7.presets import (
    bo7_role_setup_text,
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


def _txt(x: Any) -> str:
    return ("" if x is None else str(x)).strip()


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
        text = _txt(msg.get("text"))
        if not chat_id:
            return

        # ---------------- commands ----------------
        if text in ("/start", "/menu", "Меню", "📋 Меню"):
            await self._welcome(chat_id)
            return

        if text in ("/status",):
            await self._on_status(chat_id)
            return

        # ---------------- MAIN QUICKBAR ----------------
        if text in ("🎮 Игра", "Игра"):
            await self._on_game(chat_id)
            return

        if text in ("⚙️ Настройки", "Настройки"):
            await self._on_settings(chat_id)
            return

        if text in ("🎭 Роль/Класс", "🎭 Роль", "🪖 Класс", "Роль", "Класс"):
            await self._on_role_or_class(chat_id)
            return

        if text in ("🧠 ИИ", "ИИ", "/ai"):
            await self._on_ai(chat_id)
            return

        if text in ("🎯 Тренировка", "Тренировка"):
            await self._on_training(chat_id)
            return

        if text in ("🎬 VOD", "VOD"):
            await self._on_vod(chat_id)
            return

        if text in ("🧟 Zombies", "Zombies"):
            await self._on_zombies(chat_id)
            return

        if text in ("📌 Профиль", "Профиль"):
            await self._on_profile(chat_id)
            return

        if text in ("📊 Статус", "Статус"):
            await self._on_status(chat_id)
            return

        if text in ("💎 Premium", "Premium"):
            await self._on_premium(chat_id)
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

        # ---------------- SETTINGS CONTAINER ----------------
        if text == "🎮 Выбрать игру":
            await self._send(chat_id, "🎮 Выбери игру:", kb_games())
            return

        if text in ("🔥 Warzone", "💣 BO7", "🪖 BF6"):
            game = "Warzone" if "Warzone" in text else ("BO7" if "BO7" in text else "BF6")
            self._set_profile_field(chat_id, "game", game)
            await self._on_settings(chat_id, hint=f"✅ Игра = {game}")
            return

        if text == "🖥 Платформа":
            await self._send(chat_id, "🖥 Выбери платформу:", kb_platform())
            return

        if text in ("🖥 PC", "🎮 PlayStation", "🎮 Xbox"):
            platform = "PC" if "PC" in text else ("PlayStation" if "PlayStation" in text else "Xbox")
            self._set_profile_field(chat_id, "platform", platform)
            await self._on_settings(chat_id, hint=f"✅ Платформа = {platform}")
            return

        if text == "⌨️ Input":
            await self._send(chat_id, "⌨️ Выбери input:", kb_input())
            return

        if text in ("⌨️ KBM", "🎮 Controller"):
            inp = "KBM" if "KBM" in text else "Controller"
            self._set_profile_field(chat_id, "input", inp)
            await self._on_settings(chat_id, hint=f"✅ Input = {inp}")
            return

        if text == "😈 Режим мышления":
            await self._send(chat_id, "😈 Выбери режим:", kb_difficulty())
            return

        if text in ("🧠 Normal", "🔥 Pro", "😈 Demon"):
            diff = "Normal" if "Normal" in text else ("Pro" if "Pro" in text else "Demon")
            self._set_profile_field(chat_id, "difficulty", diff)
            await self._on_settings(chat_id, hint=f"✅ Режим = {diff}")
            return

        if text == "🧩 Настройки игры":
            prof = self._get_profile(chat_id)
            game = prof.get("game") or "Warzone"
            await self._send(chat_id, f"🧩 {game} — настройки:", kb_game_settings_menu(game))
            return

        # ---------------- PREMIUM HUB ----------------
        if text == "🎙 Голос: Тиммейт/Коуч":
            await self._send(chat_id, "🎙 Выбери голос общения:", kb_voice())
            return

        if text in ("🤝 Тиммейт", "📚 Коуч"):
            voice = "TEAMMATE" if "Тиммейт" in text else "COACH"
            self._set_profile_field(chat_id, "voice", voice)
            joke = (
                "🤝 Режим тиммейта активен. Буду спасать тебя… но если ты опять репикнешь — я вздохну 😄"
                if voice == "TEAMMATE"
                else "📚 Режим коуча активен. Сейчас будет диагноз, план, и никакой лирики 😈"
            )
            await self._send(chat_id, f"✅ Голос = {voice}\n{joke}", kb_premium())
            return

        if text == "🎯 Тренировка: План":
            await self._send_main(
                chat_id,
                "🎯 Тренировка (20 минут, без воды):\n"
                "Напиши: игра | платформа | input | что болит.\n"
                "Я дам дриллы + как мерить прогресс.\n"
            )
            return

        if text == "🎬 VOD: Разбор":
            await self._send_main(
                chat_id,
                "🎬 VOD Разбор:\n"
                "Пришли 2–3 таймкода + цель.\n"
                "Будет: ошибка → почему → как чинить → дрилл.\n"
            )
            return

        if text == "🧠 Память: Статус":
            await self._on_status(chat_id)
            return

        # ---------------- ROLE / CLASS (one button for all) ----------------
        if text in ("⚔️ Слэйер", "🚪 Энтри", "🧠 IGL", "🛡 Саппорт", "🌀 Флекс"):
            role_map = {
                "⚔️ Слэйер": "Slayer",
                "🚪 Энтри": "Entry",
                "🧠 IGL": "IGL",
                "🛡 Саппорт": "Support",
                "🌀 Флекс": "Flex",
            }
            role = role_map.get(text, "Flex")
            self._set_profile_field(chat_id, "role", role)
            await self._send_main(chat_id, f"✅ Роль = {role}\nТеперь пиши ситуацию — буду отвечать в стиле роли.")
            return

        # ---------------- GAME SETTINGS BUTTONS (Warzone/BO7 RU) ----------------
        # Warzone
        if text == "🎭 Warzone: Роль":
            await self._send_main(chat_id, wz_role_setup_text(self._get_profile(chat_id)))
            return
        if text == "🎯 Warzone: Aim/Sens":
            await self._send_main(chat_id, wz_aim_sens_text(self._get_profile(chat_id)))
            return
        if text == "🎮 Warzone: Controller":
            await self._send_main(chat_id, wz_controller_tuning_text(self._get_profile(chat_id)))
            return
        if text == "⌨️ Warzone: KBM":
            await self._send_main(chat_id, wz_kbm_tuning_text(self._get_profile(chat_id)))
            return
        if text == "🧠 Warzone: Мувмент/Позиционка":
            await self._send_main(chat_id, wz_movement_positioning_text(self._get_profile(chat_id)))
            return
        if text == "🎧 Warzone: Аудио/Видео":
            await self._send_main(chat_id, wz_audio_visual_text(self._get_profile(chat_id)))
            return

        # BO7
        if text == "🎭 BO7: Роль":
            await self._send_main(chat_id, bo7_role_setup_text(self._get_profile(chat_id)))
            return
        if text == "🎯 BO7: Aim/Sens":
            await self._send_main(chat_id, bo7_aim_sens_text(self._get_profile(chat_id)))
            return
        if text == "🎮 BO7: Controller":
            await self._send_main(chat_id, bo7_controller_tuning_text(self._get_profile(chat_id)))
            return
        if text == "⌨️ BO7: KBM":
            await self._send_main(chat_id, bo7_kbm_tuning_text(self._get_profile(chat_id)))
            return
        if text == "🧠 BO7: Мувмент/Позиционка":
            await self._send_main(chat_id, bo7_movement_positioning_text(self._get_profile(chat_id)))
            return
        if text == "🎧 BO7: Аудио/Видео":
            await self._send_main(chat_id, bo7_audio_visual_text(self._get_profile(chat_id)))
            return

        # ---------------- BF6 SETTINGS (EN buttons) ----------------
        if text == "🪖 BF6: Class Settings":
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            return

        if text == "🎯 BF6: Aim/Sens":
            await self._send_main(chat_id, bf6_aim_sens_text(self._get_profile(chat_id)))
            return

        if text == "🎮 BF6: Controller Tuning":
            await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            return

        if text == "⌨️ BF6: KBM Tuning":
            await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            return

        # ---------------- default: route to AI ----------------
        await self._chat_to_brain(chat_id, text)

    # =========================
    # SEND HELPERS
    # =========================
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # =========================
    # HUBS / UI
    # =========================
    async def _welcome(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🧠 FPS Coach Bot — Ultra Premium\n\n"
            "Жми кнопки снизу 👇 или напиши ситуацию одной строкой.\n"
            "Я отвечаю как тиммейт/коуч (переключается в 💎 Premium). 😈",
        )

    async def _on_settings(self, chat_id: int, hint: str = "") -> None:
        prof = self._get_profile(chat_id)
        head = "⚙️ Настройки"
        if hint:
            head = f"{hint}\n\n{head}"

        await self._send(
            chat_id,
            f"{head}\n\n"
            f"🎮 Игра: {prof.get('game')}\n"
            f"🖥 Платформа: {prof.get('platform')}\n"
            f"⌨️ Input: {prof.get('input')}\n"
            f"😈 Режим: {prof.get('difficulty')}\n"
            f"🎙 Голос: {prof.get('voice')}\n",
            kb_settings(),
        )

    async def _on_game(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        await self._send_main(
            chat_id,
            "🎮 Текущий профиль:\n"
            f"• game: {prof.get('game')}\n"
            f"• platform: {prof.get('platform')}\n"
            f"• input: {prof.get('input')}\n"
            f"• difficulty: {prof.get('difficulty')}\n"
            f"• voice: {prof.get('voice')}\n"
            f"• role: {prof.get('role')}\n"
            f"• bf6_class: {prof.get('bf6_class')}\n",
        )

    async def _on_role_or_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = prof.get("game") or "Warzone"
        if game == "BF6":
            await self._send(chat_id, "🪖 Выбери класс BF6:", kb_bf6_classes())
        else:
            await self._send(chat_id, "🎭 Выбери роль:", kb_roles())

    async def _on_ai(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        voice = prof.get("voice", "TEAMMATE")
        humor = "😄" if voice == "TEAMMATE" else "🧠"
        await self._send_main(
            chat_id,
            f"🧠 ИИ включён {humor}\n"
            "Пиши как в чат: что случилось / где умер / что хочешь улучшить.\n"
            "Я отвечу живо (тиммейт) или структурно (коуч).\n",
        )

    async def _on_training(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🎯 Тренировка:\n"
            "Напиши: игра | платформа | input | проблема.\n"
            "Сделаю план на 20 минут и что именно отслеживать.",
        )

    async def _on_vod(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🎬 VOD:\n"
            "Пришли 2–3 таймкода и цель (аим/позиционка/решения).\n"
            "Я дам: ошибка → почему → как чинить → дрилл.",
        )

    async def _on_zombies(self, chat_id: int) -> None:
        await self._send_main(
            chat_id,
            "🧟 Zombies:\n"
            "Пиши: карта | раунд | от чего умираешь | что открыто.\n"
            "Дам план, без воды.",
        )

    async def _on_profile(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        lines = "\n".join([f"• {k}: {v}" for k, v in prof.items()])
        await self._send_main(chat_id, "📌 Профиль:\n" + lines)

    async def _on_premium(self, chat_id: int) -> None:
        await self._send(chat_id, "💎 Premium Hub:", kb_premium())

    async def _on_status(self, chat_id: int) -> None:
        mem = {}
        if self.store and hasattr(self.store, "stats"):
            try:
                mem = self.store.stats(chat_id)
            except Exception:
                pass

        ai_key = _txt(getattr(self.settings, "openai_api_key", ""))
        ai_enabled = bool(getattr(self.settings, "ai_enabled", True))
        model = _txt(getattr(self.settings, "openai_model", ""))

        ai_state = "ON" if (ai_enabled and ai_key) else "OFF"
        reason = "OK" if ai_state == "ON" else ("OPENAI_API_KEY missing" if not ai_key else "AI_ENABLED=0")

        await self._send_main(
            chat_id,
            "📊 Статус:\n"
            f"• AI: {ai_state} ({reason})\n"
            f"• Model: {model or '—'}\n"
            f"• Memory: {mem or 'on'}",
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

    # =========================
    # PROFILE IO
    # =========================
    def _get_profile(self, chat_id: int) -> dict:
        if self.profiles:
            for fn in ("get", "get_profile", "read"):
                if hasattr(self.profiles, fn):
                    try:
                        p = getattr(self.profiles, fn)(chat_id)
                        if isinstance(p, dict):
                            return p
                    except Exception:
                        pass
        return {
            "game": "Warzone",
            "platform": "PC",
            "input": "Controller",
            "difficulty": "Normal",
            "voice": "TEAMMATE",
            "role": "Flex",
            "bf6_class": "Assault",
        }

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        if self.profiles:
            for fn in ("set", "set_field", "set_value"):
                if hasattr(self.profiles, fn):
                    try:
                        getattr(self.profiles, fn)(chat_id, key, val)
                        return
                    except Exception:
                        pass
            # универсальный update
            for fn in ("update", "update_profile"):
                if hasattr(self.profiles, fn):
                    try:
                        getattr(self.profiles, fn)(chat_id, {key: val})
                        return
                    except Exception:
                        pass

        # fallback в store (если profiles нет/сломался)
        if self.store and hasattr(self.store, "set_profile"):
            try:
                self.store.set_profile(chat_id, {key: val})
            except Exception:
                pass

    # =========================
    # AI CHAT
    # =========================
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
                pass

        reply = None
        if self.brain and hasattr(self.brain, "reply"):
            try:
                fn = self.brain.reply
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    reply = await out if inspect.isawaitable(out) else out
            except Exception:
                reply = None

        if not reply:
            reply = (
                "🧠 ИИ сейчас молчит (или сеть шалит).\n"
                "Зайди в 📊 Статус — там причина (ключ/AI_ENABLED/модель).\n"
                "А пока: напиши «игра | платформа | input | что случилось» — и я дам план 😄"
            )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
