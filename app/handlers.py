# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, edit_message, answer_callback
from app.state import ensure_profile, save_state, clear_memory, ensure_daily
from app.ui import (
    main_menu_markup, more_menu_markup,
    game_menu_markup, persona_menu_markup, talk_menu_markup,
    daily_menu_markup
)
from zombies.router import router as zombies_router

# ИИ-ответы (если у тебя есть app/ai.py с функцией reply_text — подключим)
try:
    from app.ai import reply_text
except Exception:
    reply_text = None


def handle_message(chat_id: int, text: str):
    p = ensure_profile(chat_id)
    t = (text or "").strip()
    if not t:
        return

    # если в Zombies-странице — любой текст = поиск
    if not t.startswith("/") and p.get("page") == "zombies":
        z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
        if z is not None:
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

    if t.lower() in ("/start", "/menu", "start"):
        p["page"] = "main"
        ensure_daily(chat_id)
        save_state()
        send_message(
            chat_id,
            "Привет! Напиши вопрос по Warzone/BF6/BO7 или зайди в Zombies 👇",
            reply_markup=main_menu_markup(p)
        )
        return

    if t.lower() in ("/zombies", "zombies", "зомби"):
        p["page"] = "zombies"
        save_state()
        z = zombies_router.handle_callback("zmb:home")
        send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
        return

    # обычный умный ответ
    if reply_text:
        out = reply_text(chat_id, t)  # твой AI модуль решает как отвечать
        send_message(chat_id, out, reply_markup=main_menu_markup(p))
        return

    # если AI модуля нет — не ломаемся
    send_message(
        chat_id,
        "Я понял 👍 Напиши подробнее (карта/режим/что именно нужно) или зайди в Zombies.",
        reply_markup=main_menu_markup(p)
    )


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not cb_id or not chat_id or not message_id:
        return

    p = ensure_profile(chat_id)

    try:
        # Zombies router перехватывает все zmb:*
        z = zombies_router.handle_callback(data)
        if z is not None:
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()
            edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        # Навигация
        if data == "nav:main":
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, "Меню 👇", reply_markup=main_menu_markup(p))
            return

        if data == "nav:more":
            edit_message(chat_id, message_id, "📦 Доп. меню:", reply_markup=more_menu_markup(p))
            return

        if data == "nav:game":
            edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=game_menu_markup(p))
            return

        if data == "nav:persona":
            edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=persona_menu_markup(p))
            return

        if data == "nav:talk":
            edit_message(chat_id, message_id, "💬 Длина ответа:", reply_markup=talk_menu_markup(p))
            return

        # Тогглы
        if data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        if data == "toggle:mode":
            p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
            save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        if data == "toggle:ai":
            p["ai"] = "off" if p.get("ai", "on") == "on" else "on"
            save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        if data == "toggle:lightning":
            p["lightning"] = "off" if p.get("lightning", "off") == "on" else "on"
            save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        # Сеты
        if data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in ("auto", "warzone", "bf6", "bo7"):
                p["game"] = g
                save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        if data.startswith("set:persona:"):
            v = data.split(":", 2)[2]
            if v in ("spicy", "chill", "pro"):
                p["persona"] = v
                save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        if data.startswith("set:talk:"):
            v = data.split(":", 2)[2]
            if v in ("short", "normal", "talkative"):
                p["verbosity"] = v
                save_state()
            edit_message(chat_id, message_id, "Ок ✅", reply_markup=main_menu_markup(p))
            return

        # Ещё-меню действия
        if data == "action:clear_memory":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=more_menu_markup(p))
            return

        if data == "action:reset_all":
            # жёсткий сброс
            from app.state import reset_all
            reset_all(chat_id)
            p = ensure_profile(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=main_menu_markup(p))
            return

        if data == "action:daily":
            d = ensure_daily(chat_id)
            edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=daily_menu_markup())
            return

        if data == "daily:done":
            d = ensure_daily(chat_id)
            d["done"] = int(d.get("done", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, "✅ Засчитал!", reply_markup=daily_menu_markup())
            return

        if data == "daily:fail":
            d = ensure_daily(chat_id)
            d["fail"] = int(d.get("fail", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, "❌ Ок, бывает.", reply_markup=daily_menu_markup())
            return

        # по умолчанию
        edit_message(chat_id, message_id, "Меню 👇", reply_markup=main_menu_markup(p))

    finally:
        answer_callback(cb_id)
