# -*- coding: utf-8 -*-
from app.state import ensure_profile, USER_MEMORY
from app.ui import (
    main_text,
    profile_text,
    status_text,
    help_text,
    menu_main,
    menu_more,
    menu_settings,
    menu_game,
    menu_persona,
    menu_talk,
)
from app.brain_v3 import brain_reply


class BotHandlers:
    def __init__(self, api, ai_engine, log, data_dir):
        self.api = api
        self.ai = ai_engine
        self.log = log
        self.data_dir = data_dir

    # ==========
    # TEXT
    # ==========
    def on_text(self, chat_id: int, text: str):
        p = ensure_profile(chat_id)

        # команды
        if text in ("/start", "/menu"):
            self.api.send_message(
                chat_id,
                main_text(chat_id, self.ai.enabled, self.ai.model),
                reply_markup=menu_main(chat_id, self.ai.enabled),
            )
            return

        if text == "/help":
            self.api.send_message(chat_id, help_text())
            return

        # основной brain v3
        reply = brain_reply(
            chat_id=chat_id,
            user_text=text,
            ai_engine=self.ai,
        )

        self.api.send_message(chat_id, reply)

    # ==========
    # CALLBACKS (КНОПКИ)
    # ==========
    def on_callback(self, chat_id: int, data: str):
        p = ensure_profile(chat_id)

        # ---- NAV ----
        if data == "nav:main":
            self.api.edit_message(
                chat_id,
                main_text(chat_id, self.ai.enabled, self.ai.model),
                reply_markup=menu_main(chat_id, self.ai.enabled),
            )
            return

        if data == "nav:more":
            self.api.edit_message(chat_id, "📦 Ещё", reply_markup=menu_more(chat_id))
            return

        if data == "nav:settings":
            self.api.edit_message(chat_id, "⚙️ Настройки", reply_markup=menu_settings(chat_id))
            return

        if data == "nav:game":
            self.api.edit_message(chat_id, "🎮 Выбери игру", reply_markup=menu_game(chat_id))
            return

        if data == "nav:persona":
            self.api.edit_message(chat_id, "🎭 Выбери стиль", reply_markup=menu_persona(chat_id))
            return

        if data == "nav:talk":
            self.api.edit_message(chat_id, "🗣 Длина ответа", reply_markup=menu_talk(chat_id))
            return

        # ---- SET ----
        if data.startswith("set:game:"):
            p["game"] = data.split(":")[-1]
            self.api.edit_message(
                chat_id,
                f"🎮 Игра установлена: {p['game']}",
                reply_markup=menu_main(chat_id, self.ai.enabled),
            )
            return

        if data.startswith("set:persona:"):
            p["persona"] = data.split(":")[-1]
            self.api.edit_message(
                chat_id,
                f"🎭 Стиль: {p['persona']}",
                reply_markup=menu_main(chat_id, self.ai.enabled),
            )
            return

        if data.startswith("set:talk:"):
            p["verbosity"] = data.split(":")[-1]
            self.api.edit_message(
                chat_id,
                f"🗣 Ответ: {p['verbosity']}",
                reply_markup=menu_main(chat_id, self.ai.enabled),
            )
            return

        # ---- ACTIONS ----
        if data == "action:profile":
            self.api.send_message(chat_id, profile_text(chat_id))
            return

        if data == "action:status":
            self.api.send_message(
                chat_id,
                status_text(self.ai.model, self.data_dir, self.ai.enabled),
            )
            return

        if data == "action:clear_memory":
            USER_MEMORY.pop(chat_id, None)
            self.api.send_message(chat_id, "🧽 Память очищена")
            return

        if data == "action:reset_all":
            USER_MEMORY.pop(chat_id, None)
            p.clear()
            self.api.send_message(chat_id, "🧨 Всё сброшено. Начинаем заново.")
            return

        # fallback
        self.api.send_message(chat_id, "⚠️ Неизвестное действие")