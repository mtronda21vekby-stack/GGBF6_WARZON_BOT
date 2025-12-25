# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, edit_message, answer_callback
from app.ui import main_menu_markup, more_menu_markup
from zombies.router import handle_zombies
from app.state import clear_memory


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()
    if not text:
        return

    if text.lower() in ("/start", "start"):
        send_message(
            chat_id,
            "👋 Добро пожаловать в FPS Coach Bot.\n\n"
            "Я не автоответчик.\n"
            "Я коуч-тиммейт: разбираю файты, ошибки и даю конкретные действия.\n\n"
            "👉 Опиши одну смерть или ситуацию.",
            reply_markup=main_menu_markup()
        )
        return

    if text.lower() in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # ❗️ВАЖНО: только ОДИН ответ
    send_message(
        chat_id,
        "Я с тобой 👍\nОпиши ситуацию подробнее или выбери режим 👇",
        reply_markup=main_menu_markup()
    )


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    msg_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not chat_id:
        answer_callback(cb_id)
        return

    # === UI ===
    if data == "ui:more":
        edit_message(chat_id, msg_id, "📦 Дополнительные действия:", reply_markup=more_menu_markup())
        answer_callback(cb_id)
        return

    if data == "ui:main":
        edit_message(chat_id, msg_id, "Главное меню 👇", reply_markup=main_menu_markup())
        answer_callback(cb_id)
        return

    # === ZOMBIES ===
    if data.startswith("zombies:"):
        handle_zombies(chat_id, callback=data, message_id=msg_id)
        answer_callback(cb_id)
        return

    # === MORE ===
    if data == "more:clear_memory":
        clear_memory(chat_id)
        edit_message(chat_id, msg_id, "🧠 Память очищена", reply_markup=more_menu_markup())
        answer_callback(cb_id)
        return

    if data == "more:reset":
        clear_memory(chat_id)
        edit_message(chat_id, msg_id, "🧨 Всё сброшено", reply_markup=main_menu_markup())
        answer_callback(cb_id)
        return

    # заглушка
    answer_callback(cb_id)
