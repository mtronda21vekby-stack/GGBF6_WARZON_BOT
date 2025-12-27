# -*- coding: utf-8 -*-
from app.state import ensure_profile, clear_memory
from app.ui import (
    reply_keyboard, menu_text, settings_text, profile_text,
    BTN_MENU, BTN_SETTINGS, BTN_GAME, BTN_STYLE, BTN_VERB, BTN_ZOMBIES,
    BTN_DAILY, BTN_VOD, BTN_PROFILE, BTN_STATUS, BTN_HELP, BTN_CLEAR, BTN_RESET
)
from app.brain_v3 import brain_reply

HELP = (
    "🆘 Помощь\n"
    "/start — показать меню\n"
    "Кнопки снизу — основной UI.\n"
    "Пиши обычным текстом смерть/ситуацию — мозг разберёт."
)

class BotHandlers:
    def __init__(self, api, ai_engine, log, data_dir):
        self.api = api
        self.ai = ai_engine
        self.log = log
        self.data_dir = data_dir

    def start(self, chat_id: int):
        self.api.send_message(
            chat_id,
            menu_text(chat_id, self.ai.enabled, self.ai.model),
            reply_markup=reply_keyboard(),
        )

    def on_text(self, chat_id: int, text: str):
        text = (text or "").strip()
        p = ensure_profile(chat_id)

        if text in ("/start", "/menu", BTN_MENU):
            return self.start(chat_id)

        if text in (BTN_SETTINGS,):
            return self.api.send_message(chat_id, settings_text(chat_id), reply_markup=reply_keyboard())

        if text in (BTN_PROFILE,):
            return self.api.send_message(chat_id, profile_text(chat_id), reply_markup=reply_keyboard())

        if text in (BTN_STATUS,):
            return self.api.send_message(
                chat_id,
                f"📡 Статус\nAI={'ON' if self.ai.enabled else 'OFF'}\nModel={self.ai.model}\nDATA_DIR={self.data_dir}",
                reply_markup=reply_keyboard(),
            )

        if text in (BTN_HELP, "/help"):
            return self.api.send_message(chat_id, HELP, reply_markup=reply_keyboard())

        if text == BTN_CLEAR:
            clear_memory(chat_id)
            return self.api.send_message(chat_id, "🧽 Память очищена", reply_markup=reply_keyboard())

        if text == BTN_RESET:
            clear_memory(chat_id)
            p.clear()
            ensure_profile(chat_id)
            return self.api.send_message(chat_id, "🧨 Сброс выполнен. /start", reply_markup=reply_keyboard())

        # быстрые циклы выбора (без inline)
        if text == BTN_GAME:
            return self.api.send_message(chat_id, "🎮 Напиши: AUTO / WARZONE / BF6 / BO7", reply_markup=reply_keyboard())

        if text == BTN_STYLE:
            return self.api.send_message(chat_id, "🎭 Напиши: SPICY / CHILL / PRO", reply_markup=reply_keyboard())

        if text == BTN_VERB:
            return self.api.send_message(chat_id, "🗣 Напиши: SHORT / NORMAL / TALKATIVE", reply_markup=reply_keyboard())

        t = text.upper()
        if t in ("AUTO", "WARZONE", "BF6", "BO7"):
            p["game"] = t.lower()
            return self.api.send_message(chat_id, f"✅ Игра: {p['game']}", reply_markup=reply_keyboard())

        if t in ("SPICY", "CHILL", "PRO"):
            p["persona"] = t.lower()
            return self.api.send_message(chat_id, f"✅ Стиль: {p['persona']}", reply_markup=reply_keyboard())

        if t in ("SHORT", "NORMAL", "TALKATIVE"):
            p["verbosity"] = t.lower()
            return self.api.send_message(chat_id, f"✅ Ответ: {p['verbosity']}", reply_markup=reply_keyboard())

        # placeholders
        if text in (BTN_ZOMBIES, BTN_DAILY, BTN_VOD):
            return self.api.send_message(chat_id, "✅ Принял. Это подключим следующим шагом (после BF6 классов).", reply_markup=reply_keyboard())

        # основной мозг
        out = brain_reply(chat_id, text, self.ai)
        return self.api.send_message(chat_id, out, reply_markup=reply_keyboard())
