# -*- coding: utf-8 -*-
import traceback
from typing import Dict, Any

from zombies import router as zombies_router

from app.kb import GAME_KB
from app.state import (
    ensure_profile, ensure_daily,
    update_memory, clear_memory,
    USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY,
    save_state, throttle, get_lock
)

from app.ui import (
    main_text, help_text, status_text, profile_text,
    menu_main, menu_more, menu_game, menu_persona, menu_talk,
    menu_training, menu_settings, menu_daily, thinking_line,
    menu_settings_game, menu_wz_device, menu_bo7_device, menu_bf6_device
)


def _wz_settings_text(device: str) -> str:
    if device == "pad":
        return (
            "⚙️ Warzone (PS5/Xbox) — Controller (RU)\n\n"
            "Главное:\n"
            "• Deadzone: минимально без дрифта\n"
            "• Sens: средняя (не завышай)\n"
            "• ADS: чуть ниже sens\n"
            "• Aim Response: Dynamic\n"
            "• FOV: 105–120 (по комфорту)\n\n"
            "Хочешь — дай свои значения, я подгоню точнее."
        )
    return (
        "⚙️ Warzone (PC) — Mouse & Keyboard (RU)\n\n"
        "Главное:\n"
        "• DPI: 800 (или 1600) + sens ниже\n"
        "• eDPI цель: ~2400–4800 (старт)\n"
        "• ADS multiplier: 0.85–1.00\n"
        "• FOV: 105–120\n"
        "• Motion blur OFF\n\n"
        "Напиши DPI и sens — соберу точный блок."
    )


def _bo7_settings_text(device: str) -> str:
    if device == "pad":
        return (
            "⚙️ BO7 (PS5/Xbox) — Controller (RU)\n\n"
            "• Deadzone: минимально без дрифта\n"
            "• Aim response: Dynamic (если есть)\n"
            "• Sens: средняя, ADS чуть ниже\n"
            "• FOV: выше среднего\n\n"
            "Если скажешь стиль (агро/позиционка) — докручу."
        )
    return (
        "⚙️ BO7 (PC) — Mouse & Keyboard (RU)\n\n"
        "• DPI 800/1600, sens ниже\n"
        "• ADS 0.85–1.00\n"
        "• FOV комфортный\n"
        "• Blur OFF\n\n"
        "Дай DPI+sense — соберу точный набор."
    )


def _bf6_settings_text(device: str) -> str:
    # BF6 просил на английском
    if device == "pad":
        return (
            "BF6 Controller (PS5/Xbox) — Settings (EN)\n\n"
            "Core:\n"
            "• Stick Deadzone: as low as possible without drift\n"
            "• Response Curve: Linear / Default (pick the most consistent)\n"
            "• Sensitivity: medium, ADS slightly lower\n"
            "• Aim Assist: ON (default)\n"
            "• FOV: 90–105 (console comfort) or higher if you can track well\n"
            "• Motion Blur: OFF\n\n"
            "Tell me if you have stick drift (yes/no) — I’ll tune deadzones."
        )
    return (
        "BF6 Mouse & Keyboard (PC) — Settings (EN)\n\n"
        "Core:\n"
        "• DPI: 800 or 1600\n"
        "• In-game sens: keep eDPI reasonable (start ~2400–4800)\n"
        "• ADS multiplier: 0.85–1.00\n"
        "• FOV: 100–110 (start), adjust for tracking\n"
        "• Raw input: ON (if available)\n"
        "• Motion Blur: OFF\n\n"
        "Send your DPI + current sens — I’ll calculate a clean setup."
    )


