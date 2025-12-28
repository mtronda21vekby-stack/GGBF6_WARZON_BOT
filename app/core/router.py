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
    kb_game_settings_menu,
)

# ---------------------------------------------------------------------------
# SAFE IMPORT: BF6 PRESETS
# Чтобы Render НИКОГДА не падал, если модуля нет или путь другой.
# ---------------------------------------------------------------------------
bf6_class_text = None
bf6_aim_sens_text = None
bf6_controller_tuning_text = None
bf6_kbm_tuning_text = None
_PRESETS_IMPORT_ERROR = None

for _path in (
    "app.worlds.bf6.presets",   # ожидаемый путь
    "app.world.bf6.presets",    # запасной
    "app.bf6.presets",          # запасной
):
    try:
        _m = __import__(
            _path,
            fromlist=[
                "bf6_class_text",
                "bf6_aim_sens_text",
                "bf6_controller_tuning_text",
                "bf6_kbm_tuning_text",
            ],
        )
        bf6_class_text = getattr(_m, "bf6_class_text", None)
        bf6_aim_sens_text = getattr(_m, "bf6_aim_sens_text", None)
        bf6_controller_tuning_text = getattr(_m, "bf6_controller_tuning_text", None)
        bf6_kbm_tuning_text = getattr(_m, "bf6_kbm_tuning_text", None)
        _PRESETS_IMPORT_ERROR = None
        break
    except Exception as e:
        _PRESETS_IMPORT_ERROR = e


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
                "Напиши ситуацию одной строкой — дам разбор как тиммейт.",
            )
            return

        if text in ("/status",):
            await self._on_status(chat_id)
            return

        # ---------- AI start (не делаем “шаблонный цикл”) ----------
        # Кнопка AI НЕ должна подменять текст на “Привет...” и уводить в одно и то же.
        if text in ("/ai_start", "ai_start", "🧠 ИИ", "ИИ"):
            await self._send_main(
                chat_id,
                "🧠 AI режим: ON.\n"
                "Пиши как в чат: ситуация / смерть / проблема.\n"
                "Я отвечу как элитный тиммейт (Normal/Pro/Demon зависит от профиля).",
            )
            return

        # ---------- MAIN quickbar ----------
        if text == "🎮 Игра":
            await self._on_game(chat_id)
            return

        if text == "⚙️ Настройки":
            await self._send(chat_id, "⚙️ Настройки:", kb_settings())
            return

        # кнопка “Класс” (BF6)
        if text in ("🪖 BF6 Класс", "🪖 Класс", "🪖 Class", "Класс"):
            await self._on_bf6_class(chat_id)
            return

        if text == "📌 Профиль":
            await self._on_profile(chat_id)
            return

        if text in ("📊 Статус",):
            await self._on_status(chat_id)
            return

        if text in ("🧹 Очистить память", "🧹 Очистить"):
            await self._on_clear_memory(chat_id)
            return

        if text in ("🧨 Сброс", "🧨 Reset"):
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
        if text in ("🪖 BF6: Class Settings", "🪖 BF6 Class Settings"):
            await self._send(chat_id, "🪖 Pick BF6 class:", kb_bf6_classes())
            return

        # BF6 classes (именно как ты хочешь)
        if text in ("🟥 Assault", "🟦 Recon", "🟨 Engineer", "🟩 Medic"):
            cls = text.split(" ", 1)[-1].strip()
            self._set_profile_field(chat_id, "bf6_class", cls)

            if bf6_class_text:
                await self._send_main(chat_id, bf6_class_text(self._get_profile(chat_id)))
            else:
                await self._send_main(
                    chat_id,
                    "⚠️ BF6 presets не найдены (поэтому текст классов не подгрузился).\n"
                    "Бот НЕ сломан — просто нет файла/пути.\n\n"
                    f"Ошибка: {_PRESETS_IMPORT_ERROR}",
                )
            return

        if text in ("🎯 BF6: Aim/Sens", "🎯 BF6 Aim/Sens"):
            if bf6_aim_sens_text:
                await self._send_main(chat_id, bf6_aim_sens_text(self._get_profile(chat_id)))
            else:
                await self._send_main(
                    chat_id,
                    "⚠️ BF6 Aim/Sens недоступно: presets не подгрузились.\n"
                    f"Ошибка: {_PRESETS_IMPORT_ERROR}",
                )
            return

        if text in ("🎮 BF6: Controller Tuning", "🎮 BF6 Controller Tuning"):
            if bf6_controller_tuning_text:
                await self._send_main(chat_id, bf6_controller_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(
                    chat_id,
                    "⚠️ BF6 Controller Tuning недоступно: presets не подгрузились.\n"
                    f"Ошибка: {_PRESETS_IMPORT_ERROR}",
                )
            return

        if text in ("⌨️ BF6: KBM Tuning", "⌨️ BF6 KBM Tuning"):
            if bf6_kbm_tuning_text:
                await self._send_main(chat_id, bf6_kbm_tuning_text(self._get_profile(chat_id)))
            else:
                await self._send_main(
                    chat_id,
                    "⚠️ BF6 KBM Tuning недоступно: presets не подгрузились.\n"
                    f"Ошибка: {_PRESETS_IMPORT_ERROR}",
                )
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
        }

    def _set_profile_field(self, chat_id: int, key: str, val: str) -> None:
        # НИЧЕГО НЕ РЕЖЕМ: поддержка разных профайл-сервисов
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

        # fallback если profiles не умеет — пишем в store (если есть)
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
            f"🪖 BF6 Class: {prof.get('bf6_class')}\n",
        )

    async def _on_bf6_class(self, chat_id: int) -> None:
        prof = self._get_profile(chat_id)
        if (prof.get("game") or "Warzone") != "BF6":
            await self._send_main(
                chat_id,
                "🪖 Класс доступен только в BF6.\n"
                "⚙️ Настройки → 🎮 Выбрать игру → 🪖 BF6",
            )
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

        presets_state = "OK" if (bf6_class_text and bf6_aim_sens_text) else "MISSING"
        presets_why = "OK" if presets_state == "OK" else str(_PRESETS_IMPORT_ERROR)

        await self._send_main(
            chat_id,
            f"📊 Status: OK\n"
            f"🧠 Memory: {mem or 'on'}\n"
            f"🤖 AI: {ai_state} | model={model} | reason={why}\n"
            f"🪖 BF6 Presets: {presets_state} | reason={presets_why}\n",
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
                # поддержка sync/async
                if inspect.iscoroutinefunction(fn):
                    reply = await fn(text=text, profile=prof, history=history)
                else:
                    out = fn(text=text, profile=prof, history=history)
                    if inspect.isawaitable(out):
                        reply = await out
                    else:
                        reply = out
            except Exception:
                reply = None

        if not reply:
            reply = (
                "🧠 AI fallback.\n"
                "📊 Статус покажет причину (OPENAI_API_KEY / AI_ENABLED).\n"
                "Напиши: игра | платформа | input | что болит — дам план."
            )

        if self.store and hasattr(self.store, "add"):
            try:
                self.store.add(chat_id, "assistant", str(reply))
            except Exception:
                pass

        await self._send_main(chat_id, str(reply))
