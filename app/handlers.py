# -*- coding: utf-8 -*-
from typing import Any, Dict

from app.state import (
    ensure_profile, update_memory, clear_memory, ensure_daily,
)
from app.ui import (
    main_text, status_text, profile_text, help_text,
    reply_keyboard_main, reply_keyboard_settings,
    reply_keyboard_wz_device, reply_keyboard_bo7_device, reply_keyboard_bf6_classes,
)
from app.kb import GAME_KB
from app.detect import detect_game
from app.ai import AIEngine

# настройки устройств/тексты (у тебя уже есть app/device_settings.py)
try:
    from app.device_settings import get_text as get_device_text
except Exception:
    get_device_text = None


class BotHandlers:
    def __init__(self, api, ai: AIEngine, cfg, log):
        self.api = api
        self.ai = ai
        self.cfg = cfg
        self.log = log

    # -------------------------
    # Public entry
    # -------------------------
    def handle_update(self, upd: Dict[str, Any]) -> None:
        # callbacks (inline) — игнорим/мягко закрываем: мы перешли на premium reply UI
        cb = upd.get("callback_query")
        if cb:
            try:
                self.api.answer_callback(cb.get("id"))
            except Exception:
                pass
            # ничего не делаем — inline кнопок больше не используем
            return

        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return

        chat = msg.get("chat") or {}
        chat_id = int(chat.get("id"))
        text = (msg.get("text") or "").strip()

        # ensure profile exists
        p = ensure_profile(chat_id)

        # commands
        if text in ("/start", "/menu"):
            self._send_main(chat_id)
            return
        if text == "/status":
            self._send_status(chat_id)
            return
        if text == "/profile":
            self._send_profile(chat_id)
            return
        if text == "/daily":
            self._send_daily(chat_id)
            return
        if text == "/reset":
            self._reset_all(chat_id)
            return

        # premium buttons (reply keyboard)
        if self._handle_reply_button(chat_id, text):
            return

        # normal chat -> AI/logic
        self._handle_chat(chat_id, text)

    # -------------------------
    # Premium Reply UI routes
    # -------------------------
    def _handle_reply_button(self, chat_id: int, text: str) -> bool:
        p = ensure_profile(chat_id)

        if text == "📋 Меню":
            self._send_main(chat_id)
            return True

        if text == "⚙️ Настройки":
            p["page"] = "settings"
            self.api.send_message(chat_id, "⚙️ Настройки игр (Premium UI снизу).", reply_markup=reply_keyboard_settings())
            return True

        if text == "⬅️ Назад в меню":
            self._send_main(chat_id)
            return True

        if text == "⬅️ Назад в настройки":
            p["page"] = "settings"
            self.api.send_message(chat_id, "⚙️ Настройки игр:", reply_markup=reply_keyboard_settings())
            return True

        if text == "🆘 Помощь":
            self.api.send_message(chat_id, help_text(), reply_markup=reply_keyboard_main())
            return True

        if text == "📡 Статус":
            self._send_status(chat_id)
            return True

        if text == "👤 Профиль":
            self._send_profile(chat_id)
            return True

        if text == "🧠 Память":
            p["memory"] = "off" if p.get("memory", "on") == "on" else "on"
            self.api.send_message(chat_id, f"🧠 Память: {'ON ✅' if p['memory']=='on' else 'OFF ❌'}", reply_markup=reply_keyboard_main())
            return True

        if text == "⚡ Молния":
            p["speed"] = "normal" if p.get("speed", "normal") == "lightning" else "lightning"
            self.api.send_message(chat_id, f"⚡ Режим: {'МОЛНИЯ' if p['speed']=='lightning' else 'ОБЫЧНЫЙ'}", reply_markup=reply_keyboard_main())
            return True

        if text == "🧽 Очистить память":
            clear_memory(chat_id)
            self.api.send_message(chat_id, "🧽 Память очищена.", reply_markup=reply_keyboard_main())
            return True

        if text == "🧨 Сброс":
            self._reset_all(chat_id)
            return True

        # game quick set
        if text == "🎮 Игра":
            self.api.send_message(
                chat_id,
                "🎮 Игра: напиши Warzone / BF6 / BO7 или AUTO.\n(или просто пиши ситуацию — авто-детект тоже работает)",
                reply_markup=reply_keyboard_main(),
            )
            return True

        # persona / verbosity quick
        if text == "🎭 Стиль":
            self.api.send_message(
                chat_id,
                "🎭 Стиль:\n• spicy — дерзко 😈\n• chill — спокойно 😌\n• pro — строго 🎯\n\nНапиши: spicy / chill / pro",
                reply_markup=reply_keyboard_main(),
            )
            return True

        if text == "🗣 Ответ":
            self.api.send_message(
                chat_id,
                "🗣 Длина ответа:\n• short\n• normal\n• talkative\n\nНапиши: short / normal / talkative",
                reply_markup=reply_keyboard_main(),
            )
            return True

        # settings pages
        if text == "🎮 Warzone настройки":
            ensure_profile(chat_id)["page"] = "wz_settings"
            self.api.send_message(chat_id, "🎮 Warzone — выбери устройство:", reply_markup=reply_keyboard_wz_device())
            return True

        if text == "🎮 BO7 настройки":
            ensure_profile(chat_id)["page"] = "bo7_settings"
            self.api.send_message(chat_id, "🎮 BO7 — выбери устройство:", reply_markup=reply_keyboard_bo7_device())
            return True

        if text == "🟨 BF6 классы":
            ensure_profile(chat_id)["page"] = "bf6_settings"
            self.api.send_message(chat_id, "🟨 BF6 — классы/уровни/устройство:", reply_markup=reply_keyboard_bf6_classes())
            return True

        # warzone device
        if text == "🎮 WZ: PS5/Xbox (Pad)":
            p["wz_device"] = "pad"
            self._send_device_text(chat_id, "wz:pad")
            return True

        if text == "🖥 WZ: PC (MnK)":
            p["wz_device"] = "mnk"
            self._send_device_text(chat_id, "wz:mnk")
            return True

        # bo7 device
        if text == "🎮 BO7: PS5/Xbox (Pad)":
            p["bo7_device"] = "pad"
            self._send_device_text(chat_id, "bo7:pad")
            return True

        if text == "🖥 BO7: PC (MnK)":
            p["bo7_device"] = "mnk"
            self._send_device_text(chat_id, "bo7:mnk")
            return True

        # bf6 class + tiers + device
        if text in ("🟥 Assault", "🟦 Engineer", "🟩 Support", "🟨 Recon"):
            cls = {"🟥 Assault":"assault","🟦 Engineer":"engineer","🟩 Support":"support","🟨 Recon":"recon"}[text]
            p["bf6_class"] = cls
            info = GAME_KB["bf6"].get("classes", {}).get(cls, "—")
            self.api.send_message(chat_id, f"✅ BF6 класс установлен: {cls}\n\n{info}", reply_markup=reply_keyboard_bf6_classes())
            return True

        if text == "🧠 BF6: Обычный":
            p["bf6_tier"] = "normal"
            self.api.send_message(chat_id, "✅ BF6 tier: normal", reply_markup=reply_keyboard_bf6_classes())
            return True

        if text == "😈 BF6: Demon":
            p["bf6_tier"] = "demon"
            self.api.send_message(chat_id, "✅ BF6 tier: demon (максимально мансит/агрессия по инфо)", reply_markup=reply_keyboard_bf6_classes())
            return True

        if text == "🎯 BF6: Pro":
            p["bf6_tier"] = "pro"
            self.api.send_message(chat_id, "✅ BF6 tier: pro (сдержанно, умно, топ-решения)", reply_markup=reply_keyboard_bf6_classes())
            return True

        if text == "🎮 BF6: Pad":
            p["bf6_device"] = "pad"
            self._send_device_text(chat_id, "bf6:pad")
            return True

        if text == "🖥 BF6: MnK":
            p["bf6_device"] = "mnk"
            self._send_device_text(chat_id, "bf6:mnk")
            return True

        # daily / vod
        if text == "🎯 Задание дня":
            self._send_daily(chat_id)
            return True

        if text == "🎬 VOD":
            g = p.get("game", "auto")
            if g == "auto":
                g = "warzone"
            txt = (GAME_KB.get(g, {}) or {}).get("vod") or "🎬 VOD: опиши момент — карта/оружие/дистанция/где умер."
            self.api.send_message(chat_id, txt, reply_markup=reply_keyboard_main())
            return True

        return False

    # -------------------------
    # Chat processing
    # -------------------------
    def _handle_chat(self, chat_id: int, user_text: str) -> None:
        p = ensure_profile(chat_id)

        # quick text setters (не ломаем, добавляем удобство)
        low = (user_text or "").strip().lower()
        if low in ("auto", "warzone", "bf6", "bo7"):
            p["game"] = low
            self.api.send_message(chat_id, f"✅ Игра установлена: {low}", reply_markup=reply_keyboard_main())
            return
        if low in ("spicy", "chill", "pro"):
            p["persona"] = low
            self.api.send_message(chat_id, f"✅ Стиль: {low}", reply_markup=reply_keyboard_main())
            return
        if low in ("short", "normal", "talkative"):
            p["verbosity"] = low
            self.api.send_message(chat_id, f"✅ Длина ответа: {low}", reply_markup=reply_keyboard_main())
            return

        # AI reply
        mode = p.get("mode", "chat")
        if mode == "coach":
            out = self.ai.coach_reply(chat_id, user_text)
        else:
            out = self.ai.chat_reply(chat_id, user_text)

        update_memory(chat_id, "user", user_text, memory_max_turns=int(getattr(self.cfg, "MEMORY_MAX_TURNS", 8)))
        update_memory(chat_id, "assistant", out, memory_max_turns=int(getattr(self.cfg, "MEMORY_MAX_TURNS", 8)))

        p["last_question"] = user_text
        p["last_answer"] = out

        self.api.send_message(chat_id, out, reply_markup=reply_keyboard_main())

    # -------------------------
    # Helpers
    # -------------------------
    def _send_main(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        p["page"] = "main"
        self.api.send_message(
            chat_id,
            main_text(chat_id, ai_enabled=self.ai.enabled, model=getattr(self.cfg, "OPENAI_MODEL", "—")),
            reply_markup=reply_keyboard_main(),
        )

    def _send_status(self, chat_id: int) -> None:
        self.api.send_message(
            chat_id,
            status_text(
                model=getattr(self.cfg, "OPENAI_MODEL", "—"),
                data_dir=getattr(self.cfg, "DATA_DIR", "data"),
                ai_enabled=self.ai.enabled,
            ),
            reply_markup=reply_keyboard_main(),
        )

    def _send_profile(self, chat_id: int) -> None:
        self.api.send_message(chat_id, profile_text(chat_id), reply_markup=reply_keyboard_main())

    def _send_daily(self, chat_id: int) -> None:
        d = ensure_daily(chat_id)
        self.api.send_message(
            chat_id,
            f"🎯 Задание дня:\n{d.get('text','—')}\n\n✅ Сделал: {d.get('done',0)} | ❌ Не вышло: {d.get('fail',0)}",
            reply_markup=reply_keyboard_main(),
        )

    def _reset_all(self, chat_id: int) -> None:
        p = ensure_profile(chat_id)
        clear_memory(chat_id)
        # мягкий reset профиля (не удаляем будущие поля — только базовые)
        p["game"] = "auto"
        p["persona"] = "spicy"
        p["verbosity"] = "normal"
        p["memory"] = "on"
        p["mode"] = "chat"
        p["speed"] = "normal"
        p["page"] = "main"
        self.api.send_message(chat_id, "🧨 Сброс выполнен (профиль + память).", reply_markup=reply_keyboard_main())

    def _send_device_text(self, chat_id: int, key: str) -> None:
        if get_device_text:
            txt = get_device_text(key)
        else:
            txt = "⚙️ Настройки: модуль device_settings.py не найден."
        self.api.send_message(chat_id, txt, reply_markup=reply_keyboard_main())
