# -*- coding: utf-8 -*-
from typing import Dict, Any

from zombies import router as zombies_router
from app.kb import GAME_KB
from app.pro_settings import get_text as pro_get_text

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
    menu_settings_game, menu_wz_device, menu_bo7_device, menu_bf6_device,
    bottom_keyboard,
    BTN_MENU, BTN_SETTINGS, BTN_GAME, BTN_PERSONA, BTN_TALK,
    BTN_ZOMBIES, BTN_DAILY, BTN_VOD, BTN_PROFILE, BTN_STATUS, BTN_HELP,
    BTN_CLEAR_MEM, BTN_RESET
)


class BotHandlers:
    def __init__(self, api, ai_engine, settings, log):
        self.api = api
        self.ai = ai_engine
        self.s = settings
        self.log = log

    def _ensure_bottom_panel(self, chat_id: int) -> None:
        """
        Включаем reply-keyboard снизу ОДИН раз.
        Inline-кнопки под сообщением не мешаем.
        """
        p = ensure_profile(chat_id)
        if p.get("ui", "show") != "show":
            return
        if p.get("bottom_panel_page") == "main":
            return
        try:
            self.api.send_message(
                chat_id,
                "⬇️ Быстрые кнопки снизу активны.",
                reply_markup=bottom_keyboard(chat_id),
                max_text_len=self.s.MAX_TEXT_LEN
            )
            p["bottom_panel_page"] = "main"
            save_state(self.s.STATE_PATH, self.log)
        except Exception:
            pass

    def _open_inline(self, chat_id: int, text: str, reply_markup: Dict[str, Any]) -> None:
        """
        Открывает экран с inline-кнопками отдельным сообщением.
        (ReplyKeyboard снизу уже включен отдельным сообщением и продолжит жить.)
        """
        self.api.send_message(chat_id, text, reply_markup=reply_markup, max_text_len=self.s.MAX_TEXT_LEN)

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

            # Всегда пытаемся держать нижние кнопки включенными (без спама)
            self._ensure_bottom_panel(chat_id)

            # ✅ Zombies: если мы в меню Zombies — любой текст = поиск по карте
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                    return

            # =========================
            # ✅ Быстрые кнопки снизу (ReplyKeyboard)
            # =========================
            if t == BTN_MENU:
                p["page"] = "main"
                ensure_daily(chat_id)
                self._open_inline(chat_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), menu_main(chat_id, self.ai.enabled))
                save_state(self.s.STATE_PATH, self.log)
                return

            if t == BTN_SETTINGS:
                self._open_inline(chat_id, "⚙️ Настройки:", menu_settings(chat_id))
                return

            if t == BTN_GAME:
                self._open_inline(chat_id, "🎮 Выбери игру:", menu_game(chat_id))
                return

            if t == BTN_PERSONA:
                self._open_inline(chat_id, "🎭 Выбери стиль:", menu_persona(chat_id))
                return

            if t == BTN_TALK:
                self._open_inline(chat_id, "🗣 Длина ответа:", menu_talk(chat_id))
                return

            if t == BTN_ZOMBIES:
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_DAILY:
                d = ensure_daily(chat_id)
                self._open_inline(chat_id, "🎯 Задание дня:\n• " + d["text"], menu_daily(chat_id))
                return

            if t == BTN_VOD:
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                self._open_inline(chat_id, GAME_KB[g]["vod"], menu_more(chat_id))
                return

            if t == BTN_PROFILE:
                self._open_inline(chat_id, profile_text(chat_id), menu_more(chat_id))
                return

            if t == BTN_STATUS:
                self._open_inline(chat_id, status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled), menu_settings(chat_id))
                return

            if t == BTN_HELP:
                self._open_inline(chat_id, help_text(), menu_main(chat_id, self.ai.enabled))
                return

            if t == BTN_CLEAR_MEM:
                clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self._open_inline(chat_id, "🧽 Память очищена.", menu_more(chat_id))
                return

            if t == BTN_RESET:
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self._open_inline(chat_id, "🧨 Сброс выполнен.", menu_main(chat_id, self.ai.enabled))
                return

            # =========================
            # Команды
            # =========================
            if t.startswith("/start") or t.startswith("/menu"):
                p["page"] = "main"
                ensure_daily(chat_id)

                self._ensure_bottom_panel(chat_id)

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

            # =========================
            # обычный диалог
            # =========================
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
                key = f"wz:{'pad' if dev=='pad' else 'mnk'}"
                self.api.edit_message(chat_id, message_id, pro_get_text(key), reply_markup=menu_wz_device(chat_id))

            elif data.startswith("bo7dev:"):
                dev = data.split(":", 1)[1]
                key = f"bo7:{'pad' if dev=='pad' else 'mnk'}"
                self.api.edit_message(chat_id, message_id, pro_get_text(key), reply_markup=menu_bo7_device(chat_id))

            elif data.startswith("bf6dev:"):
                dev = data.split(":", 1)[1]
                key = f"bf6:{'pad' if dev=='pad' else 'mnk'}"
                self.api.edit_message(chat_id, message_id, pro_get_text(key), reply_markup=menu_bf6_device(chat_id))

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
