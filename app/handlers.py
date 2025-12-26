# app/handlers.py
# -*- coding: utf-8 -*-

from app.tg import send_message, answer_callback
from app.ui import main_menu_markup
from zombies.router import handle_zombies


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()
    if not text:
        return

    low = text.lower()

    # /start
    if low.startswith("/start") or low == "start":
        send_message(
            chat_id,
            "Что умеет этот бот?\n"
            "Добро пожаловать в FPS Coach Bot.\n"
            "Я не автоответчик и не сборник советов.\n"
            "Я коуч-тиммейт: общаюсь с тобой и помогаю перестать сыпаться.\n\n"
            "Как мы работаем:\n"
            "• 💬 CHAT — диалог, уточняю и разбираюсь вместе\n"
            "• 🎯 COACH — быстрый разбор: ошибка → действия → дрилл\n"
            "• 🤖 AUTO — сам выбираю режим по ситуации\n\n"
            "👉 Опиши одну смерть (где стоял, кто убил, что делал)",
            reply_markup=main_menu_markup(chat_id)
        )
        return

    # Zombies текстом
    if low in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # обычный чат — тут можно дальше подключить ИИ/ответы
    send_message(
        chat_id,
        "Ок. Напиши в 1–2 строках:\n"
        "Игра (warzone/bf6/zombies) | где умер | от кого | что хотел сделать.\n\n"
        "Или жми меню 👇",
        reply_markup=main_menu_markup(chat_id)
    )


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    data = (cb.get("data") or "").strip()

    if not chat_id:
        answer_callback(cb_id)
        return

    # Zombies callbacks (оставляем как у тебя)
    if data.startswith("zombies:") or data.startswith("zmb:"):
        handle_zombies(chat_id, callback=data, message_id=msg.get("message_id"))
        answer_callback(cb_id)
        return

    answer_callback(cb_id)
