# -*- coding: utf-8 -*-
from typing import Dict, Any

from zombies import router as zombies_router

from app.kb import GAME_KB
from app.state import (
    ensure_profile, ensure_daily,
    update_memory, clear_memory,
    USER_PROFILE, USER_MEMORY, USER_STATS, USER_DAILY,
    save_state, throttle, get_lock
)
from app.ui import (
    main_text, help_text, status_text, profile_text,
    menu_main, menu_more, menu_game, menu_persona, menu_talk,
    menu_training, menu_settings, menu_daily, thinking_line
)

def _bf6_kb():
    try:
        from app.reply_kb import bf6_main_keyboard
        return bf6_main_keyboard()
    except Exception:
        return None

def _rm_kb():
    try:
        from app.reply_kb import remove_reply_keyboard
        return remove_reply_keyboard()
    except Exception:
        return None


class BotHandlers:
    def __init__(self, api, ai_engine, settings, log):
        self.api = api
        self.ai = ai_engine
        self.s = settings
        self.log = log

    # =========================
    # Helper: гарантируем нужную нижнюю клаву
    # =========================
    def _ensure_bottom_kb(self, chat_id: int):
        p = ensure_profile(chat_id)
        if p.get("game") == "bf6":
            kb = _bf6_kb()
            if kb:
                # Отдельным сообщением включаем ReplyKeyboard (нижнюю панель)
                self.api.send_message(chat_id, "🎮 BF6 панель включена 👇", reply_markup=kb, max_text_len=self.s.MAX_TEXT_LEN)
        else:
            rm = _rm_kb()
            if rm:
                # Убираем ReplyKeyboard когда не BF6
                self.api.send_message(chat_id, " ", reply_markup=rm, max_text_len=self.s.MAX_TEXT_LEN)

    def handle_message(self, chat_id: int, text: str) -> None:
        lock = get_lock(chat_id)
        if not lock.acquire(blocking=False):
            return
        try:
            if throttle(chat_id, self.s.MIN_SECONDS_BETWEEN_MSG):
                return

            p = ensure_profile(chat_id)
            t = (text or "").strip()
            if not t:
                return

            # ✅ Zombies: если мы в меню Zombies — любой текст = поиск по карте
            if not t.startswith("/") and p.get("page") == "zombies":
                z = zombies_router.handle_text(t, current_map=p.get("zmb_map", "ashes"))
                if z is not None:
                    self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                    return

            # =========================
            # 🎮 BF6 нижние кнопки (ReplyKeyboard) — обрабатываем текст
            # =========================
            if p.get("game") == "bf6":
                low = t.lower()

                if low in ("⬅️ назад (bf6)", "назад (bf6)", "назад"):
                    # просто покажем главное меню (INLINE под сообщением) и оставим BF6 панель
                    self.api.send_message(
                        chat_id,
                        main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)  # BF6 панель останется
                    save_state(self.s.STATE_PATH, self.log)
                    return

                if low.startswith("🎮 как играть"):
                    self.api.send_message(
                        chat_id,
                        "🎮 BF6 — основа\n"
                        "• Инфо → позиция → тайминг\n"
                        "• После контакта — репозиция (не репик лоб в лоб)\n"
                        "• Контроль линий прострела + укрытия\n\n"
                        "Напиши 1 смерть — разберу точно.",
                        reply_markup=menu_main(chat_id, self.ai.enabled),  # INLINE меню всегда
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low.startswith("🧠 мышление"):
                    self.api.send_message(
                        chat_id,
                        "🧠 Мышление BF6\n"
                        "1) Где инфо? (мини-карта/звук/союзники)\n"
                        "2) Где укрытие? (не стой на линии)\n"
                        "3) Когда выход? (под ресет/перезаряд)\n"
                        "4) После выстрелов — смена позиции\n",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low.startswith("💀 почему"):
                    self.api.send_message(
                        chat_id,
                        "💀 Почему умираешь в BF6 (часто)\n"
                        "• репик того же угла\n"
                        "• выход без инфо\n"
                        "• стоишь на линии прострела\n"
                        "• нет ресета (хил/патроны)\n"
                        "• жадность\n\n"
                        "Опиши 1 смерть: где был → кто первый увидел → чем умер.",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low.startswith("🎯 роль"):
                    self.api.send_message(
                        chat_id,
                        "🎯 Роль в BF6\n"
                        "• Entry: первым берёшь инфо, не умираешь бесплатно\n"
                        "• Anchor: держишь линию/фланг, живёшь дольше\n"
                        "• Support: ресы/ресурсы/темп\n\n"
                        "Ты чаще впереди или держишь позицию?",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low.startswith("⚙️ устройство"):
                    self.api.send_message(
                        chat_id,
                        "⚙️ Устройство\n"
                        "Напиши одним словом: PC / PS5 / Xbox\n"
                        "И я дам настройки и мышление под девайс.",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low in ("pc", "пк"):
                    self.api.send_message(
                        chat_id,
                        "🖥 BF6 PC\n"
                        "Скажи: DPI мыши и текущую сенсу в игре — под это сделаю точный блок (sens/ADS/FOV).",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low in ("ps5", "пс5", "playstation"):
                    self.api.send_message(
                        chat_id,
                        "🎮 BF6 PS5\n"
                        "Скажи: есть ли дрифт стика? (да/нет) — дам deadzone/sens/ADS блок.",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

                if low in ("xbox", "хбокс"):
                    self.api.send_message(
                        chat_id,
                        "🎮 BF6 Xbox\n"
                        "Скажи: есть ли дрифт стика? (да/нет) — дам deadzone/sens/ADS блок.",
                        reply_markup=menu_main(chat_id, self.ai.enabled),
                        max_text_len=self.s.MAX_TEXT_LEN
                    )
                    self._ensure_bottom_kb(chat_id)
                    return

            # =========================
            # Команды
            # =========================
            if t.startswith("/start") or t.startswith("/menu"):
                p["page"] = "main"
                ensure_daily(chat_id)

                # INLINE меню (старые кнопки) — всегда показываем
                self.api.send_message(
                    chat_id,
                    main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                # Нижнюю клаву включаем/убираем по текущей игре
                self._ensure_bottom_kb(chat_id)

                save_state(self.s.STATE_PATH, self.log)
                return

            if t.startswith("/help"):
                self.api.send_message(chat_id, help_text(), reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                self._ensure_bottom_kb(chat_id)
                return

            if t.startswith("/status"):
                self.api.send_message(
                    chat_id,
                    status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled),
                    reply_markup=menu_main(chat_id, self.ai.enabled),
                    max_text_len=self.s.MAX_TEXT_LEN
                )
                self._ensure_bottom_kb(chat_id)
                return

            if t.startswith("/profile"):
                self.api.send_message(chat_id, profile_text(chat_id), reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                self._ensure_bottom_kb(chat_id)
                return

            if t.startswith("/daily"):
                d = ensure_daily(chat_id)
                self.api.send_message(chat_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id), max_text_len=self.s.MAX_TEXT_LEN)
                self._ensure_bottom_kb(chat_id)
                return

            if t.startswith("/zombies"):
                p["page"] = "zombies"
                save_state(self.s.STATE_PATH, self.log)
                z = zombies_router.handle_callback("zmb:home")
                self.api.send_message(chat_id, z["text"], reply_markup=z.get("reply_markup"), max_text_len=self.s.MAX_TEXT_LEN)
                # Zombies — уберём BF6 нижнюю клаву, чтоб не мешала
                rm = _rm_kb()
                if rm:
                    self.api.send_message(chat_id, " ", reply_markup=rm, max_text_len=self.s.MAX_TEXT_LEN)
                return

            if t.startswith("/reset"):
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.send_message(chat_id, "🧨 Сброс выполнен.", reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
                self._ensure_bottom_kb(chat_id)
                return

            # =========================
            # Обычный диалог (AI)
            # =========================
            update_memory(chat_id, "user", t, self.s.MEMORY_MAX_TURNS)

            tmp_id = self.api.send_message(chat_id, thinking_line(), reply_markup=None, max_text_len=self.s.MAX_TEXT_LEN)

            mode = p.get("mode", "chat")
            try:
                reply = self.ai.coach_reply(chat_id, t) if mode == "coach" else self.ai.chat_reply(chat_id, t)
            except Exception:
                self.log.exception("Reply generation failed")
                reply = "Ошибка 😅 Напиши ещё раз коротко."

            update_memory(chat_id, "assistant", reply, self.s.MEMORY_MAX_TURNS)
            p["last_answer"] = reply[:2000]
            save_state(self.s.STATE_PATH, self.log)

            # INLINE меню возвращаем всегда
            if tmp_id:
                try:
                    self.api.edit_message(chat_id, tmp_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled))
                except Exception:
                    self.api.send_message(chat_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)
            else:
                self.api.send_message(chat_id, reply, reply_markup=menu_main(chat_id, self.ai.enabled), max_text_len=self.s.MAX_TEXT_LEN)

            # и нижняя клава — по игре
            self._ensure_bottom_kb(chat_id)

        finally:
            lock.release()

    def handle_callback(self, cb: Dict[str, Any]) -> None:
        cb_id = cb.get("id")
        msg = cb.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        message_id = msg.get("message_id")
        data = (cb.get("data") or "").strip()

        if not cb_id or not chat_id or not message_id:
            return

        try:
            p = ensure_profile(chat_id)

            # ✅ Zombies router перехватывает ВСЕ zmb:* кнопки
            z = zombies_router.handle_callback(data)
            if z is not None:
                sp = z.get("set_profile") or {}
                if isinstance(sp, dict) and sp:
                    for k, v in sp.items():
                        p[k] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, z["text"], reply_markup=z.get("reply_markup"))
                return

            if data == "nav:main":
                p["page"] = "main"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:more":
                self.api.edit_message(chat_id, message_id, "📦 Ещё:", reply_markup=menu_more(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:game":
                self.api.edit_message(chat_id, message_id, "🎮 Выбери игру:", reply_markup=menu_game(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:persona":
                self.api.edit_message(chat_id, message_id, "🎭 Выбери стиль:", reply_markup=menu_persona(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:talk":
                self.api.edit_message(chat_id, message_id, "🗣 Длина ответа:", reply_markup=menu_talk(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:training":
                self.api.edit_message(chat_id, message_id, "💪 Тренировка:", reply_markup=menu_training(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "nav:settings":
                self.api.edit_message(chat_id, message_id, "⚙️ Настройки:", reply_markup=menu_settings(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "toggle:memory":
                p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
                if p["memory"] == "off":
                    clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "toggle:mode":
                p["mode"] = "coach" if p.get("mode", "chat") == "chat" else "chat"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "toggle:ui":
                p["ui"] = "hide" if p.get("ui", "show") == "show" else "show"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "toggle:lightning":
                p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data.startswith("set:game:"):
                g = data.split(":", 2)[2]
                if g in ("auto", "warzone", "bf6", "bo7"):
                    p["game"] = g
                    save_state(self.s.STATE_PATH, self.log)

                # INLINE меню остаётся
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                # А вот нижняя клава включ/выкл по игре
                self._ensure_bottom_kb(chat_id)

            elif data.startswith("set:persona:"):
                v = data.split(":", 2)[2]
                if v in ("spicy", "chill", "pro"):
                    p["persona"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data.startswith("set:talk:"):
                v = data.split(":", 2)[2]
                if v in ("short", "normal", "talkative"):
                    p["verbosity"] = v
                    save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:status":
                self.api.edit_message(chat_id, message_id, status_text(self.s.OPENAI_MODEL, self.s.DATA_DIR, self.ai.enabled), reply_markup=menu_settings(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:profile":
                self.api.edit_message(chat_id, message_id, profile_text(chat_id), reply_markup=menu_more(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:ai_status":
                ai = "ON" if self.ai.enabled else "OFF"
                self.api.edit_message(chat_id, message_id, f"🤖 ИИ: {ai}\nМодель: {self.s.OPENAI_MODEL}", reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:clear_memory":
                clear_memory(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧽 Память очищена.", reply_markup=menu_more(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:reset_all":
                USER_PROFILE.pop(chat_id, None)
                USER_MEMORY.pop(chat_id, None)
                USER_STATS.pop(chat_id, None)
                USER_DAILY.pop(chat_id, None)
                ensure_profile(chat_id)
                ensure_daily(chat_id)
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id, "🧨 Сброс выполнен.", reply_markup=menu_more(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data.startswith("action:drill:"):
                kind = data.split(":", 2)[2]
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                txt = GAME_KB[g]["drills"].get(kind, "Доступно: aim/recoil/movement")
                self.api.edit_message(chat_id, message_id, txt, reply_markup=menu_training(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:vod":
                g = ensure_profile(chat_id).get("game", "auto")
                if g == "auto":
                    g = "warzone"
                self.api.edit_message(chat_id, message_id, GAME_KB[g]["vod"], reply_markup=menu_more(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "action:daily":
                d = ensure_daily(chat_id)
                self.api.edit_message(chat_id, message_id, "🎯 Задание дня:\n• " + d["text"], reply_markup=menu_daily(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "daily:done":
                d = ensure_daily(chat_id)
                d["done"] = int(d.get("done", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"✅ Засчитал.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))
                self._ensure_bottom_kb(chat_id)

            elif data == "daily:fail":
                d = ensure_daily(chat_id)
                d["fail"] = int(d.get("fail", 0)) + 1
                save_state(self.s.STATE_PATH, self.log)
                self.api.edit_message(chat_id, message_id,
                                      f"❌ Ок.\n\n🎯 Задание дня:\n• {d['text']}\n(сделано={d['done']} / не вышло={d['fail']})",
                                      reply_markup=menu_daily(chat_id))
                self._ensure_bottom_kb(chat_id)

            else:
                self.api.edit_message(chat_id, message_id, main_text(chat_id, self.ai.enabled, self.s.OPENAI_MODEL), reply_markup=menu_main(chat_id, self.ai.enabled))
                self._ensure_bottom_kb(chat_id)

        finally:
            self.api.answer_callback(cb_id)
