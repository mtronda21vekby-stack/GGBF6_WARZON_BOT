# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, edit_message, edit_reply_markup, answer_callback
from app.state import ensure_profile, clear_memory
from app.ui import main_menu_markup, more_menu_markup
from zombies.router import handle_zombies


START_TEXT = (
    "Что умеет этот бот?\n"
    "Добро пожаловать в FPS Coach Bot.\n"
    "Я не автоответчик и не сборник советов.\n"
    "Я коуч-тиммейт: общаюсь с тобой и помогаю перестать сыпаться.\n\n"
    "Как мы работаем:\n"
    "• 🗣 CHAT — диалог, уточняю и разбираюсь вместе\n"
    "• 🎯 COACH — быстрый разбор: ошибка → действия → дрилл\n"
    "• 🤖 AUTO — сам выбираю режим по ситуации\n\n"
    "Что я делаю:\n"
    "• разбираю смерти и файты\n"
    "• нахожу причину ошибок\n"
    "• даю персональные дриллы\n"
    "• помню твой прогресс\n"
    "• подстраиваюсь под Warzone / BF6 / BO7\n\n"
    "👉 Опиши одну смерть или жми меню 👇"
)


def _toggle(p: dict, key: str, on_val="on", off_val="off"):
    p[key] = off_val if p.get(key, off_val) == on_val else on_val


def _show_main_menu(chat_id: int) -> None:
    p = ensure_profile(chat_id)
    p["page"] = "main"

    menu_id = p.get("menu_msg_id")
    markup = main_menu_markup(chat_id)

    # Если уже есть “главное меню” — редактируем его (никаких дублей)
    if isinstance(menu_id, int) and menu_id > 0:
        try:
            edit_message(chat_id, menu_id, START_TEXT, reply_markup=markup)
            return
        except Exception:
            # если сообщение удалили/старое — отправим заново
            p["menu_msg_id"] = None

    new_id = send_message(chat_id, START_TEXT, reply_markup=markup)
    if isinstance(new_id, int):
        p["menu_msg_id"] = new_id


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()
    if not text:
        return

    low = text.lower()

    # Ловим варианты: "/start", "/start@bot", "/start что-то"
    if low.startswith("/start") or low == "start":
        _show_main_menu(chat_id)
        return

    # быстрый вход в Zombies по тексту
    if low in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # обычный ответ (и не дублируем меню отдельным сообщением каждый раз)
    p = ensure_profile(chat_id)
    menu_id = p.get("menu_msg_id")
    try:
        send_message(chat_id, "Ок. Опиши: где умер / что бесит / что хочешь улучшить.", reply_markup=None)
        # если есть меню — просто обновим клавиатуру, без новых “плиток”
        if isinstance(menu_id, int) and menu_id > 0:
            edit_reply_markup(chat_id, menu_id, main_menu_markup(chat_id))
    except Exception:
        log.exception("handle_message send failed")


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
        # --- UI страницы ---
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

        # --- тумблеры ---
        if data == "toggle:memory":
            _toggle(p, "memory", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id,
                                  main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data == "toggle:ai":
            _toggle(p, "ai", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id,
                                  main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        if data == "toggle:lightning":
            _toggle(p, "lightning", "on", "off")
            if message_id:
                edit_reply_markup(chat_id, message_id,
                                  main_menu_markup(chat_id) if p.get("page") != "more" else more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        # --- Ещё ---
        if data == "more:clear_memory":
            clear_memory(chat_id)
            if message_id:
                edit_reply_markup(chat_id, message_id, more_menu_markup(chat_id))
            answer_callback(cb_id)
            return

        # Заглушки чтобы не падало
        if data.startswith("more:") or data.startswith("set:"):
            answer_callback(cb_id)
            return

    except Exception:
        log.exception("Callback error")

    answer_callback(cb_id)
