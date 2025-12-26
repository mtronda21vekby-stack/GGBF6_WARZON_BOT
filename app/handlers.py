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
    menu_settings_game, menu_wz_device, menu_bo7_device, menu_bf6_device
)

# ✅ Нижние кнопки (ReplyKeyboard)
from app.reply_kb import (
    kb_root, kb_warzone, kb_bo7, kb_bf6,
    kb_device_pick_ru, kb_tier_pick_ru
)


# =========================
# Helpers: bottom keyboard by page
# =========================
def _bottom_kb_for_page(page: str):
    page = (page or "main").strip().lower()
    if page == "wz":
        return kb_warzone()
    if page == "bo7":
        return kb_bo7()
    if page == "bf6":
        return kb_bf6()
    # zombies / main / unknown
    return kb_root()


def _send_inline_with_bottom(api, chat_id: int, text: str, inline_kb, bottom_kb, max_len: int):
    """
    Telegram: reply_markup может быть или inline, или reply keyboard — не оба сразу.
    Поэтому:
      1) Сообщение с INLINE
      2) Пустышка с нижней клавой
    """
    api.send_message(chat_id, text, reply_markup=inline_kb, max_text_len=max_len)
    api.send_message(chat_id, " ", reply_markup=bottom_kb, max_text_len=max_len)


