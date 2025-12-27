# -*- coding: utf-8 -*-
import os
import time
from app.config import (
    TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    DATA_DIR, HTTP_TIMEOUT, USER_AGENT, POLL_LIMIT, POLL_TIMEOUT
)
from app.log import get_logger
from app.telegram_api import TelegramAPI
from app.state import load_state, save_state
from app.handlers import BotHandlers

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

class AIEngine:
    def __init__(self, api_key: str, base_url: str, model: str, log):
        self.log = log
        self.model = model
        self.client = None
        if OpenAI and api_key:
            try:
                self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=30, max_retries=0)
                self.log.info("OpenAI: ON, model=%s", model)
            except Exception as e:
                self.log.warning("OpenAI init failed: %r", e)
        else:
            self.log.warning("OpenAI: OFF")

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def chat(self, messages, max_tokens: int = 500) -> str:
        if not self.client:
            return ""
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.3,
                max_completion_tokens=max_tokens,
            )
        except TypeError:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.3,
                max_tokens=max_tokens,
            )
        return (resp.choices[0].message.content or "").strip()

def main():
    log = get_logger("fpsbot")

    os.makedirs(DATA_DIR, exist_ok=True)
    state_path = os.path.join(DATA_DIR, "state.json")

    api = TelegramAPI(TELEGRAM_BOT_TOKEN, HTTP_TIMEOUT, USER_AGENT, log)
    api.delete_webhook_on_start()

    load_state(state_path, log)

    ai = AIEngine(OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, log)
    handlers = BotHandlers(api=api, ai_engine=ai, log=log, data_dir=DATA_DIR)

    offset = 0
    log.info("BOT STARTED (polling). DATA_DIR=%s", DATA_DIR)

    while True:
        try:
            updates = api.get_updates(offset=offset, timeout=POLL_TIMEOUT, limit=POLL_LIMIT)
            for upd in updates:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                if not chat_id:
                    continue
                text = msg.get("text") or ""
                handlers.on_text(int(chat_id), text)

            # сохранение раз в цикл (не тяжело)
            save_state(state_path, log)

        except Exception as e:
            log.error("poll loop error: %r", e)
            time.sleep(2)
