# -*- coding: utf-8 -*-
from typing import Dict, Any

from app.state import ensure_profile, update_memory, clear_memory
from app.ui.reply import premium_reply_kb
from app.ui.texts import main_text, help_text, status_text, profile_text

BTN_TO_CMD = {
    "📋 Меню": "/menu",
    "⚙️ Настройки": "/settings",
    "🎮 Игра": "/game",
    "🎭 Стиль": "/persona",
    "🗣 Ответ": "/verbosity",
    "🧟 Zombies": "/zombies",
    "🎯 Задание дня": "/daily",
    "🎬 VOD": "/vod",
    "👤 Профиль": "/profile",
    "📡 Статус": "/status",
    "🆘 Помощь": "/help",
    "🧽 Очистить память": "/clear_memory",
    "🧨 Сброс": "/reset",
}

class BotHandlers:
    def __init__(self, *, api, brain, config, log):
        self.api = api
        self.brain = brain
        self.cfg = config
        self.log = log

    def _send(self, chat_id: int, text: str) -> None:
        self.api.send_message(chat_id, text, reply_markup=premium_reply_kb())

    def handle_update(self, upd: Dict[str, Any]) -> None:
        msg = upd.get("message") or upd.get("edited_message")
        if msg:
            self._handle_message(msg)
            return

        cb = upd.get("callback_query")
        if cb:
            cid = cb.get("id")
            if cid:
                try:
                    self.api.answer_callback(cid)
                except Exception:
                    pass

    def _handle_message(self, msg: Dict[str, Any]) -> None:
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return

        text = (msg.get("text") or "").strip()
        if not text:
            return

        # кнопки -> команда
        if text in BTN_TO_CMD:
            text = BTN_TO_CMD[text]

        if text.startswith("/start"):
            p = ensure_profile(chat_id)
            self._send(chat_id, "🧠 Brain v3: ONLINE\n\n" + main_text(p, self.brain.ai.enabled, self.cfg.OPENAI_MODEL))
            return

        if text.startswith("/menu"):
            p = ensure_profile(chat_id)
            self._send(chat_id, main_text(p, self.brain.ai.enabled, self.cfg.OPENAI_MODEL))
            return

        if text.startswith("/help"):
            self._send(chat_id, help_text())
            return

        if text.startswith("/status"):
            self._send(chat_id, status_text(self.cfg.OPENAI_MODEL, self.cfg.DATA_DIR, self.brain.ai.enabled))
            return

        if text.startswith("/profile"):
            self._send(chat_id, profile_text(ensure_profile(chat_id)))
            return

        if text.startswith("/clear_memory"):
            clear_memory(chat_id)
            self._send(chat_id, "🧽 Память очищена.")
            return

        if text.startswith("/reset"):
            p = ensure_profile(chat_id)
            p["game"] = "auto"
            p["persona"] = "spicy"
            p["verbosity"] = "normal"
            p["memory"] = "on"
            p["mode"] = "chat"
            p["player_level"] = "demon"
            clear_memory(chat_id)
            self._send(chat_id, "🧨 Сброс выполнен. Вернул базовые настройки.")
            return

        if text.startswith("/settings"):
            self._send(chat_id, "⚙️ Настройки:\n• /game\n• /persona\n• /verbosity\n• /mode\n• /memory\n• /level")
            return

        if text.startswith("/game"):
            self._cycle(chat_id, "game", ["auto","warzone","bf6","bo7"], "🎮 Игра")
            return

        if text.startswith("/persona"):
            self._cycle(chat_id, "persona", ["spicy","chill","pro"], "🎭 Стиль")
            return

        if text.startswith("/verbosity"):
            self._cycle(chat_id, "verbosity", ["short","normal","talkative"], "🗣 Ответ")
            return

        if text.startswith("/mode"):
            p = ensure_profile(chat_id)
            p["mode"] = "coach" if p.get("mode","chat") == "chat" else "chat"
            self._send(chat_id, f"🔁 Режим: {p['mode'].upper()}")
            return

        if text.startswith("/memory"):
            p = ensure_profile(chat_id)
            p["memory"] = "off" if p.get("memory","on") == "on" else "on"
            self._send(chat_id, f"🧠 Память: {p['memory']}")
            return

        if text.startswith("/level"):
            self._cycle(chat_id, "player_level", ["normal","pro","demon"], "😈 Уровень")
            return

        if text.startswith("/zombies"):
            self._send(chat_id, "🧟 Zombies: режим подключен. Напиши карту/волну/цель — и начнём.")
            return

        if text.startswith("/vod"):
            self._send(chat_id, "🎬 VOD: опиши момент (карта/позиция/дистанция/кто первый увидел) — разберу.")
            return

        if text.startswith("/daily"):
            self._send(chat_id, "🎯 Задание дня: напиши цель на сегодня (10 минут дрилла) — составлю план.")
            return

        # обычный текст -> Brain
        p = ensure_profile(chat_id)
        update_memory(chat_id, "user", text, max_turns=self.cfg.MEMORY_MAX_TURNS)

        out = self.brain.reply(chat_id, text)

        update_memory(chat_id, "assistant", out, max_turns=self.cfg.MEMORY_MAX_TURNS)
        p["last_question"] = text
        p["last_answer"] = out

        self._send(chat_id, out)

    def _cycle(self, chat_id: int, key: str, order, title: str) -> None:
        p = ensure_profile(chat_id)
        cur = p.get(key, order[0])
        nxt = order[(order.index(cur)+1) % len(order)] if cur in order else order[0]
        p[key] = nxt
        self._send(chat_id, f"{title}: {nxt} (переключил)")