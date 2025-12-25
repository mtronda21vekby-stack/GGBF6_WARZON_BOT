# -*- coding: utf-8 -*-
import random
from typing import Any, Dict

from app.state import (
    ensure_profile, ensure_daily, throttle,
    update_memory, clear_memory, save_state,
    USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY, _get_lock
)
from app.ui import (
    main_text, menu_main, menu_game, menu_persona, menu_talk,
    menu_training, menu_settings, menu_daily,
    status_text, profile_text
)
from app.ai import chat_reply, coach_reply
from zombies import router as zombies_router
from app.tg import send_message, edit_message, answer_callback

THINKING_LINES = ["🧠 Думаю…", "⌛ Секунду…", "🎮 Окей, ща разложу…", "🌑 Анализирую…"]

def handle_message(chat_id: int, text: str) -> None:
    lock = _get_lock(chat_id)
    if not lock.acquire(blocking=False):
        return
    try:
        if throttle(chat_id):
            return

        p = ensure_profile(chat_id)
        t = (text or "").strip()
        if not t:
            return

        # ✅ Если мы в Zombies — любой обычный текст = поиск по карте (как ты хотел)
        if not t.startswith("/") and p.get("page") == "zombies":
            z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
            if z is not None:
                send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
                return

        if t in ("/start", "/menu"):
            p["page"] = "main"
            ensure_daily(chat_id)
            send_message(chat_id, main_text(chat_id), reply_markup=menu_main(chat_id))
            save_state()
            return

        if t == "/status":
            send_message(chat_id, status_text(), reply_markup=menu_main(chat_id))
            return

        if t == "/profile":
            send_message(chat_id, profile_text(chat_id), reply_markup=menu_main(chat_id))
            return

        if t == "/daily":
            d = ensure_daily(chat_id)
            send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))
            return

        if t == "/zombies":
            p["page"] = "zombies"
            save_state()
            z = zombies_router.handle_callback("zmb:home")
            send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        if t == "/reset":
            USER_PROFILE.pop(chat_id, None)
            USER_MEMORY.pop(chat_id, None)
            USER_STATS.pop(chat_id, None)
            USER_DAILY.pop(chat_id, None)
            ensure_profile(chat_id)
            ensure_daily(chat_id)
            save_state()
            send_message(chat_id, "🧨 Сброс: профиль/память/статы/задание дня очищены.", reply_markup=menu_main(chat_id))
            return

        update_memory(chat_id, "user", t)
        tmp_id = send_message(chat_id, random.choice(THINKING_LINES), reply_markup=None)

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

    finally:
        lock.release()

def handle_callback(cb: Dict[str, Any]) -> None:
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = (cb.get("data") or "").strip()

    if not cb_id or not chat_id or not message_id:
        return

    try:
        p = ensure_profile(chat_id)

        # ✅ Zombies router перехватывает ВСЕ zmb:* кнопки (это и есть “как Ashes”)
        z = zombies_router.handle_callback(data)
        if z is not None:
            sp = z.get("set_profile") or {}
            if isinstance(sp, dict) and sp:
                for k, v in sp.items():
                    p[k] = v
                save_state()
            edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
            return

        if data == "nav:main":
            p["page"] = "main"
            save_state()
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

        elif data == "nav:game":
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
            edit_message(chat_id, message_id, status_text(), reply_markup=menu_main(chat_id))
        elif data == "action:profile":
            edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_main(chat_id))
        elif data == "action:ai_status":
            from app.ai import openai_client
            from app.config import OPENAI_MODEL
            ai = "ON" if openai_client else "OFF"
            edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {OPENAI_MODEL}", reply_markup=menu_main(chat_id))
        elif data == "action:clear_memory":
            clear_memory(chat_id)
            save_state()
            edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_main(chat_id))
        elif data == "action:reset_all":
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
            edit_message(chat_id, message_id, main_text(chat_id), reply_markup=menu_main(chat_id))

    finally:
        answer_callback(cb_id)
