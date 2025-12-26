# app/handlers.py
# -*- coding: utf-8 -*-

from app.tg import send_message, edit_message, answer_callback
from app.ui import (
    main_menu_markup, more_menu_markup,
    CB_MORE_OPEN, CB_MORE_CLOSE,
    CB_GAME, CB_STYLE, CB_VERB, CB_MEM, CB_MODE, CB_AI, CB_LIGHT,
    CB_TRAIN, CB_PROFILE, CB_SETTINGS, CB_DAILY, CB_CLEAR_MEM, CB_RESET,
    CB_ZOMBIES,
)
from app.state import ensure_profile, clear_memory

from zombies.router import handle_zombies


WELCOME_TEXT = (
    "Что умеет этот бот?\n"
    "Добро пожаловать в FPS Coach Bot.\n"
    "Я не автоответчик и не сборник советов.\n"
    "Я коуч-тиммейт: общаюсь с тобой и помогаю перестать сыпаться.\n\n"
    "Как мы работаем:\n"
    "• 💬 CHAT — диалог, уточняю и разбираюсь вместе\n"
    "• 🎯 COACH — быстрый разбор: ошибка → действия → дрилл\n"
    "• 🤖 AUTO — сам выбираю режим по ситуации\n\n"
    "Что я делаю:\n"
    "• разбираю смерти и файты\n"
    "• нахожу причину ошибок\n"
    "• даю персональные дриллы\n"
    "• помню твой прогресс\n"
    "• подстраиваюсь под Warzone / BF6 / BO7\n\n"
    "👉 Опиши одну смерть (где умер, от чего, что делал за 5 сек до)."
)


def _toggle(p: dict, key: str, a: str, b: str):
    p[key] = b if (p.get(key) == a) else a


def handle_message(chat_id: int, text: str):
    text = (text or "").strip()
    if not text:
        return

    if text.lower() in ("/start", "start"):
        send_message(chat_id, WELCOME_TEXT, reply_markup=main_menu_markup(chat_id))
        return

    # быстрый вход в зомби текстом
    if text.lower() in ("zombies", "зомби"):
        handle_zombies(chat_id)
        return

    # обычный чат: просто показываем меню под ответом (чтобы всегда было куда жать)
    send_message(
        chat_id,
        "Принял ✅\nОпиши подробнее: где умер/что бесит/какую цель хочешь (позиция, стрельба, решения)?",
        reply_markup=main_menu_markup(chat_id),
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

    p = ensure_profile(chat_id)

    # ---- Zombies callbacks (оставляем как есть) ----
    if data.startswith("zombies:"):
        handle_zombies(chat_id, callback=data, message_id=message_id)
        answer_callback(cb_id)
        return

    # ---- UI navigation ----
    if data == CB_MORE_OPEN:
        # показываем “Ещё” через edit, чтобы не плодить сообщений
        try:
            edit_message(chat_id, message_id, "📦 Ещё — выбери действие:", reply_markup=more_menu_markup(chat_id))
        except Exception:
            send_message(chat_id, "📦 Ещё — выбери действие:", reply_markup=more_menu_markup(chat_id))
        answer_callback(cb_id)
        return

    if data == CB_MORE_CLOSE:
        try:
            edit_message(chat_id, message_id, "Меню 👇", reply_markup=main_menu_markup(chat_id))
        except Exception:
            send_message(chat_id, "Меню 👇", reply_markup=main_menu_markup(chat_id))
        answer_callback(cb_id)
        return

    # ---- toggles ----
    if data == CB_GAME:
        # auto -> warzone -> bf6 -> bo7 -> auto
        cur = (p.get("game") or "auto").lower()
        nxt = {"auto": "warzone", "warzone": "bf6", "bf6": "bo7", "bo7": "auto"}.get(cur, "auto")
        p["game"] = nxt

    elif data == CB_STYLE:
        # spicy -> calm -> spicy
        _toggle(p, "persona", "spicy", "calm")

    elif data == CB_VERB:
        # normal -> talkative -> normal
        _toggle(p, "verbosity", "normal", "talkative")

    elif data == CB_MEM:
        _toggle(p, "memory", "on", "off")

    elif data == CB_MODE:
        # chat -> coach -> auto -> chat
        cur = (p.get("mode") or "chat").lower()
        nxt = {"chat": "coach", "coach": "auto", "auto": "chat"}.get(cur, "chat")
        p["mode"] = nxt

    elif data == CB_AI:
        _toggle(p, "ai", "on", "off")

    elif data == CB_LIGHT:
        _toggle(p, "lightning", "on", "off")

    elif data == CB_ZOMBIES:
        handle_zombies(chat_id, callback="zombies:home", message_id=message_id)
        answer_callback(cb_id)
        return

    # ---- “Ещё” actions ----
    elif data == CB_CLEAR_MEM:
        clear_memory(chat_id)
        try:
            edit_message(chat_id, message_id, "Память очищена ✅", reply_markup=more_menu_markup(chat_id))
        except Exception:
            send_message(chat_id, "Память очищена ✅", reply_markup=more_menu_markup(chat_id))
        answer_callback(cb_id)
        return

    elif data == CB_RESET:
        # мягкий reset профиля
        p.clear()
        ensure_profile(chat_id)
        try:
            edit_message(chat_id, message_id, "Сбросил настройки ✅", reply_markup=main_menu_markup(chat_id))
        except Exception:
            send_message(chat_id, "Сбросил настройки ✅", reply_markup=main_menu_markup(chat_id))
        answer_callback(cb_id)
        return

    elif data in (CB_TRAIN, CB_PROFILE, CB_SETTINGS, CB_DAILY):
        # пока заглушки (чтобы не ломалось)
        titles = {
            CB_TRAIN: "💪 Тренировка",
            CB_PROFILE: "📊 Профиль",
            CB_SETTINGS: "⚙️ Настройки",
            CB_DAILY: "🎯 Задание дня",
        }
        try:
            edit_message(chat_id, message_id, f"{titles[data]}\n\n(Сюда подключим логику дальше)", reply_markup=more_menu_markup(chat_id))
        except Exception:
            send_message(chat_id, f"{titles[data]}\n\n(Сюда подключим логику дальше)", reply_markup=more_menu_markup(chat_id))
        answer_callback(cb_id)
        return

    # обновляем меню в текущем сообщении (без дублей)
    try:
        edit_message(chat_id, message_id, "Меню обновлено ✅", reply_markup=main_menu_markup(chat_id))
    except Exception:
        # если edit нельзя (старое сообщение/не то) — просто отправим новое
        send_message(chat_id, "Меню обновлено ✅", reply_markup=main_menu_markup(chat_id))

    answer_callback(cb_id)
