# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, answer_callback, edit_reply_markup
from app.state import ensure_profile, clear_memory
from app.ui import main_menu_markup, more_menu_markup
from zombies.router import handle_zombies


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()
    if not text:
        return

    if text.lower() in ("/start", "start"):
        ensure_profile(chat_id)
        send_message(
            chat_id,
            "Что умеет этот бот?\n\n"
            "Я коуч-тиммейт: общаюсь с тобой и помогаю перестать сыпаться.\n\n"
            "👉 Опиши одну смерть или жми меню 👇",
            reply_markup=main_menu_markup(chat_id)
        )
        return

    # быстрый вход в zombies
    if text.lower() in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # обычный чат-ответ (оставляем как было у тебя)
    send_message(
        chat_id,
        "Ок. Напиши: где умер / что бесит / что хочешь улучшить.\nИли жми меню 👇",
        reply_markup=main_menu_markup(chat_id)
    )


def _toggle(p: dict, key: str, on_val="on", off_val="off"):
    p[key] = off_val if p.get(key, off_val) == on_val else on_val


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not chat_id:
        answer_callback(cb_id)
        return

    p = ensure_profile(chat_id)

    try:
        # --- UI переключение экранов ---
        if data == "ui:more":
            p["page"] = "more"
            if message_id:
                edit_reply_markup(chat_id, message_id, more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data == "ui:back":
            p["page"] = "main"
            if message_id:
                edit_reply_markup(chat_id, message_id, main_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        # --- Zombies ---
        if data.startswith("zombies:"):
            handle_zombies(chat_id, callback=data, message_id=message_id)
            answer_callback(cb_id)
            return

        # --- Тумблеры ---
        if data == "toggle:memory":
            _toggle(p, "memory", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id, main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data == "toggle:ai":
            _toggle(p, "ai", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id, main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data == "toggle:lightning":
            _toggle(p, "lightning", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id, main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        # --- “Ещё” кнопки ---
        if data == "more:clear_memory":
            clear_memory(chat_id)
            if message_id:
                edit_reply_markup(chat_id, message_id, more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data in ("more:training", "more:profile", "more:settings", "more:daily", "more:reset_all"):
            # Здесь можешь подключить твою старую умную логику/экраны.
            # Пока просто подтверждаем и не ломаем работу.
            answer_callback(cb_id)
            return

        # Заглушки для set:* (чтобы не падало, если нажал)
        if data.startswith("set:"):
            answer_callback(cb_id)
            return

    except Exception:
        log.exception("Callback error")

    answer_callback(cb_id)