class BotHandlers:
    def __init__(self, api, ai_engine, settings, log):
        self.api = api
        self.ai = ai_engine
        self.s = settings
        self.log = log

    def handle_message(self, chat_id: int, text: str) -> None:
        lock = get_lock(chat_id)
        if not lock.acquire(blocking=False):
            return
        try:
            if throttle(chat_id, self.s.MIN_SECONDS_BETWEEN_MSG):
                return

            p = ensure_profile(chat_id)
            t = (text or "").strip()
            if not t:
                return

            # ✅ Zombies: если мы в меню Zombies — любой текст = поиск по карте
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                    return

            # Команды
            if t.startswith("/start") or t.startswith("/menu"):
                p["page"] = "main"
                ensure_daily(chat_id)
                self.api.send_message(
                    chat_id,
                    main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                save_state(self.s.STATE_PATH, self.log)
                return

            if t.startswith("/help"):
                self.api.send_message(chat_id, help_text(), reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/status"):
                self.api.send_message(chat_id, status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                                      reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/profile"):
                self.api.send_message(chat_id, profile_text(chat_id), reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/daily"):
                d = ensure_daily(chat_id)
                self.api.send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/zombies"):
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/reset"):
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            # обычный диалог
            update_memory(chat_id, "user", t, self.s.MEMORY_MAX_TURNS)

            tmp_id = self.api.send_message(chat_id, thinking_line(), reply_markup=None, max_text_len=self.s.MAX_TEXT_LEN)

            mode = p.get("mode", "chat")
            try:
                reply = self.ai.coach_reply(chat_id, t) if mode == "coach" else self.ai.chat_reply(chat_id, t)
            except Exception:
                self.log.exception("Reply generation failed")
                reply = "Упс 😅 Ошибка. Напиши ещё раз коротко: где умер и почему думаешь?"

            update_memory(chat_id, "assistant", reply, self.s.MEMORY_MAX_TURNS)
            p["last_answer"] = reply[:2000]
            save_state(self.s.STATE_PATH, self.log)

            if tmp_id:
                try:
                    self.api.edit_message(chat_id, tmp_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled))
                except Exception:
                    self.api.send_message(chat_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
            else:
                self.api.send_message(chat_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)

        finally:
            lock.release()

    def handle_callback(self, cb: Dict[str, Any]) -> None:
        cb_id = cb.get("id")
        msg = cb.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        data = (cb.get("data") or "").strip()

        if not cb_id or not chat_id or not message_id:
            return

        try:
            p = ensure_profile(chat_id)

            # ✅ Zombies router перехватывает ВСЕ zmb:* кнопки
            z = zombies_router.handle_callback(data)
            if z is not None:
                sp = z.get("set_profile") or {}
                if isinstance(sp, dict) and sp:
                    for k, v in sp.items():
                        p[k] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
                return

            # ============= NAV / MENUS =============
            if data == "nav:main":
                p["page"] = "main"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "nav:more":
                self.api.edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=menu_more(chat_id))

            elif data == "nav:game":
                self.api.edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))

            elif data == "nav:persona":
                self.api.edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))

            elif data == "nav:talk":
                self.api.edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))

            elif data == "nav:training":
                self.api.edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))

            elif data == "nav:settings":
                self.api.edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))

            # ✅ ВОЗВРАЩАЕМ “старое” + ДОБАВЛЯЕМ BF6 аккуратно:
            elif data == "nav:settings_game":
                self.api.edit_message(chat_id, message_id, "🎮 Настройки игр:", reply_markup=menu_settings_game(chat_id))

            elif data == "nav:wz_settings":
                self.api.edit_message(chat_id, message_id, "⚙️ Warzone — выбери устройство:", reply_markup=menu_wz_device(chat_id))

            elif data == "nav:bo7_settings":
                self.api.edit_message(chat_id, message_id, "⚙️ BO7 — выбери устройство:", reply_markup=menu_bo7_device(chat_id))

            elif data == "nav:bf6_settings":
                self.api.edit_message(chat_id, message_id, "⚙️ BF6 — choose device:", reply_markup=menu_bf6_device(chat_id))

            elif data.startswith("wzdev:"):
                dev = data.split(":", 1)[1]
                self.api.edit_message(chat_id, message_id, _wz_settings_text(dev), reply_markup=menu_wz_device(chat_id))

            elif data.startswith("bo7dev:"):
                dev = data.split(":", 1)[1]
                self.api.edit_message(chat_id, message_id, _bo7_settings_text(dev), reply_markup=menu_bo7_device(chat_id))

            elif data.startswith("bf6dev:"):
                dev = data.split(":", 1)[1]
                self.api.edit_message(chat_id, message_id, _bf6_settings_text(dev), reply_markup=menu_bf6_device(chat_id))

            # ============= TOGGLES =============
            elif data == "toggle:memory":
                p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
                if p["memory"] == "off":
                    clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:mode":
                p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:ui":
                p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:lightning":
                p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            # ============= SETTERS =============
            elif data.startswith("set:game:"):
                g = data.split(":", 2)[2]
                if g in ("auto", "warzone", "bf6", "bo7"):
                    p["game"] = g
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data.startswith("set:persona:"):
                v = data.split(":", 2)[2]
                if v in ("spicy", "chill", "pro"):
                    p["persona"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data.startswith("set:talk:"):
                v = data.split(":", 2)[2]
                if v in ("short", "normal", "talkative"):
                    p["verbosity"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            # ============= ACTIONS =============
            elif data == "action:status":
                self.api.edit_message(chat_id, message_id,
                                      status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                                      reply_markup=menu_settings(chat_id))

            elif data == "action:profile":
                self.api.edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_more(chat_id))

            elif data == "action:ai_status":
                ai = "ON" if self.ai.enabled else "OFF"
                self.api.edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {self.s.OPENAI_MODEL}",
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "action:clear_memory":
                clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_more(chat_id))

            elif data == "action:reset_all":
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=menu_more(chat_id))

            elif data.startswith("action:drill:"):
                kind = data.split(":", 2)[2]
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
                self.api.edit_message(chat_id, message_id, txt, reply_markup=menu_training(chat_id))

            elif data == "action:vod":
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                self.api.edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=menu_more(chat_id))

            elif data == "action:daily":
                d = ensure_daily(chat_id)
                self.api.edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))

            elif data == "daily:done":
                d = ensure_daily(chat_id)
                d["done"] = int(d.get("done", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"✅ Засчитал.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))

            elif data == "daily:fail":
                d = ensure_daily(chat_id)
                d["fail"] = int(d.get("fail", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"❌ Ок.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))

            else:
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

        finally:
            self.api.answer_callback(cb_id)