# =========================
# BotHandlers
# =========================
class BotHandlers:
    def __init__(self, api, ai_engine, settings, log):
        self.api = api
        self.ai = ai_engine
        self.s = settings
        self.log = log

    # =========================
    # Bottom buttons router
    # =========================
    def _handle_bottom_buttons(self, chat_id: int, t: str) -> bool:
        """
        Обрабатывает текст от ReplyKeyboard (нижние кнопки).
        Возвращает True если обработали и дальше идти не надо.
        """
        p = ensure_profile(chat_id)
        low = (t or "").strip().lower()

        # ===== root =====
        if low in ("🏠 меню", "меню"):
            p["page"] = "main"
            ensure_daily(chat_id)
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                menu_main(chat_id, self.ai.enabled),
                kb_root(),
                self.s.MAX_TEXT_LEN
            )
            return True

        if low == "👤 профиль":
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                profile_text(chat_id),
                menu_main(chat_id, self.ai.enabled),
                _bottom_kb_for_page(p.get("page", "main")),
                self.s.MAX_TEXT_LEN
            )
            return True

        if low == "⚙️ настройки":
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                "⚙️ Настройки:",
                menu_settings(chat_id),
                _bottom_kb_for_page(p.get("page", "main")),
                self.s.MAX_TEXT_LEN
            )
            return True

        if low == "🧟 zombies":
            p["page"] = "zombies"
            save_state(self.s.STATE_PATH, self.log)
            z = zombies_router.handle_callback("zmb:home")
            _send_inline_with_bottom(
                self.api, chat_id,
                z["text"],
                z.get("reply_markup"),
                kb_root(),
                self.s.MAX_TEXT_LEN
            )
            return True

        # ===== enter games =====
        if low == "🎮 warzone":
            p["page"] = "wz"
            p["game"] = "warzone"
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                "🎮 Warzone — выбирай разделы снизу 👇",
                menu_main(chat_id, self.ai.enabled),
                kb_warzone(),
                self.s.MAX_TEXT_LEN
            )
            return True

        if low == "🎮 bo7":
            p["page"] = "bo7"
            p["game"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                "🎮 BO7 — выбирай разделы снизу 👇",
                menu_main(chat_id, self.ai.enabled),
                kb_bo7(),
                self.s.MAX_TEXT_LEN
            )
            return True

        if low == "🎮 bf6":
            p["page"] = "bf6"
            p["game"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                "🎮 BF6 — choose sections below 👇",
                menu_main(chat_id, self.ai.enabled),
                kb_bf6(),
                self.s.MAX_TEXT_LEN
            )
            return True

        # ===== back =====
        if low in ("⬅️ назад", "назад"):
            p["page"] = "main"
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(
                self.api, chat_id,
                main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                menu_main(chat_id, self.ai.enabled),
                kb_root(),
                self.s.MAX_TEXT_LEN
            )
            return True

        # =========================
        # WARZONE module buttons
        # =========================
        if low == "⚙️ настройки wz":
            p["page"] = "wz"
            p["game"] = "warzone"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "⚙️ Warzone — выбери устройство:", reply_markup=menu_wz_device(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🔥 pro-настройки wz":
            p["page"] = "wz"
            p["game"] = "warzone"
            save_state(self.s.STATE_PATH, self.log)
            dev = p.get("wz_device", "pad")
            tier = p.get("wz_tier", "normal")
            txt = pro_get_text(f"wz:{dev}:{tier}")
            _send_inline_with_bottom(self.api, chat_id, txt, menu_main(chat_id, self.ai.enabled), kb_warzone(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎬 vod wz":
            p["page"] = "wz"
            save_state(self.s.STATE_PATH, self.log)
            _send_inline_with_bottom(self.api, chat_id, GAME_KB["warzone"]["vod"], menu_more(chat_id), kb_warzone(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎯 тренировка wz":
            p["page"] = "wz"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "💪 Тренировка:", reply_markup=menu_training(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 устройство wz":
            p["page"] = "wz"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "Warzone: выбери устройство 👇", reply_markup=kb_device_pick_ru("wz"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "👑 уровень wz":
            p["page"] = "wz"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "Warzone: выбери уровень пресета 👇", reply_markup=kb_tier_pick_ru("wz"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🎮 ps5/xbox (wz)":
            p["wz_device"] = "pad"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ Warzone device = Controller", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 pc mnk (wz)":
            p["wz_device"] = "mnk"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ Warzone device = MnK", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🙂 normal (wz)":
            p["wz_tier"] = "normal"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ Warzone tier = Normal", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "😈 demon (wz)":
            p["wz_tier"] = "demon"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ Warzone tier = Demon", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🧠 pro (wz)":
            p["wz_tier"] = "pro"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ Warzone tier = Pro", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        # =========================
        # BO7 module buttons
        # =========================
        if low == "⚙️ настройки bo7":
            p["page"] = "bo7"
            p["game"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "⚙️ BO7 — выбери устройство:", reply_markup=menu_bo7_device(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🔥 pro-настройки bo7":
            p["page"] = "bo7"
            p["game"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            dev = p.get("bo7_device", "pad")
            tier = p.get("bo7_tier", "normal")
            txt = pro_get_text(f"bo7:{dev}:{tier}")
            _send_inline_with_bottom(self.api, chat_id, txt, menu_main(chat_id, self.ai.enabled), kb_bo7(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎬 vod bo7":
            p["page"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            txt = GAME_KB["bo7"]["vod"] if "bo7" in GAME_KB else "BO7: VOD будет расширяться."
            _send_inline_with_bottom(self.api, chat_id, txt, menu_more(chat_id), kb_bo7(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎯 тренировка bo7":
            p["page"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "💪 Тренировка:", reply_markup=menu_training(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 устройство bo7":
            p["page"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "BO7: выбери устройство 👇", reply_markup=kb_device_pick_ru("bo7"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "👑 уровень bo7":
            p["page"] = "bo7"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "BO7: выбери уровень пресета 👇", reply_markup=kb_tier_pick_ru("bo7"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🎮 ps5/xbox (bo7)":
            p["bo7_device"] = "pad"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BO7 device = Controller", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 pc mnk (bo7)":
            p["bo7_device"] = "mnk"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BO7 device = MnK", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🙂 normal (bo7)":
            p["bo7_tier"] = "normal"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BO7 tier = Normal", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "😈 demon (bo7)":
            p["bo7_tier"] = "demon"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BO7 tier = Demon", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🧠 pro (bo7)":
            p["bo7_tier"] = "pro"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BO7 tier = Pro", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        # =========================
        # BF6 module buttons
        # =========================
        if low == "⚙️ settings bf6":
            p["page"] = "bf6"
            p["game"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "⚙️ BF6 — choose device:", reply_markup=menu_bf6_device(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🔥 pro settings bf6":
            p["page"] = "bf6"
            p["game"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            dev = p.get("bf6_device", "pad")
            tier = p.get("bf6_tier", "normal")
            txt = pro_get_text(f"bf6:{dev}:{tier}")
            _send_inline_with_bottom(self.api, chat_id, txt, menu_main(chat_id, self.ai.enabled), kb_bf6(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎬 vod bf6":
            p["page"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            txt = GAME_KB["bf6"]["vod"] if "bf6" in GAME_KB else "BF6: VOD будет расширяться."
            _send_inline_with_bottom(self.api, chat_id, txt, menu_more(chat_id), kb_bf6(), self.s.MAX_TEXT_LEN)
            return True

        if low == "🎯 training bf6":
            p["page"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "💪 Training:", reply_markup=menu_training(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
            self.api.send_message(chat_id, " ", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 device bf6":
            p["page"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "BF6: choose device 👇", reply_markup=kb_device_pick_ru("bf6"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "👑 tier bf6":
            p["page"] = "bf6"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "BF6: choose tier 👇", reply_markup=kb_tier_pick_ru("bf6"), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🎮 ps5/xbox (bf6)":
            p["bf6_device"] = "pad"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BF6 device = Controller", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🖥 pc mnk (bf6)":
            p["bf6_device"] = "mnk"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BF6 device = MnK", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🙂 normal (bf6)":
            p["bf6_tier"] = "normal"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BF6 tier = Normal", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "😈 demon (bf6)":
            p["bf6_tier"] = "demon"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BF6 tier = Demon", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        if low == "🧠 pro (bf6)":
            p["bf6_tier"] = "pro"
            save_state(self.s.STATE_PATH, self.log)
            self.api.send_message(chat_id, "✅ BF6 tier = Pro", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)
            return True

        return False

    # =========================
    # handle_message
    # =========================
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

            # ✅ 1) нижние кнопки
            if self._handle_bottom_buttons(chat_id, t):
                return

            # ✅ 2) Zombies: если мы в меню Zombies — любой текст = поиск по карте
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    _send_inline_with_bottom(self.api, chat_id, z["text"], z.get("reply_markup"), kb_root(), self.s.MAX_TEXT_LEN)
                    return

            # ✅ 3) Команды (как было) + нижняя панель
            if t.startswith("/start") or t.startswith("/menu"):
                p["page"] = "main"
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                _send_inline_with_bottom(
                    self.api, chat_id,
                    main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                    menu_main(chat_id, self.ai.enabled),
                    kb_root(),
                    self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/help"):
                _send_inline_with_bottom(self.api, chat_id, help_text(), menu_main(chat_id, self.ai.enabled), _bottom_kb_for_page(p.get("page", "main")), self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/status"):
                _send_inline_with_bottom(
                    self.api, chat_id,
                    status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                    menu_main(chat_id, self.ai.enabled),
                    _bottom_kb_for_page(p.get("page", "main")),
                    self.s.MAX_TEXT_LEN
                )
                return

            if t.startswith("/profile"):
                _send_inline_with_bottom(self.api, chat_id, profile_text(chat_id), menu_main(chat_id, self.ai.enabled), _bottom_kb_for_page(p.get("page", "main")), self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/daily"):
                d = ensure_daily(chat_id)
                _send_inline_with_bottom(self.api, chat_id, "🎯 Задание дня:\n• " + d["text"], menu_daily(chat_id), _bottom_kb_for_page(p.get("page", "main")), self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/zombies"):
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                _send_inline_with_bottom(self.api, chat_id, z["text"], z.get("reply_markup"), kb_root(), self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/reset"):
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                _send_inline_with_bottom(self.api, chat_id, "🧨 Сброс выполнен.", menu_main(chat_id, self.ai.enabled), kb_root(), self.s.MAX_TEXT_LEN)
                return

            # ✅ 4) обычный диалог AI (как было)
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

            # ✅ после ответа — снова нижняя панель
            self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

        finally:
            lock.release()

    # =========================
    # handle_callback (INLINE) — твой старый функционал
    # =========================
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
                self.api.send_message(chat_id, " ", reply_markup=kb_root(), max_text_len=self.s.MAX_TEXT_LEN)
                return

            # ============= NAV / MENUS =============
            if data == "nav:main":
                p["page"] = "main"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=kb_root(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:more":
                self.api.edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=menu_more(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:game":
                self.api.edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_root(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:persona":
                self.api.edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:talk":
                self.api.edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:training":
                self.api.edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:settings":
                self.api.edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:settings_game":
                self.api.edit_message(chat_id, message_id, "🎮 Настройки игр:", reply_markup=menu_settings_game(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:wz_settings":
                p["page"] = "wz"
                p["game"] = "warzone"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "⚙️ Warzone — выбери устройство:", reply_markup=menu_wz_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:bo7_settings":
                p["page"] = "bo7"
                p["game"] = "bo7"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "⚙️ BO7 — выбери устройство:", reply_markup=menu_bo7_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "nav:bf6_settings":
                p["page"] = "bf6"
                p["game"] = "bf6"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "⚙️ BF6 — choose device:", reply_markup=menu_bf6_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("wzdev:"):
                dev = data.split(":", 1)[1]
                p["page"] = "wz"
                p["game"] = "warzone"
                p["wz_device"] = "pad" if dev == "pad" else "mnk"
                save_state(self.s.STATE_PATH, self.log)
                tier = p.get("wz_tier", "normal")
                self.api.edit_message(chat_id, message_id, pro_get_text(f"wz:{p['wz_device']}:{tier}"), reply_markup=menu_wz_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_warzone(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("bo7dev:"):
                dev = data.split(":", 1)[1]
                p["page"] = "bo7"
                p["game"] = "bo7"
                p["bo7_device"] = "pad" if dev == "pad" else "mnk"
                save_state(self.s.STATE_PATH, self.log)
                tier = p.get("bo7_tier", "normal")
                self.api.edit_message(chat_id, message_id, pro_get_text(f"bo7:{p['bo7_device']}:{tier}"), reply_markup=menu_bo7_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_bo7(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("bf6dev:"):
                dev = data.split(":", 1)[1]
                p["page"] = "bf6"
                p["game"] = "bf6"
                p["bf6_device"] = "pad" if dev == "pad" else "mnk"
                save_state(self.s.STATE_PATH, self.log)
                tier = p.get("bf6_tier", "normal")
                self.api.edit_message(chat_id, message_id, pro_get_text(f"bf6:{p['bf6_device']}:{tier}"), reply_markup=menu_bf6_device(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_bf6(), max_text_len=self.s.MAX_TEXT_LEN)

            # ============= TOGGLES =============
            elif data == "toggle:memory":
                p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
                if p["memory"] == "off":
                    clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "toggle:mode":
                p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "toggle:ui":
                p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "toggle:lightning":
                p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            # ============= SETTERS =============
            elif data.startswith("set:game:"):
                g = data.split(":", 2)[2]
                if g in ("auto", "warzone", "bf6", "bo7"):
                    p["game"] = g
                    if g == "warzone":
                        p["page"] = "wz"
                    elif g == "bf6":
                        p["page"] = "bf6"
                    elif g == "bo7":
                        p["page"] = "bo7"
                    else:
                        p["page"] = "main"
                    save_state(self.s.STATE_PATH, self.log)

                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("set:persona:"):
                v = data.split(":", 2)[2]
                if v in ("spicy", "chill", "pro"):
                    p["persona"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("set:talk:"):
                v = data.split(":", 2)[2]
                if v in ("short", "normal", "talkative"):
                    p["verbosity"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            # ============= ACTIONS =============
            elif data == "action:status":
                self.api.edit_message(chat_id, message_id,
                                      status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                                      reply_markup=menu_settings(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:profile":
                self.api.edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_more(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:ai_status":
                ai = "ON" if self.ai.enabled else "OFF"
                self.api.edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {self.s.OPENAI_MODEL}",
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:clear_memory":
                clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_more(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:reset_all":
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=menu_more(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=kb_root(), max_text_len=self.s.MAX_TEXT_LEN)

            elif data.startswith("action:drill:"):
                kind = data.split(":", 2)[2]
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
                self.api.edit_message(chat_id, message_id, txt, reply_markup=menu_training(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:vod":
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                self.api.edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=menu_more(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "action:daily":
                d = ensure_daily(chat_id)
                self.api.edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "daily:done":
                d = ensure_daily(chat_id)
                d["done"] = int(d.get("done", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"✅ Засчитал.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            elif data == "daily:fail":
                d = ensure_daily(chat_id)
                d["fail"] = int(d.get("fail", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"❌ Ок.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

            else:
                self.api.edit_message(chat_id, message_id,
                                      main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                                      reply_markup=menu_main(chat_id, self.ai.enabled))
                self.api.send_message(chat_id, " ", reply_markup=_bottom_kb_for_page(p.get("page", "main")), max_text_len=self.s.MAX_TEXT_LEN)

        finally:
            self.api.answer_callback(cb_id)
