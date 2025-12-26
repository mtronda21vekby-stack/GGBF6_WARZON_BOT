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
    menu_training, menu_settings, menu_daily, thinking_line
)

# ✅ Нижняя клавиатура (reply keyboard)
from app.reply_kb import (
    reply_kb,
    BTN_HOME, BTN_MORE, BTN_BACK,
    BTN_GAME, BTN_MODE, BTN_LIGHTNING, BTN_MEMORY,
    BTN_ZOMBIES, BTN_TRAINING, BTN_DAILY, BTN_VOD, BTN_PROFILE, BTN_PRO,
    BTN_DEVICE,
    BTN_FINE, BTN_SETTINGS, BTN_CLEAR_MEM, BTN_RESET, BTN_STATUS, BTN_AI, BTN_HELP
)

# ✅ Настройки под девайсы
from app.device_settings import get_text


class BotHandlers:
    def __init__(self, api, ai_engine, settings, log):
        self.api = api
        self.ai = ai_engine
        self.s = settings
        self.log = log

    # -------------------------
    # Inline menus for Device Settings
    # -------------------------
    def _device_menu_kb(self) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "🎮 Xbox", "callback_data": "dev:plat:xbox"},
                 {"text": "🎮 PS5", "callback_data": "dev:plat:ps5"},
                 {"text": "🖥 PC", "callback_data": "dev:plat:pc"}],
                [{"text": "⬅️ Назад", "callback_data": "dev:close"}],
            ]
        }

    def _device_sections_kb(self, plat: str) -> Dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "📦 Полный сетап", "callback_data": f"dev:sec:{plat}:full"}],
                [{"text": "🎯 Aim", "callback_data": f"dev:sec:{plat}:aim"},
                 {"text": "🕹 Movement", "callback_data": f"dev:sec:{plat}:move"}],
                [{"text": "🎛 Видео", "callback_data": f"dev:sec:{plat}:video"},
                 {"text": "🔊 Звук", "callback_data": f"dev:sec:{plat}:audio"}],
                [{"text": "⬅️ Платформа", "callback_data": "dev:back"}],
            ]
        }

    def _send_home(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        p["rk_page"] = "main"
        ensure_daily(chat_id)
        save_state(self.s.STATE_PATH, self.log)
        self.api.send_message(
            chat_id,
            main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
            reply_markup=reply_kb(p, self.ai.enabled),
            max_text_len=self.s.MAX_TEXT_LEN
        )

    # -------------------------
    # MESSAGE HANDLER
    # -------------------------
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

            # ✅ Если мы в Zombies-режиме — любой НЕ-командный текст = поиск по текущей карте
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    self.api.send_message(
                        chat_id,
                        z["text"],
                        reply_markup=z.get("reply_markup"),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    return

            # -------------------------
            # Команды
            # -------------------------
            if t.startswith("/start") or t.startswith("/menu"):
                p["page"] = "main"
                p["rk_page"] = "main"
                self._send_home(chat_id)
                return

            if t.startswith("/help"):
                self.api.send_message(
                    chat_id,
                    help_text(),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/status"):
                self.api.send_message(
                    chat_id,
                    status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/profile"):
                self.api.send_message(
                    chat_id,
                    profile_text(chat_id),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/daily"):
                d = ensure_daily(chat_id)
                self.api.send_message(
                    chat_id,
                    "🎯 Задание дня:\n• " + d["text"],
                    reply_markup=menu_daily(chat_id),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/zombies"):
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                self.api.send_message(
                    chat_id,
                    z["text"],
                    reply_markup=z.get("reply_markup"),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/reset"):
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    "🧨 Сброс: профиль/память/статы/задание дня очищены.",
                    reply_markup=reply_kb(ensure_profile(chat_id), self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # -------------------------
            # ✅ НИЖНЯЯ КЛАВИАТУРА (Reply Keyboard) — весь функционал кнопками
            # -------------------------
            # Главная/Ещё/Назад
            if t == BTN_HOME:
                self._send_home(chat_id)
                return

            if t == BTN_MORE:
                p["rk_page"] = "more"
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    "📦 Ещё:",
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t == BTN_BACK:
                p["rk_page"] = "main"
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    "⬅️ Назад:",
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Тогглы
            if t.startswith(BTN_MODE):
                p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith(BTN_LIGHTNING):
                p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    "⚡ Режим Молния переключён.",
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith(BTN_MEMORY):
                p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
                if p["memory"] == "off":
                    clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(
                    chat_id,
                    "🧠 Память переключена.",
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Игра — оставим выбор через inline (надёжно и красиво)
            if t.startswith(BTN_GAME):
                self.api.send_message(
                    chat_id,
                    "🎮 Выбери игру:",
                    reply_markup=menu_game(chat_id),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Zombies / Training / Daily / VOD / Profile — открываем через inline меню (как у тебя)
            if t == BTN_ZOMBIES:
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_TRAINING:
                self.api.send_message(chat_id, "💪 Тренировка:", reply_markup=menu_training(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_DAILY:
                d = ensure_daily(chat_id)
                self.api.send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_VOD:
                self.api.send_message(chat_id, "📼 VOD-разбор:", reply_markup=menu_more(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_PROFILE:
                self.api.send_message(chat_id, profile_text(chat_id), reply_markup=reply_kb(p, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            # ✅ Настройки девайса (Xbox/PS5/PC) — inline
            if t == BTN_DEVICE:
                self.api.send_message(
                    chat_id,
                    "🎮 Выбери платформу (Xbox / PS5 / PC):",
                    reply_markup=self._device_menu_kb(),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Статус/Настройки/Помощь/Очистить/Сброс из страницы "more"
            if t == BTN_STATUS:
                self.api.send_message(
                    chat_id,
                    status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t == BTN_SETTINGS:
                self.api.send_message(chat_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_HELP:
                self.api.send_message(chat_id, help_text(), reply_markup=reply_kb(p, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_CLEAR_MEM:
                clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(chat_id, "🧽 Память очищена.", reply_markup=reply_kb(p, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t == BTN_RESET:
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=reply_kb(ensure_profile(chat_id), self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                return

            # -------------------------
            # Обычный диалог (AI)
            # -------------------------
            update_memory(chat_id, "user", t, self.s.MEMORY_MAX_TURNS)

            tmp_id = self.api.send_message(chat_id, thinking_line(), reply_markup=None, max_text_len=self.s.MAX_TEXT_LEN)

            mode = p.get("mode", "chat")
            try:
                reply = self.ai.coach_reply(chat_id, t) if mode == "coach" else self.ai.chat_reply(chat_id, t)
            except Exception:
                self.log.exception("Reply generation failed")
                reply = "Упс 😅 Что-то сломалось. Напиши ещё раз коротко: где умер и почему думаешь?"

            update_memory(chat_id, "assistant", reply, self.s.MEMORY_MAX_TURNS)
            p["last_answer"] = reply[:2000]
            save_state(self.s.STATE_PATH, self.log)

            # редактируем “думаю…”
            if tmp_id:
                try:
                    self.api.edit_message(chat_id, tmp_id, reply, reply_markup=reply_kb(p, self.ai.enabled))
                except Exception:
                    self.api.send_message(chat_id, reply, reply_markup=reply_kb(p, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
            else:
                self.api.send_message(chat_id, reply, reply_markup=reply_kb(p, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)

        finally:
            lock.release()

    # -------------------------
    # CALLBACK HANDLER
    # -------------------------
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

            # ✅ Device settings inline
            if data.startswith("dev:"):
                parts = data.split(":")

                if data == "dev:close":
                    # просто закрываем (перерисуем главную)
                    self.api.edit_message(
                        chat_id, message_id,
                        "🎮 Ок. Если нужно — снова нажми кнопку «🎮 Настройки».",
                        reply_markup=None
                    )
                    return

                if data == "dev:back":
                    self.api.edit_message(chat_id, message_id, "🎮 Выбери платформу:", reply_markup=self._device_menu_kb())
                    return

                # dev:plat:<plat>
                if len(parts) == 3 and parts[1] == "plat":
                    plat = parts[2]
                    p["device"] = plat
                    save_state(self.s.STATE_PATH, self.log)
                    self.api.edit_message(chat_id, message_id, f"✅ Платформа: {plat.upper()}\nВыбери раздел:", reply_markup=self._device_sections_kb(plat))
                    return

                # dev:sec:<plat>:<sec>
                if len(parts) == 4 and parts[1] == "sec":
                    plat, sec = parts[2], parts[3]
                    p["device"] = plat
                    save_state(self.s.STATE_PATH, self.log)

                    g = (p.get("game") or "auto").lower()
                    if g == "auto":
                        g = "warzone"

                    txt = get_text(g, plat, sec)
                    self.api.edit_message(chat_id, message_id, txt, reply_markup=self._device_sections_kb(plat))
                    return

                self.api.edit_message(chat_id, message_id, "🎮 Меню настроек:", reply_markup=self._device_menu_kb())
                return

            # -------------------------
            # ТВОИ СТАРЫЕ INLINE МЕНЮ (оставляем как было)
            # -------------------------
            if data == "nav:main":
                p["page"] = "main"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
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

            elif data == "toggle:memory":
                p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
                if p["memory"] == "off":
                    clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:mode":
                p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:ui":
                p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data == "toggle:lightning":
                p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data.startswith("set:game:"):
                g = data.split(":", 2)[2]
                if g in ("auto", "warzone", "bf6", "bo7"):
                    p["game"] = g
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data.startswith("set:persona:"):
                v = data.split(":", 2)[2]
                if v in ("spicy", "chill", "pro"):
                    p["persona"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

            elif data.startswith("set:talk:"):
                v = data.split(":", 2)[2]
                if v in ("short", "normal", "talkative"):
                    p["verbosity"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

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
                self.api.edit_message(
                    chat_id, message_id,
                    f"✅ Засчитал.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                    reply_markup=menu_daily(chat_id)
                )

            elif data == "daily:fail":
                d = ensure_daily(chat_id)
                d["fail"] = int(d.get("fail", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(
                    chat_id, message_id,
                    f"❌ Ок, честно.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                    reply_markup=menu_daily(chat_id)
                )

            else:
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))

        finally:
            self.api.answer_callback(cb_id)
