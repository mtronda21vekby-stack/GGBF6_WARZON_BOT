# -*- coding: utf-8 -*-
import traceback
from typing import Dict, Any

from zombies import router as zombies_router
from app.bf6_module import (
    get_role_text, get_death_text,
    roles_keyboard, deaths_keyboard
)

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
from app.reply_kb import reply_kb


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

            # ===== BF6 Reply buttons =====
            if t in ("🎯 BF6 Роли",):
                self.api.send_message(
                    chat_id,
                    "🎯 BF6 — выбери роль:",
                    reply_markup=roles_keyboard(),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t in ("📊 BF6 Почему я умираю",):
                self.api.send_message(
                    chat_id,
                    "📊 BF6 — выбери причину:",
                    reply_markup=deaths_keyboard(),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Роли
            if t.startswith("🟠"):
                self.api.send_message(
                    chat_id,
                    get_role_text("assault", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("🟢"):
                self.api.send_message(
                    chat_id,
                    get_role_text("support", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("🔵"):
                self.api.send_message(
                    chat_id,
                    get_role_text("engineer", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("🟣"):
                self.api.send_message(
                    chat_id,
                    get_role_text("recon", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # Причины смерти
            if t.startswith("👁"):
                self.api.send_message(
                    chat_id,
                    get_death_text("no_vision", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("🔙"):
                self.api.send_message(
                    chat_id,
                    get_death_text("backstab", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("🔁"):
                self.api.send_message(
                    chat_id,
                    get_death_text("instadeath", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("⚔️"):
                self.api.send_message(
                    chat_id,
                    get_death_text("duel", p.get("persona","spicy"), p.get("mode","chat")),
                    reply_markup=reply_kb(p, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                return

            # ===== Zombies =====
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"),
                                          max_text_len=self.s.MAX_TEXT_LEN)
                    return

            # ===== Стандартный поток =====
            update_memory(chat_id, "user", t, self.s.MEMORY_MAX_TURNS)
            tmp_id = self.api.send_message(chat_id, thinking_line(), reply_markup=None,
                                           max_text_len=self.s.MAX_TEXT_LEN)

            try:
                reply = self.ai.coach_reply(chat_id, t) if p.get("mode") == "coach" else self.ai.chat_reply(chat_id, t)
            except Exception:
                self.log.exception("Reply generation failed")
                reply = "Упс 😅 Напиши ещё раз коротко."

            update_memory(chat_id, "assistant", reply, self.s.MEMORY_MAX_TURNS)
            save_state(self.s.STATE_PATH, self.log)

            if tmp_id:
                self.api.edit_message(chat_id, tmp_id, reply, reply_markup=reply_kb(p, self.ai.enabled))
            else:
                self.api.send_message(chat_id, reply, reply_markup=reply_kb(p, self.ai.enabled),
                                      max_text_len=self.s.MAX_TEXT_LEN)

        finally:
            lock.release()
