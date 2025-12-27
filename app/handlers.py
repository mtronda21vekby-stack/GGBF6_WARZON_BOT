# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional

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
    """
    ReplyKeyboard-only UI.
    Все кнопки снизу приходят как обычный текст — мы маппим их в команды.
    """
    def __init__(self, *, api, ai_engine, config, log):
        self.api = api
        self.ai = ai_engine
        self.cfg = config
        self.log = log

    def _send(self, chat_id: int, text: str) -> None:
        self.api.send_message(chat_id, text, reply_markup=premium_reply_kb())

    def handle_update(self, upd: Dict[str, Any]) -> None:
        # message
        msg = upd.get("message") or upd.get("edited_message")
        if msg:
            self._handle_message(msg)
            return

        # callback_query (если где-то остались inline — просто "съедим", чтобы не падать)
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

        # кнопки снизу -> команда
        if text in BTN_TO_CMD:
            text = BTN_TO_CMD[text]

        if text.startswith("/start"):
            self._cmd_start(chat_id)
            return
        if text.startswith("/menu"):
            self._cmd_menu(chat_id)
            return
        if text.startswith("/help"):
            self._send(chat_id, help_text())
            return
        if text.startswith("/status"):
            self._send(chat_id, status_text(self.cfg.OPENAI_MODEL, self.cfg.DATA_DIR, self.ai.enabled))
            return
        if text.startswith("/profile"):
            p = ensure_profile(chat_id)
            self._send(chat_id, profile_text(p))
            return
        if text.startswith("/clear_memory"):
            clear_memory(chat_id)
            self._send(chat_id, "🧽 Память очищена.")
            return
        if text.startswith("/reset"):
            # мягкий reset профиля (не трогаем файл состояния целиком)
            p = ensure_profile(chat_id)
            p["game"] = "auto"
            p["persona"] = "spicy"
            p["verbosity"] = "normal"
            p["memory"] = "on"
            p["ui"] = "show"
            p["mode"] = "chat"
            p["speed"] = "normal"
            clear_memory(chat_id)
            self._send(chat_id, "🧨 Сброс выполнен. Вернул базовые настройки.")
            return

        # меню-настройки (без inline: просто циклим по вариантам)
        if text.startswith("/settings"):
            self._send(chat_id, "⚙️ Настройки:\n• /game\n• /persona\n• /verbosity\n• /mode\n• /memory\n• /speed")
            return

        if text.startswith("/game"):
            self._cycle_game(chat_id)
            return
        if text.startswith("/persona"):
            self._cycle_persona(chat_id)
            return
        if text.startswith("/verbosity"):
            self._cycle_verbosity(chat_id)
            return
        if text.startswith("/mode"):
            self._toggle_mode(chat_id)
            return
        if text.startswith("/memory"):
            self._toggle_memory(chat_id)
            return
        if text.startswith("/speed"):
            self._toggle_speed(chat_id)
            return

        # zombies/vod/daily — пока как “точки входа”, потом нарастим жиром
        if text.startswith("/zombies"):
            self._send(chat_id, "🧟 Zombies: режим подключен. Напиши карту/волну/цель — и начнём.")
            return
        if text.startswith("/vod"):
            self._send(chat_id, "🎬 VOD: опиши момент (карта/позиция/дистанция/кто первый увидел) — разберу.")
            return
        if text.startswith("/daily"):
            self._send(chat_id, "🎯 Задание дня: напиши 'сделал' или 'не вышло' и что мешало.")
            return

        # обычный чат -> Brain
        p = ensure_profile(chat_id)
        update_memory(chat_id, "user", text, memory_max_turns=self.cfg.MEMORY_MAX_TURNS)

        out = self.ai.reply(chat_id, text)

        update_memory(chat_id, "assistant", out, memory_max_turns=self.cfg.MEMORY_MAX_TURNS)
        p["last_question"] = text
        p["last_answer"] = out

        self._send(chat_id, out)

    def _cmd_start(self, chat_id: int) -> None:
        ensure_profile(chat_id)
        self._send(chat_id, "🧠 Brain v3: ONLINE\n\n" + main_text(ensure_profile(chat_id), self.ai.enabled, self.cfg.OPENAI_MODEL))

    def _cmd_menu(self, chat_id: int) -> None:
        self._send(chat_id, main_text(ensure_profile(chat_id), self.ai.enabled, self.cfg.OPENAI_MODEL))

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

    def _toggle_speed(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        p["speed"] = "lightning" if p.get("speed", "normal") == "normal" else "normal"
        self._send(chat_id, f"⚡ Скорость: {p['speed']}")