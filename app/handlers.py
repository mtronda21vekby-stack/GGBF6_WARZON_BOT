# -*- coding: utf-8 -*-
"""
SAFE BOOT HANDLERS
Цель: гарантированный старт бота без TypeError
Логика будет расширена на следующем шаге
"""

from typing import Any


class BotHandlers:
    def __init__(
        self,
        api,
        ai_engine=None,
        state=None,
        ui=None,
        metrics=None,
        **kwargs
    ):
        self.api = api
        self.ai = ai_engine
        self.state = state
        self.ui = ui
        self.metrics = metrics

    # ===== SAFE FALLBACK HANDLERS =====

    def on_message(self, update: dict) -> None:
        try:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"].get("text", "")
            self.api.send_message(
                chat_id,
                "🧠 Бот запущен.\n"
                "Brain v3 загружается...\n\n"
                "Следующий шаг — активация логики."
            )
        except Exception:
            pass

    def on_callback(self, update: dict) -> None:
        try:
            cb = update.get("callback_query", {})
            cid = cb.get("id")
            if cid:
                self.api.answer_callback(cid)
        except Exception:
            pass

    def handle_update(self, update: dict) -> None:
        if "message" in update:
            self.on_message(update)
        elif "callback_query" in update:
            self.on_callback(update)
