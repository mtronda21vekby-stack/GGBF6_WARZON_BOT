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

from app.reply_kb import bf6_main_keyboard


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

            # =========================
            # 🧟 ZOMBIES (поиск текстом)
            # =========================
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z:
                    self.api.send_message(
                        chat_id,
                        z["text"],
                        reply_markup=z.get("reply_markup"),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    return

            # =========================
            # 🎮 BF6 — ТОЛЬКО КНОПКИ
            # =========================
            if p.get("game") == "bf6":
                if t.lower().startswith("как играть"):
                    self.api.send_message(
                        chat_id,
                        "🎮 Battlefield 6\nВыбери, что именно хочешь разобрать:",
                        reply_markup=bf6_main_keyboard()
                    )
                    return

            # =========================
            # /START /MENU
            # =========================
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
                self.api.send_message(
                    chat_id,
                    help_text(),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/status"):
                self.api.send_message(
                    chat_id,
                    status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/profile"):
                self.api.send_message(
                    chat_id,
                    profile_text(chat_id),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
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
                    "🧨 Сброс выполнен.",
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # =========================
            # 💬 ОБЫЧНЫЙ ДИАЛОГ (AI)
            # =========================
            update_memory(chat_id, "user", t, self.s.MEMORY_MAX_TURNS)

            tmp_id = self.api.send_message(
                chat_id,
                thinking_line(),
                reply_markup=None,
                max_text_len=self.s.MAX_TEXT_LEN
            )

            try:
                mode = p.get("mode", "chat")
                reply = (
                    self.ai.coach_reply(chat_id, t)
                    if mode == "coach"
                    else self.ai.chat_reply(chat_id, t)
                )
            except Exception:
                self.log.exception("AI reply failed")
                reply = "😅 Напиши чуть конкретнее: где умер или что бесит."

            update_memory(chat_id, "assistant", reply, self.s.MEMORY_MAX_TURNS)
            p["last_answer"] = reply[:2000]
            save_state(self.s.STATE_PATH, self.log)

            if tmp_id:
                try:
                    self.api.edit_message(
                        chat_id,
                        tmp_id,
                        reply,
                        reply_markup=menu_main(chat_id, self.ai.enabled)
                    )
                except Exception:
                    self.api.send_message(
                        chat_id,
                        reply,
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
            else:
                self.api.send_message(
                    chat_id,
                    reply,
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )

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

            z = zombies_router.handle_callback(data)
            if z:
                sp = z.get("set_profile") or {}
                for k, v in sp.items():
                    p[k] = v
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(
                    chat_id,
                    message_id,
                    z["text"],
                    reply_markup=z.get("reply_markup")
                )
                return

            self.api.edit_message(
                chat_id,
                message_id,
                main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                reply_markup=menu_main(chat_id, self.ai.enabled)
            )

        finally:
            self.api.answer_callback(cb_id)
