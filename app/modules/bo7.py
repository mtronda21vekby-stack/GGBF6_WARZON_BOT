# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from app.state import ensure_profile
from app.pro_settings import get_tier_text

def _kb(rows):
    return {"inline_keyboard": rows}

class BO7Module:
    key = "bo7"

    def hub(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        return {
            "text": "🟦 BO7 Hub\nВыбирай раздел 👇",
            "reply_markup": _kb([
                [{"text": "⚙️ Premium-настройки", "callback_data": "mod:bo7:settings"}],
                [{"text": "🎯 Дриллы (Aim/Recoil/Move)", "callback_data": "mod:bo7:drills"}],
                [{"text": "🎬 VOD / Разбор", "callback_data": "mod:bo7:vod"}],
                [{"text": "⬅️ Назад в меню", "callback_data": "nav:main"}],
            ])
        }

    def _settings_menu(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        dev = p.get("bo7_device", "pad")
        tier = p.get("bo7_tier", "normal")
        return {
            "text": f"🟦 BO7 Premium\nУстройство: {dev} | Уровень: {tier}\n\nВыбирай 👇",
            "reply_markup": _kb([
                [{"text": "🎮 Controller", "callback_data": "mod:bo7:setdev:pad"},
                 {"text": "🖥 MnK", "callback_data": "mod:bo7:setdev:mnk"}],
                [{"text": "🙂 Обычный", "callback_data": "mod:bo7:settier:normal"},
                 {"text": "😈 Демон", "callback_data": "mod:bo7:settier:demon"}],
                [{"text": "🎯 Pro", "callback_data": "mod:bo7:settier:pro"}],
                [{"text": "📌 Показать пресет", "callback_data": "mod:bo7:show"}],
                [{"text": "⬅️ Назад", "callback_data": "mod:bo7:hub"}],
            ])
        }

    def handle_callback(self, chat_id: int, data: str) -> Optional[Dict[str, Any]]:
        p = ensure_profile(chat_id)

        if data == "mod:bo7:hub":
            p["page"] = "bo7"
            return self.hub(chat_id)

        if data == "mod:bo7:settings":
            p["page"] = "bo7"
            return self._settings_menu(chat_id)

        if data.startswith("mod:bo7:setdev:"):
            dev = data.split(":")[-1]
            if dev in ("pad", "mnk"):
                p["bo7_device"] = dev
            return self._settings_menu(chat_id)

        if data.startswith("mod:bo7:settier:"):
            tier = data.split(":")[-1]
            if tier in ("normal", "demon", "pro"):
                p["bo7_tier"] = tier
            return self._settings_menu(chat_id)

        if data == "mod:bo7:show":
            dev = p.get("bo7_device", "pad")
            tier = p.get("bo7_tier", "normal")
            txt = get_tier_text("bo7", dev, tier)
            return {"text": txt, "reply_markup": self._settings_menu(chat_id)["reply_markup"]}

        if data == "mod:bo7:drills":
            return {"text": "🎯 Дриллы доступны через старую кнопку (мы не ломаем): меню → Тренировка.",
                    "reply_markup": _kb([[{"text": "⬅️ Назад", "callback_data": "mod:bo7:hub"}]])}

        if data == "mod:bo7:vod":
            return {"text": "🎬 VOD: меню → Ещё → VOD / Разбор (как было).",
                    "reply_markup": _kb([[{"text": "⬅️ Назад", "callback_data": "mod:bo7:hub"}]])}

        return None

    def handle_text(self, chat_id: int, text: str) -> Optional[Dict[str, Any]]:
        return None
