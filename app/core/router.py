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
    kb_roles,
    kb_bf6_classes,
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

# Эти файлы ты создашь по моим пресетам (ты сказал: дашь после)
# app/worlds/warzone/presets.py
# app/worlds/bo7/presets.py
try:
    from app.worlds.warzone.presets import (
        wz_role_setup_text,
        wz_aim_sens_text,
        wz_controller_tuning_text,
        wz_kbm_tuning_text,
        wz_movement_positioning_text,
        wz_audio_visual_text,
    )
except Exception:
    wz_role_setup_text = None
    wz_aim_sens_text = None
    wz_controller_tuning_text = None
    wz_kbm_tuning_text = None
    wz_movement_positioning_text = None
    wz_audio_visual_text = None

try:
    from app.worlds.bo7.presets import (
        bo7_role_setup_text,
        bo7_aim_sens_text,
        bo7_controller_tuning_text,
        bo7_kbm_tuning_text,
        bo7_movement_positioning_text,
        bo7_audio_visual_text,
    )
except Exception:
    bo7_role_setup_text = None
    bo7_aim_sens_text = None
    bo7_controller_tuning_text = None
    bo7_kbm_tuning_text = None
    bo7_movement_positioning_text = None
    bo7_audio_visual_text = None


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
                "Нижний Premium UI закреплён 👇\n\n"
                "Пиши ситуацию одной строкой — разберу как тиммейт.\n"
                "Хочешь “по полочкам” — переключи голос на 📚 Коуч.\n"
                "Если хочешь чисто угар — ставь 😈 Demon и погнали 😄",
            )
            return

        if text in ("/status",):
            await self._on_status(chat_id)
            return

        # ---------- MAIN quickbar ----------
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки:", kb_settings())
            return

        if text == "🎭 Роль/Класс":
            await self._on_role_or_class(chat_id)
            return

        if text in ("🧠 ИИ", "ИИ"):
            prof = self._get_profile(chat_id)
            voice = (prof.get("voice") or "TEAMMATE").upper()
            vv = "Тиммейт 🤝" if voice == "TEAMMATE" else "Коуч 📚"
            await self._send_main(
                chat_id,
                f"🧠 AI: ON | Голос: {vv}\n"
                "Пиши как в обычный чат: ситуация / смерть / проблема.\n"
                "Отвечу живо, без копипасты. Если начну душнить — пни меня 😈",
            )
            return

        if text == "🎯 Тренировка":
            await self._send_main(
                chat_id,
                "🎯 Тренировка\n\n"
                "Напиши одной строкой:\n"
                "Игра | input | что болит (аим/мувмент/позиционка) | где чаще умираешь\n\n"
                "Сделаю план на 20 минут + как мерить прогресс.\n"
                "Да, будет без “воды”. Вода — только в твоих слезах после гуллага 😄",
            )
            return

        if text == "🎬 VOD":
            await self._send_main(
                chat_id,
                "🎬 VOD (разбор)\n\n"
                "Пока без загрузки видео.\n"
                "Кинь 3 таймкода текстом (00:12 / 01:40 / 03:05) + что хотел сделать.\n"
                "Я разберу решения как тиммейт/коуч.\n"
                "Если ты 3 раза подряд умер одинаково — не стыдно, это “обучение” 😄",
            )
            return

        if text == "🧟 Zombies":
            await self._send_main(
                chat_id,
                "🧟 Zombies\n\n"
                "Зомби не режем — просто сейчас приоритет UI/ИИ.\n"
                "Но если надо срочно: карта | раунд | от чего падаешь | что открыл — дам план.\n"
                "И да: если тебя съел зомби — это не баг, это “механика” 😄",
            )
            return

        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return

        if text == "📊 Статус":
            await self._on_status(chat_id)
            return

        if text == "💎 Premium":
            await self._send(chat_id, "💎 Premium Hub:", kb_premium())
            return

        if text == "🧹 Очистить память":
            await self._on_clear_memory(chat_id)
            return

        if text == "🧨 Сброс":
            await self._on_reset(chat_id)
            return

        # ---------- PREMIUM HUB ----------
        if text == "🎙 Голос: Тиммейт/Коуч":
            await self._send(chat_id, "🎙 Выбери стиль общения:", kb_voice())
            return

        if text in ("🤝 Тиммейт", "📚 Коуч"):
            voice = "TEAMMATE" if "Тиммейт" in text else "COACH"
            self._set_profile_field(chat_id, "voice", voice)
            await self._send(chat_id, f"✅ Голос = {voice}", kb_premium())
            return

        if text == "🎯 Тренировка: План":
            await self._send_main(
                chat_id,
                "🎯 План тренировки (20 минут)\n"
                "1) 5 мин — разминка (контроль)\n"
                "2) 10 мин — основной фокус (твой слабый элемент)\n"
                "3) 5 мин — закрепление в реальном бою\n\n"
                "Напиши: игра | input | слабое место — я сделаю план под тебя.\n"
                "И да: “мне просто не везёт” — это тоже диагноз 😄",
            )
            return

        if text == "🎬 VOD: Разбор":
            await self._send_main(chat_id, "🎬 Кидай 3 таймкода + что хотел сделать. Разберу.")
            return

        if text == "🧠 Память: Статус":
            await self._on_status(chat_id)
            return

        # ---------- SETTINGS FLOW ----------
        if text in ("⬅️ Назад", "Назад"):
            await self._send_main(chat_id, "↩️ Ок. Меню снизу 👇")
            return

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

        if text in ("😈 Режим мышления",):
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

        # ---------- ROLE/CLASS ----------
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
            await self._send_main(
                chat_id,
                f"✅ Роль = {role}\n"
                "Теперь открой 🧩 Настройки игры — там будет магия цифр 😈"
            )
            return

        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)
            await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            return

        # ---------- MENU ITEMS (MUST MATCH quickbar.py) ----------
        # WARZONE (RU buttons)
        if text == "🎭 Warzone: Роль":
            self._set_profile_field(chat_id, "game", "Warzone")
            await self._send(chat_id, "🎭 Выбери роль (Warzone):", kb_roles())
            return

        if text == "🎯 Warzone: Aim/Sens":
            if wz_aim_sens_text:
                await self._send_main(chat_id, wz_aim_sens_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/warzone/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🎮 Warzone: Controller":
            if wz_controller_tuning_text:
                await self._send_main(chat_id, wz_controller_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/warzone/presets.py — пришли пресеты, я соберу.")
            return

        if text == "⌨️ Warzone: KBM":
            if wz_kbm_tuning_text:
                await self._send_main(chat_id, wz_kbm_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/warzone/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🧠 Warzone: Мувмент/Позиционка":
            if wz_movement_positioning_text:
                await self._send_main(chat_id, wz_movement_positioning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/warzone/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🎧 Warzone: Аудио/Видео":
            if wz_audio_visual_text:
                await self._send_main(chat_id, wz_audio_visual_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/warzone/presets.py — пришли пресеты, я соберу.")
            return

        # BO7 (RU buttons)
        if text == "🎭 BO7: Роль":
            self._set_profile_field(chat_id, "game", "BO7")
            await self._send(chat_id, "🎭 Выбери роль (BO7):", kb_roles())
            return

        if text == "🎯 BO7: Aim/Sens":
            if bo7_aim_sens_text:
                await self._send_main(chat_id, bo7_aim_sens_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/bo7/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🎮 BO7: Controller":
            if bo7_controller_tuning_text:
                await self._send_main(chat_id, bo7_controller_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/bo7/presets.py — пришли пресеты, я соберу.")
            return

        if text == "⌨️ BO7: KBM":
            if bo7_kbm_tuning_text:
                await self._send_main(chat_id, bo7_kbm_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/bo7/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🧠 BO7: Мувмент/Позиционка":
            if bo7_movement_positioning_text:
                await self._send_main(chat_id, bo7_movement_positioning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/bo7/presets.py — пришли пресеты, я соберу.")
            return

        if text == "🎧 BO7: Аудио/Видео":
            if bo7_audio_visual_text:
                await self._send_main(chat_id, bo7_audio_visual_text(self._get_profile(chat_id)))
            else:
                await self._send_main(chat_id, "❗️Нет файла app/worlds/bo7/presets.py — пришли пресеты, я соберу.")
            return

        # BF6 (EN buttons)
        if text == "🪖 BF6: Class Settings":
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
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

        # ---------- default -> AI chat ----------
        await self._chat_to_brain(chat_id, text)

    # ---------------- messaging helpers ----------------
    async def _send(self, chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
        if reply_markup is None:
            reply_markup = kb_main()
        await self.tg.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def _send_main(self, chat_id: int, text: str) -> None:
        await self._send(chat_id, text, kb_main())

    # ---------------- profile helpers ----------------
    def _get_profile(self, chat_id: int) -> dict:
        if self.profiles:
            for name in ("get", "get_profile", "read"):
                if hasattr(self.profiles, name):
                    try:
                        prof = getattr(self.profiles, name)(chat_id)
                        if isinstance(prof, dict):
                            # гарантируем ключи (не ломаем старые профили)
                            prof.setdefault("game", "Warzone")
                            prof.setdefault("platform", "PC")
                            prof.setdefault("input", "Controller")
                            prof.setdefault("difficulty", "Normal")
                            prof.setdefault("voice", "TEAMMATE")
                            prof.setdefault("role", "Flex")
                            prof.setdefault("bf6_class", "Assault")
                            return prof
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
            for name in ("set_field", "set", "set_value", "update", "update_profile"):
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
            "🎮 Текущее:\n"
            f"• Game: {prof.get('game')}\n"
            f"• Platform: {prof.get('platform')}\n"
            f"• Input: {prof.get('input')}\n"
            f"• Brain Mode: {prof.get('difficulty')}\n"
            f"• Voice: {prof.get('voice')}\n"
            f"• Role: {prof.get('role')}\n"
            f"• BF6 Class: {prof.get('bf6_class')}\n",
        )

    async def _on_role_or_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        game = (prof.get("game") or "Warzone").upper()
        if game == "BF6":
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return
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
            f"📊 Статус: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n",
        )

    async def _on_clear_memory(self, chat_id: int) -> None:
        if self.store and hasattr(self.store, "clear"):
            try:
                self.store.clear(chat_id)
            except Exception:
                pass
        await self._send_main(chat_id, "🧹 Память очищена ✅ (прошлые фейлы забыты, скилл — нет 😄)")

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
        await self._send_main(chat_id, "🧨 Сброс выполнен ✅ (мы не сдаёмся, мы делаем демона 😈)")

    # ---------------- AI chat ----------------
    async def _chat_to_brain(self, chat_id: int, text: str) -> None:
        # add user to memory
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
                # поддержка sync/async
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    if inspect.isawaitable(out):
                        reply = await out
                    else:
                        reply = out
            except Exception as e:
                reply = (
                    "🧠 ИИ: ERROR\n"
                    f"{type(e).__name__}: {e}\n\n"
                    "Если это случилось внезапно — глянь 📊 Статус."
                )

        if not reply:
            reply = (
                "🧠 AI fallback.\n"
                "📊 Статус покажет причину (OPENAI_API_KEY / AI_ENABLED).\n"
                "Напиши: игра | платформа | input | что болит — дам план.\n"
                "И да: “я умер потому что лаги” — мы это тоже лечим 😄"
            )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
