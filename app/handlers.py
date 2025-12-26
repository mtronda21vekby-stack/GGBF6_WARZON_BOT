# app/handlers.py
# -*- coding: utf-8 -*-

import random

from app.log import log
from app.tg import send_message, edit_message, answer_callback
from app.state import (
    ensure_profile, throttle, save_state, clear_memory,
    ensure_daily, update_memory
)
from app.ui import (
    main_menu_markup, more_menu_markup, main_text,
    menu_game, menu_persona, menu_talk, menu_settings,
    menu_training, menu_daily
)
from app.ai import generate_reply, ai_is_on

from zombies import router as zombies_router


THINKING_LINES = ["🧠 Думаю…", "⌛ Секунду…", "🎮 Окей, ща разложу…", "🌑 Анализирую…"]


def handle_message(chat_id: int, text: str):
    p = ensure_profile(chat_id)
    t = (text or "").strip()
    if not t:
        return
    if throttle(chat_id):
        return

    # ✅ Если в Zombies-меню — любой НЕ-командный текст = поиск по текущей карте
    if not t.startswith("/") and p.get("page") == "zombies":
        z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
        if z is not None:
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

    # commands
    if t.startswith("/start") or t.startswith("/menu"):
        p["page"] = "main"
        ensure_daily(chat_id)
        save_state()
        send_message(chat_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))
        return

    if t.startswith("/zombies"):
        p["page"] = "zombies"
        save_state()
        z = zombies_router.handle_callback("zmb:home")
        send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
        return

    if t.startswith("/reset"):
        # мягкий reset
        clear_memory(chat_id)
        p = ensure_profile(chat_id)
        p["mode"] = "chat"
        p["game"] = "auto"
        p["persona"] = "spicy"
        p["verbosity"] = "normal"
        p["lightning"] = "off"
        p["page"] = "main"
        save_state()
        send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=main_menu_markup(chat_id))
        return

    # обычный чат
    update_memory(chat_id, "user", t)

    # отправляем "думаю…" и потом редактируем (чтобы НЕ было 2 сообщений)
    tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

    try:
        reply = generate_reply(chat_id, t)
        if not reply:
            reply = "Напиши ещё раз коротко: где умер/что бесит/что хочешь улучшить?"
    except Exception:
        log.exception("Reply generation failed")
        reply = "Упс 😅 Что-то сломалось. Напиши ещё раз коротко: где умер и почему думаешь?"

    update_memory(chat_id, "assistant", reply)
    p["last_answer"] = reply[:2000]
    save_state()

    # редактируем tmp сообщение (и всё)
    try:
        if tmp_id:
            edit_message(chat_id, tmp_id, reply, reply_markup=main_menu_markup(chat_id))
        else:
            send_message(chat_id, reply, reply_markup=main_menu_markup(chat_id))
    except Exception:
        # если редактирование не вышло — шлём один раз
        send_message(chat_id, reply, reply_markup=main_menu_markup(chat_id))


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not chat_id or not message_id:
        if cb_id:
            answer_callback(cb_id)
        return

    p = ensure_profile(chat_id)

    try:
        # ✅ Zombies router забирает ВСЕ zmb:* кнопки
        z = zombies_router.handle_callback(data)
        if z is not None:
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()
            edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        # ---- NAV ----
        if data == "nav:main":
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data == "nav:more":
            p["page"] = "more"
            save_state()
            edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=more_menu_markup(chat_id))

        elif data == "nav:game":
            edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))

        elif data == "nav:persona":
            edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))

        elif data == "nav:talk":
            edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))

        elif data == "nav:settings":
            edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))

        elif data == "nav:training":
            edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))

        # ---- TOGGLES ----
        elif data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data == "toggle:mode":
            cur = p.get("mode", "chat")
            # chat -> coach -> auto -> chat
            p["mode"] = "coach" if cur == "chat" else ("auto" if cur == "coach" else "chat")
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data == "toggle:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data == "toggle:lightning":
            p["lightning"] = "off" if p.get("lightning", "off") == "on" else "on"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        # ---- SETTERS ----
        elif data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in ("auto", "warzone", "bf6", "bo7"):
                p["game"] = g
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data.startswith("set:persona:"):
            v = data.split(":", 2)[2]
            if v in ("spicy", "chill", "pro"):
                p["persona"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        elif data.startswith("set:talk:"):
            v = data.split(":", 2)[2]
            if v in ("short", "normal", "talkative"):
                p["verbosity"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

        # ---- ACTIONS ----
        elif data == "action:ai_status":
            edit_message(chat_id, message_id, f"🤖 ИИ: {'ON' if ai_is_on() else 'OFF'}\nМодель: {os.getenv('OPENAI_MODEL','gpt-4o-mini')}",
                         reply_markup=main_menu_markup(chat_id))

        elif data == "action:daily":
            d = ensure_daily(chat_id)
            edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))

        elif data == "daily:done":
            d = ensure_daily(chat_id)
            d["done"] = int(d.get("done", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, f"✅ Засчитал.\n\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                         reply_markup=menu_daily(chat_id))

        elif data == "daily:fail":
            d = ensure_daily(chat_id)
            d["fail"] = int(d.get("fail", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, f"❌ Ок.\n\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                         reply_markup=menu_daily(chat_id))

        elif data == "action:clear_memory":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=more_menu_markup(chat_id))

        elif data == "action:reset_all":
            clear_memory(chat_id)
            p["mode"] = "chat"
            p["game"] = "auto"
            p["persona"] = "spicy"
            p["verbosity"] = "normal"
            p["lightning"] = "off"
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=main_menu_markup(chat_id))

        else:
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=main_menu_markup(chat_id))

    except Exception:
        log.exception("Callback handling error")

    finally:
        if cb_id:
            answer_callback(cb_id)
