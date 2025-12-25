# app/handlers.py
# -*- coding: utf-8 -*-

from app.tg import send_message, edit_message, answer_callback
from app.ui import main_menu_markup
from zombies import router as zombies_router


def handle_message(chat_id: int, text: str):
    t = (text or "").strip()
    if not t:
        return

    if t.lower() in ("/start", "/menu", "start"):
        send_message(
            chat_id,
            "Привет! Выбирай режим ниже 👇",
            reply_markup=main_menu_markup()
        )
        return

    if t.lower() in ("/zombies", "zombies", "зомби"):
        z = zombies_router.handle_callback("zmb:home")
        send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
        return

    send_message(
        chat_id,
        "Ок 👍 Напиши вопрос или открой Zombies 👇",
        reply_markup=main_menu_markup()
    )


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not chat_id:
        answer_callback(cb_id)
        return

    # ✅ все кнопки Zombies: zmb:*
    z = zombies_router.handle_callback(data)
    if z is not None and message_id:
        edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
        answer_callback(cb_id)
        return

    answer_callback(cb_id)
