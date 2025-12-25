# app/handlers.py
# -*- coding: utf-8 -*-

import random

from app.state import (
    ensure_profile, throttle, update_memory, clear_memory,
    ensure_daily, save_state
)
from app.ui import (
    main_text, menu_main, menu_more,
    menu_game, menu_persona, menu_talk,
    menu_training, menu_settings, menu_daily
)
from app.ai import chat_reply, coach_reply, CAUSE_LABEL, USER_STATS
from app.tg import send_message, edit_message, answer_callback

from zombies import router as zombies_router


THINKING_LINES = ["🧠 Думаю…", "⌛ Секунду…", "🎮 Окей, ща разложу…", "🌑 Анализирую…"]


def profile_text(chat_id: int) -> str:
    p = ensure_profile(chat_id)
    st = USER_STATS.get(chat_id, {})
    mem_len = 0
    from app.state import USER_MEMORY
    mem_len = len(USER_MEMORY.get(chat_id, []))
    daily = ensure_daily(chat_id)
    top = sorted(st.items(), key=lambda kv: kv[1], reverse=True)[:3]

    lines = [
        "📊 Профиль",
        f"Режим: {p.get('mode','chat').upper()}",
        f"Игра: {p.get('game','auto').upper()}",
        f"Стиль: {p.get('persona')}",
        f"Длина: {p.get('verbosity')}",
        f"Память: {p.get('memory','on').upper()} (сообщений: {mem_len})",
        f"⚡ Молния: {p.get('lightning','off').upper()}",
        "",
        "🧩 Карта проблем (топ):"
    ]
    if not top:
        lines.append("— пока пусто (нужны ситуации/смерти).")
    else:
        for c, n in top:
            lines.append(f"• {CAUSE_LABEL.get(c,c)}: {n}")

    lines += [
        "",
        "🎯 Задание дня:",
        f"• {daily.get('text')}",
        f"• сделано={daily.get('done',0)} / не вышло={daily.get('fail',0)}",
    ]
    return "\n".join(lines)


def status_text() -> str:
    from app import config
    from app.ai import openai_client
    return (
        "🧾 Статус\n"
        f"OPENAI_MODEL: {config.OPENAI_MODEL}\n"
        f"DATA_DIR: {config.DATA_DIR}\n"
        f"ИИ: {'ON' if openai_client else 'OFF'}\n"
        "Если Conflict 409 — у тебя два инстанса или где-то ещё включён getUpdates.\n"
    )


def handle_message(chat_id: int, text: str) -> None:
    if throttle(chat_id):
        return

    p = ensure_profile(chat_id)
    t = (text or "").strip()
    if not t:
        return

    # ✅ Zombies: если в режиме zombies — любой текст = поиск
    if not t.startswith("/") and p.get("page") == "zombies":
        z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
        if z is not None:
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

    if t.startswith("/start") or t.startswith("/menu"):
        p["page"] = "main"
        ensure_daily(chat_id)
        send_message(chat_id, main_text(chat_id), reply_markup=menu_main(chat_id))
        save_state()
        return

    if t.startswith("/zombies"):
        p["page"] = "zombies"
        save_state()
        z = zombies_router.handle_callback("zmb:home")
        send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
        return

    if t.startswith("/profile"):
        send_message(chat_id, profile_text(chat_id), reply_markup=menu_main(chat_id))
        return

    if t.startswith("/daily"):
        d = ensure_daily(chat_id)
        send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))
        return

    if t.startswith("/reset"):
        from app.state import USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        USER_STATS.pop(chat_id, None)
        USER_DAILY.pop(chat_id, None)
        ensure_profile(chat_id)
        ensure_daily(chat_id)
        save_state()
        send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=menu_main(chat_id))
        return

    # обычный чат/коуч
    update_memory(chat_id, "user", t)

    # ⚡ Молния: вкл — без “думаю…”
    lightning = (p.get("lightning") == "on")
    tmp_id = None if lightning else send_message(chat_id, random.choice(THINKING_LINES))

    mode = p.get("mode", "chat")
    reply = coach_reply(chat_id, t) if mode == "coach" else chat_reply(chat_id, t)

    update_memory(chat_id, "assistant", reply)
    p["last_answer"] = reply[:2000]
    save_state()

    if tmp_id:
        try:
            edit_message(chat_id, tmp_id, reply, reply_markup=menu_main(chat_id))
        except Exception:
            send_message(chat_id, reply, reply_markup=menu_main(chat_id))
    else:
        send_message(chat_id, reply, reply_markup=menu_main(chat_id))


def handle_callback(cb: dict) -> None:
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not cb_id or not chat_id or not message_id:
        return

    try:
        p = ensure_profile(chat_id)

        # ✅ Zombies router перехватывает все zmb:* кнопки
        z = zombies_router.handle_callback(data)
        if z is not None:
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()
            edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        # ✅ ВОТ ГЛАВНОЕ: “ЕЩЁ”
        if data == "nav:more":
            p["page"] = "more"
            save_state()
            edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=menu_more(chat_id))
            return

        if data == "nav:main":
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))
            return

        # остальная навигация
        if data == "nav:game":
            edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))
        elif data == "nav:persona":
            edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))
        elif data == "nav:talk":
            edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))
        elif data == "nav:training":
            edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))
        elif data == "nav:settings":
            edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))

        elif data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "toggle:mode":
            p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "toggle:ui":
            p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "toggle:lightning":
            p["lightning"] = "off" if p.get("lightning", "off") == "on" else "on"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:game:"):
            g = data.split(":", 2)[2]
            if g in ("auto", "warzone", "bf6", "bo7"):
                p["game"] = g
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:persona:"):
            v = data.split(":", 2)[2]
            if v in ("spicy", "chill", "pro"):
                p["persona"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data.startswith("set:talk:"):
            v = data.split(":", 2)[2]
            if v in ("short", "normal", "talkative"):
                p["verbosity"] = v
                save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "action:status":
            edit_message(chat_id, message_id, status_text(), reply_markup=menu_more(chat_id))

        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_more(chat_id))

        elif data == "action:ai_status":
            from app.ai import openai_client
            from app import config
            ai = "ON" if openai_client else "OFF"
            edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {config.OPENAI_MODEL}", reply_markup=menu_main(chat_id))

        elif data == "action:clear_memory":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_more(chat_id))

        elif data == "action:reset_all":
            from app.state import USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_STATS.pop(chat_id, None)
            USER_DAILY.pop(chat_id, None)
            ensure_profile(chat_id)
            ensure_daily(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=menu_main(chat_id))

        elif data == "action:daily":
            d = ensure_daily(chat_id)
            edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))

        elif data == "daily:done":
            d = ensure_daily(chat_id)
            d["done"] = int(d.get("done", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, f"✅ Засчитал.\n\n• {d['text']}", reply_markup=menu_daily(chat_id))

        elif data == "daily:fail":
            d = ensure_daily(chat_id)
            d["fail"] = int(d.get("fail", 0)) + 1
            save_state()
            edit_message(chat_id, message_id, f"❌ Ок.\n\n• {d['text']}", reply_markup=menu_daily(chat_id))

        else:
            # дефолт — возвращаем главное меню
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

    finally:
        answer_callback(cb_id)
