# -*- coding: utf-8 -*-
"""
SAFE BOOT HANDLERS v2
Цель: гарантированный старт при ЛЮБОМ runner.py
"""

class BotHandlers:
    def __init__(self, *args, **kwargs):
        """
        runner.py может передавать:
        - api
        - ai_engine
        - state
        - ui
        - metrics
        - config
        - log
        и ещё что угодно

        Мы принимаем ВСЁ без падений
        """

        # --- безопасное извлечение ---
        self.api = kwargs.get("api") or (args[0] if len(args) > 0 else None)
        self.ai = kwargs.get("ai_engine")
        self.state = kwargs.get("state")
        self.ui = kwargs.get("ui")
        self.metrics = kwargs.get("metrics")
        self.log = kwargs.get("log")

        if self.log:
            self.log.info("BotHandlers SAFE INIT OK")

    # ============================
    # SAFE HANDLERS
    # ============================

    def handle_update(self, update: dict) -> None:
        try:
            if "message" in update:
                self._on_message(update["message"])
            elif "callback_query" in update:
                self._on_callback(update["callback_query"])
        except Exception as e:
            if self.log:
                self.log.error("handle_update error: %r", e)

    def _on_message(self, message: dict) -> None:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if not self.api:
            return

        self.api.send_message(
            chat_id,
            "🧠 FPS Coach Bot запущен\n\n"
            "Brain v3: LOADING...\n"
            "UI Premium: NEXT STEP\n\n"
            "Бот жив. Двигаемся дальше."
        )

    def _on_callback(self, cb: dict) -> None:
        cid = cb.get("id")
        if cid and self.api:
            try:
                self.api.answer_callback(cid)
            except Exception:
                pass
