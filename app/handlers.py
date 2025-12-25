# app/handlers.py
# -*- coding: utf-8 -*-

from app.log import log
from app.tg import send_message, edit_message, answer_callback
from app.ui import main_menu_markup, more_menu_markup

from app.state import (
    ensure_profile, throttle, update_memory, clear_memory, ensure_daily,
    USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY, save_state
)

# ВАЖНО: как в твоём старом рабочем коде
from zombies import router as zombies_router

# если у тебя AI/ответы в app.ai — импортируй тут
try:
    from app.ai import chat_reply, coach_reply, ai_is_on
except Exception:
    chat_reply = None
    coach_reply = None
    def ai_is_on():
        return False


def _main_text(chat_id: int) -> str:
    return (
        "Что умеет этот бот?\n"
        "Добро пожаловать в FPS Coach Bot.\n"
        "Я не автоответчик и не сборник советов.\n"
        "Я коуч-тиммейт: общаюсь с тобой и помогаю перестать сыпаться.\n\n"
        "Как мы работаем:\n"
        "• 💬 CHAT — диалог, уточняю и разбираюсь вместе\n"
        "• 🎯 COACH — быстрый разбор: ошибка → действия → дрилл\n\n"
        "👉 Опиши одну смерть/ситуацию."
    )


def handle_message(chat_id: int, text: str):
    p = ensure_profile(chat_id)
    t = (text or "").strip()
    if not t:
        return

    if throttle(chat_id):
        return

    # ✅ Если в Zombies-странице — любой НЕ-командный текст = поиск по карте
    if not t.startswith("/") and p.get("page") == "zombies":
        z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
        if z is not None:
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

    # команды
    if t.startswith("/start") or t.startswith("/menu") or t.lower() == "start":
        p["page"] = "main"
        ensure_daily(chat_id)
        save_state()
        send_message(chat_id, _main_text(chat_id), reply_markup=main_menu_markup(p, ai_is_on()))
        return

    if t.startswith("/zombies"):
        p["page"] = "zombies"
        save_state()
        z = zombies_router.handle_callback("zmb:home")
        send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
        return

    if t.startswith("/reset"):
        USER_PROFILE.pop(chat_id, None)
        USER_MEMORY.pop(chat_id, None)
        USER_STATS.pop(chat_id, None)
        USER_DAILY.pop(chat_id, None)
        ensure_profile(chat_id)
        ensure_daily(chat_id)
        save_state()
        send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=main_menu_markup(ensure_profile(chat_id), ai_is_on()))
        return

    # === обычный умный ответ (если у тебя app.ai есть) ===
    update_memory(chat_id, "user", t)

    # если у тебя ещё нет app.ai — будет просто короткий ответ
    if not chat_reply or not coach_reply:
        reply = "Ок 👍 Опиши одну смерть: где был, кто первый увидел, на чём умер?"
    else:
        mode = p.get("mode", "chat")
        reply = coach_reply(chat_id, t) if mode == "coach" else chat_reply(chat_id, t)

    update_memory(chat_id, "assistant", reply)
    p["last_answer"] = (reply or "")[:2000]
    save_state()

    # ✅ ВАЖНО: отправляем ТОЛЬКО ОДНО сообщение
    send_message(chat_id, reply, reply_markup=main_menu_markup(p, ai_is_on()))


def handle_callback(cb: dict):
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not cb_id or not chat_id:
        return

    p = ensure_profile(chat_id)

    try:
        # ✅ Zombies router перехватывает ВСЕ zmb:* кнопки
        z = zombies_router.handle_callback(data)
        if z is not None:
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()

            # если нет message_id — просто отправим
            if message_id:
                edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            else:
                send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        # === ЕЩЁ ===
        if data == "ui:more":
            if message_id:
                edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=more_menu_markup())
            else:
                send_message(chat_id, "📦 Ещё:", reply_markup=more_menu_markup())
            return

        if data == "ui:main":
            if message_id:
                edit_message(chat_id, message_id, _main_text(chat_id), reply_markup=main_menu_markup(p, ai_is_on()))
            else:
                send_message(chat_id, _main_text(chat_id), reply_markup=main_menu_markup(p, ai_is_on()))
            return

        # === ТУМБЛЕРЫ ===
        if data == "toggle:memory":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            if p["memory"] == "off":
                clear_memory(chat_id)
            save_state()

        elif data == "toggle:mode":
            p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
            save_state()

        elif data == "toggle:lightning":
            p["lightning"] = "off" if p.get("lightning", "off") == "on" else "on"
            save_state()

        # Остальные кнопки из “Ещё” пусть обрабатывает твой старый код
        # (если позже захочешь — я подключу всё полностью)

        # просто перерисуем меню
        if message_id:
            edit_message(chat_id, message_id, _main_text(chat_id), reply_markup=main_menu_markup(p, ai_is_on()))
        else:
            send_message(chat_id, _main_text(chat_id), reply_markup=main_menu_markup(p, ai_is_on()))

    finally:
        answer_callback(cb_id)
