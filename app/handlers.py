# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, edit_message, answer_callback
from zombies.router import handle_zombies
from app.ui import main_menu_markup


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()

    # базовая защита
    if not text:
        return

    # старт
    if text.lower() in ("/start", "start"):
        send_message(
            chat_id,
            "Привет! Я помощник по Warzone, BF6 и Zombies.\nВыбирай режим ниже 👇",
            reply_markup=main_menu_markup()
        )
        return

    # zombies
    if text.lower() in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # дефолт
    send_message(
        chat_id,
        "Я понял 👍\nЗадай вопрос по Warzone / BF6 или выбери Zombies 👇",
        reply_markup=main_menu_markup()
    )


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    data = (cb.get("data") or "").strip()

    if not chat_id:
        answer_callback(cb_id)
        return

    # Zombies callbacks
    if data.startswith("zombies:"):
        handle_zombies(chat_id, callback=data, message_id=msg.get("message_id"))
        answer_callback(cb_id)
        return

    answer_callback(cb_id)
