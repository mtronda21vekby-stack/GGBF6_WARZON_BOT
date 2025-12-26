# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional
from app.state import ensure_profile, save_state
from app.pro_settings import get_tier_text

def _kb(rows):
    return {"inline_keyboard": rows}

class WarzoneModule:
    key = "wz"

    def hub(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        return {
            "text": "🟩 Warzone Hub\nВыбирай раздел 👇",
            "reply_markup": _kb([
                [{"text": "⚙️ Premium-настройки", "callback_data": "mod:wz:settings"}],
                [{"text": "🎯 Дриллы (Aim/Recoil/Move)", "callback_data": "mod:wz:drills"}],
                [{"text": "🎬 VOD / Разбор", "callback_data": "mod:wz:vod"}],
                [{"text": "⬅️ Назад в меню", "callback_data": "nav:main"}],
            ])
        }

    def _settings_menu(self, chat_id: int) -> Dict[str, Any]:
        p = ensure_profile(chat_id)
        dev = p.get("wz_device", "pad")
        tier = p.get("wz_tier", "normal")
        return {
            "text": f"🟩 Warzone Premium\nУстройство: {dev} | Уровень: {tier}\n\nВыбирай 👇",
            "reply_markup": _kb([
                [{"text": "🎮 Controller", "callback_data": "mod:wz:setdev:pad"},
                 {"text": "🖥 MnK", "callback_data": "mod:wz:setdev:mnk"}],
                [{"text": "🙂 Обычный", "callback_data": "mod:wz:settier:normal"},
                 {"text": "😈 Демон", "callback_data": "mod:wz:settier:demon"}],
                [{"text": "🎯 Pro", "callback_data": "mod:wz:settier:pro"}],
                [{"text": "📌 Показать пресет", "callback_data": "mod:wz:show"}],
                [{"text": "⬅️ Назад", "callback_data": "mod:wz:hub"}],
            ])
        }

    def handle_callback(self, chat_id: int, data: str) -> Optional[Dict[str, Any]]:
        p = ensure_profile(chat_id)

        if data == "mod:wz:hub":
            p["page"] = "wz"
            return self.hub(chat_id)

        if data == "mod:wz:settings":
            p["page"] = "wz"
            return self._settings_menu(chat_id)

        if data.startswith("mod:wz:setdev:"):
            dev = data.split(":")[-1]
            if dev in ("pad", "mnk"):
                p["wz_device"] = dev
            return self._settings_menu(chat_id)

        if data.startswith("mod:wz:settier:"):
            tier = data.split(":")[-1]
            if tier in ("normal", "demon", "pro"):
                p["wz_tier"] = tier
            return self._settings_menu(chat_id)

        if data == "mod:wz:show":
            dev = p.get("wz_device", "pad")
            tier = p.get("wz_tier", "normal")
            txt = get_tier_text("warzone", dev, tier)
            return {"text": txt, "reply_markup": self._settings_menu(chat_id)["reply_markup"]}

        # интеграция с твоим GAME_KB (не ломаем)
        if data == "mod:wz:drills":
            return {"text": "🎯 Выбери дрилл в главном меню: Тренировка (Aim/Recoil/Movement).",
                    "reply_markup": _kb([[{"text": "⬅️ Назад", "callback_data": "mod:wz:hub"}]])}

        if data == "mod:wz:vod":
            return {"text": "🎬 VOD: открой меню → Ещё → VOD / Разбор (мы не ломаем старую кнопку).",
                    "reply_markup": _kb([[{"text": "⬅️ Назад", "callback_data": "mod:wz:hub"}]])}

        return None

    def handle_text(self, chat_id: int, text: str) -> Optional[Dict[str, Any]]:
        # Пока Warzone текстом не перехватываем (чтобы не ломать AI чат).
        # Позже добавим “Причины смерти Warzone” и т.д.
        return None
