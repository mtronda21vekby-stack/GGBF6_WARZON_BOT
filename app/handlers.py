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
    def __init__(self, *, api, ai_engine, config, log):
        self.api = api
        self.ai = ai_engine
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
            return

    def _handle_message(self, msg: Dict[str, Any]) -> None:
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return

        text = (msg.get("text") or "").strip()
        if not text:
            return

        # ReplyKeyboard кнопки -> команды
        if text in BTN_TO_CMD:
            text = BTN_TO_CMD[text]

        # --- команды ---
        if text.startswith("/start") or text.startswith("/menu"):
            ensure_profile(chat_id)
            self._send(chat_id, main_text(chat_id, self.ai.enabled, self.cfg.OPENAI_MODEL))
            return

        if text.startswith("/help"):
            self._send(chat_id, help_text())
            return

        if text.startswith("/status"):
            self._send(chat_id, status_text(self.cfg.OPENAI_MODEL, self.cfg.DATA_DIR, self.ai.enabled))
            return

        if text.startswith("/profile"):
            self._send(chat_id, profile_text(chat_id))
            return

        if text.startswith("/clear_memory"):
            clear_memory(chat_id)
            self._send(chat_id, "🧽 Память очищена.")
            return

        if text.startswith("/reset"):
            p = ensure_profile(chat_id)
            p.update({
                "game": "auto",
                "persona": "spicy",
                "verbosity": "normal",
                "memory": "on",
                "mode": "chat",
                "player_level": "demon",
            })
            clear_memory(chat_id)
            self._send(chat_id, "🧨 Сброс выполнен. Вернул базовые настройки.")
            return

        if text.startswith("/settings"):
            self._send(chat_id, "⚙️ Настройки:\n• /game\n• /persona\n• /verbosity\n• /mode\n• /memory\n• /level")
            return

        if text.startswith("/game"):
            self._cycle_game(chat_id); return
        if text.startswith("/persona"):
            self._cycle_persona(chat_id); return
        if text.startswith("/verbosity"):
            self._cycle_verbosity(chat_id); return
        if text.startswith("/mode"):
            self._toggle_mode(chat_id); return
        if text.startswith("/memory"):
            self._toggle_memory(chat_id); return
        if text.startswith("/level"):
            self._cycle_level(chat_id); return

        if text.startswith("/zombies"):
            self._send(chat_id, "🧟 Zombies: режим подключен. Напиши карту/волну/цель — и начнём.")
            return

        if text.startswith("/vod"):
            self._send(chat_id, "🎬 VOD: опиши момент (карта/позиция/дистанция/кто первый увидел) — разберу.")
            return

        if text.startswith("/daily"):
            self._send(chat_id, "🎯 Задание дня: напиши 'сделал' или 'не вышло' и что мешало.")
            return

        # --- обычный чат -> AI ---
        p = ensure_profile(chat_id)

        mem_turns = int(getattr(self.cfg, "MEMORY_MAX_TURNS", 10))

        update_memory(chat_id, "user", text, max_turns=mem_turns)

        mode = p.get("mode", "chat")
        if mode == "coach":
            out = self.ai.coach_reply(chat_id, text)
        else:
            out = self.ai.chat_reply(chat_id, text)

        update_memory(chat_id, "assistant", out, max_turns=mem_turns)

        p["last_question"] = text
        p["last_answer"] = out

        self._send(chat_id, out)

    # ---------- helpers ----------
    def _cycle_game(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        order = ["auto", "warzone", "bf6", "bo7"]
        cur = p.get("game", "auto")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "auto"
        p["game"] = nxt
        self._send(chat_id, f"🎮 Игра: {nxt} (переключил)")

    def _cycle_persona(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        order = ["spicy", "chill", "pro"]
        cur = p.get("persona", "spicy")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "spicy"
        p["persona"] = nxt
        self._send(chat_id, f"🎭 Стиль: {nxt} (переключил)")

    def _cycle_verbosity(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        order = ["short", "normal", "talkative"]
        cur = p.get("verbosity", "normal")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "normal"
        p["verbosity"] = nxt
        self._send(chat_id, f"🗣 Ответ: {nxt} (переключил)")

    def _toggle_mode(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
        self._send(chat_id, f"🔁 Режим: {p['mode'].upper()}")

    def _toggle_memory(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
        self._send(chat_id, f"🧠 Память: {p['memory']}")

    def _cycle_level(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        order = ["normal", "pro", "demon"]
        cur = p.get("player_level", "demon")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "demon"
        p["player_level"] = nxt
        self._send(chat_id, f"😈 Уровень игрока: {nxt} (переключил)")
